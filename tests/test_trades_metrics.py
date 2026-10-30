"""GET /metrics/trades e resumo por ativo."""

from __future__ import annotations

import importlib
import sqlite3
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from api.trades_metrics import build_trade_summaries, filter_trade_rows, row_to_trade_dict
from api.database import SignalRow
from shared.schemas import SignalSide


def _closed_row(**kw) -> SignalRow:
    base = {
        "id": 1,
        "symbol": "PETR4",
        "side": SignalSide.BUY.value,
        "entry": 30.0,
        "stop": 29.0,
        "target": 31.0,
        "contracts": 100,
        "strategy_id": "t",
        "mode": "paper",
        "status": "closed",
        "note": None,
        "execution_message": None,
        "created_at": "2026-03-01T10:00:00",
        "exit_price": 30.5,
        "closed_at": "2026-03-01T16:00:00",
        "outcome": "win",
        "gross_pnl_brl": 55.0,
        "net_pnl_brl": 50.0,
        "strategy_type": "volatility",
        "strategy_version": "1",
        "entry_reason": "teste",
        "exit_reason": "alvo",
        "regime": None,
    }
    base.update(kw)
    return SignalRow(**base)


def test_row_to_trade_dict_win_flag():
    item = row_to_trade_dict(_closed_row())
    assert item is not None
    assert item["win"] is True
    assert item["exit"] == 30.5
    assert item["shares"] == 100


def test_build_trade_summaries_by_symbol():
    trades = [
        {"symbol": "PETR4", "net_pnl": 50.0, "win": True},
        {"symbol": "PETR4", "net_pnl": -20.0, "win": False},
        {"symbol": "VALE3", "net_pnl": 10.0, "win": True},
    ]
    global_s, by_sym = build_trade_summaries(trades)
    assert global_s["wins"] == 2
    assert global_s["losses"] == 1
    assert global_s["net_pnl_brl"] == 40.0
    assert global_s["best_trade_net"] == 50.0
    assert global_s["worst_trade_net"] == -20.0
    petr = next(x for x in by_sym if x["symbol"] == "PETR4")
    assert petr["trades"] == 2
    assert petr["win_rate"] == 50.0


def test_metrics_trades_endpoint(tmp_path, monkeypatch):
    db_file = tmp_path / "trades.db"
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
            'volatility', '1', 'entrada', 'alvo', NULL
        );
        INSERT INTO signals VALUES (
            2, 'VALE3', 'SELL', 60, 61, 58, 100, 's1', 'paper', 'pending', NULL, NULL,
            '2026-02-02T09:00:00', NULL, NULL, NULL, NULL, NULL,
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

    res = client.get("/metrics/trades")
    assert res.status_code == 200
    data = res.json()
    assert len(data["trades"]) == 1
    assert data["trades"][0]["symbol"] == "PETR4"
    assert data["global_summary"]["wins"] == 1
    assert data["by_symbol"][0]["net_pnl_brl"] == 50.0

    res2 = client.get("/metrics/trades/summary")
    assert res2.status_code == 200
    assert res2.json()["global_summary"]["trades"] == 1


def test_filter_today_only():
    rows = [
        _closed_row(id=1, closed_at="2026-03-15T12:00:00"),
        _closed_row(id=2, symbol="VALE3", closed_at="2026-03-10T12:00:00"),
    ]
    out = filter_trade_rows(rows, symbol=None, today_only=True, today="2026-03-15")
    assert len(out) == 1
    assert out[0].id == 1
