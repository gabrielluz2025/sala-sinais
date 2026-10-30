"""Loop principal: simulação ou MT5, publica sinais na API."""

from __future__ import annotations

import logging
import sys
import time

from engine.api_client import SignalApiClient
from engine.config import effective_live_trading, resolve_operating_mode, settings
from engine.agent_runtime import pick_symbol
from engine.control import (
    clear_emergency_flatten,
    fetch_agent_config,
    fetch_system_state,
    send_heartbeat,
    write_last_quote,
)
from engine.execution import close_all_positions, place_market_order, volume_for_signal
from shared.execution_policy import load_execution_env, should_execute_orders
from shared.session_hours import (
    b3_session_block_reason,
    resolve_enforce_b3_session_hours,
)
from engine.mt5_connection import (
    account_trade_context,
    copy_rates,
    ensure_symbol,
    initialize,
    last_tick,
    shutdown,
    timeframe_constant,
)
from engine.preflight_live import assert_engine_may_start_live
from engine.risk import RiskManager
from engine.simulator import WinMarketSimulator
from engine.mt5_close import Mt5SignalCloseTracker
from engine.sim_close import SimOpenTrade, SimPositionTracker
from engine.strategy_meta import STRATEGY_VERSION
from engine.market_snapshot import write_m1_bars
from engine.strategy_factory import resolve_strategy
from engine.overnight_study import run_study_pass, run_trade_learning_pass
from engine.trade_feedback import apply_before_auto_signal, effective_cooldown_sec
from shared.schemas import OperatingMode, SignalCreate, SignalMode, SignalSide

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("engine")


def resolve_signal_mode() -> SignalMode:
    return SignalMode.LIVE if settings.signal_mode.lower() == "live" else SignalMode.PAPER


def sleep_with_heartbeat(total_sec: float, heartbeat) -> None:
    """Aguarda mantendo heartbeat a cada poll_interval (engine_online na API)."""
    deadline = time.monotonic() + total_sec
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        heartbeat()
        time.sleep(min(float(settings.poll_interval_sec), remaining))


def run_simulation_loop(max_iterations: int | None = None) -> None:
    """Mercado simulado — sem MT5, sem ordens."""
    if settings.live_trading:
        log.warning(
            "LIVE_TRADING=true ignorado em ENGINE_MODE=simulation (segurança)."
        )

    mode = SignalMode.PAPER
    op = OperatingMode.SIMULATION
    risk = RiskManager()
    api = SignalApiClient()
    sim_positions = SimPositionTracker(api)
    markets: dict[str, WinMarketSimulator] = {}
    last_demo_signal = 0.0
    demo_side_toggle = True
    iterations = 0
    last_study_mono = 0.0
    last_library_mono = 0.0

    if settings.overnight_learning:
        log.info("=" * 60)
        log.info(
            "MODO APRENDIZADO 24h — sinais simulados + estudo até abrir o pregão B3 "
            "(OVERNIGHT_LEARNING=true, sem ordens MT5)."
        )
        log.info("=" * 60)

    log.info(
        "Simulação ativa | poll=%ss | intervalo_demo=%ss (símbolos via /agent/config)",
        settings.poll_interval_sec,
        settings.sim_signal_interval_sec,
    )

    def heartbeat_tick() -> None:
        send_heartbeat(
            mode.value,
            is_demo=True,
            data_source="simulation",
            mt5_connected=False,
            operating_mode=op.value,
        )

    try:
        while True:
            agent_cfg = fetch_agent_config()
            symbol = pick_symbol(agent_cfg)
            if symbol not in markets:
                markets[symbol] = WinMarketSimulator(symbol)
            market = markets[symbol]

            state = fetch_system_state()
            heartbeat_tick()

            if state.get("emergency_flatten"):
                log.info("emergency_flatten em simulação — apenas limpando flag (sem MT5)")
                clear_emergency_flatten()

            market.maybe_roll_m1()
            tick = market.step_tick()
            write_last_quote(symbol, tick["bid"], tick["ask"], source="simulation")
            sim_positions.tick(tick["bid"], tick["ask"], agent_cfg)

            if state.get("engine_paused"):
                log.debug("Engine pausado — simulação continua cotação")
                sleep_with_heartbeat(settings.poll_interval_sec, heartbeat_tick)
                iterations += 1
                if max_iterations and iterations >= max_iterations:
                    break
                continue

            ok, reason = risk.can_trade(
                enforce_session_hours=(
                    settings.sim_respect_risk_hours and not settings.overnight_learning
                ),
                min_cooldown_sec=effective_cooldown_sec(
                    api,
                    (agent_cfg.get("strategy_type") or "volatility").strip().lower(),
                ),
            )
            if settings.sim_respect_risk_hours and not settings.overnight_learning and not ok:
                log.debug("Sim sem trade (horário): %s", reason)
                sleep_with_heartbeat(settings.poll_interval_sec, heartbeat_tick)
                iterations += 1
                if max_iterations and iterations >= max_iterations:
                    break
                continue

            rates = market.copy_rates(100)
            write_m1_bars(symbol, rates)
            strategy = resolve_strategy(agent_cfg)
            signal = strategy.evaluate(
                symbol, rates, tick["bid"], tick["ask"], mode, agent_config=agent_cfg
            )
            now_mono = time.monotonic()
            if (
                signal is None
                and settings.sim_demo_signals
                and now_mono - last_demo_signal >= settings.sim_signal_interval_sec
            ):
                from engine.agent_runtime import contracts_for_config

                side = SignalSide.BUY if demo_side_toggle else SignalSide.SELL
                demo_side_toggle = not demo_side_toggle
                entry, stop, target = market.demo_signal_payload(
                    side.value,
                    stop_loss_pct=agent_cfg.get("stop_loss_pct"),
                    take_profit_pct=agent_cfg.get("take_profit_pct"),
                )
                st = (agent_cfg.get("strategy_type") or "volatility").strip().lower()
                if st not in ("breakout", "volatility"):
                    st = "volatility"
                entry_reason = "Sinal demo periódico (simulação) — não veio da estratégia ao vivo"
                signal_payload = SignalCreate(
                    symbol=symbol,
                    side=side,
                    entry=round(entry, 2),
                    stop=round(stop, 2),
                    target=round(target, 2),
                    contracts=contracts_for_config(agent_cfg, symbol),
                    strategy_id=settings.strategy_id,
                    mode=mode,
                    note="Sinal demo (simulação)",
                    strategy_type=st,
                    strategy_version=STRATEGY_VERSION,
                    entry_reason=entry_reason,
                )
                from engine.strategy import StrategyResult

                signal = StrategyResult(
                    payload=signal_payload,
                    entry_reason=entry_reason,
                    strategy_type=st,
                    strategy_version=STRATEGY_VERSION,
                )
                last_demo_signal = now_mono

            if signal is None:
                now_study = time.monotonic()
                if settings.overnight_learning:
                    if now_study - last_study_mono >= settings.overnight_study_interval_sec:
                        run_study_pass(api, agent_cfg)
                        run_trade_learning_pass(api)
                        last_study_mono = now_study
                    # Biblioteca do agente: ticks só na API (AGENT_AUTO_STUDY_LIBRARY), evita duplicar.
                    lib_interval = settings.overnight_study_interval_sec * 2
                    if now_study - last_library_mono >= lib_interval:
                        if not settings.agent_auto_study_library:
                            try:
                                stats = api.get_library_stats()
                                log.info(
                                    "Aprendizado 24h · biblioteca · artigos=%s",
                                    stats.get("article_count", "—"),
                                )
                            except Exception as exc:
                                log.debug("Stats biblioteca: %s", exc)
                        last_library_mono = now_study
                sleep_with_heartbeat(settings.poll_interval_sec, heartbeat_tick)
                iterations += 1
                if max_iterations and iterations >= max_iterations:
                    break
                continue

            signal, learn_skip = apply_before_auto_signal(api, signal, agent_cfg)
            if signal is None:
                log.debug("%s", learn_skip or "Sinal filtrado por aprendizado")
                sleep_with_heartbeat(settings.poll_interval_sec, heartbeat_tick)
                iterations += 1
                if max_iterations and iterations >= max_iterations:
                    break
                continue

            log.info(
                "Sinal [sim]: %s %s @ %s — %s",
                signal.payload.side,
                symbol,
                signal.payload.entry,
                signal.reason,
            )
            try:
                saved = api.post_signal(signal.payload)
                log.info("API registrou sinal id=%s status=%s", saved.id, saved.status)
                sim_positions.register(
                    SimOpenTrade(
                        signal_id=saved.id,
                        side=signal.payload.side,
                        entry=signal.payload.entry,
                        stop=signal.payload.stop,
                        target=signal.payload.target,
                        strategy_type=signal.strategy_type,
                        strategy_version=signal.strategy_version,
                        regime=signal.regime,
                    )
                )
            except Exception as exc:
                log.error("Falha ao enviar sinal à API: %s", exc)
                sleep_with_heartbeat(settings.poll_interval_sec, heartbeat_tick)
                iterations += 1
                if max_iterations and iterations >= max_iterations:
                    break
                continue

            risk.mark_signal_sent()
            sleep_with_heartbeat(settings.signal_cooldown_sec, heartbeat_tick)
            iterations += 1
            if max_iterations and iterations >= max_iterations:
                break
    finally:
        log.debug("Simulação encerrada")


def run_mt5_loop() -> None:
    op = resolve_operating_mode()
    mode = resolve_signal_mode()
    risk = RiskManager()
    api = SignalApiClient()
    sim_positions = SimPositionTracker(api)
    mt5_close = Mt5SignalCloseTracker(api)
    tf = timeframe_constant(settings.mt5_timeframe)
    live = effective_live_trading()

    log.info(
        "Iniciando engine MT5 | operating=%s signal_mode=%s live_trading=%s (símbolo via /agent/config)",
        op.value,
        mode.value,
        live,
    )

    if live:
        log.warning("=" * 60)
        log.warning("LIVE_TRADING=true — ORDENS REAIS NO MT5. RISCO DE PERDA.")
        log.warning("Confirme preflight: python -m engine.scripts.preflight_live")
        log.warning("=" * 60)
        assert_engine_may_start_live()

    initialize()

    def heartbeat_tick() -> None:
        try:
            hb_ctx = account_trade_context()
            send_heartbeat(
                mode.value,
                account_login=hb_ctx.get("account_login"),
                is_demo=hb_ctx.get("is_demo"),
                account_server=hb_ctx.get("account_server"),
                data_source="mt5",
                mt5_connected=True,
                operating_mode=op.value,
            )
        except Exception as exc:
            log.debug("Heartbeat sem dados de conta: %s", exc)
            send_heartbeat(
                mode.value,
                data_source="mt5",
                mt5_connected=True,
                operating_mode=op.value,
            )

    try:
        while True:
            agent_cfg = fetch_agent_config()
            symbol = pick_symbol(agent_cfg)
            mt5_symbol = ensure_symbol(symbol)

            state = fetch_system_state()
            heartbeat_tick()

            if state.get("emergency_flatten"):
                log.warning("emergency_flatten ativo — tentando zerar posições")
                result = close_all_positions(mt5_symbol)
                log.info("Emergency flatten: %s", result.get("message"))
                clear_emergency_flatten()

            try:
                tick = last_tick(mt5_symbol)
                write_last_quote(symbol, tick["bid"], tick["ask"], source="mt5")
                agent_cfg_tick = fetch_agent_config()
                sim_positions.tick(tick["bid"], tick["ask"], agent_cfg_tick)
                mt5_close.tick()
            except Exception as exc:
                log.debug("Cotação MT5 indisponível: %s", exc)

            if state.get("engine_paused"):
                log.debug("Engine pausado via API — apenas heartbeat")
                sleep_with_heartbeat(settings.poll_interval_sec, heartbeat_tick)
                continue

            exec_env = load_execution_env()
            enforce_hours = resolve_enforce_b3_session_hours(
                live_trading=exec_env.live_trading,
                execute_on_demo=exec_env.execute_on_demo,
                b3_ignore_session_hours=exec_env.b3_ignore_session_hours,
                operating_mode=op,
                overnight_learning=exec_env.overnight_learning,
            )
            ok, reason = risk.can_trade(
                enforce_session_hours=enforce_hours,
                min_cooldown_sec=effective_cooldown_sec(
                    api,
                    (agent_cfg.get("strategy_type") or "volatility").strip().lower(),
                ),
            )
            if not ok:
                log.debug("Sem trade: %s", reason)
                sleep_with_heartbeat(settings.poll_interval_sec, heartbeat_tick)
                continue

            tick = last_tick(mt5_symbol)
            rates = copy_rates(mt5_symbol, tf, 100)
            write_m1_bars(symbol, rates)
            strategy = resolve_strategy(agent_cfg)
            signal = strategy.evaluate(
                symbol, rates, tick["bid"], tick["ask"], mode, agent_config=agent_cfg
            )
            if signal is None:
                sleep_with_heartbeat(settings.poll_interval_sec, heartbeat_tick)
                continue

            signal, learn_skip = apply_before_auto_signal(api, signal, agent_cfg)
            if signal is None:
                log.debug("%s", learn_skip or "Sinal filtrado por aprendizado")
                sleep_with_heartbeat(settings.poll_interval_sec, heartbeat_tick)
                continue

            log.info("Sinal: %s %s @ %s — %s", signal.payload.side, symbol, signal.payload.entry, signal.reason)

            try:
                saved = api.post_signal(signal.payload)
                log.info("API registrou sinal id=%s status=%s", saved.id, saved.status)
                sim_positions.register(
                    SimOpenTrade(
                        signal_id=saved.id,
                        side=signal.payload.side,
                        entry=signal.payload.entry,
                        stop=signal.payload.stop,
                        target=signal.payload.target,
                        strategy_type=signal.strategy_type,
                        strategy_version=signal.strategy_version,
                        regime=signal.regime,
                    )
                )
            except Exception as exc:
                log.error("Falha ao enviar sinal à API: %s", exc)
                sleep_with_heartbeat(settings.poll_interval_sec, heartbeat_tick)
                continue

            risk.mark_signal_sent()

            try:
                hb_ctx = account_trade_context()
                is_demo_acc = hb_ctx.get("is_demo")
            except Exception:
                is_demo_acc = None

            state = fetch_system_state()
            can_exec, block_reason = should_execute_orders(
                operating_mode=op,
                engine_paused=bool(state.get("engine_paused")),
                is_demo=is_demo_acc,
            )
            if can_exec:
                result = place_market_order(
                    signal.payload,
                    engine_paused=bool(state.get("engine_paused")),
                    is_demo=is_demo_acc,
                )
                log.info("ORDEM %s", result.get("message"))
                try:
                    new_status = "filled" if result.get("ok") else "rejected"
                    api.update_status(saved.id, new_status, result.get("message"))
                    if result.get("ok"):
                        vol = volume_for_signal(signal.payload)
                        fill_sym = result.get("mt5_symbol") or mt5_symbol
                        mt5_close.register_fill(
                            saved.id,
                            fill_sym,
                            signal.payload.side,
                            signal.payload.entry,
                            vol,
                        )
                except Exception as exc:
                    log.warning("Não foi possível atualizar status na API: %s", exc)
            elif block_reason and mode == SignalMode.LIVE:
                log.debug("Ordem não enviada: %s", block_reason)

            sleep_with_heartbeat(settings.signal_cooldown_sec, heartbeat_tick)
    finally:
        shutdown()


def run_loop() -> None:
    if settings.overnight_learning:
        run_simulation_loop()
        return
    op = resolve_operating_mode()
    if op == OperatingMode.SIMULATION:
        run_simulation_loop()
    else:
        run_mt5_loop()


def main() -> None:
    try:
        if len(sys.argv) > 1 and sys.argv[1] in ("--sim-once", "--dry-run"):
            run_simulation_loop(max_iterations=1)
            return
        run_loop()
    except KeyboardInterrupt:
        log.info("Encerrado pelo usuário")
    except Exception as exc:
        log.exception("Engine parou: %s", exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
