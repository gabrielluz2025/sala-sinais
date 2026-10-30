"""Detecção pure Python de padrões de candlestick."""

from shared.candle_patterns import analyze_bars, detect_bar_patterns_pure


def test_detect_hammer():
    hits = detect_bar_patterns_pure(100.0, 100.5, 94.0, 100.4)
    ids = {h["id"] for h in hits}
    assert "hammer" in ids


def test_detect_doji():
    hits = detect_bar_patterns_pure(50.0, 51.5, 48.5, 50.02)
    ids = {h["id"] for h in hits}
    assert "doji" in ids


def test_bullish_engulfing_two_bars():
    prev = {"open": 10.0, "high": 10.2, "low": 9.8, "close": 9.85}
    hits = detect_bar_patterns_pure(9.8, 10.5, 9.75, 10.45, prev=prev)
    ids = {h["id"] for h in hits}
    assert "bullish_engulfing" in ids


def test_analyze_bars_last_bar_summary():
    bars = [
        {"time": 1, "open": 10.0, "high": 10.2, "low": 9.9, "close": 9.95},
        {"time": 2, "open": 9.9, "high": 10.0, "low": 8.5, "close": 9.85},
    ]
    out = analyze_bars(bars, lookback=2, timeframe="M5")
    assert out["bars_analyzed"] == 2
    assert out["engine"] in ("pure_python", "talib")
    assert "summary_pt" in out
    assert out["last_bar"] is not None


def test_candle_patterns_endpoint():
    from fastapi.testclient import TestClient

    import api.main as main_mod

    client = TestClient(main_mod.app)
    res = client.get("/agent/candle-patterns?symbol=PETR4&lookback=10")
    assert res.status_code == 200
    data = res.json()
    assert data["symbol"] == "PETR4"
    assert "hits" in data
    assert "engine" in data
