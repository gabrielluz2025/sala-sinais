"""Curva de patrimônio — GET /metrics/equity-curve."""

from __future__ import annotations

import importlib
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from api.database import AgentConfigRow, SignalRow
from api.equity_curve import build_equity_curve
from shared.schemas import SignalSide

TZ_BR = ZoneInfo("America/Sao_Paulo")


def _signal(
    *,
    id: int,
    net: float,
    closed_at: str,
    exit_price: float = 100.0,
) -> SignalRow:
    return SignalRow(
        id=id,
        symbol="PETR4",
        side=SignalSide.BUY.value,
        entry=30.0,
        stop=29.0,
        target=31.0,
        contracts=100,
        strategy_id="t",
        mode="paper",
        status="closed",
        created_at=closed_at,
        exit_price=exit_price,
        closed_at=closed_at,
        gross_pnl_brl=net + 5.0,
        net_pnl_brl=net,
    )


def test_build_equity_curve_no_closed_trades():
    capital = 10000.0
    now = datetime(2026, 3, 15, 12, 0, tzinfo=TZ_BR)
    out = build_equity_curve([], capital, now=now)
    assert out["message"]
    assert len(out["points"]) == 1
    assert out["points"][0]["equity_brl"] == capital
    assert out["points"][0]["date"] == "2026-03-15"
    assert out["summary"]["change_pct"] == 0.0


def test_build_equity_curve_daily_aggregation():
    capital = 10000.0
    rows = [
        _signal(id=1, net=100.0, closed_at="2026-01-10T10:00:00"),
        _signal(id=2, net=-40.0, closed_at="2026-01-10T15:00:00"),
        _signal(id=3, net=50.0, closed_at="2026-01-12T11:00:00"),
    ]
    out = build_equity_curve(rows, capital)
    assert len(out["points"]) == 2
    assert out["points"][0]["daily_pnl_net"] == 60.0
    assert out["points"][0]["equity_brl"] == 10060.0
    assert out["points"][1]["cumulative_pnl_net"] == 110.0
    assert out["summary"]["current_equity_brl"] == 10110.0
    assert out["summary"]["change_pct"] == 1.1


def test_metrics_equity_curve_endpoint(tmp_path, monkeypatch):
    db_file = tmp_path / "eq.db"
    conn = sqlite3.connect(db_file)
    conn.executescript(
        """
        CREATE TABLE signals (
            id INTEGER PRIMARY KEY,
            symbol VARCHAR(32), side VARCHAR(8), entry FLOAT, stop FLOAT, target FLOAT,
            contracts INTEGER, strategy_id VARCHAR(64), mode VARCHAR(16), status VARCHAR(16),
            note TEXT, execution_message TEXT, created_at VARCHAR(32),
            exit_price FLOAT, closed_at VARCHAR(32), outcome VARCHAR(16),
            gross_pnl_brl FLOAT, net_pnl_brl FLOAT,
            strategy_type VARCHAR(16), strategy_version VARCHAR(16),
            entry_reason TEXT, exit_reason TEXT, regime VARCHAR(32)
        );
        CREATE TABLE agent_config (
            id INTEGER PRIMARY KEY, symbols_json TEXT, active_symbol VARCHAR(16),
            rotate_symbols BOOLEAN, capital_brl FLOAT, risk_per_trade_pct FLOAT,
            max_position_brl FLOAT, shares_per_order INTEGER, stop_loss_pct FLOAT,
            take_profit_pct FLOAT, stop_points INTEGER, target_points INTEGER,
            asset_class VARCHAR(16), strategy_type VARCHAR(16), use_news_filter BOOLEAN,
            applied_preset VARCHAR(32), updated_at VARCHAR(32)
        );
        CREATE TABLE system_state (
            id INTEGER PRIMARY KEY, engine_paused BOOLEAN, emergency_flatten BOOLEAN,
            last_heartbeat VARCHAR(32), mode VARCHAR(16), updated_at VARCHAR(32),
            account_login INTEGER, is_demo BOOLEAN, account_server VARCHAR(64),
            data_source VARCHAR(32), mt5_connected BOOLEAN, operating_mode VARCHAR(32)
        );
        INSERT INTO agent_config VALUES (
            1, '["PETR4"]', 'PETR4', 0, 5000.0, 1.0, 2000.0, 100, 2.0, 3.0, 80, 120,
            'acoes', 'volatility', 1, 'moderado', '2026-01-01T00:00:00'
        );
        INSERT INTO system_state VALUES (
            1, 0, 0, NULL, 'paper', '2026-01-01T00:00:00',
            NULL, NULL, NULL, NULL, NULL, NULL
        );
        INSERT INTO signals VALUES (
            1, 'PETR4', 'BUY', 30, 29, 31, 100, 's1', 'paper', 'closed', NULL, NULL,
            '2026-02-01T09:00:00', 30.5, '2026-02-01T16:00:00', 'win', 55.0, 50.0,
            NULL, NULL, NULL, NULL, NULL
        );
        """
    )
    conn.commit()
    conn.close()

    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_file.as_posix()}")

    import api.config as api_config

    importlib.reload(api_config)
    import api.database as database

    importlib.reload(database)
    database.init_db()

    from fastapi.testclient import TestClient

    import api.main as main_mod

    importlib.reload(main_mod)
    client = TestClient(main_mod.app)
    res = client.get("/metrics/equity-curve")
    assert res.status_code == 200
    body = res.json()
    assert body["initial_capital_brl"] == 5000.0
    assert body["points"]
    assert body["summary"]["current_equity_brl"] == 5050.0
