"""Análise simplificada de estrutura de mercado (SMC) para overlay no Pulse Deck."""

from __future__ import annotations

from typing import Any


def _bar_time(b: dict, index: int) -> int:
    t = b.get("time")
    if t is not None:
        try:
            tv = int(float(t))
            return tv // 1000 if tv > 1_000_000_000_000 else tv
        except (TypeError, ValueError):
            pass
    return index


def _norm_bars(bars: list[dict]) -> list[dict]:
    out: list[dict] = []
    for i, b in enumerate(bars):
        try:
            out.append(
                {
                    "time": _bar_time(b, i),
                    "open": float(b["open"]),
                    "high": float(b["high"]),
                    "low": float(b["low"]),
                    "close": float(b["close"]),
                    "volume": float(b.get("volume") or 0),
                }
            )
        except (KeyError, TypeError, ValueError):
            continue
    return out


def find_swings(bars: list[dict], *, left: int = 2, right: int = 2) -> list[dict]:
    """Fractais: pivôs de máxima/mínima locais."""
    if len(bars) < left + right + 1:
        return []
    swings: list[dict] = []
    for i in range(left, len(bars) - right):
        hi = bars[i]["high"]
        lo = bars[i]["low"]
        window_hi = [bars[j]["high"] for j in range(i - left, i + right + 1)]
        window_lo = [bars[j]["low"] for j in range(i - left, i + right + 1)]
        if hi >= max(window_hi):
            swings.append({"index": i, "time": bars[i]["time"], "price": hi, "kind": "high"})
        if lo <= min(window_lo):
            swings.append({"index": i, "time": bars[i]["time"], "price": lo, "kind": "low"})
    swings.sort(key=lambda s: s["index"])
    dedup: list[dict] = []
    last_idx = -1
    for s in swings:
        if s["index"] == last_idx:
            if dedup and dedup[-1]["kind"] != s["kind"]:
                dedup.append(s)
            continue
        dedup.append(s)
        last_idx = s["index"]
    return dedup


def classify_swings(swings: list[dict]) -> list[dict]:
    """Rotula HH/HL/LH/LL comparando com o pivô anterior do mesmo tipo."""
    last_high: float | None = None
    last_low: float | None = None
    out: list[dict] = []
    for s in swings:
        row = dict(s)
        if s["kind"] == "high":
            if last_high is None:
                label = "H"
            elif s["price"] > last_high:
                label = "HH"
            elif s["price"] < last_high:
                label = "LH"
            else:
                label = "H"
            last_high = s["price"]
        else:
            if last_low is None:
                label = "L"
            elif s["price"] > last_low:
                label = "HL"
            elif s["price"] < last_low:
                label = "LL"
            else:
                label = "L"
            last_low = s["price"]
        row["label"] = label
        out.append(row)
    return out


def _zone_band(price: float, *, pct: float = 0.0018) -> tuple[float, float]:
    half = max(price * pct, 0.01)
    return price - half, price + half


def build_zones(swings: list[dict], bars: list[dict]) -> list[dict]:
    if not bars:
        return []
    zones: list[dict] = []
    t0 = bars[0]["time"]
    t1 = bars[-1]["time"]
    highs = [s for s in swings if s["kind"] == "high" and s.get("label") in ("HH", "LH", "H")]
    lows = [s for s in swings if s["kind"] == "low" and s.get("label") in ("HL", "LL", "L")]
    if highs:
        sh = highs[-1]
        bot, top = _zone_band(sh["price"])
        zones.append(
            {
                "type": "supply",
                "price_top": top,
                "price_bottom": bot,
                "time_start": sh["time"],
                "time_end": t1,
                "label_pt": "Zona oferta · resistência intraday",
            }
        )
    if lows:
        sl = lows[-1]
        bot, top = _zone_band(sl["price"])
        zones.append(
            {
                "type": "demand",
                "price_top": top,
                "price_bottom": bot,
                "time_start": sl["time"],
                "time_end": t1,
                "label_pt": "Zona demanda · suporte intraday",
            }
        )
    if not zones and bars:
        mid = (bars[-1]["high"] + bars[-1]["low"]) / 2
        bot, top = _zone_band(mid)
        zones.append(
            {
                "type": "demand",
                "price_top": top,
                "price_bottom": bot,
                "time_start": t0,
                "time_end": t1,
                "label_pt": "Zona neutra",
            }
        )
    return zones


def find_fvgs(bars: list[dict], *, max_count: int = 3) -> list[dict]:
    fvgs: list[dict] = []
    for i in range(2, len(bars)):
        b0 = bars[i - 2]
        b2 = bars[i]
        if b2["low"] > b0["high"]:
            fvgs.append(
                {
                    "direction": "bullish",
                    "top": b2["low"],
                    "bottom": b0["high"],
                    "time": b2["time"],
                    "index": i,
                    "label_pt": "FVG alta",
                }
            )
        elif b2["high"] < b0["low"]:
            fvgs.append(
                {
                    "direction": "bearish",
                    "top": b0["low"],
                    "bottom": b2["high"],
                    "time": b2["time"],
                    "index": i,
                    "label_pt": "FVG baixa",
                }
            )
    fvgs.sort(key=lambda x: x["index"], reverse=True)
    trimmed = fvgs[:max_count]
    trimmed.reverse()
    return trimmed


def detect_choch(classified: list[dict], bars: list[dict]) -> dict | None:
    if len(bars) < 5 or len(classified) < 3:
        return None
    highs = [s for s in classified if s["kind"] == "high"]
    lows = [s for s in classified if s["kind"] == "low"]
    if len(highs) < 1 or len(lows) < 2:
        return None

    last_hl = next((s for s in reversed(lows) if s.get("label") in ("HL", "L")), None)
    last_lh = next((s for s in reversed(highs) if s.get("label") in ("LH", "H")), None)
    last_close = bars[-1]["close"]

    uptrend = len([s for s in classified[-6:] if s.get("label") == "HH"]) >= 1 or (
        last_hl and last_hl.get("label") == "HL"
    )

    if uptrend and last_hl and last_close < last_hl["price"]:
        return {
            "direction": "bearish",
            "price": last_hl["price"],
            "time": bars[-1]["time"],
            "label_pt": "CHoCH · viés venda",
            "broken_swing_label": last_hl.get("label", "HL"),
        }

    downtrend = len([s for s in classified[-6:] if s.get("label") == "LL"]) >= 1 or (
        last_lh and last_lh.get("label") == "LH"
    )
    if downtrend and last_lh and last_close > last_lh["price"]:
        return {
            "direction": "bullish",
            "price": last_lh["price"],
            "time": bars[-1]["time"],
            "label_pt": "CHoCH · viés compra",
            "broken_swing_label": last_lh.get("label", "LH"),
        }

    for i in range(len(bars) - 1, max(0, len(bars) - 40), -1):
        c = bars[i]["close"]
        if last_hl and c < last_hl["price"]:
            return {
                "direction": "bearish",
                "price": last_hl["price"],
                "time": bars[i]["time"],
                "label_pt": "CHoCH · viés venda",
                "broken_swing_label": last_hl.get("label", "HL"),
            }
        if last_lh and c > last_lh["price"]:
            return {
                "direction": "bullish",
                "price": last_lh["price"],
                "time": bars[i]["time"],
                "label_pt": "CHoCH · viés compra",
                "broken_swing_label": last_lh.get("label", "LH"),
            }
    return None


def narrative_pt(
    classified: list[dict],
    choch: dict | None,
    zones: list[dict],
    fvgs: list[dict],
) -> str:
    parts: list[str] = []
    recent = [s for s in classified if s.get("label") in ("HH", "HL", "LH", "LL")][-4:]
    if recent:
        labels = " → ".join(s["label"] for s in recent)
        parts.append(f"Swings recentes: {labels}")
    if choch:
        parts.append(choch["label_pt"])
    elif recent:
        last = recent[-1]["label"]
        if last in ("HH", "HL"):
            parts.append("Estrutura de alta (HH/HL)")
        elif last in ("LH", "LL"):
            parts.append("Estrutura de baixa (LH/LL)")
    supply = next((z for z in zones if z["type"] == "supply"), None)
    demand = next((z for z in zones if z["type"] == "demand"), None)
    if supply:
        parts.append("Oferta acima do último topo")
    if demand:
        parts.append("Demanda no último fundo")
    if fvgs:
        parts.append(f"{len(fvgs)} FVG(s) recente(s)")
    return " · ".join(parts) if parts else "Estrutura ainda indefinida — aguarde mais barras M5."


def analyze_structure(bars: list[dict], *, timeframe: str = "M5") -> dict[str, Any]:
    norm = _norm_bars(bars)
    if len(norm) < 10:
        return {
            "timeframe": timeframe,
            "bars_analyzed": len(norm),
            "swings": [],
            "zones": [],
            "fvgs": [],
            "choch": None,
            "trend_bias": "neutral",
            "narrative_pt": "Poucas barras para mapear estrutura SMC.",
        }

    raw_swings = find_swings(norm)
    classified = classify_swings(raw_swings)
    display_swings = [
        {
            "time": s["time"],
            "price": s["price"],
            "kind": s["kind"],
            "label": s.get("label", ""),
        }
        for s in classified
        if s.get("label") in ("HH", "HL", "LH", "LL")
    ][-12:]

    zones = build_zones(classified, norm)
    fvgs = find_fvgs(norm)
    choch = detect_choch(classified, norm)

    bias = "neutral"
    if choch:
        bias = "bearish" if choch["direction"] == "bearish" else "bullish"
    else:
        tail = [s.get("label") for s in classified[-4:]]
        if any(x == "HH" for x in tail) or tail[-1:] == ["HL"]:
            bias = "bullish"
        elif any(x == "LL" for x in tail) or tail[-1:] == ["LH"]:
            bias = "bearish"

    return {
        "timeframe": timeframe,
        "bars_analyzed": len(norm),
        "swings": display_swings,
        "zones": zones,
        "fvgs": fvgs,
        "choch": choch,
        "trend_bias": bias,
        "narrative_pt": narrative_pt(classified, choch, zones, fvgs),
    }
