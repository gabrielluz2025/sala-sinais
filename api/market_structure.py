"""API: estrutura SMC (swings, zonas, FVG, CHoCH)."""

from __future__ import annotations

from api.market_ohlc import get_ohlc
from shared.structure_analysis import analyze_structure


def get_market_structure(
    symbol: str,
    *,
    tf: str = "M5",
    limit: int = 200,
) -> dict:
    ohlc = get_ohlc(symbol, tf=tf, limit=limit)
    bars = ohlc.get("bars") or []
    analysis = analyze_structure(bars, timeframe=ohlc.get("timeframe", tf))
    return {
        "symbol": symbol.upper(),
        "source": ohlc.get("source"),
        "bars_total": ohlc.get("bars_total", len(bars)),
        **analysis,
    }
