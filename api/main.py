from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager
from datetime import datetime
from zoneinfo import ZoneInfo

from pathlib import Path

from fastapi import Depends, FastAPI, File, Header, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from api.config import settings
from api.database import SessionLocal, SignalRow, init_db
from api.news import get_headlines
from api.pnl import (
    closed_in_month,
    closed_in_today,
    estimate_open_pnl_brl,
    fees_for_row,
    gross_pnl_brl,
    count_open_positions,
    is_open_row,
    latest_open_positions,
    load_quote_mid_map,
    net_pnl_brl,
    resolved_pnl_for_row,
    row_closed_timestamp,
    _mid_from_quote_point,
)
from api.agent_config import (
    apply_config_patch,
    apply_preset_to_row,
    config_to_dict,
    get_or_create_config,
    list_presets_public,
)
from api.pnl import pnl_tax_breakdown
from api.execution_status import build_execution_status
from api.system_state import compute_engine_online, get_or_create_state, state_to_dict
from api.equity_curve import build_equity_curve
from api.signal_close import finalize_signal_close, persist_resolved_pnl
from api.trades_metrics import (
    build_trade_summaries,
    filter_trade_rows,
    row_to_trade_dict,
)
from api.market_ohlc import get_ohlc
from api.library import (
    build_library_export_zip,
    get_knowledge_counts_for_read_ids,
    get_library_article,
    get_library_index,
    get_library_stats,
    import_library_archive,
    load_library_read_progress,
    merge_library_read_progress,
    save_library_read_progress,
)
from api.agent_library_study import (
    agent_knowledge_level,
    agent_study_tick,
    get_agent_study_status,
)
from api.agent_journal import get_agent_journal
from api.agent_study import get_agent_study
from api.trade_learning import (
    get_learning_insights_response,
    get_learning_stats_response,
    maybe_refresh_trade_learning_db,
)
from api.candle_patterns import get_candle_patterns
from api.strategy_series import get_strategy_series
from api.market_tickers_summary import get_tickers_summary
from api.orders_execute import execute_manual_order
from api.system_flatten import flatten_system
from api.system_reset_session import reset_metrics_session
from api.session_epoch import load_session_epoch_at, row_in_metrics_session
from api.market_structure import get_market_structure
from api.b3_tickers import search_popular_tickers
from shared.schemas import (
    AgentConfigPatch,
    AgentConfigRead,
    AgentPresetsResponse,
    AgentPresetSummary,
    AgentTickerItem,
    AgentTickersResponse,
    AlertRead,
    AlertType,
    MarketQuote,
    NewsFeedResponse,
    NewsItem,
    LibraryArticleResponse,
    LibraryIndexResponse,
    LibraryImportResponse,
    LibraryStatsResponse,
    LibraryKnowledgeLevelResponse,
    LibraryReadProgressResponse,
    LibraryReadProgressUpdate,
    AgentLibraryStudyStatusResponse,
    AgentLibraryStudyTickResponse,
    AgentJournalResponse,
    ClosedTradeSummary,
    EquityCurveResponse,
    MarketMidsResponse,
    MarketTickersSummaryResponse,
    OrderExecuteRequest,
    OrderExecuteResponse,
    PnlMetrics,
    PnlMetricsResponse,
    SessionActivitySummary,
    SignalCreate,
    SignalOutcome,
    SignalRead,
    SignalSide,
    SignalStatus,
    SignalUpdate,
    StatsResponse,
    ExecutionStatusRead,
    SystemStatePatch,
    SystemStateRead,
    SystemFlattenResponse,
    SystemResetSessionResponse,
    TradeMetricsItem,
    TradesGlobalSummary,
    TradesMetricsResponse,
    TradesSummaryResponse,
    TradeSymbolSummary,
)

TZ_BR = ZoneInfo("America/Sao_Paulo")
_ROOT = Path(__file__).resolve().parents[1]
_WEB_DIR = _ROOT / "web"
_COCKPIT_DIST = _ROOT / "cockpit" / "dist"
_QUOTE_FILE = _ROOT / "data" / "last_quote.json"
_QUOTE_HISTORY_FILE = _ROOT / "data" / "quote_history.json"

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    db = SessionLocal()
    try:
        get_or_create_config(db)
    finally:
        db.close()

    study_task: asyncio.Task | None = None

    async def _agent_library_study_loop() -> None:
        first = True
        while True:
            interval = max(30, settings.agent_study_interval_sec)
            if settings.agent_study_background_enabled:
                try:
                    agent_study_tick()
                except Exception:
                    pass
            if first:
                first = False
                interval = min(interval, 15)
            await asyncio.sleep(interval)

    if settings.agent_study_background_enabled:
        study_task = asyncio.create_task(_agent_library_study_loop())

    ingest_task: asyncio.Task | None = None

    async def _library_auto_ingest_loop() -> None:
        from api.library_ingest_job import library_ingest_tick

        while True:
            hours = float(settings.library_auto_ingest_hours or 0)
            if hours > 0:
                try:
                    await asyncio.to_thread(library_ingest_tick)
                except Exception:
                    pass
                await asyncio.sleep(max(3600, int(hours * 3600)))
            else:
                await asyncio.sleep(600)

    if settings.library_auto_ingest_hours and settings.library_auto_ingest_hours > 0:
        ingest_task = asyncio.create_task(_library_auto_ingest_loop())

    yield

    if ingest_task is not None:
        ingest_task.cancel()
        try:
            await ingest_task
        except asyncio.CancelledError:
            pass

    if study_task is not None:
        study_task.cancel()
        try:
            await study_task
        except asyncio.CancelledError:
            pass


app = FastAPI(title="Sala de Sinais API", version="0.2.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def verify_webhook(x_webhook_secret: str | None = Header(default=None)) -> None:
    if x_webhook_secret != settings.webhook_secret:
        raise HTTPException(status_code=401, detail="Webhook secret inválido")


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value)


_DOCS_DIR = _ROOT / "docs"

if _WEB_DIR.is_dir():
    app.mount(
        "/static",
        StaticFiles(directory=str(_WEB_DIR)),
        name="static",
    )

if _DOCS_DIR.is_dir():
    app.mount(
        "/docs",
        StaticFiles(directory=str(_DOCS_DIR)),
        name="docs",
    )

def _cockpit_index() -> Path:
    return _COCKPIT_DIST / "index.html"


def _cockpit_available() -> bool:
    return _cockpit_index().is_file()


if _COCKPIT_DIST.is_dir() and (_COCKPIT_DIST / "assets").is_dir():
    app.mount(
        "/assets",
        StaticFiles(directory=str(_COCKPIT_DIST / "assets")),
        name="cockpit_assets",
    )


def _cockpit_favicon_path(name: str) -> Path | None:
    path = _COCKPIT_DIST / name
    return path if path.is_file() else None


@app.get("/favicon.ico", include_in_schema=False)
def cockpit_favicon_ico() -> FileResponse:
    path = _cockpit_favicon_path("favicon.ico")
    if path is None:
        raise HTTPException(status_code=404, detail="Not Found")
    return FileResponse(path, media_type="image/x-icon")


@app.get("/favicon.svg", include_in_schema=False)
def cockpit_favicon_svg() -> FileResponse:
    path = _cockpit_favicon_path("favicon.svg")
    if path is None:
        raise HTTPException(status_code=404, detail="Not Found")
    return FileResponse(path, media_type="image/svg+xml")


if _WEB_DIR.is_dir():

    @app.get("/classic", include_in_schema=False)
    @app.get("/classic/", include_in_schema=False)
    @app.get("/v1", include_in_schema=False)
    @app.get("/v1/", include_in_schema=False)
    def painel_classic() -> FileResponse:
        return FileResponse(_WEB_DIR / "index.html")

    @app.get("/", include_in_schema=False)
    def painel() -> FileResponse:
        if _cockpit_available():
            return FileResponse(_cockpit_index())
        return FileResponse(_WEB_DIR / "index.html")

    @app.get("/dashboard", include_in_schema=False)
    def painel_alias() -> FileResponse:
        if _cockpit_available():
            return FileResponse(_cockpit_index())
        return FileResponse(_WEB_DIR / "index.html")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


def _system_state_read(row) -> SystemStateRead:
    return SystemStateRead(
        engine_paused=row.engine_paused,
        emergency_flatten=row.emergency_flatten,
        last_heartbeat=_parse_dt(row.last_heartbeat),
        engine_online=compute_engine_online(row.last_heartbeat),
        mode=row.mode,
        updated_at=datetime.fromisoformat(row.updated_at),
        account_login=row.account_login,
        is_demo=row.is_demo,
        account_server=row.account_server,
        data_source=row.data_source,
        mt5_connected=row.mt5_connected,
        operating_mode=row.operating_mode,
    )


@app.get("/system/state", response_model=SystemStateRead)
def read_system_state(db: Session = Depends(get_db)) -> SystemStateRead:
    row = get_or_create_state(db)
    return _system_state_read(row)


@app.get("/system/execution-status", response_model=ExecutionStatusRead)
def read_execution_status(db: Session = Depends(get_db)) -> ExecutionStatusRead:
    row = get_or_create_state(db)
    online = compute_engine_online(row.last_heartbeat)
    return build_execution_status(
        engine_online=online,
        engine_paused=row.engine_paused,
        mt5_connected=row.mt5_connected,
        is_demo=row.is_demo,
        operating_mode=row.operating_mode,
        mode=row.mode or "paper",
    )


@app.get("/agent/config", response_model=AgentConfigRead)
def read_agent_config(db: Session = Depends(get_db)) -> AgentConfigRead:
    row = get_or_create_config(db)
    data = config_to_dict(row)
    return AgentConfigRead(
        **{k: v for k, v in data.items() if k != "updated_at"},
        updated_at=datetime.fromisoformat(row.updated_at),
    )


@app.get("/agent/presets", response_model=AgentPresetsResponse)
def read_agent_presets() -> AgentPresetsResponse:
    return AgentPresetsResponse(
        presets=[AgentPresetSummary(**p) for p in list_presets_public()],
        recommended_id="moderado",
    )


@app.get("/agent/tickers", response_model=AgentTickersResponse)
def read_agent_tickers(
    q: str = Query("", max_length=32, description="Filtro por ticker ou nome"),
) -> AgentTickersResponse:
    rows = search_popular_tickers(q, limit=15)
    return AgentTickersResponse(tickers=[AgentTickerItem(**r) for r in rows])


@app.post("/agent/config/apply-preset", response_model=AgentConfigRead)
def apply_agent_preset(
    name: str = Query(..., description="moderado | conservador | agressivo"),
    db: Session = Depends(get_db),
) -> AgentConfigRead:
    row = get_or_create_config(db)
    apply_preset_to_row(row, name)
    db.commit()
    db.refresh(row)
    return read_agent_config(db)


@app.patch("/agent/config", response_model=AgentConfigRead)
def patch_agent_config(body: AgentConfigPatch, db: Session = Depends(get_db)) -> AgentConfigRead:
    row = get_or_create_config(db)
    patch = body.model_dump(exclude_unset=True)
    apply_config_patch(row, patch)
    db.commit()
    db.refresh(row)
    return read_agent_config(db)


@app.patch("/system/state", response_model=SystemStateRead)
def patch_system_state(body: SystemStatePatch, db: Session = Depends(get_db)) -> SystemStateRead:
    row = get_or_create_state(db)
    if body.engine_paused is not None:
        row.engine_paused = body.engine_paused
    if body.emergency_flatten is not None:
        row.emergency_flatten = body.emergency_flatten
    if body.mode is not None:
        row.mode = body.mode
    row.updated_at = datetime.now(TZ_BR).isoformat()
    db.commit()
    db.refresh(row)
    return _system_state_read(row)


@app.post("/system/heartbeat", response_model=SystemStateRead)
def system_heartbeat(
    mode: str | None = None,
    account_login: int | None = None,
    is_demo: bool | None = None,
    account_server: str | None = None,
    data_source: str | None = None,
    mt5_connected: bool | None = None,
    operating_mode: str | None = None,
    db: Session = Depends(get_db),
    _: None = Depends(verify_webhook),
) -> SystemStateRead:
    row = get_or_create_state(db)
    row.last_heartbeat = datetime.now(TZ_BR).isoformat()
    if mode:
        row.mode = mode
    if account_login is not None:
        row.account_login = account_login
    if is_demo is not None:
        row.is_demo = is_demo
    if account_server is not None:
        row.account_server = account_server
    if data_source is not None:
        row.data_source = data_source
    if mt5_connected is not None:
        row.mt5_connected = mt5_connected
    if operating_mode is not None:
        row.operating_mode = operating_mode
    row.updated_at = row.last_heartbeat
    db.commit()
    return _system_state_read(row)


@app.get("/system/state/raw")
def read_system_state_raw(db: Session = Depends(get_db)) -> dict:
    """Compatível com engine — inclui flags booleanas."""
    return state_to_dict(get_or_create_state(db))


@app.post("/system/flatten", response_model=SystemFlattenResponse)
async def system_flatten(db: Session = Depends(get_db)) -> SystemFlattenResponse:
    """Kill switch: fecha posições abertas na base, cancela pendentes e aciona emergency_flatten."""
    return flatten_system(db, state_to_read=_system_state_read)


@app.post("/system/reset-session", response_model=SystemResetSessionResponse)
async def system_reset_session(db: Session = Depends(get_db)) -> SystemResetSessionResponse:
    """Marca epoch — KPIs passam a ignorar sinais anteriores (MT5 inalterado)."""
    return reset_metrics_session(db)


@app.post("/orders/execute", response_model=OrderExecuteResponse)
async def orders_execute(
    body: OrderExecuteRequest,
    db: Session = Depends(get_db),
) -> OrderExecuteResponse:
    """Ordem manual da UI — simulation/paper_mt5; live só se política permitir."""
    return execute_manual_order(db, body, row_to_read=_row_to_read)


@app.post("/signals", response_model=SignalRead)
def create_signal(
    body: SignalCreate,
    db: Session = Depends(get_db),
    _: None = Depends(verify_webhook),
) -> SignalRead:
    now = datetime.now(TZ_BR).isoformat()
    row = SignalRow(
        symbol=body.symbol,
        side=body.side.value,
        entry=body.entry,
        stop=body.stop,
        target=body.target,
        contracts=body.contracts,
        strategy_id=body.strategy_id,
        mode=body.mode.value,
        status=SignalStatus.SENT.value,
        note=body.note,
        created_at=now,
        strategy_type=body.strategy_type,
        strategy_version=body.strategy_version,
        entry_reason=body.entry_reason,
        regime=body.regime,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _row_to_read(row)


@app.get("/signals", response_model=list[SignalRead])
def list_signals(
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
) -> list[SignalRead]:
    rows = db.query(SignalRow).order_by(SignalRow.id.desc()).limit(limit).all()
    return [_row_to_read(r) for r in rows]


@app.patch("/signals/{signal_id}/status", response_model=SignalRead)
def update_status(
    signal_id: int,
    status: SignalStatus,
    message: str | None = None,
    db: Session = Depends(get_db),
    _: None = Depends(verify_webhook),
) -> SignalRead:
    return _apply_signal_update(
        db,
        signal_id,
        SignalUpdate(status=status, message=message),
    )


@app.patch("/signals/{signal_id}", response_model=SignalRead)
def patch_signal(
    signal_id: int,
    body: SignalUpdate,
    db: Session = Depends(get_db),
    _: None = Depends(verify_webhook),
) -> SignalRead:
    return _apply_signal_update(db, signal_id, body)


def _apply_signal_update(db: Session, signal_id: int, body: SignalUpdate) -> SignalRead:
    row = db.get(SignalRow, signal_id)
    if row is None:
        raise HTTPException(404, "Sinal não encontrado")

    if body.status is not None:
        row.status = body.status.value
    if body.message:
        row.execution_message = body.message
    if body.exit_price is not None:
        row.exit_price = body.exit_price
    if body.outcome is not None:
        row.outcome = body.outcome.value
    if body.exit_reason is not None:
        row.exit_reason = body.exit_reason

    exit_px = body.exit_price if body.exit_price is not None else row.exit_price
    closing = (
        body.status in (SignalStatus.CLOSED, SignalStatus.FILLED)
        or body.exit_price is not None
        or (body.status == SignalStatus.CLOSED and exit_px is not None)
    )
    if closing and exit_px is not None:
        finalize_signal_close(
            row,
            float(exit_px),
            outcome=body.outcome,
            closed_at=body.closed_at,
            force_status_closed=body.status != SignalStatus.FILLED,
        )
        persist_resolved_pnl(row)
        if body.status == SignalStatus.CLOSED:
            row.status = SignalStatus.CLOSED.value
        elif body.status == SignalStatus.FILLED:
            row.status = SignalStatus.FILLED.value

    db.commit()
    db.refresh(row)
    if closing and exit_px is not None:
        maybe_refresh_trade_learning_db(db)
        try:
            from api.agent_journal import on_trade_closed_row

            on_trade_closed_row(row)
        except Exception:
            pass
    return _row_to_read(row)


def _outcome_counts(closed: list[tuple[SignalRow, float, float, float]]) -> tuple[int, int, int]:
    wins = losses = breakeven = 0
    for row, _, net, _ in closed:
        if row.outcome == "breakeven" or net == 0:
            breakeven += 1
        elif row.outcome == "win" or net > 0:
            wins += 1
        elif row.outcome == "loss" or net < 0:
            losses += 1
    return wins, losses, breakeven


def _closed_with_pnl(rows: list[SignalRow]) -> list[tuple[SignalRow, float, float, float]]:
    out: list[tuple[SignalRow, float, float, float]] = []
    for r in rows:
        gross, net, fees = resolved_pnl_for_row(r)
        if net is not None and gross is not None:
            out.append((r, gross, net, fees))
    return out


def _metrics_for_rows(rows: list[SignalRow], period: str) -> PnlMetrics:
    closed = _closed_with_pnl(rows)
    wins, losses, breakeven = _outcome_counts(closed)
    gross_vals = [g for _, g, _, _ in closed]
    gross_profit = sum(g for g in gross_vals if g > 0)
    gross_loss = sum(g for g in gross_vals if g < 0)
    gross = sum(gross_vals)
    net = sum(n for _, _, n, _ in closed)
    fees = sum(f for _, _, _, f in closed)
    ir, net_after = pnl_tax_breakdown(round(net, 2))
    wr = (wins / len(closed) * 100) if closed else None
    return PnlMetrics(
        period=period,
        closed_trades=len(closed),
        wins=wins,
        losses=losses,
        breakeven_count=breakeven,
        win_rate_pct=round(wr, 2) if wr is not None else None,
        gross_pnl_brl=round(gross, 2),
        gross_profit_brl=round(gross_profit, 2),
        gross_loss_brl=round(gross_loss, 2),
        fees_brl=round(fees, 2),
        net_before_tax_brl=round(net, 2),
        estimated_ir_brl=ir,
        net_after_tax_estimated_brl=net_after,
        net_pnl_brl=round(net, 2),
    )


def _session_today_summary(
    rows: list[SignalRow],
    *,
    today: str,
    daily_net: float,
    portfolio_open: list[SignalRow],
    quote_mids: dict[str, float],
) -> SessionActivitySummary:
    today_rows = [r for r in rows if (r.created_at or "").startswith(today)]
    buys = sum(1 for r in today_rows if (r.side or "").upper() == "BUY")
    sells = sum(1 for r in today_rows if (r.side or "").upper() == "SELL")
    volume = sum(int(r.contracts or 0) for r in today_rows)
    open_mtm = sum(estimate_open_pnl_brl(r, quote_mids) for r in portfolio_open)
    fees_open = sum(fees_for_row(r) for r in portfolio_open)
    ir = pnl_tax_breakdown(round(daily_net + open_mtm, 2))[0]
    return SessionActivitySummary(
        buys=buys,
        sells=sells,
        volume_shares=volume,
        closed_net_brl=round(daily_net, 2),
        open_mtm_brl=round(open_mtm, 2),
        fees_open_est_brl=round(fees_open, 2),
        estimated_ir_brl=ir,
    )


def _signal_rows_for_metrics(db: Session) -> list[SignalRow]:
    epoch_at = load_session_epoch_at()
    rows = db.query(SignalRow).all()
    if not epoch_at:
        return rows
    return [r for r in rows if row_in_metrics_session(r, epoch_at=epoch_at)]


@app.get("/metrics/pnl", response_model=PnlMetricsResponse)
def metrics_pnl(db: Session = Depends(get_db)) -> PnlMetricsResponse:
    rows = _signal_rows_for_metrics(db)
    now = datetime.now(TZ_BR)
    today = now.date().isoformat()
    month_prefix = now.strftime("%Y-%m")

    daily_rows = [r for r in rows if closed_in_today(r, today)]
    monthly_rows = [r for r in rows if closed_in_month(r, month_prefix)]
    all_closed = _closed_with_pnl(rows)
    all_time = _metrics_for_rows(rows, "all_time")
    daily = _metrics_for_rows(daily_rows, "daily")
    monthly = _metrics_for_rows(monthly_rows, "monthly")

    quote_mids = load_quote_mid_map()
    open_rows = [r for r in rows if is_open_row(r)]
    portfolio_open = latest_open_positions(open_rows)
    open_est = sum(estimate_open_pnl_brl(r, quote_mids) for r in portfolio_open)
    session_today = _session_today_summary(
        rows,
        today=today,
        daily_net=daily.net_pnl_brl,
        portfolio_open=portfolio_open,
        quote_mids=quote_mids,
    )

    recent = sorted(all_closed, key=lambda t: row_closed_timestamp(t[0]), reverse=True)[:20]
    recent_closed = [
        ClosedTradeSummary(
            id=r.id,
            symbol=r.symbol,
            side=r.side,
            entry=r.entry,
            exit_price=float(r.exit_price or r.entry),
            gross_pnl_brl=round(g, 2),
            net_pnl_brl=round(n, 2),
            fees_brl=round(f, 2),
            closed_at=_parse_dt(r.closed_at),
            strategy_type=r.strategy_type,
            entry_reason=r.entry_reason,
            exit_reason=r.exit_reason,
        )
        for r, g, n, f in recent
    ]

    return PnlMetricsResponse(
        daily=daily,
        monthly=monthly,
        all_time=all_time,
        gross_profit_brl=all_time.gross_profit_brl,
        gross_loss_brl=all_time.gross_loss_brl,
        net_pnl_brl=all_time.net_pnl_brl,
        today_net=daily.net_pnl_brl,
        month_net=monthly.net_pnl_brl,
        all_time_net=all_time.net_pnl_brl,
        wins=all_time.wins,
        losses=all_time.losses,
        breakeven_count=all_time.breakeven_count,
        open_positions_estimated_pnl=round(open_est, 2),
        open_positions_count=count_open_positions(open_rows),
        fees_paid_brl=all_time.fees_brl,
        net_before_tax_brl=all_time.net_before_tax_brl,
        estimated_ir_brl=all_time.estimated_ir_brl,
        net_after_tax_estimated_brl=all_time.net_after_tax_estimated_brl,
        recent_closed=recent_closed,
        session_today=session_today,
    )


def _trades_payload(
    rows: list[SignalRow],
    *,
    symbol: str | None,
    limit: int,
    today_only: bool,
) -> TradesMetricsResponse:
    now = datetime.now(TZ_BR)
    today = now.date().isoformat()
    filtered = filter_trade_rows(rows, symbol=symbol, today_only=today_only, today=today)
    trade_dicts: list[dict] = []
    for r in filtered:
        item = row_to_trade_dict(r)
        if item:
            trade_dicts.append(item)
    trade_dicts = trade_dicts[:limit]
    global_raw, by_sym_raw = build_trade_summaries(trade_dicts)
    return TradesMetricsResponse(
        trades=[TradeMetricsItem(**t) for t in trade_dicts],
        global_summary=TradesGlobalSummary(**global_raw),
        by_symbol=[TradeSymbolSummary(**s) for s in by_sym_raw],
    )


@app.get("/metrics/trades", response_model=TradesMetricsResponse)
def metrics_trades(
    symbol: str | None = Query(default=None),
    limit: int = Query(100, ge=1, le=500),
    today_only: bool = Query(False),
    db: Session = Depends(get_db),
) -> TradesMetricsResponse:
    rows = _signal_rows_for_metrics(db)
    return _trades_payload(rows, symbol=symbol, limit=limit, today_only=today_only)


@app.get("/metrics/trades/summary", response_model=TradesSummaryResponse)
def metrics_trades_summary(
    symbol: str | None = Query(default=None),
    today_only: bool = Query(False),
    db: Session = Depends(get_db),
) -> TradesSummaryResponse:
    payload = _trades_payload(
        _signal_rows_for_metrics(db),
        symbol=symbol,
        limit=10_000,
        today_only=today_only,
    )
    return TradesSummaryResponse(
        global_summary=payload.global_summary,
        by_symbol=payload.by_symbol,
    )


@app.get("/metrics/equity-curve", response_model=EquityCurveResponse)
def metrics_equity_curve(db: Session = Depends(get_db)) -> EquityCurveResponse:
    rows = _signal_rows_for_metrics(db)
    cfg = get_or_create_config(db)
    capital = float(cfg.capital_brl or 0.0)
    if capital <= 0:
        capital = 10000.0
    data = build_equity_curve(rows, capital)
    return EquityCurveResponse(**data)


@app.get("/library", response_model=LibraryIndexResponse)
def library_index() -> LibraryIndexResponse:
    return get_library_index()


@app.get("/library/stats", response_model=LibraryStatsResponse)
def library_stats() -> LibraryStatsResponse:
    return get_library_stats()


@app.get("/library/knowledge-level", response_model=LibraryKnowledgeLevelResponse)
def library_knowledge_level(
    read_ids: str | None = Query(
        default=None,
        description="IDs de artigos lidos (vírgula). Se presente, nível = progresso do usuário.",
    ),
    agent: bool = Query(
        default=False,
        description="Se true, nível = artigos estudados autonomamente pelo agente.",
    ),
) -> LibraryKnowledgeLevelResponse:
    from api.library_knowledge import READ_PROGRESS_FORMULA_NOTE, compute_knowledge_level

    if agent:
        level = agent_knowledge_level()
        return level.model_copy(update={"progress_scope": "agent_study"})

    if read_ids is not None:
        ids = [x.strip() for x in read_ids.split(",") if x.strip()]
        article_count, total_words = get_knowledge_counts_for_read_ids(ids)
        level = compute_knowledge_level(
            article_count,
            total_words,
            formula_note=READ_PROGRESS_FORMULA_NOTE,
        )
        return level.model_copy(update={"progress_scope": "user_read"})
    stats = get_library_stats()
    level = compute_knowledge_level(stats.catalog_total or stats.article_count, stats.total_words)
    return level.model_copy(update={"progress_scope": "library_size"})


@app.get("/library/agent-study-status", response_model=AgentLibraryStudyStatusResponse)
def library_agent_study_status() -> AgentLibraryStudyStatusResponse:
    return AgentLibraryStudyStatusResponse(**get_agent_study_status())


@app.post("/library/agent-study/tick", response_model=AgentLibraryStudyTickResponse)
def library_agent_study_tick(
    force: bool = Query(False, description="Executa um tick mesmo com AGENT_AUTO_STUDY_LIBRARY=false"),
) -> AgentLibraryStudyTickResponse:
    return AgentLibraryStudyTickResponse(**agent_study_tick(force=force))


@app.get("/library/agent-journal", response_model=AgentJournalResponse)
def library_agent_journal() -> AgentJournalResponse:
    return AgentJournalResponse(**get_agent_journal())


@app.get("/library/read-progress", response_model=LibraryReadProgressResponse)
def library_read_progress_get() -> LibraryReadProgressResponse:
    return LibraryReadProgressResponse(read_article_ids=load_library_read_progress())


@app.put("/library/read-progress", response_model=LibraryReadProgressResponse)
def library_read_progress_put(body: LibraryReadProgressUpdate) -> LibraryReadProgressResponse:
    ids = list(body.read_article_ids or [])
    if body.merge:
        merged = merge_library_read_progress(ids)
    else:
        merged = save_library_read_progress(ids)
    return LibraryReadProgressResponse(read_article_ids=merged)


@app.get("/library/articles/{article_id}", response_model=LibraryArticleResponse)
def library_article(article_id: str) -> LibraryArticleResponse:
    return get_library_article(article_id)


@app.get("/library/export", include_in_schema=True)
def library_export() -> Response:
    payload = build_library_export_zip()
    filename = "sala_sinais_conhecimento.zip"
    return Response(
        content=payload,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.post("/library/import", response_model=LibraryImportResponse)
async def library_import(
    file: UploadFile = File(..., description="ZIP exportado por GET /library/export"),
    mode: str = Query(
        "merge",
        description="merge: mescla por id; replace: substitui toda a biblioteca (com backup)",
    ),
) -> LibraryImportResponse:
    raw = await file.read()
    if not raw:
        raise HTTPException(400, "Arquivo vazio")
    result = import_library_archive(raw, mode=mode)
    return LibraryImportResponse(**result)


@app.get("/news/headlines", response_model=NewsFeedResponse)
def news_headlines(limit: int = Query(8, ge=1, le=15)) -> NewsFeedResponse:
    data = get_headlines(limit=limit)
    return NewsFeedResponse(
        items=[NewsItem(**i) for i in data["items"]],
        cached=data["cached"],
        error=data.get("error"),
    )


@app.get("/market/quote", response_model=MarketQuote)
def market_quote() -> MarketQuote:
    if not _QUOTE_FILE.is_file():
        raise HTTPException(
            404,
            "Cotação indisponível — inicie Sala-Sinais.bat (simulacao ou engine)",
        )
    try:
        raw = json.loads(_QUOTE_FILE.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError("quote inválido")
        payload = dict(raw)
        mid = _mid_from_quote_point(payload)
        if mid is not None:
            payload["mid"] = mid
        for key in ("bid", "ask", "mid"):
            if key not in payload or payload[key] is None:
                continue
            try:
                payload[key] = float(payload[key])
            except (TypeError, ValueError):
                if key == "mid":
                    payload.pop("mid", None)
                else:
                    payload[key] = 0.0
        return MarketQuote(**payload)
    except Exception as exc:
        raise HTTPException(500, f"Erro ao ler cotação: {exc}") from exc


@app.get("/market/mids", response_model=MarketMidsResponse)
def market_mids() -> MarketMidsResponse:
    """Último mid por símbolo (quote_history + last_quote) para MTM no cockpit."""
    return MarketMidsResponse(mids=load_quote_mid_map())


@app.get("/market/tickers-summary", response_model=MarketTickersSummaryResponse)
async def market_tickers_summary() -> MarketTickersSummaryResponse:
    """Cotações rápidas + variação % para faixa do Pulse Deck."""
    return get_tickers_summary()


@app.get("/market/ohlc")
def market_ohlc(
    symbol: str = Query("PETR4"),
    tf: str = Query("M5"),
    limit: int = Query(80, ge=1, le=5000),
) -> dict:
    """Barras OHLC (M1/M5/H1) a partir de barras M1 do engine ou quote_history."""
    return get_ohlc(symbol, tf=tf, limit=limit)


@app.get("/agent/candle-patterns")
def agent_candle_patterns(
    symbol: str = Query("PETR4"),
    tf: str = Query("M5"),
    limit: int = Query(80, ge=10, le=500),
    lookback: int = Query(24, ge=5, le=120),
) -> dict:
    """Padrões clássicos de candlestick (camada matemática) com rótulos PT-BR."""
    try:
        return get_candle_patterns(symbol, tf=tf, limit=limit, lookback=lookback)
    except Exception as exc:
        raise HTTPException(500, f"Erro nos padrões de candle: {exc}") from exc


@app.get("/agent/study")
def agent_study(symbol: str = Query("PETR4")) -> dict:
    """Estudo ao vivo: estratégia, horário, tamanho, entrada/saída proposta."""
    sym = symbol.upper()
    bid = ask = None
    if _QUOTE_FILE.is_file():
        try:
            raw = json.loads(_QUOTE_FILE.read_text(encoding="utf-8"))
            if (raw.get("symbol") or "").upper() == sym:
                bid = float(raw.get("bid") or 0)
                ask = float(raw.get("ask") or 0)
        except Exception:
            pass
    if bid is None or ask is None or (bid == 0 and ask == 0):
        mids = load_quote_mid_map()
        mid = mids.get(sym)
        if mid:
            spread = max(0.01, mid * 0.0002)
            bid = mid - spread / 2
            ask = mid + spread / 2
    try:
        return get_agent_study(symbol, bid, ask)
    except Exception as exc:
        raise HTTPException(500, f"Erro no estudo do agente: {exc}") from exc


@app.get("/agent/learning-stats")
def agent_learning_stats(db: Session = Depends(get_db)) -> dict:
    """Agregados de trades fechados + guardas soft para o motor."""
    return get_learning_stats_response(db)


@app.get("/library/learning-insights")
def library_learning_insights(db: Session = Depends(get_db)) -> dict:
    """Insights curtos em PT (também persistidos em data/trade_learning.json)."""
    return get_learning_insights_response(db)


@app.get("/market/strategy-series")
def market_strategy_series(
    symbol: str = Query("PETR4"),
    tf: str = Query("M5"),
    limit: int = Query(100, ge=20, le=5000),
) -> dict:
    """Bollinger + regime para overlay no Pulse Deck."""
    return get_strategy_series(symbol, tf=tf, limit=limit)


@app.get("/market/structure")
def market_structure(
    symbol: str = Query("PETR4"),
    tf: str = Query("M5"),
    limit: int = Query(200, ge=30, le=500),
) -> dict:
    """Swings HH/HL, zonas oferta/demanda, FVG e CHoCH (SMC simplificado)."""
    try:
        return get_market_structure(symbol, tf=tf, limit=limit)
    except Exception as exc:
        raise HTTPException(500, f"Erro na estrutura de mercado: {exc}") from exc


@app.get("/alerts/recent", response_model=list[AlertRead])
def alerts_recent(
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> list[AlertRead]:
    """Alertas de entrada (novos sinais) e saída (sinais fechados)."""
    rows = db.query(SignalRow).order_by(SignalRow.id.desc()).limit(limit * 2).all()
    alerts: list[AlertRead] = []
    for r in rows:
        created = datetime.fromisoformat(r.created_at)
        st = r.strategy_type
        alerts.append(
            AlertRead(
                id=len(alerts) + 1,
                alert_type=AlertType.ENTRY,
                symbol=r.symbol,
                side=SignalSide(r.side),
                price=r.entry,
                note=r.entry_reason or r.note,
                created_at=created,
                signal_id=r.id,
                strategy_type=st,
                entry_reason=r.entry_reason,
            )
        )
        if r.closed_at and r.exit_price is not None:
            alerts.append(
                AlertRead(
                    id=len(alerts) + 1,
                    alert_type=AlertType.EXIT,
                    symbol=r.symbol,
                    side=SignalSide(r.side),
                    price=float(r.exit_price),
                    note=r.exit_reason or r.execution_message or r.note,
                    created_at=datetime.fromisoformat(r.closed_at),
                    signal_id=r.id,
                    strategy_type=st,
                    exit_reason=r.exit_reason,
                )
            )
    alerts.sort(key=lambda a: a.created_at, reverse=True)
    return alerts[:limit]


@app.get("/market/history")
def market_history(limit: int = Query(100, ge=1, le=100)) -> dict:
    """Últimas cotações gravadas pelo engine (buffer em data/quote_history.json)."""
    if not _QUOTE_HISTORY_FILE.is_file():
        return {"points": []}
    try:
        points = json.loads(_QUOTE_HISTORY_FILE.read_text(encoding="utf-8"))
        if not isinstance(points, list):
            return {"points": []}
        return {"points": points[-limit:]}
    except Exception:
        return {"points": []}


@app.get("/stats", response_model=StatsResponse)
def stats(db: Session = Depends(get_db)) -> StatsResponse:
    rows = db.query(SignalRow).all()
    today = datetime.now(TZ_BR).date().isoformat()
    today_count = sum(1 for r in rows if r.created_at.startswith(today))
    by_status: dict[str, int] = {}
    for r in rows:
        by_status[r.status] = by_status.get(r.status, 0) + 1
    return StatsResponse(
        total_signals=len(rows),
        today_signals=today_count,
        by_status=by_status,
    )


def _row_to_read(row: SignalRow) -> SignalRead:
    from shared.schemas import SignalMode

    outcome = SignalOutcome(row.outcome) if row.outcome else None
    return SignalRead(
        id=row.id,
        symbol=row.symbol,
        side=SignalSide(row.side),
        entry=row.entry,
        stop=row.stop,
        target=row.target,
        contracts=row.contracts,
        strategy_id=row.strategy_id,
        mode=SignalMode(row.mode),
        status=SignalStatus(row.status),
        note=row.note,
        execution_message=row.execution_message,
        created_at=datetime.fromisoformat(row.created_at),
        exit_price=row.exit_price,
        closed_at=_parse_dt(row.closed_at),
        outcome=outcome,
        gross_pnl_brl=_read_gross_pnl(row),
        net_pnl_brl=_read_net_pnl(row),
        strategy_type=row.strategy_type,
        strategy_version=row.strategy_version,
        entry_reason=row.entry_reason,
        exit_reason=row.exit_reason,
        regime=row.regime,
    )


def _read_gross_pnl(row: SignalRow) -> float | None:
    gross, _, _ = resolved_pnl_for_row(row)
    return gross


def _read_net_pnl(row: SignalRow) -> float | None:
    _, net, _ = resolved_pnl_for_row(row)
    return net


def run() -> None:
    import uvicorn

    uvicorn.run(
        "api.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=False,
    )


if __name__ == "__main__":
    run()
