"""Resolve símbolo e tamanho de posição a partir da config da API."""

from __future__ import annotations

import logging

from engine.config import settings

log = logging.getLogger("engine.agent_runtime")

_ROTATE_IDX = 0


def is_win_symbol(symbol: str) -> bool:
    s = symbol.upper()
    return s.startswith("WIN") or s.startswith("WDO")


def default_agent_config() -> dict:
    return {
        "symbols": ["PETR4", "VALE3"],
        "use_news_filter": True,
        "active_symbol": "PETR4",
        "rotate_symbols": False,
        "capital_brl": 10000.0,
        "risk_per_trade_pct": 1.0,
        "max_position_brl": 2000.0,
        "shares_per_order": 100,
        "stop_loss_pct": 2.0,
        "take_profit_pct": 3.0,
        "stop_points": settings.stop_points,
        "target_points": settings.target_points,
        "asset_class": "acoes",
        "strategy_type": "volatility",
    }


def pick_symbol(config: dict) -> str:
    global _ROTATE_IDX
    symbols = config.get("symbols") or default_agent_config()["symbols"]
    if not symbols:
        return settings.mt5_symbol

    asset = (config.get("asset_class") or "acoes").lower()
    if asset == "win":
        win_syms = [s for s in symbols if is_win_symbol(s)]
        pool = win_syms or [settings.mt5_symbol]
    elif asset == "acoes":
        pool = [s for s in symbols if not is_win_symbol(s)] or symbols
    else:
        pool = symbols

    if config.get("rotate_symbols"):
        sym = pool[_ROTATE_IDX % len(pool)]
        _ROTATE_IDX += 1
        return sym

    active = config.get("active_symbol")
    if active and active in pool:
        return active
    return pool[0]


def contracts_for_config(config: dict, symbol: str) -> int:
    asset = (config.get("asset_class") or "acoes").lower()
    if asset == "win" or is_win_symbol(symbol):
        return settings.max_contracts
    shares = int(config.get("shares_per_order") or 100)
    return max(100, shares)
