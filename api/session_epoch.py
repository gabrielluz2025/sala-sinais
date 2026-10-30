"""Marca temporal de sessão — KPIs ignoram sinais anteriores ao epoch."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

TZ_BR = ZoneInfo("America/Sao_Paulo")
_ROOT = Path(__file__).resolve().parents[1]
_EPOCH_FILE = _ROOT / "data" / "sala_sinais_session_epoch.json"


def _read_raw() -> dict | None:
    if not _EPOCH_FILE.is_file():
        return None
    try:
        return json.loads(_EPOCH_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def load_session_epoch_at() -> str | None:
    raw = _read_raw()
    if not raw:
        return None
    epoch = raw.get("epoch_at")
    if isinstance(epoch, str) and epoch.strip():
        return epoch.strip()
    return None


def set_session_epoch(*, reason: str = "user_reset") -> str:
    now = datetime.now(TZ_BR).isoformat()
    _EPOCH_FILE.parent.mkdir(parents=True, exist_ok=True)
    payload = {"epoch_at": now, "reason": reason}
    _EPOCH_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return now


def row_in_metrics_session(row, *, epoch_at: str | None = None) -> bool:
    """True se o sinal entra nos KPIs / PnL do painel."""
    epoch = epoch_at if epoch_at is not None else load_session_epoch_at()
    if not epoch:
        return True
    created = (getattr(row, "created_at", None) or "").strip()
    if not created:
        return False
    return created >= epoch
