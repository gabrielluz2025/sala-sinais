"""Estratégia placeholder: rompimento da máxima/mínima dos últimos N candles M1."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional

import numpy as np

from engine.agent_runtime import contracts_for_config, is_win_symbol
from engine.config import settings
from engine.strategy_meta import STRATEGY_VERSION
from shared.schemas import SignalCreate, SignalMode, SignalSide


@dataclass
class StrategyResult:
    payload: SignalCreate
    entry_reason: str
    strategy_type: Literal["volatility", "breakout"]
    strategy_version: str = STRATEGY_VERSION
    regime: Optional[str] = None

    @property
    def reason(self) -> str:
        """Compatível com logs legados."""
        return self.entry_reason


StrategySignal = StrategyResult


class BreakoutStrategy:
    LOOKBACK = 12

    def evaluate(
        self,
        symbol: str,
        rates,
        bid: float,
        ask: float,
        mode: SignalMode,
        agent_config: dict | None = None,
    ) -> Optional[StrategyResult]:
        if len(rates) < self.LOOKBACK + 2:
            return None

        highs = rates["high"][-(self.LOOKBACK + 1) : -1]
        lows = rates["low"][-(self.LOOKBACK + 1) : -1]
        range_high = float(np.max(highs))
        range_low = float(np.min(lows))
        last_close = float(rates["close"][-2])

        side: SignalSide | None = None
        entry = 0.0
        if last_close > range_high:
            side = SignalSide.BUY
            entry = ask
        elif last_close < range_low:
            side = SignalSide.SELL
            entry = bid

        if side is None:
            return None

        cfg = agent_config or {}
        if is_win_symbol(symbol):
            stop_pts = int(cfg.get("stop_points") or settings.stop_points)
            target_pts = int(cfg.get("target_points") or settings.target_points)
            if side == SignalSide.BUY:
                stop = entry - stop_pts
                target = entry + target_pts
            else:
                stop = entry + stop_pts
                target = entry - target_pts
        else:
            sl_pct = float(cfg.get("stop_loss_pct") or 2.0)
            tp_pct = float(cfg.get("take_profit_pct") or 3.0)
            if side == SignalSide.BUY:
                stop = entry * (1 - sl_pct / 100)
                target = entry * (1 + tp_pct / 100)
            else:
                stop = entry * (1 + sl_pct / 100)
                target = entry * (1 - tp_pct / 100)

        contracts = contracts_for_config(cfg, symbol)

        if side == SignalSide.BUY:
            entry_reason = (
                f"Rompimento de alta — close {last_close:.2f} acima da máxima "
                f"dos últimos {self.LOOKBACK} candles ({range_high:.2f})"
            )
        else:
            entry_reason = (
                f"Rompimento de baixa — close {last_close:.2f} abaixo da mínima "
                f"dos últimos {self.LOOKBACK} candles ({range_low:.2f})"
            )
        note = f"Breakout v1 · lookback={self.LOOKBACK}"
        payload = SignalCreate(
            symbol=symbol,
            side=side,
            entry=round(entry, 2),
            stop=round(stop, 2),
            target=round(target, 2),
            contracts=contracts,
            strategy_id=settings.strategy_id,
            mode=mode,
            note=note,
            strategy_type="breakout",
            strategy_version=STRATEGY_VERSION,
            entry_reason=entry_reason,
        )
        result = StrategyResult(
            payload=payload,
            entry_reason=entry_reason,
            strategy_type="breakout",
            strategy_version=STRATEGY_VERSION,
        )
        from engine.news_context import filter_strategy_result

        return filter_strategy_result(result, agent_config)
