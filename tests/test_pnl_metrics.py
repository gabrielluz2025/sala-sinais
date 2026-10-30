"""Métricas PnL — posições abertas deduplicadas e MTM."""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from api.database import SignalRow
from api.pnl import (
    count_open_positions,
    estimate_open_pnl_brl,
    is_open_row,
    latest_open_positions,
)


def _row(**kwargs) -> SignalRow:
    row = SignalRow(
        id=kwargs.get("id", 1),
        symbol=kwargs["symbol"],
        side=kwargs.get("side", "BUY"),
        entry=kwargs.get("entry", 10.0),
        stop=9.0,
        target=11.0,
        contracts=kwargs.get("contracts", 100),
        strategy_id="t",
        status=kwargs.get("status", "sent"),
        created_at=kwargs.get("created_at", "2026-10-29T10:00:00-03:00"),
    )
    if "exit_price" in kwargs:
        row.exit_price = kwargs["exit_price"]
    return row


def test_latest_open_positions_dedupes_by_symbol():
    rows = [
        _row(id=1, symbol="PETR4", created_at="2026-10-29T09:00:00-03:00", entry=50.0),
        _row(id=2, symbol="PETR4", created_at="2026-10-29T11:00:00-03:00", entry=51.0),
        _row(id=3, symbol="VALE3", created_at="2026-10-29T10:00:00-03:00", entry=60.0),
    ]
    open_rows = [r for r in rows if is_open_row(r)]
    portfolio = latest_open_positions(open_rows)
    assert len(portfolio) == 2
    assert count_open_positions(open_rows) == 2
    petr = next(r for r in portfolio if r.symbol == "PETR4")
    assert petr.entry == 51.0


def test_mtm_sums_once_per_symbol():
    rows = [
        _row(id=1, symbol="PETR4", entry=50.0, contracts=100),
        _row(id=2, symbol="PETR4", entry=50.5, contracts=100),
    ]
    open_rows = [r for r in rows if is_open_row(r)]
    portfolio = latest_open_positions(open_rows)
    mids = {"PETR4": 51.0}
    single = estimate_open_pnl_brl(portfolio[0], mids)
    dup_sum = sum(estimate_open_pnl_brl(r, mids) for r in open_rows)
    portfolio_sum = sum(estimate_open_pnl_brl(r, mids) for r in portfolio)
    assert portfolio_sum == single
    assert dup_sum > portfolio_sum
