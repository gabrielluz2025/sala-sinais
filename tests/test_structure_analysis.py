"""Testes da análise de estrutura SMC."""

from shared.structure_analysis import analyze_structure, classify_swings, find_fvgs, find_swings


def _bar(i: int, o: float, h: float, l: float, c: float) -> dict:
    return {"time": 1_700_000_000 + i * 300, "open": o, "high": h, "low": l, "close": c}


def test_find_swings_on_synthetic_zigzag():
    bars = []
    price = 100.0
    for i in range(20):
        if i % 4 == 0:
            h, l, c = price + 2, price - 0.5, price + 1.5
            price += 1
        elif i % 4 == 2:
            h, l, c = price + 0.5, price - 2, price - 1
            price -= 0.8
        else:
            h, l, c = price + 0.3, price - 0.3, price
        bars.append(_bar(i, price, h, l, c))
    swings = find_swings(bars, left=2, right=2)
    assert len(swings) >= 2


def test_classify_hh_hl():
    swings = [
        {"index": 1, "time": 1, "price": 10.0, "kind": "high"},
        {"index": 3, "time": 2, "price": 9.0, "kind": "low"},
        {"index": 5, "time": 3, "price": 11.0, "kind": "high"},
        {"index": 7, "time": 4, "price": 9.5, "kind": "low"},
    ]
    out = classify_swings(swings)
    labels = [s["label"] for s in out]
    assert labels[2] == "HH"
    assert labels[3] == "HL"


def test_bullish_fvg():
    bars = [
        _bar(0, 10, 10.5, 9.8, 10.2),
        _bar(1, 10.2, 10.4, 10.0, 10.3),
        _bar(2, 11.0, 11.5, 10.8, 11.4),
    ]
    fvgs = find_fvgs(bars)
    assert any(f["direction"] == "bullish" for f in fvgs)


def test_analyze_structure_returns_narrative():
    bars = [_bar(i, 100 + i * 0.1, 101 + i * 0.1, 99 + i * 0.1, 100.5 + i * 0.1) for i in range(30)]
    out = analyze_structure(bars, timeframe="M5")
    assert out["bars_analyzed"] == 30
    assert "narrative_pt" in out
    assert isinstance(out["zones"], list)


def test_get_market_structure_wrapper():
    from api.market_structure import get_market_structure

    out = get_market_structure("PETR4", tf="M5", limit=50)
    assert out["symbol"] == "PETR4"
    assert "swings" in out
    assert "narrative_pt" in out
