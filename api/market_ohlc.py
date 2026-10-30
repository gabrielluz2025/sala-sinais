"""OHLC multi-timeframe para o painel."""

from __future__ import annotations

import json
from pathlib import Path

from shared.ohlc_utils import resample_bars, ticks_to_m1

_ROOT = Path(__file__).resolve().parents[1]
_QUOTE_HISTORY = _ROOT / "data" / "quote_history.json"
_DATA = _ROOT / "data"

_TF_MINUTES = {"M1": 1, "M5": 5, "H1": 60}


def load_m1_bars(symbol: str) -> list[dict]:
    sym = symbol.upper()
    bars_path = _DATA / f"bars_{sym}.json"
    if bars_path.is_file():
        try:
            data = json.loads(bars_path.read_text(encoding="utf-8"))
            if isinstance(data, list) and data:
                return data
        except Exception:
            pass
    if _QUOTE_HISTORY.is_file():
        try:
            points = json.loads(_QUOTE_HISTORY.read_text(encoding="utf-8"))
            if isinstance(points, list):
                sym_points = [p for p in points if (p.get("symbol") or "").upper() == sym]
                pool = sym_points if sym_points else points
                return ticks_to_m1(pool)
        except Exception:
            pass
    return []


def get_ohlc(symbol: str, tf: str = "M5", limit: int = 80) -> dict:
    tf_key = (tf or "M5").upper()
    minutes = _TF_MINUTES.get(tf_key, 5)
    m1 = load_m1_bars(symbol)
    if minutes > 1:
        bars = resample_bars(m1, minutes)
    else:
        bars = m1
    total = len(bars)
    if limit is not None and limit > 0:
        bars = bars[-limit:]
    return {
        "symbol": symbol.upper(),
        "timeframe": tf_key,
        "bars": bars,
        "bars_total": total,
        "source": "bars_file" if (_DATA / f"bars_{symbol.upper()}.json").is_file() else "quote_history",
    }
