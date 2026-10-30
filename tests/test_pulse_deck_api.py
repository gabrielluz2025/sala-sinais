"""Pulse Deck Pro — tickers-summary, orders/execute, system/flatten."""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from shared.execution_policy import ExecutionEnvSettings, can_submit_manual_order
from shared.schemas import OperatingMode, SignalSide, SignalStatus


def test_can_submit_manual_order_simulation():
    ok, reason = can_submit_manual_order(
        operating_mode=OperatingMode.SIMULATION,
        engine_paused=False,
        is_demo=True,
        env=ExecutionEnvSettings(),
    )
    assert ok is True
    assert reason is None


def test_can_submit_manual_order_blocks_live_without_policy():
    env = ExecutionEnvSettings(
        signal_mode="paper",
        live_trading=False,
        engine_mode="live_mt5",
    )
    ok, reason = can_submit_manual_order(
        operating_mode=OperatingMode.LIVE_MT5,
        engine_paused=False,
        is_demo=False,
        env=env,
    )
    assert ok is False
    assert reason


@pytest.fixture()
def api_client(tmp_path, monkeypatch):
    db_file = tmp_path / "pulse_deck.db"
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    history = [
        {
            "symbol": "PETR4",
            "bid": 50.0,
            "ask": 50.02,
            "timestamp": "2026-10-29T10:00:00-03:00",
            "source": "test",
        },
        {
            "symbol": "PETR4",
            "bid": 52.0,
            "ask": 52.02,
            "timestamp": "2026-10-29T15:00:00-03:00",
            "source": "test",
        },
        {
            "symbol": "VALE3",
            "bid": 60.0,
            "ask": 60.05,
            "timestamp": "2026-10-29T15:00:00-03:00",
            "source": "test",
        },
    ]
    (data_dir / "quote_history.json").write_text(json.dumps(history), encoding="utf-8")
    (data_dir / "last_quote.json").write_text(
        json.dumps(
            {
                "symbol": "WIN$",
                "bid": 129000,
                "ask": 129005,
                "timestamp": "2026-10-29T15:00:00-03:00",
                "source": "test",
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_file.as_posix()}")
    monkeypatch.setenv("ENGINE_MODE", "simulation")
    monkeypatch.setenv("SIGNAL_MODE", "paper")

    import api.config as api_config
    import api.database as database
    import api.market_tickers_summary as mts
    import api.pnl as pnl_mod

    importlib.reload(api_config)
    importlib.reload(database)
    database.init_db()

    monkeypatch.setattr(mts, "_ROOT", tmp_path)
    monkeypatch.setattr(mts, "_QUOTE_HISTORY_FILE", data_dir / "quote_history.json")
    monkeypatch.setattr(mts, "_QUOTE_FILE", data_dir / "last_quote.json")
    monkeypatch.setattr(mts, "_try_mt5_quote", lambda _sym: None)
    monkeypatch.setattr(pnl_mod, "_ROOT", tmp_path)
    monkeypatch.setattr(pnl_mod, "_QUOTE_HISTORY_FILE", data_dir / "quote_history.json")
    monkeypatch.setattr(pnl_mod, "_QUOTE_FILE", data_dir / "last_quote.json")

    import shared.execution_policy as ep

    importlib.reload(ep)

    from fastapi.testclient import TestClient
    import api.main as main_mod

    importlib.reload(main_mod)
    return TestClient(main_mod.app)


def test_favicon_from_cockpit_dist(api_client):
    res = api_client.get("/favicon.ico")
    if (_ROOT / "cockpit" / "dist" / "favicon.ico").is_file():
        assert res.status_code == 200
        assert res.headers.get("content-type", "").startswith("image/")
    else:
        assert res.status_code == 404


def test_market_tickers_summary(api_client):
    res = api_client.get("/market/tickers-summary")
    assert res.status_code == 200
    data = res.json()
    assert len(data["tickers"]) == 7
    by_sym = {t["symbol"]: t for t in data["tickers"]}
    assert by_sym["PETR4"]["available"] is True
    assert by_sym["PETR4"]["mid"] == pytest.approx(52.01, rel=1e-3)
    assert by_sym["PETR4"]["change_pct"] is not None
    assert by_sym["WIN$"]["available"] is True
    assert "available" in by_sym["IBOV"]


def test_orders_execute_quantity_alias(api_client, monkeypatch):
    class _FixedRisk:
        def can_trade(self, now=None, enforce_session_hours=True):
            return True, "ok"

        def clamp_contracts(self, requested: int) -> int:
            return requested

    monkeypatch.setattr("api.orders_execute.RiskManager", _FixedRisk)

    state = api_client.get("/system/state").json()
    assert state["engine_paused"] is False

    res = api_client.post(
        "/orders/execute",
        json={"symbol": "PETR4", "side": "BUY", "contracts": 100},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["ok"] is True
    assert body["operating_mode"] == "simulation"
    assert body["signal"]["symbol"] == "PETR4"
    assert body["signal"]["status"] == "sent"
    assert body["signal"]["strategy_id"] == "pulse_deck_manual"
    assert body.get("db_only") is True
    assert body.get("mt5_sent") is False


def test_orders_execute_paper_mt5_calls_mt5(api_client, monkeypatch):
    monkeypatch.setenv("ENGINE_MODE", "paper_mt5")
    monkeypatch.setenv("SIGNAL_MODE", "live")
    monkeypatch.setenv("EXECUTE_ON_DEMO", "true")

    import shared.execution_policy as ep

    importlib.reload(ep)

    from api.database import SessionLocal, SystemStateRow

    db = SessionLocal()
    try:
        st = db.get(SystemStateRow, 1)
        if st:
            st.operating_mode = "paper_mt5"
            st.is_demo = True
            db.commit()
    finally:
        db.close()

    class _FixedRisk:
        def can_trade(self, now=None, enforce_session_hours=True):
            return True, "ok"

        def clamp_contracts(self, requested: int) -> int:
            return requested

    monkeypatch.setattr("api.orders_execute.RiskManager", _FixedRisk)

    calls: list[dict] = []

    def _fake_mt5(payload, **kwargs):
        calls.append({"manual": kwargs.get("manual"), "symbol": payload.symbol})
        return {"ok": True, "message": "Ordem executada ticket=1 deal=2"}

    monkeypatch.setattr("engine.mt5_runtime.execute_signal_on_mt5", _fake_mt5)

    res = api_client.post(
        "/orders/execute",
        json={"symbol": "PETR4", "side": "BUY", "contracts": 100},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["mt5_sent"] is True
    assert body["mt5_ok"] is True
    assert "MT5" in body["message"]
    assert len(calls) == 1
    assert calls[0]["manual"] is True


def test_orders_execute_rejects_live(api_client, monkeypatch):
    monkeypatch.setenv("ENGINE_MODE", "live_mt5")
    monkeypatch.setenv("SIGNAL_MODE", "paper")
    monkeypatch.setenv("LIVE_TRADING", "false")

    import shared.execution_policy as ep

    importlib.reload(ep)

    from api.database import SessionLocal, SystemStateRow

    db = SessionLocal()
    try:
        st = db.get(SystemStateRow, 1)
        if st:
            st.operating_mode = "live_mt5"
            db.commit()
    finally:
        db.close()

    class _FixedRisk:
        def can_trade(self, now=None, enforce_session_hours=True):
            return True, "ok"

        def clamp_contracts(self, requested: int) -> int:
            return requested

    monkeypatch.setattr("api.orders_execute.RiskManager", _FixedRisk)

    res = api_client.post(
        "/orders/execute",
        json={"symbol": "PETR4", "side": "BUY", "contracts": 100},
    )
    assert res.status_code == 403


def test_system_flatten_closes_open_signals(api_client):
    from api.database import SessionLocal, SignalRow

    db = SessionLocal()
    try:
        row = SignalRow(
            symbol="PETR4",
            side=SignalSide.BUY.value,
            entry=50.0,
            stop=49.0,
            target=55.0,
            contracts=100,
            strategy_id="test",
            mode="paper",
            status=SignalStatus.FILLED.value,
            created_at="2026-10-29T12:00:00-03:00",
        )
        db.add(row)
        pending = SignalRow(
            symbol="VALE3",
            side=SignalSide.SELL.value,
            entry=60.0,
            stop=61.0,
            target=58.0,
            contracts=100,
            strategy_id="test",
            mode="paper",
            status=SignalStatus.PENDING.value,
            created_at="2026-10-29T12:01:00-03:00",
        )
        db.add(pending)
        db.commit()
    finally:
        db.close()

    res = api_client.post("/system/flatten")
    assert res.status_code == 200
    payload = res.json()
    assert payload["ok"] is True
    assert payload["positions_closed"] == 1
    assert payload["signals_cancelled"] == 1
    assert payload["emergency_flatten"] is True
    assert payload["engine_paused"] is True

    signals = api_client.get("/signals?limit=10").json()
    filled = next(s for s in signals if s["symbol"] == "PETR4")
    assert filled["status"] == "closed"
    assert filled["exit_price"] is not None
    cancelled = next(s for s in signals if s["symbol"] == "VALE3")
    assert cancelled["status"] == "cancelled"
