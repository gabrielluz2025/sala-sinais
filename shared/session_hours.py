"""Janela operacional B3 (pregão) — compartilhado entre API, engine e status."""

from __future__ import annotations

from datetime import datetime, time
from zoneinfo import ZoneInfo

from shared.schemas import OperatingMode

TZ_BR = ZoneInfo("America/Sao_Paulo")


def resolve_enforce_b3_session_hours(
    *,
    live_trading: bool,
    execute_on_demo: bool,
    b3_ignore_session_hours: bool,
    operating_mode: OperatingMode | None = None,
    overnight_learning: bool = False,
) -> bool:
    """
    True = aplicar TRADE_START/END e leilão (bloqueio de novos sinais/ordens).

    LIVE_TRADING=true → sempre estrito.
    Demo/paper noturno → ignora se EXECUTE_ON_DEMO ou B3_IGNORE_SESSION_HOURS.
    OVERNIGHT_LEARNING → nunca bloqueia loops internos (até abrir o pregão).
    """
    if overnight_learning:
        return False
    if live_trading:
        return True
    if operating_mode == OperatingMode.SIMULATION:
        return False
    if execute_on_demo or b3_ignore_session_hours:
        return False
    return True


def b3_session_block_reason(
    now: datetime | None = None,
    *,
    trade_start_hour: int = 10,
    trade_end_hour: int = 17,
    enforce: bool = True,
) -> str | None:
    """Motivo em português se a janela B3 bloqueia; None se permitido."""
    if not enforce:
        return None
    now = now or datetime.now(TZ_BR)
    if now.weekday() >= 5:
        return "Mercado fechado (fim de semana)"

    start = time(trade_start_hour, 0)
    end = time(trade_end_hour, 0)
    t = now.time()
    if t < start or t >= end:
        return f"Fora do horário ({trade_start_hour}h–{trade_end_hour}h)"

    if (time(9, 0) <= t < time(9, 5)) or (time(17, 55) <= t):
        return "Janela de leilão — sem novos sinais"

    return None


def b3_pregao_regular_open(now: datetime | None = None) -> bool:
    """Pregão regular exibível no ticker (10h–17h BRT, seg–sex), independente de bypass demo."""
    now = now or datetime.now(TZ_BR)
    if now.weekday() >= 5:
        return False
    t = now.time()
    return time(10, 0) <= t < time(17, 0)
