"""Migração SQLite e imports básicos."""

from __future__ import annotations

import importlib
import sqlite3
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def test_init_db_adds_strategy_columns_on_existing_sqlite(tmp_path, monkeypatch):
    db_file = tmp_path / "legacy.db"
    conn = sqlite3.connect(db_file)
    conn.execute(
        """
        CREATE TABLE signals (
            id INTEGER PRIMARY KEY,
            symbol VARCHAR(32),
            side VARCHAR(8),
            entry FLOAT,
            stop FLOAT,
            target FLOAT,
            contracts INTEGER,
            strategy_id VARCHAR(64),
            mode VARCHAR(16),
            status VARCHAR(16),
            note TEXT,
            execution_message TEXT,
            created_at VARCHAR(32)
        )
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

    conn = sqlite3.connect(db_file)
    cols = {row[1] for row in conn.execute("PRAGMA table_info(signals)")}
    conn.close()

    for name in (
        "strategy_type",
        "strategy_version",
        "entry_reason",
        "exit_reason",
        "regime",
        "exit_price",
        "closed_at",
    ):
        assert name in cols


def test_core_imports():
    import api.library
    import api.main
    import engine.sim_close
    import engine.strategy
    import engine.strategy_volatility

    assert api.library.get_library_index().articles
