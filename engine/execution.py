"""Envio de ordens ao MT5 com SL/TP."""

from __future__ import annotations

from typing import Any

import MetaTrader5 as mt5

from engine.agent_runtime import is_win_symbol
from engine.config import resolve_operating_mode, settings
from engine.preflight_live import live_orders_blocked_reason
from shared.execution_policy import (
    ExecutionEnvSettings,
    load_execution_env,
    should_execute_orders,
    should_send_manual_order_to_mt5,
)
from shared.schemas import OperatingMode
from shared.mt5_symbols import resolve_mt5_symbol
from shared.schemas import SignalCreate, SignalSide


def _symbol_info(symbol: str):
    info = mt5.symbol_info(symbol)
    if info is None:
        raise RuntimeError(f"Símbolo {symbol} inválido")
    return info


def _equity_contract_size(info) -> float:
    for attr in ("trade_contract_size", "contract_size"):
        raw = getattr(info, attr, None)
        if raw is not None:
            try:
                val = float(raw)
                if val > 0:
                    return val
            except (TypeError, ValueError):
                pass
    return 100.0


def _volume_from_signal(signal: SignalCreate, *, info=None) -> float:
    if is_win_symbol(signal.symbol):
        return float(signal.contracts)
    size = _equity_contract_size(info) if info is not None else 100.0
    return float(signal.contracts) / size


def volume_for_signal(signal: SignalCreate, *, info=None) -> float:
    return _volume_from_signal(signal, info=info)


def _pick_filling_mode(info) -> int:
    mode = int(getattr(info, "filling_mode", 0) or 0)
    if mode & mt5.ORDER_FILLING_IOC:
        return mt5.ORDER_FILLING_IOC
    if mode & mt5.ORDER_FILLING_FOK:
        return mt5.ORDER_FILLING_FOK
    if mode & mt5.ORDER_FILLING_RETURN:
        return mt5.ORDER_FILLING_RETURN
    return mt5.ORDER_FILLING_RETURN


def _normalize_volume(symbol: str, volume: float) -> float:
    info = _symbol_info(symbol)
    vol = float(volume)
    step = info.volume_step or 1.0
    min_vol = info.volume_min or step
    max_vol = info.volume_max or vol
    vol = max(min_vol, min(vol, max_vol))
    # Ajusta ao step
    steps = round(vol / step)
    return steps * step


def place_market_order(
    signal: SignalCreate,
    *,
    engine_paused: bool = False,
    is_demo: bool | None = None,
    operating_mode: OperatingMode | None = None,
    env: ExecutionEnvSettings | None = None,
    manual: bool = False,
) -> dict[str, Any]:
    env = env or load_execution_env()
    op = operating_mode or resolve_operating_mode()
    if manual:
        can, reason = should_send_manual_order_to_mt5(
            operating_mode=op,
            engine_paused=engine_paused,
            is_demo=is_demo,
            env=env,
        )
    else:
        can, reason = should_execute_orders(
            operating_mode=op,
            engine_paused=engine_paused,
            is_demo=is_demo,
            env=env,
        )
    if not can:
        return {"ok": False, "message": reason or "Execução bloqueada"}

    if env.signal_mode.lower() != "live":
        return {
            "ok": False,
            "message": "SIGNAL_MODE=paper — ordem não enviada (use SIGNAL_MODE=live)",
        }

    if not manual and signal.mode.value != "live":
        return {
            "ok": False,
            "message": "SIGNAL_MODE=paper — ordem não enviada",
        }

    blocked = live_orders_blocked_reason()
    if blocked:
        return {"ok": False, "message": blocked}

    try:
        mt5_symbol = resolve_mt5_symbol(signal.symbol, symbol_info=mt5.symbol_info)
    except RuntimeError as exc:
        return {"ok": False, "message": str(exc)}

    if not mt5.symbol_select(mt5_symbol, True):
        return {"ok": False, "message": f"Não foi possível selecionar {mt5_symbol} no MT5"}

    info = _symbol_info(mt5_symbol)
    tick = mt5.symbol_info_tick(mt5_symbol)
    if tick is None:
        raise RuntimeError("Tick indisponível")

    volume = _normalize_volume(mt5_symbol, _volume_from_signal(signal, info=info))
    if signal.side == SignalSide.BUY:
        order_type = mt5.ORDER_TYPE_BUY
        price = tick.ask
    else:
        order_type = mt5.ORDER_TYPE_SELL
        price = tick.bid

    filling = _pick_filling_mode(info)

    def _send(*, with_stops: bool) -> Any:
        req = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": mt5_symbol,
            "volume": volume,
            "type": order_type,
            "price": price,
            "deviation": 20,
            "magic": 88001,
            "comment": f"sala-sinais:{signal.strategy_id}"[:31],
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": filling,
        }
        if with_stops:
            req["sl"] = float(signal.stop)
            req["tp"] = float(signal.target)
        return mt5.order_send(req)

    result = _send(with_stops=True)
    if result is None:
        code, msg = mt5.last_error()
        return {"ok": False, "message": f"order_send falhou: {code} {msg}"}

    invalid_stops = getattr(mt5, "TRADE_RETCODE_INVALID_STOPS", 10016)
    if result.retcode != mt5.TRADE_RETCODE_DONE and result.retcode == invalid_stops:
        retry = _send(with_stops=False)
        if retry and retry.retcode == mt5.TRADE_RETCODE_DONE:
            result = retry
        elif retry:
            result = retry

    if result.retcode != mt5.TRADE_RETCODE_DONE:
        from engine.mt5_terminal_diagnostics import format_mt5_rejection_hint

        min_vol = getattr(info, "volume_min", None)
        hint = ""
        if not is_win_symbol(signal.symbol) and volume < (min_vol or 0):
            hint = f" volume={volume} abaixo do mínimo {min_vol}"
        ret_hint = format_mt5_rejection_hint(result.retcode)
        extra = f" — {ret_hint}" if ret_hint else ""
        return {
            "ok": False,
            "message": (
                f"Ordem rejeitada retcode={result.retcode} {result.comment}"
                f"{hint} (volume enviado={volume}){extra}"
            ),
            "retcode": result.retcode,
            "volume": volume,
            "hint": ret_hint or None,
        }

    return {
        "ok": True,
        "message": f"Ordem executada ticket={result.order} deal={result.deal}",
        "order": result.order,
        "deal": result.deal,
        "price": result.price,
        "mt5_symbol": mt5_symbol,
    }


def close_all_positions(symbol: str | None = None) -> dict[str, Any]:
    """Fecha posições abertas no MT5 (requer LIVE_TRADING + terminal conectado)."""
    if not settings.live_trading:
        return {
            "ok": False,
            "message": "LIVE_TRADING=false — zerar posição só define flag na API; MT5 não alterado",
        }

    blocked = live_orders_blocked_reason()
    if blocked:
        return {"ok": False, "message": blocked}

    positions = mt5.positions_get(symbol=symbol) if symbol else mt5.positions_get()
    if positions is None:
        code, msg = mt5.last_error()
        return {"ok": False, "message": f"positions_get falhou: {code} {msg}"}
    if not positions:
        return {"ok": True, "message": "Nenhuma posição aberta", "closed": 0}

    closed = 0
    errors: list[str] = []
    for pos in positions:
        tick = mt5.symbol_info_tick(pos.symbol)
        if tick is None:
            errors.append(f"tick ausente {pos.symbol}")
            continue
        if pos.type == mt5.POSITION_TYPE_BUY:
            order_type = mt5.ORDER_TYPE_SELL
            price = tick.bid
        else:
            order_type = mt5.ORDER_TYPE_BUY
            price = tick.ask
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": pos.symbol,
            "volume": pos.volume,
            "type": order_type,
            "position": pos.ticket,
            "price": price,
            "deviation": 30,
            "magic": pos.magic,
            "comment": "sala-sinais:emergency_flatten",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        result = mt5.order_send(request)
        if result and result.retcode == mt5.TRADE_RETCODE_DONE:
            closed += 1
        else:
            rc = result.retcode if result else "?"
            errors.append(f"ticket {pos.ticket} retcode={rc}")

    msg = f"Fechadas {closed}/{len(positions)} posição(ões)"
    if errors:
        msg += "; erros: " + "; ".join(errors[:3])
    return {"ok": closed > 0 or not errors, "message": msg, "closed": closed}
