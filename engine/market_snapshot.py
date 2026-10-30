"""Persiste barras M1 para a API montar OHLC multi-timeframe."""

from __future__ import annotations

import json
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_BARS_DIR = _ROOT / "data"


def write_m1_bars(symbol: str, rates) -> None:
    if rates is None or len(rates) == 0:
        return
    sym = symbol.upper()
    path = _BARS_DIR / f"bars_{sym}.json"
    _BARS_DIR.mkdir(parents=True, exist_ok=True)
    rows: list[dict] = []
    for bar in rates:
        rows.append(
            {
                "time": int(bar["time"]),
                "open": float(bar["open"]),
                "high": float(bar["high"]),
                "low": float(bar["low"]),
                "close": float(bar["close"]),
                "volume": int(bar["tick_volume"] if "tick_volume" in bar.dtype.names else 0),
            }
        )
    path.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
