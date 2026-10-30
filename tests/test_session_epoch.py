"""Epoch de sessão — KPIs filtrados."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from api.database import SignalRow
from api.session_epoch import row_in_metrics_session, set_session_epoch
from shared.schemas import SignalSide, SignalStatus


def test_row_in_metrics_respects_epoch(tmp_path, monkeypatch):
    from datetime import datetime, timedelta

    data_dir = tmp_path / "data"
    data_dir.mkdir()
    monkeypatch.setattr("api.session_epoch._EPOCH_FILE", data_dir / "sala_sinais_session_epoch.json")

    old = SignalRow(
        symbol="PETR4",
        side=SignalSide.BUY.value,
        entry=50.0,
        stop=49.0,
        target=55.0,
        contracts=100,
        strategy_id="demo",
        mode="paper",
        status=SignalStatus.CLOSED.value,
        created_at="2026-10-28T10:00:00-03:00",
    )
    assert row_in_metrics_session(old) is True
    epoch = set_session_epoch(reason="test")
    assert row_in_metrics_session(old, epoch_at=epoch) is False
    after = datetime.fromisoformat(epoch) + timedelta(seconds=2)
    new = SignalRow(
        symbol="VALE3",
        side=SignalSide.BUY.value,
        entry=60.0,
        stop=59.0,
        target=65.0,
        contracts=100,
        strategy_id="demo",
        mode="paper",
        status=SignalStatus.CLOSED.value,
        created_at=after.isoformat(),
    )
    assert row_in_metrics_session(new, epoch_at=epoch) is True


@pytest.fixture()
def api_client(tmp_path, monkeypatch):
    db_file = tmp_path / "epoch.db"
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_file.as_posix()}")
    monkeypatch.setattr("api.session_epoch._EPOCH_FILE", data_dir / "sala_sinais_session_epoch.json")

    import api.config as api_config
    import api.database as database

    importlib.reload(api_config)
    importlib.reload(database)
    database.init_db()

    from fastapi.testclient import TestClient
    import api.main as main_mod

    importlib.reload(main_mod)
    return TestClient(main_mod.app)


def test_reset_session_endpoint(api_client):
    from datetime import datetime
    from zoneinfo import ZoneInfo

    from api.database import SessionLocal, SignalRow

    today = datetime.now(ZoneInfo("America/Sao_Paulo")).date().isoformat()
    ts_old = f"{today}T09:00:00-03:00"
    ts_close = f"{today}T10:00:00-03:00"

    db = SessionLocal()
    try:
        db.add(
            SignalRow(
                symbol="PETR4",
                side=SignalSide.BUY.value,
                entry=50.0,
                stop=49.0,
                target=55.0,
                contracts=100,
                strategy_id="demo_old",
                mode="paper",
                status=SignalStatus.CLOSED.value,
                exit_price=51.0,
                gross_pnl_brl=100.0,
                net_pnl_brl=90.0,
                created_at=ts_old,
                closed_at=ts_close,
            )
        )
        db.commit()
    finally:
        db.close()

    before = api_client.get("/metrics/pnl").json()
    assert before["daily"]["closed_trades"] >= 1

    res = api_client.post("/system/reset-session")
    assert res.status_code == 200
    assert res.json()["ok"] is True

    after = api_client.get("/metrics/pnl").json()
    assert after["daily"]["closed_trades"] == 0
    assert after["today_net"] == 0


def test_reset_session_preserves_library_progress(api_client, tmp_path, monkeypatch):
    progress_file = tmp_path / "data" / "agent_library_progress.json"
    progress_file.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "read_article_ids": ["01-o-que-e-day-trade"],
        "operational_maturity_pct": 42.0,
        "closed_trades_count": 3,
    }
    progress_file.write_text(__import__("json").dumps(payload), encoding="utf-8")
    monkeypatch.setattr("api.agent_library_study._PROGRESS_FILE", progress_file)

    res = api_client.post("/system/reset-session")
    assert res.status_code == 200

    loaded = __import__("json").loads(progress_file.read_text(encoding="utf-8"))
    assert loaded["read_article_ids"] == payload["read_article_ids"]
    assert loaded["operational_maturity_pct"] == payload["operational_maturity_pct"]
