"""Política de horário B3 e bypass demo."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from shared.execution_policy import ExecutionEnvSettings
from shared.schemas import OperatingMode
from shared.session_hours import (
    b3_pregao_regular_open,
    b3_session_block_reason,
    resolve_enforce_b3_session_hours,
)

TZ_BR = ZoneInfo("America/Sao_Paulo")


def _dt(hour: int, minute: int = 0, weekday: int = 0) -> datetime:
    """Segunda-feira por padrão (weekday=0)."""
    base = datetime(2026, 3, 2, hour, minute, tzinfo=TZ_BR)
    if weekday:
        base = base.replace(day=base.day + weekday)
    return base


def test_enforce_strict_when_live_trading():
    assert (
        resolve_enforce_b3_session_hours(
            live_trading=True,
            execute_on_demo=True,
            b3_ignore_session_hours=True,
            operating_mode=OperatingMode.PAPER_MT5,
        )
        is True
    )


def test_bypass_demo_paper_night_flags():
    assert (
        resolve_enforce_b3_session_hours(
            live_trading=False,
            execute_on_demo=True,
            b3_ignore_session_hours=False,
            operating_mode=OperatingMode.PAPER_MT5,
        )
        is False
    )
    assert (
        resolve_enforce_b3_session_hours(
            live_trading=False,
            execute_on_demo=False,
            b3_ignore_session_hours=True,
            operating_mode=OperatingMode.PAPER_MT5,
        )
        is False
    )


def test_enforce_when_demo_flags_off():
    assert (
        resolve_enforce_b3_session_hours(
            live_trading=False,
            execute_on_demo=False,
            b3_ignore_session_hours=False,
            operating_mode=OperatingMode.PAPER_MT5,
        )
        is True
    )


def test_session_block_outside_hours():
    evening = datetime(2026, 3, 2, 19, 10, tzinfo=TZ_BR)
    msg = b3_session_block_reason(
        evening,
        trade_start_hour=10,
        trade_end_hour=17,
        enforce=True,
    )
    assert msg is not None
    assert "10h" in msg and "17h" in msg


def test_session_no_block_when_not_enforced():
    evening = datetime(2026, 3, 2, 19, 10, tzinfo=TZ_BR)
    assert b3_session_block_reason(evening, enforce=False) is None


def test_risk_manager_demo_bypass_integration():
    from engine.risk import RiskManager

    evening = datetime(2026, 3, 2, 19, 10, tzinfo=TZ_BR)
    rm = RiskManager()
    ok, reason = rm.can_trade(evening, enforce_session_hours=False)
    assert ok is True
    ok2, reason2 = rm.can_trade(evening, enforce_session_hours=True)
    assert ok2 is False
    assert "horário" in reason2


def test_b3_pregao_regular_open_display():
    open_dt = datetime(2026, 3, 2, 11, 0, tzinfo=TZ_BR)
    closed_dt = datetime(2026, 3, 2, 19, 12, tzinfo=TZ_BR)
    assert b3_pregao_regular_open(open_dt) is True
    assert b3_pregao_regular_open(closed_dt) is False


def test_overnight_learning_disables_session_enforce():
    assert (
        resolve_enforce_b3_session_hours(
            live_trading=False,
            execute_on_demo=False,
            b3_ignore_session_hours=False,
            operating_mode=OperatingMode.PAPER_MT5,
            overnight_learning=True,
        )
        is False
    )


def test_execution_env_default_ignore_hours():
    env = ExecutionEnvSettings(
        signal_mode="live",
        live_trading=False,
        execute_on_demo=True,
        b3_ignore_session_hours=True,
        engine_mode="paper_mt5",
    )
    assert env.b3_ignore_session_hours is True
    assert (
        resolve_enforce_b3_session_hours(
            live_trading=env.live_trading,
            execute_on_demo=env.execute_on_demo,
            b3_ignore_session_hours=env.b3_ignore_session_hours,
            operating_mode=OperatingMode.PAPER_MT5,
        )
        is False
    )
