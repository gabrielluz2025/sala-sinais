"""Finalização de sinal fechado (preço de saída + PnL persistido)."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from api.database import SignalRow
from api.pnl import gross_pnl_brl, net_pnl_brl, resolved_pnl_for_row
from shared.schemas import SignalOutcome, SignalSide, SignalStatus

TZ_BR = ZoneInfo("America/Sao_Paulo")


def persist_resolved_pnl(row: SignalRow) -> tuple[float | None, float | None, float]:
    """Garante gross/net_pnl_brl no row quando há saída ou PnL já calculado."""
    gross, net, fees = resolved_pnl_for_row(row)
    if net is None and row.net_pnl_brl is not None:
        net = float(row.net_pnl_brl)
        gross = row.gross_pnl_brl
    if row.exit_price is not None and net is not None:
        side = SignalSide(row.side)
        if row.gross_pnl_brl is None and gross is None:
            gross = gross_pnl_brl(
                side, row.entry, row.exit_price, row.contracts, symbol=row.symbol
            )
        if row.gross_pnl_brl is None and gross is not None:
            row.gross_pnl_brl = round(float(gross), 2)
        if row.net_pnl_brl is None:
            row.net_pnl_brl = round(float(net), 2)
    return gross, net, fees


def finalize_signal_close(
    row: SignalRow,
    exit_price: float,
    *,
    outcome: SignalOutcome | None = None,
    closed_at: datetime | None = None,
    force_status_closed: bool = True,
) -> None:
    side = SignalSide(row.side)
    row.exit_price = float(exit_price)
    row.gross_pnl_brl = gross_pnl_brl(
        side, row.entry, row.exit_price, row.contracts, symbol=row.symbol
    )
    row.net_pnl_brl = net_pnl_brl(
        side, row.entry, row.exit_price, row.contracts, symbol=row.symbol
    )
    net = row.net_pnl_brl
    if outcome is not None:
        row.outcome = outcome.value
    elif row.outcome is None:
        if net > 0:
            row.outcome = SignalOutcome.WIN.value
        elif net < 0:
            row.outcome = SignalOutcome.LOSS.value
        else:
            row.outcome = SignalOutcome.BREAKEVEN.value
    if closed_at is not None:
        row.closed_at = closed_at.isoformat()
    elif not row.closed_at:
        row.closed_at = datetime.now(TZ_BR).isoformat()
    if force_status_closed and row.status not in (
        SignalStatus.CLOSED.value,
        SignalStatus.FILLED.value,
    ):
        row.status = SignalStatus.CLOSED.value
