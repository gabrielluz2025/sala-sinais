"""POST /system/flatten — kill switch: fecha posições na base e sinaliza engine."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from api.database import SignalRow
from api.pnl import is_open_row, load_quote_mid_map
from api.signal_close import finalize_signal_close
from api.system_state import get_or_create_state
from shared.schemas import SignalStatus, SystemFlattenResponse

TZ_BR = ZoneInfo("America/Sao_Paulo")


def flatten_system(
    db: Session,
    *,
    pause_engine: bool = True,
    state_to_read,
) -> SystemFlattenResponse:
    quote_mids = load_quote_mid_map()
    rows = db.query(SignalRow).all()
    open_rows = [r for r in rows if is_open_row(r)]

    closed = 0
    cancelled = 0
    for row in open_rows:
        st = (row.status or "").lower()
        if st == SignalStatus.PENDING.value:
            row.status = SignalStatus.CANCELLED.value
            row.execution_message = "Cancelado por flatten de emergência"
            cancelled += 1
            continue

        exit_px = quote_mids.get((row.symbol or "").upper())
        if exit_px is None:
            exit_px = float(row.entry)
        finalize_signal_close(
            row,
            float(exit_px),
            force_status_closed=True,
        )
        row.exit_reason = "emergency_flatten"
        row.status = SignalStatus.CLOSED.value
        row.execution_message = "Fechado por flatten de emergência"
        closed += 1

    state = get_or_create_state(db)
    state.emergency_flatten = True
    if pause_engine:
        state.engine_paused = True
    state.updated_at = datetime.now(TZ_BR).isoformat()
    db.commit()
    db.refresh(state)

    parts: list[str] = []
    if closed:
        parts.append(f"{closed} posição(ões) fechada(s) na base")
    if cancelled:
        parts.append(f"{cancelled} sinal(is) cancelado(s)")
    if not parts:
        parts.append("Nenhuma posição aberta na base")
    parts.append("Flag emergency_flatten ativa para o engine")

    return SystemFlattenResponse(
        ok=True,
        message="; ".join(parts),
        emergency_flatten=True,
        engine_paused=bool(state.engine_paused),
        positions_closed=closed,
        signals_cancelled=cancelled,
        state=state_to_read(state),
    )
