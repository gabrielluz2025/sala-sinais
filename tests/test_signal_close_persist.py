"""Persistência de net_pnl_brl ao fechar sinal."""

from __future__ import annotations

from types import SimpleNamespace


def test_persist_resolved_pnl_backfills_columns():
    from api.signal_close import persist_resolved_pnl

    row = SimpleNamespace(
        symbol="PETR4",
        side="BUY",
        entry=29.0,
        exit_price=30.0,
        contracts=100,
        gross_pnl_brl=None,
        net_pnl_brl=None,
    )
    gross, net, fees = persist_resolved_pnl(row)
    assert net is not None
    assert gross is not None
    assert row.net_pnl_brl is not None
    assert row.gross_pnl_brl is not None
    assert fees > 0
