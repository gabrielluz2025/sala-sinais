from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

_DATA_PATH = Path(__file__).resolve().parents[1] / "data" / "b3_tickers_popular.json"


@lru_cache(maxsize=1)
def load_popular_tickers() -> list[dict[str, str]]:
    raw = json.loads(_DATA_PATH.read_text(encoding="utf-8"))
    items = raw.get("tickers") or []
    out: list[dict[str, str]] = []
    for item in items:
        sym = str(item.get("symbol", "")).strip().upper()
        if not sym:
            continue
        out.append({"symbol": sym, "name": str(item.get("name") or sym).strip()})
    return out


def search_popular_tickers(query: str, limit: int = 12) -> list[dict[str, str]]:
    q = (query or "").strip().upper()
    pool = load_popular_tickers()
    if not q:
        return pool[:limit]
    matched: list[dict[str, str]] = []
    for row in pool:
        sym = row["symbol"]
        name = row.get("name", "")
        if q in sym or q in name.upper():
            matched.append(row)
        if len(matched) >= limit:
            break
    return matched
