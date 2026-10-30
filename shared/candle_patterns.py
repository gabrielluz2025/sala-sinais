"""Detecção de padrões de candlestick — pure Python com TA-Lib opcional."""

from __future__ import annotations

from typing import Any

try:
    import talib  # type: ignore[import-untyped]

    _HAS_TALIB = True
except ImportError:
    talib = None  # type: ignore[assignment,misc]
    _HAS_TALIB = False

# id → metadados PT-BR e artigo da biblioteca
PATTERN_CATALOG: dict[str, dict[str, str]] = {
    "hammer": {
        "label_pt": "Martelo",
        "bias": "bullish",
        "library_article_id": "09-martelo-hammer",
    },
    "inverted_hammer": {
        "label_pt": "Martelo invertido",
        "bias": "bullish",
        "library_article_id": "09-martelo-hammer",
    },
    "doji": {
        "label_pt": "Doji",
        "bias": "neutral",
        "library_article_id": "10-doji-indecisao",
    },
    "bullish_engulfing": {
        "label_pt": "Engolfo de alta",
        "bias": "bullish",
        "library_article_id": "11-engolfo",
    },
    "bearish_engulfing": {
        "label_pt": "Engolfo de baixa",
        "bias": "bearish",
        "library_article_id": "11-engolfo",
    },
    "shooting_star": {
        "label_pt": "Estrela cadente",
        "bias": "bearish",
        "library_article_id": "12-estrela-cadente",
    },
    "spinning_top": {
        "label_pt": "Pião",
        "bias": "neutral",
        "library_article_id": "13-piao-indecisao",
    },
    "marubozu_bull": {
        "label_pt": "Marubozu de alta",
        "bias": "bullish",
        "library_article_id": "13-piao-indecisao",
    },
    "marubozu_bear": {
        "label_pt": "Marubozu de baixa",
        "bias": "bearish",
        "library_article_id": "13-piao-indecisao",
    },
}

_TALIB_MAP: dict[str, str] = {
    "hammer": "CDLHAMMER",
    "inverted_hammer": "CDLINVERTEDHAMMER",
    "doji": "CDLDOJI",
    "bullish_engulfing": "CDLENGULFING",
    "bearish_engulfing": "CDLENGULFING",
    "shooting_star": "CDLSHOOTINGSTAR",
    "spinning_top": "CDLSPINNINGTOP",
    "marubozu_bull": "CDLMARUBOZU",
    "marubozu_bear": "CDLMARUBOZU",
}


def talib_available() -> bool:
    return _HAS_TALIB


def detection_engine_name() -> str:
    return "talib" if _HAS_TALIB else "pure_python"


def _bar_parts(o: float, h: float, l: float, c: float) -> dict[str, float]:
    body = abs(c - o)
    rng = max(h - l, 1e-12)
    upper = h - max(o, c)
    lower = min(o, c) - l
    return {"body": body, "range": rng, "upper": upper, "lower": lower, "bullish": c >= o}


def _pack_hit(pattern_id: str, strength: float = 1.0) -> dict[str, Any]:
    meta = PATTERN_CATALOG[pattern_id]
    return {
        "id": pattern_id,
        "label_pt": meta["label_pt"],
        "bias": meta["bias"],
        "library_article_id": meta["library_article_id"],
        "strength": round(strength, 3),
    }


def detect_bar_patterns_pure(o: float, h: float, l: float, c: float, prev: dict | None = None) -> list[dict]:
    """Padrões na barra atual (prev necessário para engolfo)."""
    p = _bar_parts(o, h, l, c)
    body, rng, upper, lower = p["body"], p["range"], p["upper"], p["lower"]
    hits: list[dict] = []

    if rng > 0 and body / rng <= 0.1:
        hits.append(_pack_hit("doji"))

    if body > 0:
        if lower >= 2.0 * body and upper <= body * 0.35:
            hits.append(_pack_hit("hammer", min(1.0, lower / (body * 3))))
        if upper >= 2.0 * body and lower <= body * 0.35:
            if p["bullish"]:
                hits.append(_pack_hit("inverted_hammer", min(1.0, upper / (body * 3))))
            else:
                hits.append(_pack_hit("shooting_star", min(1.0, upper / (body * 3))))
        if upper >= body * 0.4 and lower >= body * 0.4 and body / rng <= 0.35:
            hits.append(_pack_hit("spinning_top"))
        if body / rng >= 0.88:
            hits.append(_pack_hit("marubozu_bull" if p["bullish"] else "marubozu_bear", body / rng))

    if prev is not None:
        po, ph, pl, pc = float(prev["open"]), float(prev["high"]), float(prev["low"]), float(prev["close"])
        pp = _bar_parts(po, ph, pl, pc)
        if pp["body"] > 0 and body > pp["body"]:
            if not pp["bullish"] and p["bullish"] and o <= pc and c >= po:
                hits.append(_pack_hit("bullish_engulfing", min(1.0, body / pp["body"])))
            if pp["bullish"] and not p["bullish"] and o >= pc and c <= po:
                hits.append(_pack_hit("bearish_engulfing", min(1.0, body / pp["body"])))

    return hits


def _talib_hits_at(
    pattern_id: str,
    func_name: str,
    opens,
    highs,
    lows,
    closes,
    index: int,
) -> list[dict]:
    if not _HAS_TALIB or talib is None:
        return []
    func = getattr(talib, func_name, None)
    if func is None:
        return []
    try:
        out = func(opens, highs, lows, closes)
    except Exception:
        return []
    val = int(out[index])
    if val == 0:
        return []
    if pattern_id in ("bullish_engulfing", "bearish_engulfing", "marubozu_bull", "marubozu_bear"):
        if pattern_id == "bullish_engulfing" and val <= 0:
            return []
        if pattern_id == "bearish_engulfing" and val >= 0:
            return []
        if pattern_id == "marubozu_bull" and val <= 0:
            return []
        if pattern_id == "marubozu_bear" and val >= 0:
            return []
    strength = min(1.0, abs(val) / 100.0) if val != 0 else 1.0
    return [_pack_hit(pattern_id, strength)]


def analyze_bars(
    bars: list[dict],
    *,
    lookback: int = 24,
    timeframe: str = "M5",
) -> dict[str, Any]:
    """Analisa as últimas `lookback` barras OHLC."""
    if not bars:
        return {
            "timeframe": timeframe,
            "engine": detection_engine_name(),
            "bars_analyzed": 0,
            "hits": [],
            "last_bar": None,
            "summary_pt": "Sem barras OHLC para analisar padrões de candle.",
        }

    window = bars[-lookback:] if lookback > 0 else bars
    n = len(window)
    opens = [float(b["open"]) for b in window]
    highs = [float(b["high"]) for b in window]
    lows = [float(b["low"]) for b in window]
    closes = [float(b["close"]) for b in window]

    hits: list[dict] = []
    for i in range(n):
        prev = window[i - 1] if i > 0 else None
        bar_hits: list[dict] = []
        if _HAS_TALIB:
            for pid, fname in _TALIB_MAP.items():
                if pid in ("bullish_engulfing", "bearish_engulfing"):
                    continue
                bar_hits.extend(_talib_hits_at(pid, fname, opens, highs, lows, closes, i))
            bar_hits.extend(_talib_hits_at("bullish_engulfing", "CDLENGULFING", opens, highs, lows, closes, i))
            bar_hits.extend(_talib_hits_at("bearish_engulfing", "CDLENGULFING", opens, highs, lows, closes, i))
            if not bar_hits:
                bar_hits = detect_bar_patterns_pure(opens[i], highs[i], lows[i], closes[i], prev)
        else:
            bar_hits = detect_bar_patterns_pure(opens[i], highs[i], lows[i], closes[i], prev)

        if not bar_hits:
            continue
        ts = window[i].get("time")
        hits.append(
            {
                "bar_offset": i - (n - 1),
                "time": int(ts) if ts is not None else None,
                "open": opens[i],
                "high": highs[i],
                "low": lows[i],
                "close": closes[i],
                "patterns": bar_hits,
            }
        )

    last = window[-1]
    last_patterns = hits[-1]["patterns"] if hits and hits[-1]["bar_offset"] == 0 else []
    if not last_patterns:
        last_patterns = detect_bar_patterns_pure(
            float(last["open"]),
            float(last["high"]),
            float(last["low"]),
            float(last["close"]),
            window[-2] if n > 1 else None,
        )

    names = ", ".join(p["label_pt"] for p in last_patterns) if last_patterns else "nenhum padrão clássico"
    summary = f"Última barra {timeframe}: {names}. Motor: {detection_engine_name()}."

    return {
        "timeframe": timeframe,
        "engine": detection_engine_name(),
        "bars_analyzed": n,
        "hits": hits,
        "last_bar": {
            "time": last.get("time"),
            "open": float(last["open"]),
            "high": float(last["high"]),
            "low": float(last["low"]),
            "close": float(last["close"]),
            "patterns": last_patterns,
        },
        "summary_pt": summary,
    }
