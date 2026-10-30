"""POST /orders/execute — ordens manuais da UI."""

from __future__ import annotations

import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy.orm import Session

from api.agent_config import get_or_create_config
from api.database import SignalRow
from api.pnl import load_quote_mid_map
from api.system_state import get_or_create_state
from engine.risk import RiskManager
from shared.execution_policy import (
    load_execution_env,
    can_submit_manual_order,
    resolve_operating_mode_from_env,
    should_send_manual_order_to_mt5,
)
from shared.session_hours import resolve_enforce_b3_session_hours
from shared.schemas import (
    OperatingMode,
    OrderExecuteRequest,
    OrderExecuteResponse,
    SignalCreate,
    SignalMode,
    SignalRead,
    SignalSide,
    SignalStatus,
)

TZ_BR = ZoneInfo("America/Sao_Paulo")
MANUAL_STRATEGY_ID = "pulse_deck_manual"
log = logging.getLogger("api.orders_execute")


def _resolve_operating_mode(state_row) -> OperatingMode:
    env = load_execution_env()
    raw = (state_row.operating_mode or env.engine_mode or "").strip().lower()
    if raw:
        aliases = {
            "simulation": OperatingMode.SIMULATION,
            "sim": OperatingMode.SIMULATION,
            "paper_mt5": OperatingMode.PAPER_MT5,
            "paper-mt5": OperatingMode.PAPER_MT5,
            "live_mt5": OperatingMode.LIVE_MT5,
            "live-mt5": OperatingMode.LIVE_MT5,
            "live": OperatingMode.LIVE_MT5,
        }
        return aliases.get(raw, resolve_operating_mode_from_env(env))
    return resolve_operating_mode_from_env(env)


def _entry_side_price(side: SignalSide, bid: float, ask: float) -> float:
    if side == SignalSide.BUY:
        return ask if ask > 0 else bid
    return bid if bid > 0 else ask


def _default_levels(
    side: SignalSide,
    entry: float,
    *,
    stop_loss_pct: float,
    take_profit_pct: float,
    stop_points: int,
    target_points: int,
    symbol: str,
) -> tuple[float, float]:
    sym = symbol.upper()
    if sym.startswith("WIN") or sym.startswith("WDO"):
        if side == SignalSide.BUY:
            stop = entry - float(stop_points)
            target = entry + float(target_points)
        else:
            stop = entry + float(stop_points)
            target = entry - float(target_points)
        return round(stop, 2), round(target, 2)
    sl = stop_loss_pct / 100.0
    tp = take_profit_pct / 100.0
    if side == SignalSide.BUY:
        stop = entry * (1 - sl)
        target = entry * (1 + tp)
    else:
        stop = entry * (1 + sl)
        target = entry * (1 - tp)
    return round(stop, 2), round(target, 2)


def execute_manual_order(
    db: Session,
    body: OrderExecuteRequest,
    *,
    row_to_read,
) -> OrderExecuteResponse:
    state = get_or_create_state(db)
    op = _resolve_operating_mode(state)
    env = load_execution_env()

    allowed, block_reason = can_submit_manual_order(
        operating_mode=op,
        engine_paused=state.engine_paused,
        is_demo=state.is_demo,
        env=env,
    )
    if not allowed:
        raise HTTPException(status_code=403, detail=block_reason or "Ordem manual bloqueada")

    risk = RiskManager()
    enforce_hours = resolve_enforce_b3_session_hours(
        live_trading=env.live_trading,
        execute_on_demo=env.execute_on_demo,
        b3_ignore_session_hours=env.b3_ignore_session_hours,
        operating_mode=op,
        overnight_learning=env.overnight_learning,
    )
    ok, risk_reason = risk.can_trade(enforce_session_hours=enforce_hours)
    if not ok:
        code = "session_hours" if enforce_hours and (
            "horário" in risk_reason or "fechado" in risk_reason or "leilão" in risk_reason
        ) else "risk"
        raise HTTPException(
            status_code=400,
            detail={
                "code": code,
                "message": risk_reason,
                "enforce_session_hours": enforce_hours,
            },
        )

    symbol = body.symbol.strip().upper()
    if not symbol:
        raise HTTPException(status_code=422, detail="symbol inválido")

    mids = load_quote_mid_map()
    mid = mids.get(symbol)
    if body.entry is not None:
        entry = float(body.entry)
    elif mid is not None:
        spread = max(0.01, mid * 0.0002)
        bid = mid - spread / 2
        ask = mid + spread / 2
        entry = _entry_side_price(body.side, bid, ask)
    else:
        raise HTTPException(
            status_code=404,
            detail="Cotação indisponível para o símbolo — inicie engine ou simulação",
        )

    cfg = get_or_create_config(db)
    if body.stop is not None and body.target is not None:
        stop, target = float(body.stop), float(body.target)
    else:
        stop, target = _default_levels(
            body.side,
            entry,
            stop_loss_pct=float(cfg.stop_loss_pct or 2.0),
            take_profit_pct=float(cfg.take_profit_pct or 3.0),
            stop_points=int(cfg.stop_points or 80),
            target_points=int(cfg.target_points or 120),
            symbol=symbol,
        )

    contracts = risk.clamp_contracts(body.contracts)
    signal_mode = SignalMode.LIVE if env.signal_mode.lower() == "live" else SignalMode.PAPER
    now = datetime.now(TZ_BR).isoformat()

    row = SignalRow(
        symbol=symbol,
        side=body.side.value,
        entry=round(entry, 2),
        stop=stop,
        target=target,
        contracts=contracts,
        strategy_id=MANUAL_STRATEGY_ID,
        mode=signal_mode.value,
        status=SignalStatus.SENT.value,
        note=body.note or "Ordem manual (Pulse Deck)",
        execution_message="Registrada via POST /orders/execute",
        created_at=now,
        strategy_type=cfg.strategy_type,
        entry_reason="Entrada manual pelo operador",
    )
    db.add(row)
    db.commit()
    db.refresh(row)

    mt5_sent = False
    mt5_ok: bool | None = None
    db_only = True
    msg = "Sinal registrado"

    if op == OperatingMode.SIMULATION:
        msg = "Ordem simulada registrada (sem MT5)"
    else:
        can_mt5, block_reason = should_send_manual_order_to_mt5(
            operating_mode=op,
            engine_paused=state.engine_paused,
            is_demo=state.is_demo,
            env=env,
        )
        if can_mt5:
            mt5_sent = True
            db_only = False
            try:
                from engine.mt5_runtime import execute_signal_on_mt5

                payload = SignalCreate(
                    symbol=symbol,
                    side=body.side,
                    entry=round(entry, 2),
                    stop=stop,
                    target=target,
                    contracts=contracts,
                    strategy_id=MANUAL_STRATEGY_ID,
                    mode=SignalMode.LIVE,
                    note=body.note or "Ordem manual (Pulse Deck)",
                )
                result = execute_signal_on_mt5(
                    payload,
                    engine_paused=state.engine_paused,
                    is_demo=state.is_demo,
                    operating_mode=op,
                    env=env,
                    manual=True,
                )
                mt5_ok = bool(result.get("ok"))
                exec_msg = result.get("message") or "Execução MT5"
                hint = result.get("hint")
                if not hint and result.get("retcode") == 10027:
                    from engine.mt5_terminal_diagnostics import mt5_retcode_10027_hint

                    hint = mt5_retcode_10027_hint()
                row.execution_message = exec_msg
                row.status = (
                    SignalStatus.FILLED.value if mt5_ok else SignalStatus.REJECTED.value
                )
                db.commit()
                db.refresh(row)
                log.info("ORDEM manual %s %s — %s", symbol, body.side.value, exec_msg)
                if mt5_ok:
                    msg = f"Ordem enviada ao MT5 — {exec_msg}"
                else:
                    msg = f"MT5 rejeitou ordem — {exec_msg}"
                    if hint:
                        msg = f"{msg} | {hint}"
            except Exception as exc:
                mt5_ok = False
                row.execution_message = f"Falha MT5: {exc}"
                row.status = SignalStatus.REJECTED.value
                db.commit()
                db.refresh(row)
                log.warning("ORDEM manual falhou %s: %s", symbol, exc)
                msg = f"Erro ao enviar ao MT5: {exc}"
        else:
            msg = (
                "Ordem registrada (somente SQLite) — "
                f"{block_reason or 'política não permite envio imediato ao MT5'}"
            )

    return OrderExecuteResponse(
        ok=True,
        message=msg,
        operating_mode=op.value,
        signal=row_to_read(row),
        mt5_sent=mt5_sent,
        mt5_ok=mt5_ok,
        db_only=db_only and not mt5_sent,
    )
