"""API interna: padrões de candlestick a partir de OHLC resampleado."""

from __future__ import annotations

from api.market_ohlc import get_ohlc
from shared.candle_patterns import analyze_bars, talib_available


def get_candle_patterns(
    symbol: str,
    *,
    tf: str = "M5",
    limit: int = 80,
    lookback: int = 24,
) -> dict:
    ohlc = get_ohlc(symbol, tf=tf, limit=limit)
    bars = ohlc.get("bars") or []
    analysis = analyze_bars(bars, lookback=min(lookback, len(bars) or lookback), timeframe=ohlc.get("timeframe", tf))
    return {
        "symbol": symbol.upper(),
        "source": ohlc.get("source"),
        "bars_total": ohlc.get("bars_total", len(bars)),
        "talib_available": talib_available(),
        **analysis,
    }
