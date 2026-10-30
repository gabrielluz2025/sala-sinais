from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

from shared.schemas import OperatingMode

_ROOT = Path(__file__).resolve().parents[1]


class EngineSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    api_base_url: str = "http://127.0.0.1:8000"
    webhook_secret: str = "change-me-to-a-long-random-string"

    mt5_path: str = ""
    mt5_symbol: str = "WIN$"
    mt5_timeframe: str = "M1"

    strategy_id: str = "win_scalp_v1"
    poll_interval_sec: int = 5

    max_contracts: int = 1
    trade_start_hour: int = 10
    trade_end_hour: int = 17
    signal_cooldown_sec: int = 60
    stop_points: int = 80
    target_points: int = 120

    signal_mode: str = "paper"
    live_trading: bool = False
    # Permite LIVE_TRADING=true em conta demo (apenas testes — não use em produção)
    allow_demo_live: bool = False
    auto_execute_orders: bool = True
    execute_on_demo: bool = True
    b3_ignore_session_hours: bool = True
    overnight_learning: bool = False
    overnight_study_interval_sec: int = 300
    agent_auto_study_library: bool = True
    agent_study_interval_sec: int = 300
    auto_learn_from_trades: bool = True

    # Modo de operação: simulation | paper_mt5 | live_mt5 (alias OPERATING_MODE)
    engine_mode: str = ""
    operating_mode: str = ""

    # Simulador (sem MT5)
    sim_signal_interval_sec: int = 120
    sim_base_price: float = 125000.0
    sim_respect_risk_hours: bool = False
    sim_demo_signals: bool = True


settings = EngineSettings()


def resolve_operating_mode() -> OperatingMode:
    """Resolve modo atual; mapeia variáveis legadas se ENGINE_MODE não estiver definido."""
    raw = (settings.engine_mode or settings.operating_mode or "").strip().lower()
    aliases: dict[str, OperatingMode] = {
        "simulation": OperatingMode.SIMULATION,
        "sim": OperatingMode.SIMULATION,
        "paper_mt5": OperatingMode.PAPER_MT5,
        "paper-mt5": OperatingMode.PAPER_MT5,
        "live_mt5": OperatingMode.LIVE_MT5,
        "live-mt5": OperatingMode.LIVE_MT5,
        "live": OperatingMode.LIVE_MT5,
    }
    if raw:
        return aliases.get(raw, OperatingMode.PAPER_MT5)

    if settings.live_trading and settings.signal_mode.lower() == "live":
        return OperatingMode.LIVE_MT5
    return OperatingMode.PAPER_MT5


def effective_live_trading() -> bool:
    """Simulação nunca habilita ordens reais."""
    if resolve_operating_mode() == OperatingMode.SIMULATION:
        return False
    return settings.live_trading
