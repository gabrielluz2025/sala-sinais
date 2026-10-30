"""Política should_execute_orders e endpoint de status."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from shared.execution_policy import (
    ExecutionEnvSettings,
    should_execute_orders,
)
from shared.schemas import OperatingMode


def _env(**kwargs) -> ExecutionEnvSettings:
    base = {
        "signal_mode": "live",
        "live_trading": False,
        "allow_demo_live": False,
        "auto_execute_orders": True,
        "execute_on_demo": True,
        "engine_mode": "paper_mt5",
    }
    base.update(kwargs)
    return ExecutionEnvSettings(**base)


def test_should_execute_demo_paper_mt5():
    env = _env()
    ok, reason = should_execute_orders(
        operating_mode=OperatingMode.PAPER_MT5,
        engine_paused=False,
        is_demo=True,
        env=env,
    )
    assert ok is True
    assert reason is None


def test_should_not_execute_when_auto_execute_off():
    env = _env(auto_execute_orders=False)
    ok, reason = should_execute_orders(
        operating_mode=OperatingMode.PAPER_MT5,
        is_demo=True,
        env=env,
    )
    assert ok is False
    assert "AUTO_EXECUTE_ORDERS" in (reason or "")


def test_should_not_execute_simulation():
    env = _env(engine_mode="simulation")
    ok, reason = should_execute_orders(
        operating_mode=OperatingMode.SIMULATION,
        is_demo=True,
        env=env,
    )
    assert ok is False
    assert "simulation" in (reason or "").lower()


def test_should_not_execute_demo_without_execute_on_demo():
    env = _env(execute_on_demo=False)
    ok, _ = should_execute_orders(
        operating_mode=OperatingMode.PAPER_MT5,
        is_demo=True,
        env=env,
    )
    assert ok is False


def test_should_execute_real_when_live_trading():
    env = _env(engine_mode="live_mt5", live_trading=True)
    ok, reason = should_execute_orders(
        operating_mode=OperatingMode.LIVE_MT5,
        is_demo=False,
        env=env,
    )
    assert ok is True
    assert reason is None


def test_should_block_demo_live_without_allow():
    env = _env(engine_mode="live_mt5", live_trading=True, execute_on_demo=False)
    ok, reason = should_execute_orders(
        operating_mode=OperatingMode.LIVE_MT5,
        is_demo=True,
        env=env,
    )
    assert ok is False
    assert reason is not None


@pytest.fixture()
def api_client(tmp_path, monkeypatch):
    db_file = tmp_path / "exec_status.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_file.as_posix()}")
    monkeypatch.setenv("ENGINE_MODE", "paper_mt5")
    monkeypatch.setenv("SIGNAL_MODE", "paper")
    monkeypatch.setenv("LIVE_TRADING", "false")
    monkeypatch.setenv("AUTO_EXECUTE_ORDERS", "true")
    monkeypatch.setenv("EXECUTE_ON_DEMO", "true")

    import api.config as api_config
    import api.database as database

    importlib.reload(api_config)
    importlib.reload(database)
    database.init_db()

    import shared.execution_policy as ep

    importlib.reload(ep)

    from fastapi.testclient import TestClient
    import api.main as main_mod

    importlib.reload(main_mod)
    return TestClient(main_mod.app)


def test_should_execute_demo_paper_mt5_when_is_demo_unknown():
    env = _env()
    ok, reason = should_execute_orders(
        operating_mode=OperatingMode.PAPER_MT5,
        engine_paused=False,
        is_demo=None,
        env=env,
    )
    assert ok is True
    assert reason is None


def test_manual_mt5_without_auto_execute():
    from shared.execution_policy import should_send_manual_order_to_mt5

    env = _env(auto_execute_orders=False)
    ok, reason = should_send_manual_order_to_mt5(
        operating_mode=OperatingMode.PAPER_MT5,
        engine_paused=False,
        is_demo=True,
        env=env,
    )
    assert ok is True
    assert reason is None

    ok2, reason2 = should_execute_orders(
        operating_mode=OperatingMode.PAPER_MT5,
        is_demo=True,
        env=env,
    )
    assert ok2 is False
    assert "AUTO_EXECUTE" in (reason2 or "")


def test_execution_status_endpoint(api_client):
    res = api_client.get("/system/execution-status")
    assert res.status_code == 200
    data = res.json()
    assert "can_send_orders" in data
    assert data["can_execute"] == data["can_send_orders"]
    assert "blockers" in data
    assert "structured_blockers" in data
    assert isinstance(data["blockers"], list)
    assert len(data["steps"]) >= 5
    assert data["live_trading"] is False
    assert "ENGINE_MODE=paper_mt5" in data["env_snippet_paper_demo"]
    assert "mt5_terminal" in data


def test_execution_status_mt5_terminal_mock(api_client, monkeypatch):
    class _Info:
        trade_allowed = True
        connected = True
        tradeapi_disabled = False
        company = "Clear Corretora"
        name = "MetaTrader 5"

    def _fake_collect(**kwargs):
        return {
            "available": True,
            "error": None,
            "trade_allowed": True,
            "connected": True,
            "tradeapi_disabled": False,
            "company": "Clear Corretora",
            "name": "MetaTrader 5",
            "checklist": [
                {
                    "id": "trade_allowed",
                    "label": "Permitir algotrading",
                    "done": True,
                    "blocked": False,
                    "message": "",
                }
            ],
        }

    monkeypatch.setattr(
        "api.execution_status.collect_mt5_terminal_diagnostics",
        _fake_collect,
    )
    res = api_client.get("/system/execution-status")
    assert res.status_code == 200
    term = res.json().get("mt5_terminal")
    assert term is not None
    assert term["available"] is True
    assert term["trade_allowed"] is True
    assert len(term["checklist"]) >= 1


def test_execution_status_mt5_terminal_blocked(api_client, monkeypatch):
    def _fake_collect(**kwargs):
        return {
            "available": True,
            "error": None,
            "trade_allowed": False,
            "connected": True,
            "tradeapi_disabled": True,
            "company": "Clear",
            "name": "MT5",
            "checklist": [
                {
                    "id": "trade_allowed",
                    "label": "Permitir algotrading",
                    "done": False,
                    "blocked": True,
                    "message": "Marque Permitir algotrading",
                }
            ],
        }

    monkeypatch.setattr(
        "api.execution_status.collect_mt5_terminal_diagnostics",
        _fake_collect,
    )
    res = api_client.get("/system/execution-status")
    data = res.json()
    assert data["can_send_orders"] is False
    assert any("Permitir algotrading" in b for b in data["blockers"])
