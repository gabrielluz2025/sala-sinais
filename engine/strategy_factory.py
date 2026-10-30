"""Resolve estratégia conforme agent_config.strategy_type."""

from __future__ import annotations

from engine.strategy import BreakoutStrategy
from engine.strategy_volatility import VolatilityAdaptiveStrategy


def resolve_strategy(agent_config: dict | None):
    cfg = agent_config or {}
    st = (cfg.get("strategy_type") or "volatility").strip().lower()
    if st == "breakout":
        return BreakoutStrategy()
    return VolatilityAdaptiveStrategy()
