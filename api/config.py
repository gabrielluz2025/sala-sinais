import os
from pathlib import Path
from typing import Self

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_ROOT = Path(__file__).resolve().parents[1]

_DEFAULT_SQLITE = "sqlite+aiosqlite:///./data/sala_sinais.db"


def _env_defines_database_url() -> bool:
    if os.environ.get("DATABASE_URL", "").strip():
        return True
    env_file = _ROOT / ".env"
    if not env_file.is_file():
        return False
    for line in env_file.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        if s.split("=", 1)[0].strip() == "DATABASE_URL":
            return True
    return False


def normalize_database_url(url: str) -> str:
    """Normaliza URI para SQLAlchemy síncrono (API usa create_engine sync)."""
    url = (url or "").strip()
    if not url:
        return _DEFAULT_SQLITE
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://") :]
    scheme, _, rest = url.partition("://")
    if scheme == "postgresql" and "+" not in scheme:
        url = f"postgresql+psycopg://{rest}"
    if url.startswith("postgresql+asyncpg://"):
        url = url.replace("postgresql+asyncpg://", "postgresql+psycopg://", 1)
    return url


class ApiSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    api_host: str = "127.0.0.1"
    api_port: int = 8000
    database_url: str = _DEFAULT_SQLITE
    """SQLite local por padrão. Postgres (Supabase): Settings → Database → URI no .env."""
    supabase_db_url: str = ""
    """Alias opcional: SUPABASE_DB_URL — usado se DATABASE_URL não estiver definido."""
    webhook_secret: str = "change-me-to-a-long-random-string"
    cors_origins: str = "http://127.0.0.1:5500,http://localhost:5173,http://127.0.0.1:8080"

    b3_fee_per_contract_round: float = 0.28
    broker_fee_per_contract: float = 0.0
    day_trade_ir_rate: float = 0.20
    equity_emolument_pct: float = 0.0003
    news_cache_sec: int = 600
    library_auto_ingest_hours: float = 0
    library_news_rss_urls: str = ""
    finnhub_api_key: str = ""
    newsapi_key: str = ""
    auto_learn_from_trades: bool = True
    agent_auto_study_library: bool = True
    agent_study_interval_sec: int = 300
    overnight_learning: bool = False

    @model_validator(mode="after")
    def resolve_database_url(self) -> Self:
        sup = (self.supabase_db_url or "").strip()
        if sup and not _env_defines_database_url():
            resolved = sup
        else:
            resolved = self.database_url
        object.__setattr__(self, "database_url", normalize_database_url(resolved))
        return self

    @property
    def sqlalchemy_sync_url(self) -> str:
        u = self.database_url
        if u.startswith("sqlite+aiosqlite"):
            return u.replace("sqlite+aiosqlite", "sqlite", 1)
        return u

    @property
    def uses_postgres(self) -> bool:
        return self.database_url.startswith("postgresql")

    @property
    def agent_study_background_enabled(self) -> bool:
        """Loop na API (24h enquanto a API estiver no ar; independente de pregão e live)."""
        return self.agent_auto_study_library

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = ApiSettings()
