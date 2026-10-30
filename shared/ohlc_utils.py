"""Utilitários OHLC compartilhados entre API e engine."""

from __future__ import annotations

from datetime import datetime


def resample_bars(m1_bars: list[dict], tf_minutes: int) -> list[dict]:
    if not m1_bars or tf_minutes <= 1:
        return list(m1_bars)
    buckets: dict[int, dict] = {}
    for b in m1_bars:
        t = int(b["time"])
        bucket = (t // (tf_minutes * 60)) * (tf_minutes * 60)
        o, h, l, c = float(b["open"]), float(b["high"]), float(b["low"]), float(b["close"])
        vol = int(b.get("volume") or 0)
        if bucket not in buckets:
            buckets[bucket] = {
                "time": bucket,
                "open": o,
                "high": h,
                "low": l,
                "close": c,
                "volume": vol,
            }
        else:
            cur = buckets[bucket]
            cur["high"] = max(cur["high"], h)
            cur["low"] = min(cur["low"], l)
            cur["close"] = c
            cur["volume"] += vol
    return [buckets[k] for k in sorted(buckets.keys())]


def ticks_to_m1(points: list[dict]) -> list[dict]:
    buckets: dict[int, dict] = {}
    for p in points:
        ts = p.get("timestamp")
        if not ts:
            continue
        try:
            dt = datetime.fromisoformat(str(ts))
            t = int(dt.timestamp())
        except ValueError:
            continue
        bid = float(p.get("bid") or 0)
        ask = float(p.get("ask") or 0)
        mid = (bid + ask) / 2 if bid and ask else bid or ask
        if not mid:
            continue
        bucket = (t // 60) * 60
        if bucket not in buckets:
            buckets[bucket] = {
                "time": bucket,
                "open": mid,
                "high": mid,
                "low": mid,
                "close": mid,
                "volume": 1,
            }
        else:
            cur = buckets[bucket]
            cur["high"] = max(cur["high"], mid)
            cur["low"] = min(cur["low"], mid)
            cur["close"] = mid
            cur["volume"] += 1
    return [buckets[k] for k in sorted(buckets.keys())]
