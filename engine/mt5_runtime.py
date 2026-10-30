"""Sessão MT5 reutilizável (API + engine) para envio pontual de ordens."""

from __future__ import annotations

import logging
from typing import Any

import MetaTrader5 as mt5
import time

from engine.execution import place_market_order
from engine.mt5_connection import account_trade_context, initialize, shutdown
from engine.mt5_experts_ini import read_experts_flags_for_data_dir
from shared.mt5_symbols import pick_mt5_symbol_from_module
from shared.execution_policy import ExecutionEnvSettings, load_execution_env
from shared.schemas import OperatingMode, SignalCreate

log = logging.getLogger("engine.mt5_runtime")

_session_active = False
_cached_autotrading: bool | None = None
_last_enabled0_log_mono: float = 0.0
_ENABLED0_LOG_COOLDOWN_SEC = 300.0


def mt5_autotrading_enabled() -> bool | None:
    """None se MT5 não está acessível neste processo."""
    return _cached_autotrading


def _refresh_autotrading_cache(*, log_enabled0: bool = True) -> None:
    global _cached_autotrading, _last_enabled0_log_mono
    try:
        info = mt5.terminal_info()
        if info is None:
            _cached_autotrading = None
            return
        allowed = getattr(info, "trade_allowed", None)
        api_off = getattr(info, "tradeapi_disabled", None)
        if allowed is not None:
            _cached_autotrading = bool(allowed) and not bool(api_off)
        elif api_off is not None:
            _cached_autotrading = not bool(api_off)
        else:
            _cached_autotrading = None
        if _cached_autotrading is False:
            data_path = getattr(info, "data_path", None) if info else None
            if data_path:
                flags = read_experts_flags_for_data_dir(str(data_path))
                if flags.get("Enabled") == "0" and log_enabled0:
                    now = time.monotonic()
                    if now - _last_enabled0_log_mono >= _ENABLED0_LOG_COOLDOWN_SEC:
                        _last_enabled0_log_mono = now
                        log.warning(
                            "MT5 trade_allowed=False com common.ini Enabled=0 — feche o MT5 e rode "
                            "scripts\\prepare_mt5_trading.bat (ou fix_mt5_experts_ini.py)"
                        )
    except Exception:
        pass


def ensure_mt5_session(*, log_enabled0: bool = True) -> None:
    global _session_active
    try:
        info = mt5.terminal_info()
        if info is not None and getattr(info, "connected", False):
            _session_active = True
            _refresh_autotrading_cache(log_enabled0=log_enabled0)
            return
    except Exception:
        pass
    initialize()
    _session_active = True
    _refresh_autotrading_cache(log_enabled0=log_enabled0)


def release_mt5_session(force: bool = False) -> None:
    """Não encerra se o terminal ainda está em uso (engine rodando)."""
    global _session_active
    if not _session_active:
        return
    if force:
        shutdown()
        _session_active = False


def execute_signal_on_mt5(
    signal: SignalCreate,
    *,
    engine_paused: bool = False,
    is_demo: bool | None = None,
    operating_mode: OperatingMode | None = None,
    env: ExecutionEnvSettings | None = None,
    manual: bool = False,
) -> dict[str, Any]:
    """
    Inicializa MT5 se necessário, resolve símbolo e chama place_market_order.
    Retorno inclui mt5_symbol quando a ordem foi tentada.
    """
    ensure_mt5_session()
    if is_demo is None:
        try:
            is_demo = bool(account_trade_context().get("is_demo"))
        except Exception as exc:
            log.debug("Tipo de conta MT5 indisponível: %s", exc)

    try:
        mt5_sym = pick_mt5_symbol_from_module(signal.symbol)
    except RuntimeError as exc:
        return {"ok": False, "message": str(exc), "mt5_symbol": None}

    payload = signal.model_copy(update={"symbol": mt5_sym})
    result = place_market_order(
        payload,
        engine_paused=engine_paused,
        is_demo=is_demo,
        operating_mode=operating_mode,
        env=env or load_execution_env(),
        manual=manual,
    )
    if manual or result.get("ok") is False:
        level = logging.INFO if result.get("ok") else logging.WARNING
        log.log(level, "ORDEM %s — %s", signal.symbol, result.get("message"))
    result["mt5_symbol"] = mt5_sym
    result["logical_symbol"] = signal.symbol
    return result
