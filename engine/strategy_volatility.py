"""Estratégia adaptativa à volatilidade (ATR%, largura Bollinger, regime)."""

from __future__ import annotations

from typing import Optional

import numpy as np

from engine.agent_runtime import contracts_for_config, is_win_symbol
from engine.config import settings
from engine.strategy import StrategyResult
from engine.strategy_meta import STRATEGY_VERSION
from shared.schemas import SignalCreate, SignalMode, SignalSide


def _atr_percent(rates, period: int = 14) -> float:
    if len(rates) < period + 1:
        return 0.0
    highs = rates["high"][-(period + 1) :]
    lows = rates["low"][-(period + 1) :]
    closes = rates["close"][-(period + 1) :]
    tr_list: list[float] = []
    for i in range(1, len(closes)):
        h, l, pc = float(highs[i]), float(lows[i]), float(closes[i - 1])
        tr = max(h - l, abs(h - pc), abs(l - pc))
        tr_list.append(tr)
    atr = float(np.mean(tr_list)) if tr_list else 0.0
    last_close = float(closes[-1])
    if last_close <= 0:
        return 0.0
    return (atr / last_close) * 100.0


def _bb_width_percent(rates, period: int = 20, num_std: float = 2.0) -> float:
    if len(rates) < period:
        return 0.0
    closes = rates["close"][-period:].astype(float)
    mid = float(np.mean(closes))
    if mid <= 0:
        return 0.0
    std = float(np.std(closes))
    upper = mid + num_std * std
    lower = mid - num_std * std
    return ((upper - lower) / mid) * 100.0


def _vol_regime(atr_pct: float, bb_width_pct: float) -> tuple[str, float]:
    """Retorna (regime_label, score 0..1). score alto = vol alta."""
    # Normalização empírica para WIN (~0.1-0.5% ATR) e ações (~0.5-3%)
    atr_score = min(1.0, atr_pct / 2.5)
    bb_score = min(1.0, bb_width_pct / 6.0)
    score = 0.55 * atr_score + 0.45 * bb_score
    if score >= 0.55:
        return "vol alta", score
    if score <= 0.35:
        return "vol baixa", score
    return "vol moderada", score


class VolatilityAdaptiveStrategy:
    """Ajusta stops/alvos e filtra sinais conforme regime de volatilidade."""

    LOOKBACK = 12
    ATR_PERIOD = 14
    BB_PERIOD = 20

    def evaluate(
        self,
        symbol: str,
        rates,
        bid: float,
        ask: float,
        mode: SignalMode,
        agent_config: dict | None = None,
    ) -> Optional[StrategyResult]:
        if len(rates) < self.BB_PERIOD + 2:
            return None

        atr_pct = _atr_percent(rates, self.ATR_PERIOD)
        bb_width = _bb_width_percent(rates, self.BB_PERIOD)
        regime_label, vol_score = _vol_regime(atr_pct, bb_width)

        # Alta vol: exige rompimento mais forte; baixa vol: aceita rompimento menor
        base = 12
        if vol_score >= 0.55:
            effective_lookback = base + 4
            stop_mult = 1.45
            target_mult = 1.35
            min_break_extra = 0.0008
        elif vol_score <= 0.35:
            effective_lookback = max(6, base - 2)
            stop_mult = 0.75
            target_mult = 0.85
            min_break_extra = 0.0
        else:
            effective_lookback = base
            stop_mult = 1.0
            target_mult = 1.0
            min_break_extra = 0.0003

        if len(rates) < effective_lookback + 2:
            return None

        highs = rates["high"][-(effective_lookback + 1) : -1]
        lows = rates["low"][-(effective_lookback + 1) : -1]
        range_high = float(np.max(highs))
        range_low = float(np.min(lows))
        last_close = float(rates["close"][-2])
        mid = (bid + ask) / 2.0
        break_buffer = mid * min_break_extra

        side: SignalSide | None = None
        entry = 0.0
        if last_close > range_high + break_buffer:
            side = SignalSide.BUY
            entry = ask
        elif last_close < range_low - break_buffer:
            side = SignalSide.SELL
            entry = bid

        if side is None:
            return None

        cfg = agent_config or {}
        if is_win_symbol(symbol):
            stop_pts = int((cfg.get("stop_points") or settings.stop_points) * stop_mult)
            target_pts = int((cfg.get("target_points") or settings.target_points) * target_mult)
            if side == SignalSide.BUY:
                stop = entry - stop_pts
                target = entry + target_pts
            else:
                stop = entry + stop_pts
                target = entry - target_pts
        else:
            sl_pct = float(cfg.get("stop_loss_pct") or 2.0) * stop_mult
            tp_pct = float(cfg.get("take_profit_pct") or 3.0) * target_mult
            if side == SignalSide.BUY:
                stop = entry * (1 - sl_pct / 100)
                target = entry * (1 + tp_pct / 100)
            else:
                stop = entry * (1 + sl_pct / 100)
                target = entry * (1 - tp_pct / 100)

        contracts = contracts_for_config(cfg, symbol)
        if side == SignalSide.BUY:
            entry_reason = (
                f"Rompimento filtrado por vol — {regime_label}: close {last_close:.2f} "
                f"rompe máxima (lookback {effective_lookback}, ATR% {atr_pct:.2f})"
            )
        else:
            entry_reason = (
                f"Rompimento filtrado por vol — {regime_label}: close {last_close:.2f} "
                f"rompe mínima (lookback {effective_lookback}, ATR% {atr_pct:.2f})"
            )
        note = (
            f"Volatilidade {STRATEGY_VERSION} · {regime_label} "
            f"(BB%={bb_width:.2f}, lookback={effective_lookback})"
        )
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
            strategy_type="volatility",
            strategy_version=STRATEGY_VERSION,
            entry_reason=entry_reason,
            regime=regime_label,
        )
        result = StrategyResult(
            payload=payload,
            entry_reason=entry_reason,
            strategy_type="volatility",
            strategy_version=STRATEGY_VERSION,
            regime=regime_label,
        )
        from engine.news_context import filter_strategy_result

        return filter_strategy_result(result, agent_config)
