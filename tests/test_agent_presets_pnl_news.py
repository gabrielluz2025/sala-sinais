"""Presets, PnL fiscal e news_context."""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from api.agent_config import AGENT_PRESETS, apply_preset_to_row, list_presets_public
from api.b3_tickers import search_popular_tickers
from api.database import AgentConfigRow
from api.pnl import estimated_ir_brl, net_pnl_brl, pnl_tax_breakdown, trade_fees_brl
from engine.news_context import bias_from_headlines, filter_strategy_result
from shared.schemas import SignalSide


def test_search_tickers_filters_symbol():
    all_rows = search_popular_tickers("", limit=50)
    assert len(all_rows) >= 20
    pet = search_popular_tickers("pet", limit=5)
    assert any(r["symbol"] == "PETR4" for r in pet)


def test_list_presets_has_three():
    presets = list_presets_public()
    assert len(presets) == 3
    ids = {p["id"] for p in presets}
    assert ids == {"moderado", "conservador", "agressivo"}


def test_apply_preset_moderado():
    row = AgentConfigRow(id=1, symbols_json="[]", updated_at="2026-01-01T00:00:00")
    apply_preset_to_row(row, "moderado")
    assert row.applied_preset == "moderado"
    assert row.capital_brl == AGENT_PRESETS["moderado"]["capital_brl"]
    assert row.use_news_filter is True


def test_pnl_tax_breakdown_fields():
    net = 100.0
    ir, after = pnl_tax_breakdown(net)
    assert ir == estimated_ir_brl(net)
    assert after == round(net - ir, 2)
    assert estimated_ir_brl(-50) == 0.0


def test_equity_fees_use_emolument_pct():
    fees = trade_fees_brl(30.0, 31.0, 100, symbol="PETR4")
    assert fees > 0


def test_news_bias_cautious_blocks_signal(monkeypatch):
    from engine import news_context as nc

    ctx = bias_from_headlines([{"title": "Copom mantém Selic em foco no mercado"}])
    assert ctx.bias == "cautious"
    monkeypatch.setattr(nc, "load_news_context", lambda: ctx)

    class DummyPayload:
        entry_reason = "teste"

    class DummyResult:
        payload = DummyPayload()
        entry_reason = "teste"
        strategy_type = "volatility"
        strategy_version = "v1"
        regime = None

    out = filter_strategy_result(DummyResult(), {"use_news_filter": True})
    assert out is None


def test_news_context_import():
    import engine.news_context as nc

    assert nc.LIB_ARTICLE_CAUTION == "04"
