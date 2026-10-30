"""Tests for GET /market/strategy-series."""

from __future__ import annotations

from api.strategy_series import get_strategy_series


def test_strategy_series_empty_bars(monkeypatch):
    import api.strategy_series as mod

    monkeypatch.setattr(mod, "get_ohlc", lambda *a, **k: {"bars": [], "timeframe": "M5", "source": "test"})
    out = get_strategy_series("ZZZZ99", tf="M5", limit=30)
    assert out["symbol"] == "ZZZZ99"
    assert out["bb_upper"] == []
    assert "regime" in out


def test_strategy_series_with_sample_bars(monkeypatch):
    import api.strategy_series as mod

    bars = []
    base = 10.0
    for i in range(40):
        c = base + i * 0.05
        bars.append(
            {
                "time": 1_700_000_000 + i * 300,
                "open": c - 0.02,
                "high": c + 0.05,
                "low": c - 0.05,
                "close": c,
            }
        )

    def fake_get_ohlc(symbol, tf="M5", limit=80):
        return {"symbol": symbol, "timeframe": tf, "bars": bars[-limit:], "source": "test"}

    monkeypatch.setattr(mod, "get_ohlc", fake_get_ohlc)
    out = mod.get_strategy_series("TEST4", limit=40)
    assert len(out["bb_mid"]) == 40
    assert out["bb_mid"][-1] is not None
    assert out["atr_pct_last"] >= 0
    assert out["regime"] in ("vol alta", "vol baixa", "vol moderada")
