from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_ROOT = Path(__file__).resolve().parents[1]


class ApiSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    api_host: str = "127.0.0.1"
    api_port: int = 8000
    database_url: str = "sqlite+aiosqlite:///./data/sala_sinais.db"
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

    @property
    def agent_study_background_enabled(self) -> bool:
        """Loop na API (24h enquanto a API estiver no ar; independente de pregão e live)."""
        return self.agent_auto_study_library

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = ApiSettings()
