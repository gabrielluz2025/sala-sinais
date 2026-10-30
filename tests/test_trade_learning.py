"""Testes de agregação e faixas horárias do aprendizado com trades."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from shared.trade_learning import (
    aggregate_by_strategy,
    compute_performance_learning,
    compute_soft_guards,
    enrich_closed_trade,
    expectancy,
    generate_insights_pt,
    rolling_last_n,
    session_hour_bucket,
    session_hour_bucket_label,
    trade_duration_minutes,
)

TZ_BR = ZoneInfo("America/Sao_Paulo")


def _trade(**kw):
    base = {
        "symbol": "PETR4",
        "side": "BUY",
        "net_pnl": 10.0,
        "win": True,
        "strategy_type": "breakout",
        "entry_reason": "rompimento",
        "opened_at": datetime(2026, 3, 2, 10, 15, tzinfo=TZ_BR),
        "closed_at": datetime(2026, 3, 2, 11, 0, tzinfo=TZ_BR),
    }
    base.update(kw)
    return enrich_closed_trade(base)


def test_session_hour_bucket_pregao_slices():
    assert session_hour_bucket(datetime(2026, 3, 2, 9, 30, tzinfo=TZ_BR)) == "pre_10"
    assert session_hour_bucket(datetime(2026, 3, 2, 10, 30, tzinfo=TZ_BR)) == "10_12"
    assert session_hour_bucket(datetime(2026, 3, 2, 13, 0, tzinfo=TZ_BR)) == "12_14"
    assert session_hour_bucket(datetime(2026, 3, 2, 15, 30, tzinfo=TZ_BR)) == "14_16"
    assert session_hour_bucket(datetime(2026, 3, 2, 16, 45, tzinfo=TZ_BR)) == "16_17"
    assert session_hour_bucket(datetime(2026, 3, 2, 18, 0, tzinfo=TZ_BR)) == "pos_17"
    assert "10h" in session_hour_bucket_label("10_12")


def test_trade_duration_and_enrich():
    raw = {
        "symbol": "VALE3",
        "side": "SELL",
        "net_pnl": -5.0,
        "win": False,
        "strategy_type": "volatility",
        "entry_reason": "teste",
        "opened_at": datetime(2026, 3, 2, 14, 0, tzinfo=TZ_BR),
        "closed_at": datetime(2026, 3, 2, 14, 45, tzinfo=TZ_BR),
    }
    t = enrich_closed_trade(raw)
    assert t["session_hour_bucket"] == "14_16"
    assert t["duration_minutes"] == 45.0
    assert trade_duration_minutes(t["opened_at"], t["closed_at"]) == 45.0


def test_aggregates_win_rate_and_expectancy():
    trades = [
        _trade(net_pnl=20.0, win=True),
        _trade(net_pnl=-10.0, win=False, strategy_type="breakout"),
        _trade(net_pnl=15.0, win=True, strategy_type="volatility"),
    ]
    by_st = aggregate_by_strategy(trades)
    assert by_st["breakout"]["trades"] == 2
    assert by_st["breakout"]["win_rate_pct"] == 50.0
    exp = expectancy(20.0, -10.0, 50.0)
    assert exp == 5.0
    perf = compute_performance_learning(trades, rolling_n=3)
    assert perf["global"]["trades"] == 3
    rolling = rolling_last_n(trades, 3)
    assert rolling["loss_streak"] == 0


def test_soft_guards_after_loss_streak():
    trades = [
        _trade(net_pnl=-1.0, win=False),
        _trade(net_pnl=-2.0, win=False),
        _trade(net_pnl=-3.0, win=False),
    ]
    perf = compute_performance_learning(trades, rolling_n=3)
    guards = compute_soft_guards(perf, "breakout", base_cooldown_sec=60)
    assert guards["active"] is True
    assert guards["cooldown_sec"] == 120
    assert guards["skip_weak_signals"] is True
    insights = generate_insights_pt(perf)
    assert any("perdas" in i.lower() for i in insights)


def test_learning_stats_endpoint(tmp_path, monkeypatch):
    import importlib
    import sqlite3
    import sys
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    db_file = tmp_path / "learn.db"
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
            'acoes', 'breakout', 1, 'moderado', '2026-01-01T00:00:00'
        );
        INSERT INTO system_state VALUES (
            1, 0, 0, NULL, 'paper', '2026-01-01T00:00:00',
            NULL, NULL, NULL, NULL, NULL, NULL
        );
        INSERT INTO signals VALUES (
            1, 'PETR4', 'BUY', 30, 29, 31, 100, 's1', 'paper', 'closed', NULL, NULL,
            '2026-03-02T10:00:00', 30.5, '2026-03-02T11:00:00', 'win', 55.0, 50.0,
            'breakout', '1', 'entrada', 'alvo', NULL
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

    res = client.get("/agent/learning-stats")
    assert res.status_code == 200
    body = res.json()
    assert body["performance_learning"]["trade_count"] == 1
    assert body["insights_pt"]

    res2 = client.get("/library/learning-insights")
    assert res2.status_code == 200
    assert res2.json().get("last_insight")
