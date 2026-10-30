from datetime import datetime
from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


class SignalSide(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class SignalMode(str, Enum):
    PAPER = "paper"
    LIVE = "live"


class OperatingMode(str, Enum):
    """Modo de operação do engine (fonte de dados + execução)."""

    SIMULATION = "simulation"
    PAPER_MT5 = "paper_mt5"
    LIVE_MT5 = "live_mt5"


class SignalStatus(str, Enum):
    PENDING = "pending"
    SENT = "sent"
    FILLED = "filled"
    CLOSED = "closed"
    CANCELLED = "cancelled"
    REJECTED = "rejected"


class SignalOutcome(str, Enum):
    WIN = "win"
    LOSS = "loss"
    BREAKEVEN = "breakeven"
    OPEN = "open"


class SignalCreate(BaseModel):
    symbol: str
    side: SignalSide
    entry: float
    stop: float
    target: float
    contracts: int = Field(ge=1, le=100_000)
    strategy_id: str
    mode: SignalMode = SignalMode.PAPER
    note: Optional[str] = None
    strategy_type: Optional[Literal["breakout", "volatility"]] = None
    strategy_version: Optional[str] = None
    entry_reason: Optional[str] = None
    regime: Optional[str] = None


class SignalUpdate(BaseModel):
    status: Optional[SignalStatus] = None
    message: Optional[str] = None
    exit_price: Optional[float] = None
    outcome: Optional[SignalOutcome] = None
    closed_at: Optional[datetime] = None
    exit_reason: Optional[str] = None


class SignalRead(SignalCreate):
    id: int
    status: SignalStatus
    created_at: datetime
    execution_message: Optional[str] = None
    exit_price: Optional[float] = None
    closed_at: Optional[datetime] = None
    outcome: Optional[SignalOutcome] = None
    gross_pnl_brl: Optional[float] = None
    net_pnl_brl: Optional[float] = None
    exit_reason: Optional[str] = None

    model_config = {"from_attributes": True}


class StatsResponse(BaseModel):
    total_signals: int
    today_signals: int
    by_status: dict[str, int]


class SystemStateRead(BaseModel):
    engine_paused: bool
    emergency_flatten: bool
    last_heartbeat: Optional[datetime] = None
    engine_online: bool = False
    mode: str
    updated_at: datetime
    account_login: Optional[int] = None
    is_demo: Optional[bool] = None
    account_server: Optional[str] = None
    data_source: Optional[str] = None
    mt5_connected: Optional[bool] = None
    operating_mode: Optional[str] = None


class ExecutionChecklistStep(BaseModel):
    id: str
    label: str
    done: bool


class ExecutionBlockersStructured(BaseModel):
    """Bloqueios categorizados (além de blockers[] legível)."""

    session_hours: bool = False
    session_hours_message: Optional[str] = None
    mt5_trade_allowed: bool = False
    mt5_trade_allowed_message: Optional[str] = None
    experts_ini_enabled: bool = False
    experts_ini_message: Optional[str] = None


class Mt5TerminalChecklistStep(BaseModel):
    id: str
    label: str
    done: bool
    blocked: bool = False
    message: str = ""


class Mt5TerminalDiagnosticsRead(BaseModel):
    available: bool = False
    error: Optional[str] = None
    trade_allowed: Optional[bool] = None
    connected: Optional[bool] = None
    tradeapi_disabled: Optional[bool] = None
    company: Optional[str] = None
    name: Optional[str] = None
    terminal_executable_dir: Optional[str] = None
    data_path: Optional[str] = None
    checklist: list[Mt5TerminalChecklistStep] = Field(default_factory=list)


class ExecutionStatusRead(BaseModel):
    can_send_orders: bool
    can_execute: bool = False
    engine_online: bool = False
    auto_execute_enabled: bool
    mode: str
    live_trading: bool
    engine_paused: bool
    mt5_connected: Optional[bool] = None
    operating_mode: Optional[str] = None
    auto_execute_orders: bool = True
    execute_on_demo: bool = True
    signal_mode: str = "paper"
    blockers: list[str] = Field(default_factory=list)
    structured_blockers: ExecutionBlockersStructured = Field(
        default_factory=ExecutionBlockersStructured
    )
    steps: list[ExecutionChecklistStep] = Field(default_factory=list)
    env_snippet_paper_demo: str = ""
    recommended_env_note: str = ""
    live_trading_warning: bool = False
    overnight_learning: bool = False
    mt5_path_env: Optional[str] = None
    mt5_path_mismatch: bool = False
    mt5_terminal: Optional[Mt5TerminalDiagnosticsRead] = None


class StrategyType(str, Enum):
    BREAKOUT = "breakout"
    VOLATILITY = "volatility"


class AlertType(str, Enum):
    ENTRY = "entry"
    EXIT = "exit"


class AlertRead(BaseModel):
    id: int
    alert_type: AlertType
    symbol: str
    side: Optional[SignalSide] = None
    price: float
    note: Optional[str] = None
    created_at: datetime
    signal_id: Optional[int] = None
    strategy_type: Optional[Literal["breakout", "volatility"]] = None
    entry_reason: Optional[str] = None
    exit_reason: Optional[str] = None


class AgentPresetSummary(BaseModel):
    id: str
    label: str
    description_pt: str


class AgentPresetsResponse(BaseModel):
    presets: list[AgentPresetSummary]
    recommended_id: str = "moderado"


class AgentTickerItem(BaseModel):
    symbol: str
    name: str


class AgentTickersResponse(BaseModel):
    tickers: list[AgentTickerItem]


class AgentConfigRead(BaseModel):
    symbols: list[str]
    active_symbol: Optional[str] = None
    rotate_symbols: bool = False
    strategy_type: Literal["breakout", "volatility"] = "volatility"
    capital_brl: float
    risk_per_trade_pct: float
    max_position_brl: float
    shares_per_order: int
    stop_loss_pct: float
    take_profit_pct: float
    stop_points: int = 80
    target_points: int = 120
    asset_class: Literal["acoes", "win", "mixed"] = "acoes"
    use_news_filter: bool = True
    applied_preset: Optional[str] = None
    recommended_defaults_active: bool = False
    updated_at: datetime
    presets: list[str] = Field(default_factory=list)


class AgentConfigPatch(BaseModel):
    symbols: Optional[list[str]] = None
    active_symbol: Optional[str] = None
    rotate_symbols: Optional[bool] = None
    capital_brl: Optional[float] = Field(default=None, gt=0)
    risk_per_trade_pct: Optional[float] = Field(default=None, gt=0, le=100)
    max_position_brl: Optional[float] = Field(default=None, gt=0)
    shares_per_order: Optional[int] = Field(default=None, ge=100, le=100000)
    stop_loss_pct: Optional[float] = Field(default=None, gt=0, le=50)
    take_profit_pct: Optional[float] = Field(default=None, gt=0, le=100)
    stop_points: Optional[int] = Field(default=None, ge=1)
    target_points: Optional[int] = Field(default=None, ge=1)
    asset_class: Optional[Literal["acoes", "win", "mixed"]] = None
    strategy_type: Optional[Literal["breakout", "volatility"]] = None
    use_news_filter: Optional[bool] = None

    @field_validator("shares_per_order")
    @classmethod
    def shares_lot_b3(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and v % 100 != 0:
            raise ValueError("shares_per_order deve ser múltiplo de 100 (lote B3)")
        return v


class SystemStatePatch(BaseModel):
    engine_paused: Optional[bool] = None
    emergency_flatten: Optional[bool] = None
    mode: Optional[str] = None


class PnlMetrics(BaseModel):
    period: str
    closed_trades: int
    wins: int
    losses: int
    breakeven_count: int = 0
    win_rate_pct: Optional[float] = None
    gross_pnl_brl: float
    gross_profit_brl: float = 0.0
    gross_loss_brl: float = 0.0
    fees_brl: float
    net_before_tax_brl: float
    estimated_ir_brl: float = 0.0
    net_after_tax_estimated_brl: float
    net_pnl_brl: float


class ClosedTradeSummary(BaseModel):
    id: int
    symbol: str
    side: str
    entry: float
    exit_price: float
    gross_pnl_brl: float
    net_pnl_brl: float
    fees_brl: float
    closed_at: Optional[datetime] = None
    strategy_type: Optional[Literal["breakout", "volatility"]] = None
    entry_reason: Optional[str] = None
    exit_reason: Optional[str] = None


class EquityCurvePoint(BaseModel):
    date: str
    equity_brl: float
    daily_pnl_net: float
    cumulative_pnl_net: float
    drawdown_pct: float


class EquityCurveSummary(BaseModel):
    initial_capital_brl: float
    current_equity_brl: float
    peak_equity_brl: float
    min_equity_brl: float
    change_pct: float
    includes_open_mtm: bool = False


class EquityCurveResponse(BaseModel):
    initial_capital_brl: float
    points: list[EquityCurvePoint]
    summary: EquityCurveSummary
    message: Optional[str] = None


class TradeMetricsItem(BaseModel):
    id: int
    symbol: str
    side: str
    entry: float
    exit: float
    shares: int
    gross_pnl: float
    fees: float
    net_pnl: float
    opened_at: datetime
    closed_at: Optional[datetime] = None
    strategy_type: Optional[Literal["breakout", "volatility"]] = None
    entry_reason: Optional[str] = None
    exit_reason: Optional[str] = None
    win: bool


class TradeSymbolSummary(BaseModel):
    symbol: str
    trades: int
    wins: int
    losses: int
    net_pnl_brl: float
    win_rate: Optional[float] = None


class TradesGlobalSummary(BaseModel):
    trades: int
    wins: int
    losses: int
    net_pnl_brl: float
    best_trade_net: Optional[float] = None
    worst_trade_net: Optional[float] = None


class TradesMetricsResponse(BaseModel):
    trades: list[TradeMetricsItem]
    global_summary: TradesGlobalSummary
    by_symbol: list[TradeSymbolSummary] = Field(default_factory=list)


class TradesSummaryResponse(BaseModel):
    global_summary: TradesGlobalSummary
    by_symbol: list[TradeSymbolSummary] = Field(default_factory=list)


class SessionActivitySummary(BaseModel):
    """Resumo do pregão corrente (sinais criados hoje + PnL fechado/MTM)."""

    buys: int = 0
    sells: int = 0
    volume_shares: int = 0
    closed_net_brl: float = 0.0
    open_mtm_brl: float = 0.0
    fees_open_est_brl: float = 0.0
    estimated_ir_brl: float = 0.0


class PnlMetricsResponse(BaseModel):
    daily: PnlMetrics
    monthly: PnlMetrics
    all_time: PnlMetrics
    gross_profit_brl: float
    gross_loss_brl: float
    net_pnl_brl: float
    today_net: float
    month_net: float
    all_time_net: float
    wins: int
    losses: int
    breakeven_count: int
    open_positions_estimated_pnl: float
    open_positions_count: int = 0
    fees_paid_brl: float
    net_before_tax_brl: float = 0.0
    estimated_ir_brl: float = 0.0
    net_after_tax_estimated_brl: float = 0.0
    recent_closed: list[ClosedTradeSummary] = Field(default_factory=list)
    session_today: SessionActivitySummary = Field(default_factory=SessionActivitySummary)


class MarketMidsResponse(BaseModel):
    mids: dict[str, float] = Field(default_factory=dict)


class MarketQuote(BaseModel):
    symbol: str
    bid: float
    ask: float
    mid: Optional[float] = None
    timestamp: str
    source: str = "engine"


class NewsItem(BaseModel):
    title: str
    link: str
    published: str = ""


class NewsFeedResponse(BaseModel):
    items: list[NewsItem]
    cached: bool
    error: Optional[str] = None


class LibraryCategory(BaseModel):
    id: str
    label: str


class LibraryArticleIndex(BaseModel):
    id: str
    title: str
    category: str
    tags: list[str] = Field(default_factory=list)
    path: str
    updated: str
    source: str = "curated"
    source_url: Optional[str] = None
    disclaimer: Optional[str] = None


class LibraryIndexResponse(BaseModel):
    categories: list[LibraryCategory]
    articles: list[LibraryArticleIndex]


class LibraryArticleResponse(BaseModel):
    id: str
    title: str
    category: str
    tags: list[str] = Field(default_factory=list)
    markdown: str
    updated: str


class LibraryCategoryCount(BaseModel):
    id: str
    label: str
    count: int


class LibraryStoragePaths(BaseModel):
    articles: str
    index: str
    signals_db: str
    note: str


class LibraryStatsResponse(BaseModel):
    article_count: int
    curated_count: int = 0
    imported_count: int = 0
    news_count: int = 0
    catalog_total: int = 0
    categories: list[LibraryCategoryCount]
    total_words: int
    total_bytes: int
    last_updated: str
    storage_paths: LibraryStoragePaths


class LibraryKnowledgeTierInfo(BaseModel):
    id: str
    label: str
    min_articles: int
    min_words: int


class LibraryKnowledgeLevelResponse(BaseModel):
    level_id: str
    level_label: str
    article_count: int
    total_words: int
    progress_pct: float
    articles_progress_pct: float = 0.0
    words_progress_pct: float = 0.0
    next_level_id: Optional[str] = None
    next_level_label: Optional[str] = None
    articles_to_next: int = 0
    words_to_next: int = 0
    tiers: list[LibraryKnowledgeTierInfo] = Field(default_factory=list)
    formula_note: str = ""
    progress_scope: str = "library_size"


class LibraryReadProgressResponse(BaseModel):
    read_article_ids: list[str] = Field(default_factory=list)


class LibraryReadProgressUpdate(BaseModel):
    read_article_ids: list[str] = Field(default_factory=list)
    merge: bool = True


class AgentLibraryStudyStatusResponse(BaseModel):
    auto_study_enabled: bool
    state: str
    studied_count: int
    total_articles: int
    level_id: str
    level_label: str
    progress_pct: float
    article_count: int = 0
    total_words: int = 0
    last_studied_at: Optional[str] = None
    last_article_id: Optional[str] = None
    last_article_title: Optional[str] = None
    next_article_id: Optional[str] = None
    next_article_title: Optional[str] = None
    recently_active: bool = False
    formula_note: str = ""
    studied_article_ids: list[str] = Field(default_factory=list)
    operational_maturity_pct: float = 0.0
    closed_trades_count: int = 0


class AgentLibraryStudyTickResponse(BaseModel):
    ticked: bool
    article_id: Optional[str] = None
    title: Optional[str] = None
    digest: Optional[str] = None
    studied_count: int
    total_articles: int
    complete: bool
    message: str


class AgentJournalResponse(BaseModel):
    markdown: str
    win_count: int = 0
    close_count: int = 0
    loss_count: int = 0
    saved_since_first_win: bool = False
    updated_at: Optional[str] = None
    last_win_at: Optional[str] = None
    last_study_at: Optional[str] = None
    path: str = "data/agent_journal/agente-aprendizado.md"


class LibraryImportResponse(BaseModel):
    format: str
    mode: str
    articles_written: int
    articles_in_index: int
    backup_dir: Optional[str] = None
    message: str


class MarketTickerSummaryItem(BaseModel):
    symbol: str
    label: str
    bid: Optional[float] = None
    ask: Optional[float] = None
    last: Optional[float] = None
    mid: Optional[float] = None
    change_pct: Optional[float] = None
    reference_price: Optional[float] = None
    available: bool = False
    source: Optional[str] = None
    timestamp: Optional[str] = None


class MarketTickersSummaryResponse(BaseModel):
    as_of: Optional[datetime] = None
    tickers: list[MarketTickerSummaryItem] = Field(default_factory=list)


class OrderExecuteRequest(BaseModel):
    symbol: str
    side: SignalSide
    contracts: int = Field(ge=1, le=100_000)
    entry: Optional[float] = Field(default=None, gt=0)
    stop: Optional[float] = Field(default=None, gt=0)
    target: Optional[float] = Field(default=None, gt=0)
    note: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def map_quantity_to_contracts(cls, data):
        if isinstance(data, dict) and "contracts" not in data and "quantity" in data:
            data = dict(data)
            data["contracts"] = data["quantity"]
        return data


class OrderExecuteResponse(BaseModel):
    ok: bool
    message: str
    operating_mode: str
    signal: SignalRead
    mt5_sent: bool = False
    mt5_ok: bool | None = None
    db_only: bool = True


class SystemFlattenResponse(BaseModel):
    ok: bool
    message: str
    emergency_flatten: bool
    engine_paused: bool
    positions_closed: int
    signals_cancelled: int
    state: SystemStateRead


class SystemResetSessionResponse(BaseModel):
    ok: bool
    message: str
    epoch_at: str
    previous_epoch_at: str | None = None
