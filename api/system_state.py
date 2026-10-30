from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from api.database import SystemStateRow

TZ_BR = ZoneInfo("America/Sao_Paulo")
_STATE_ID = 1


def _now_iso() -> str:
    return datetime.now(TZ_BR).isoformat()


def get_or_create_state(db: Session) -> SystemStateRow:
    row = db.get(SystemStateRow, _STATE_ID)
    if row is None:
        row = SystemStateRow(
            id=_STATE_ID,
            engine_paused=False,
            emergency_flatten=False,
            last_heartbeat=None,
            mode="paper",
            updated_at=_now_iso(),
        )
        db.add(row)
        db.commit()
        db.refresh(row)
    return row


def compute_engine_online(last_heartbeat: str | None, max_age_sec: float = 60.0) -> bool:
    if not last_heartbeat:
        return False
    try:
        hb = datetime.fromisoformat(last_heartbeat)
        if hb.tzinfo is None:
            hb = hb.replace(tzinfo=TZ_BR)
    except ValueError:
        return False
    age = (datetime.now(TZ_BR) - hb).total_seconds()
    return 0 <= age < max_age_sec


def state_to_dict(row: SystemStateRow) -> dict:
    return {
        "engine_paused": row.engine_paused,
        "emergency_flatten": row.emergency_flatten,
        "last_heartbeat": row.last_heartbeat,
        "engine_online": compute_engine_online(row.last_heartbeat),
        "mode": row.mode,
        "updated_at": row.updated_at,
        "account_login": row.account_login,
        "is_demo": row.is_demo,
        "account_server": row.account_server,
        "data_source": row.data_source,
        "mt5_connected": row.mt5_connected,
        "operating_mode": row.operating_mode,
    }
