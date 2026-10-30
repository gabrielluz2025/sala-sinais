"""Séries de indicadores da estratégia (BB, ATR) para overlay no chart."""

from __future__ import annotations

import numpy as np

from api.market_ohlc import get_ohlc

BB_PERIOD = 20
BB_STD = 2.0
ATR_PERIOD = 14


def _bb_series(closes: np.ndarray) -> tuple[list[float | None], list[float | None], list[float | None]]:
    n = len(closes)
    upper: list[float | None] = [None] * n
    mid: list[float | None] = [None] * n
    lower: list[float | None] = [None] * n
    for i in range(BB_PERIOD - 1, n):
        window = closes[i - BB_PERIOD + 1 : i + 1]
        m = float(np.mean(window))
        std = float(np.std(window))
        upper[i] = m + BB_STD * std
        mid[i] = m
        lower[i] = m - BB_STD * std
    return upper, mid, lower


def _atr_percent_last(rates: list[dict], period: int = ATR_PERIOD) -> float:
    if len(rates) < period + 1:
        return 0.0
    highs = np.array([float(r["high"]) for r in rates[-(period + 1) :]], dtype=float)
    lows = np.array([float(r["low"]) for r in rates[-(period + 1) :]], dtype=float)
    closes = np.array([float(r["close"]) for r in rates[-(period + 1) :]], dtype=float)
    tr_list: list[float] = []
    for i in range(1, len(closes)):
        tr = max(highs[i] - lows[i], abs(highs[i] - closes[i - 1]), abs(lows[i] - closes[i - 1]))
        tr_list.append(tr)
    atr = float(np.mean(tr_list)) if tr_list else 0.0
    last_close = float(closes[-1])
    if last_close <= 0:
        return 0.0
    return (atr / last_close) * 100.0


def _vol_regime(atr_pct: float, bb_width_pct: float) -> tuple[str, float]:
    atr_score = min(1.0, atr_pct / 2.5)
    bb_score = min(1.0, bb_width_pct / 6.0)
    score = 0.55 * atr_score + 0.45 * bb_score
    if score >= 0.55:
        return "vol alta", score
    if score <= 0.35:
        return "vol baixa", score
    return "vol moderada", score


def get_strategy_series(symbol: str, tf: str = "M5", limit: int = 100) -> dict:
    raw = get_ohlc(symbol, tf=tf, limit=max(limit, BB_PERIOD + 5))
    bars = raw.get("bars") or []
    if not bars:
        return {
            "symbol": symbol.upper(),
            "timeframe": tf.upper(),
            "bars": [],
            "bb_upper": [],
            "bb_mid": [],
            "bb_lower": [],
            "atr_pct_last": 0.0,
            "regime": "—",
            "regime_score": 0.0,
        }

    closes = np.array([float(b["close"]) for b in bars], dtype=float)
    upper, mid, lower = _bb_series(closes)

    atr_pct = _atr_percent_last(bars)
    last_mid = mid[-1] if mid[-1] is not None else float(closes[-1])
    bb_width = 0.0
    if last_mid > 0 and upper[-1] is not None and lower[-1] is not None:
        bb_width = ((upper[-1] - lower[-1]) / last_mid) * 100.0
    regime, score = _vol_regime(atr_pct, bb_width)

    times = [b.get("time") for b in bars]
    return {
        "symbol": symbol.upper(),
        "timeframe": raw.get("timeframe", tf.upper()),
        "times": times,
        "bb_upper": upper,
        "bb_mid": mid,
        "bb_lower": lower,
        "atr_pct_last": round(atr_pct, 4),
        "regime": regime,
        "regime_score": round(score, 3),
        "source": raw.get("source"),
    }
