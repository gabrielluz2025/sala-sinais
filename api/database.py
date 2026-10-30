from pathlib import Path

from sqlalchemy import String, Text, Boolean, Float, create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

from api.config import settings

_ROOT = Path(__file__).resolve().parents[1]
if settings.database_url.startswith("sqlite"):
    db_path = _ROOT / "data"
    db_path.mkdir(parents=True, exist_ok=True)

_sync_url = settings.database_url.replace("sqlite+aiosqlite", "sqlite")
engine = create_engine(_sync_url, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


class SignalRow(Base):
    __tablename__ = "signals"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(32))
    side: Mapped[str] = mapped_column(String(8))
    entry: Mapped[float]
    stop: Mapped[float]
    target: Mapped[float]
    contracts: Mapped[int]
    strategy_id: Mapped[str] = mapped_column(String(64))
    mode: Mapped[str] = mapped_column(String(16))
    status: Mapped[str] = mapped_column(String(16), default="pending")
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    execution_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[str] = mapped_column(String(32))
    exit_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    closed_at: Mapped[str | None] = mapped_column(String(32), nullable=True)
    outcome: Mapped[str | None] = mapped_column(String(16), nullable=True)
    gross_pnl_brl: Mapped[float | None] = mapped_column(Float, nullable=True)
    net_pnl_brl: Mapped[float | None] = mapped_column(Float, nullable=True)
    strategy_type: Mapped[str | None] = mapped_column(String(16), nullable=True)
    strategy_version: Mapped[str | None] = mapped_column(String(16), nullable=True)
    entry_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    exit_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    regime: Mapped[str | None] = mapped_column(String(32), nullable=True)


class AgentConfigRow(Base):
    __tablename__ = "agent_config"

    id: Mapped[int] = mapped_column(primary_key=True)
    symbols_json: Mapped[str] = mapped_column(Text, default='["PETR4","VALE3"]')
    active_symbol: Mapped[str | None] = mapped_column(String(16), nullable=True)
    rotate_symbols: Mapped[bool] = mapped_column(Boolean, default=False)
    capital_brl: Mapped[float] = mapped_column(Float, default=10000.0)
    risk_per_trade_pct: Mapped[float] = mapped_column(Float, default=1.0)
    max_position_brl: Mapped[float] = mapped_column(Float, default=2000.0)
    shares_per_order: Mapped[int] = mapped_column(default=100)
    stop_loss_pct: Mapped[float] = mapped_column(Float, default=2.0)
    take_profit_pct: Mapped[float] = mapped_column(Float, default=3.0)
    stop_points: Mapped[int] = mapped_column(default=80)
    target_points: Mapped[int] = mapped_column(default=120)
    asset_class: Mapped[str] = mapped_column(String(16), default="acoes")
    strategy_type: Mapped[str] = mapped_column(String(16), default="volatility")
    use_news_filter: Mapped[bool] = mapped_column(Boolean, default=True)
    applied_preset: Mapped[str | None] = mapped_column(String(32), nullable=True)
    updated_at: Mapped[str] = mapped_column(String(32))


class SystemStateRow(Base):
    __tablename__ = "system_state"

    id: Mapped[int] = mapped_column(primary_key=True)
    engine_paused: Mapped[bool] = mapped_column(Boolean, default=False)
    emergency_flatten: Mapped[bool] = mapped_column(Boolean, default=False)
    last_heartbeat: Mapped[str | None] = mapped_column(String(32), nullable=True)
    mode: Mapped[str] = mapped_column(String(16), default="paper")
    updated_at: Mapped[str] = mapped_column(String(32))
    account_login: Mapped[int | None] = mapped_column(nullable=True)
    is_demo: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    account_server: Mapped[str | None] = mapped_column(String(128), nullable=True)
    data_source: Mapped[str | None] = mapped_column(String(32), nullable=True)
    mt5_connected: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    operating_mode: Mapped[str | None] = mapped_column(String(32), nullable=True)


_SIGNAL_EXTRA_COLUMNS: dict[str, str] = {
    "exit_price": "FLOAT",
    "closed_at": "VARCHAR(32)",
    "outcome": "VARCHAR(16)",
    "gross_pnl_brl": "FLOAT",
    "net_pnl_brl": "FLOAT",
    "strategy_type": "VARCHAR(16)",
    "strategy_version": "VARCHAR(16)",
    "entry_reason": "TEXT",
    "exit_reason": "TEXT",
    "regime": "VARCHAR(32)",
}


def _migrate_signals_columns() -> None:
    insp = inspect(engine)
    if "signals" not in insp.get_table_names():
        return
    existing = {c["name"] for c in insp.get_columns("signals")}
    with engine.begin() as conn:
        for name, sql_type in _SIGNAL_EXTRA_COLUMNS.items():
            if name not in existing:
                conn.execute(text(f"ALTER TABLE signals ADD COLUMN {name} {sql_type}"))


_STATE_EXTRA_COLUMNS: dict[str, str] = {
    "account_login": "INTEGER",
    "is_demo": "BOOLEAN",
    "account_server": "VARCHAR(128)",
    "data_source": "VARCHAR(32)",
    "mt5_connected": "BOOLEAN",
    "operating_mode": "VARCHAR(32)",
}


_AGENT_CONFIG_EXTRA_COLUMNS: dict[str, str] = {
    "strategy_type": "VARCHAR(16)",
    "use_news_filter": "BOOLEAN",
    "applied_preset": "VARCHAR(32)",
}


def _migrate_agent_config_columns() -> None:
    insp = inspect(engine)
    if "agent_config" not in insp.get_table_names():
        return
    existing = {c["name"] for c in insp.get_columns("agent_config")}
    with engine.begin() as conn:
        for name, sql_type in _AGENT_CONFIG_EXTRA_COLUMNS.items():
            if name not in existing:
                conn.execute(text(f"ALTER TABLE agent_config ADD COLUMN {name} {sql_type}"))


def _migrate_system_state_columns() -> None:
    insp = inspect(engine)
    if "system_state" not in insp.get_table_names():
        return
    existing = {c["name"] for c in insp.get_columns("system_state")}
    with engine.begin() as conn:
        for name, sql_type in _STATE_EXTRA_COLUMNS.items():
            if name not in existing:
                conn.execute(text(f"ALTER TABLE system_state ADD COLUMN {name} {sql_type}"))


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
    _migrate_signals_columns()
    _migrate_system_state_columns()
    _migrate_agent_config_columns()
