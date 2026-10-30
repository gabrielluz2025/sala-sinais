"""Conexão com MetaTrader 5 — rode `python -m engine.scripts.check_mt5` para validar."""

from __future__ import annotations

import sys
from typing import Any, Optional

import MetaTrader5 as mt5

from engine.config import settings
from shared.mt5_symbols import resolve_mt5_symbol

TIMEFRAME_MAP = {
    "M1": mt5.TIMEFRAME_M1,
    "M5": mt5.TIMEFRAME_M5,
    "M15": mt5.TIMEFRAME_M15,
    "H1": mt5.TIMEFRAME_H1,
}


def timeframe_constant(name: str) -> int:
    key = name.upper()
    if key not in TIMEFRAME_MAP:
        raise ValueError(f"Timeframe não suportado: {name}")
    return TIMEFRAME_MAP[key]


def initialize() -> None:
    kwargs: dict[str, Any] = {}
    if settings.mt5_path:
        kwargs["path"] = settings.mt5_path
    if not mt5.initialize(**kwargs):
        code, msg = mt5.last_error()
        raise RuntimeError(f"Falha ao inicializar MT5: {code} {msg}")


def shutdown() -> None:
    mt5.shutdown()


def ensure_symbol(symbol: str) -> str:
    resolved = resolve_mt5_symbol(symbol, symbol_info=mt5.symbol_info)
    info = mt5.symbol_info(resolved)
    if info is None:
        raise RuntimeError(
            f"Símbolo '{symbol}' não encontrado. Abra o MT5, adicione o ativo no Market Watch "
            "e confira o nome exato (ex.: PETR4, WIN$)."
        )
    if not info.visible:
        if not mt5.symbol_select(resolved, True):
            raise RuntimeError(f"Não foi possível selecionar o símbolo {resolved}")
    return resolved


def last_tick(symbol: str) -> dict[str, float]:
    tick = mt5.symbol_info_tick(symbol)
    if tick is None:
        code, msg = mt5.last_error()
        raise RuntimeError(f"Sem tick para {symbol}: {code} {msg}")
    return {
        "bid": tick.bid,
        "ask": tick.ask,
        "last": tick.last,
        "time": tick.time,
    }


def copy_rates(symbol: str, timeframe: int, count: int = 100):
    rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, count)
    if rates is None or len(rates) == 0:
        code, msg = mt5.last_error()
        raise RuntimeError(f"Sem candles para {symbol}: {code} {msg}")
    return rates


def account_summary() -> dict[str, Any]:
    acc = mt5.account_info()
    if acc is None:
        raise RuntimeError("Conta MT5 indisponível — faça login no terminal")
    return {
        "login": acc.login,
        "server": acc.server,
        "balance": acc.balance,
        "trade_mode": acc.trade_mode,
    }


def account_trade_context() -> dict[str, Any]:
    """Dados da conta para heartbeat e guardas de modo real."""
    acc = mt5.account_info()
    if acc is None:
        raise RuntimeError("Conta MT5 indisponível — faça login no terminal")
    is_demo = acc.trade_mode != mt5.ACCOUNT_TRADE_MODE_REAL
    return {
        "login": acc.login,
        "server": acc.server,
        "balance": acc.balance,
        "trade_mode": acc.trade_mode,
        "is_demo": is_demo,
        "account_login": acc.login,
        "account_server": acc.server,
    }


def diagnose(symbol: Optional[str] = None) -> int:
    sym = symbol or settings.mt5_symbol
    try:
        initialize()
        acc = account_summary()
        ensure_symbol(sym)
        tick = last_tick(sym)
        tf = timeframe_constant(settings.mt5_timeframe)
        rates = copy_rates(sym, tf, 3)
        print("MT5 OK")
        print(f"  Conta: {acc['login']} @ {acc['server']}")
        print(f"  Símbolo: {sym} | bid={tick['bid']} ask={tick['ask']}")
        print(f"  Últimos {len(rates)} candles {settings.mt5_timeframe}")
        return 0
    except Exception as exc:
        print(f"MT5 ERRO: {exc}", file=sys.stderr)
        return 1
    finally:
        shutdown()
