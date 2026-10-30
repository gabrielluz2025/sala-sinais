from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from engine.config import settings

TZ_BR = ZoneInfo("America/Sao_Paulo")


class RiskManager:
    def __init__(self) -> None:
        self._last_signal_at: datetime | None = None

    def mark_signal_sent(self) -> None:
        self._last_signal_at = datetime.now(TZ_BR)

    def can_trade(
        self,
        now: datetime | None = None,
        *,
        enforce_session_hours: bool = True,
        min_cooldown_sec: int | None = None,
    ) -> tuple[bool, str]:
        now = now or datetime.now(TZ_BR)
        if enforce_session_hours:
            from shared.session_hours import b3_session_block_reason

            block = b3_session_block_reason(
                now,
                trade_start_hour=settings.trade_start_hour,
                trade_end_hour=settings.trade_end_hour,
                enforce=True,
            )
            if block:
                return False, block

        if self._last_signal_at:
            elapsed = (now - self._last_signal_at).total_seconds()
            min_cd = max(
                settings.signal_cooldown_sec,
                int(min_cooldown_sec or 0),
            )
            if elapsed < min_cd:
                return False, f"Cooldown ({int(min_cd - elapsed)}s restantes)"

        return True, "ok"

    def clamp_contracts(self, requested: int) -> int:
        return max(1, min(requested, settings.max_contracts))
