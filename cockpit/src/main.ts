import "./styles/pulse-deck.css";
import "./styles/deck-v2.css";
import {
  api,
  apiBase,
  persistApiBase,
  type AgentConfig,
  type AlertRead,
  type PnlMetricsResponse,
  type Signal,
  type ExecutionStatusRead,
  type StrategySeriesResponse,
  type SystemState,
} from "./api/client";
import { asFiniteNumberOrNull, safeFixed } from "./util/numbers";
import type { ZoneId } from "./orbit/zones";
import { initCommandBar } from "./pulse/commandBar";
import { renderDecisionPanel, pickLatestSignalForSymbol } from "./pulse/decisionPanel";
import { loadAgentStudy, applyStrategyBadge } from "./pulse/agentStudyFetch";
import { renderAgentStudy } from "./pulse/agentStudy";
import { renderInsightDeck, syncInsightDeckLiveContext } from "./pulse/insights";
import { fetchSymbolStrategyStats, syncSymbolStrategyCard } from "./pulse/symbolStrategyStats";
import { syncHeaderKpis, syncModeBadge, syncOvernightBadge, syncAgentStudy24hBadge } from "./pulse/headerKpis";
import { initHeaderXrayPopovers, syncHeaderXrayLiveContext, syncHeaderXrayPopovers } from "./pulse/headerXray";
import { fetchLucrosLiveData, mountLucrosPanel, syncLucrosLive } from "./pulse/pnlLive";
import {
  bindRiverChart,
  drawRiverChart,
  type ChartLevelLine,
  type ChartMarker,
  type OhlcBar,
} from "./pulse/riverChart";
import { initSheetChrome, openSheet, refreshSheetBody } from "./pulse/sheet";
import { mountDayTimeline } from "./pulse/timeline";
import { fetchKnowledgeLevel, fetchAgentKnowledgeLevel } from "./pulse/knowledge";
import {
  fetchAgentJournal,
  fetchAgentLibraryStudyStatus,
  syncAgentJournalDom,
  syncAgentLibraryStudyDom,
  type AgentLibraryStudyStatus,
} from "./pulse/agentLibraryStudy";
import type { KnowledgeLevel } from "./pulse/knowledge";
import {
  hydrateReadProgressFromApi,
  LIBRARY_READ_CHANGED_EVENT,
} from "./pulse/libraryReadProgress";
import { fetchTradeLearning } from "./pulse/tradeLearning";
import { bindOpsFilters, renderLiveOps, type LiveOpsQuote, type OpsFilter, bindBoleta, clearPositionsAfterFlatten, syncChartPrice, resolveDisplayMid } from "./pulse/liveOps";
import { applyBoletaExecutionGate } from "./pulse/boletaGate";
import { initPulseTabs, getActiveTab, navigateToTab, applyDeckStageLayout } from "./pulse/tabs";
import { refreshTabPanel } from "./pulse/tabPanels";
import {
  chartLevelsFromSignals,
  chartLevelsFromStudy,
  signalMarkersForSymbol,
} from "./pulse/chartOverlays";
import { initDeckSplitResize } from "./pulse/splitResize";
import { appendEngineLog, initEngineLog, logHeartbeat, logLatency, appendEngineLogOnce } from "./pulse/engineLog";
import {
  mountMarketTicker,
  syncMarketTicker,
  refreshMarketTickerSummary,
  isTickersSummaryApiAvailable,
  bindTickerRailSymbol,
} from "./pulse/marketTicker";
import { bindTradeChart, updateTradeChart, setChartTimeRange, resizeTradeChart, setStructureLayerEnabled, resetChartViewForSymbol } from "./pulse/tradeChart";
import {
  persistStructureToggle,
  readStructureToggleDefault,
} from "./pulse/structureChart";
import type { MarketStructureResponse } from "./api/client";
import { refreshTickerGrid } from "./pulse/tickerGrid";
import {
  getViewSymbol,
  getWatchlistSymbols,
  initWatchlist,
  setViewSymbol,
  syncWatchlistFromAgent,
} from "./pulse/watchlist";
import { resolveTodayClosedNet } from "./pulse/pnlDisplay";
import { PULSE_DECK_VERSION } from "./version";

declare global {
  interface Window {
    PULSE_DECK_VERSION?: string;
  }
}

const $ = (id: string) => document.getElementById(id);

function setChip(id: string, text: string, ok?: boolean, extraClass?: string): void {
  const el = $(id);
  if (!el) return;
  el.textContent = text;
  el.classList.remove("chip-ok", "chip-bad", "chip-neutral", "chip-live");
  el.classList.add(ok === true ? "chip-ok" : ok === false ? "chip-bad" : "chip-neutral");
  if (extraClass) el.classList.add(extraClass);
}

function setLatency(ms: number | null): void {
  const el = $("header-latency");
  if (!el) return;
  el.textContent = ms != null ? `Latência: ${Math.round(ms)}ms` : "Latência: —";
}

let ctx: { state: SystemState | null; pnl: PnlMetricsResponse | null; agent: AgentConfig | null } = {
  state: null,
  pnl: null,
  agent: null,
};
let activeZone: ZoneId | null = null;
let chartMarkers: ChartMarker[] = [];
let chartLevels: ChartLevelLine[] = [];
let riverBarsCache: OhlcBar[] = [];
let strategySeriesCache: StrategySeriesResponse | null = null;
let structureCache: MarketStructureResponse | null = null;
let recentSignals: Signal[] = [];
let useTradeChart = false;
let lastLoadedChartSymbol = "";

const POLL_FAST_MS = 4_000;
const POLL_SLOW_MS = 9_000;
const CHART_OHLC_LIMIT = 2000;
const CHART_STRUCTURE_LIMIT = 280;
let chartTimeframe = "M5";
const TF_STORAGE_KEY = "sala_pulse_chart_tf";
let fastPollBusy = false;
let slowPollBusy = false;
let apiOnline = false;

function touchLastUpdate(ok: boolean): void {
  const last = $("last-update-label");
  const dot = $("live-sync-dot");
  apiOnline = ok;
  if (last) {
    last.textContent = ok
      ? `Última atualização ${new Date().toLocaleTimeString("pt-BR")}`
      : "Falha na atualização";
  }
  if (dot) {
    dot.classList.toggle("live", ok);
    dot.classList.toggle("offline", !ok);
    if (ok) {
      dot.classList.remove("pulse-once");
      void dot.offsetWidth;
      dot.classList.add("pulse-once");
    }
  }
}

function applyEngineUi(state: SystemState | null): void {
  const status = $("engine-status");
  const label = $("engine-label");
  const dot = $("engine-dot");
  if (!status || !label) return;

  const online = state?.engine_online ?? false;
  const paused = Boolean(online && state?.engine_paused);
  status.classList.toggle("online", online && !paused);
  status.classList.toggle("offline", !online);
  status.classList.toggle("paused", paused);
  label.textContent = online
    ? paused
      ? "MOTOR PAUSADO — use Retomar"
      : "MOTOR ATIVO"
    : "MOTOR OFFLINE";
  label.title = paused
    ? "ZERAR TUDO pausa o motor de propósito. Clique Retomar (menu esquerdo) para enviar ordens de novo."
    : "";
  if (dot) {
    dot.setAttribute(
      "aria-label",
      !online ? "offline" : paused ? "pausado" : "online",
    );
  }

  const engineChip = online
    ? paused
      ? "Motor pausado — Retomar"
      : "Motor ativo"
    : "Motor offline";
  setChip("chip-engine", engineChip, online && !paused);
  syncModeBadge(state);
}

function applyPnlDisplay(pnl: PnlMetricsResponse | null): void {
  syncHeaderKpis(pnl);
}

function paintChartCanvas(): void {
  const canvas = $("river-chart") as HTMLCanvasElement | null;
  if (canvas) drawRiverChart(canvas, riverBarsCache, chartMarkers, chartLevels);
  if (useTradeChart) {
    updateTradeChart(
      riverBarsCache,
      chartMarkers,
      chartLevels,
      strategySeriesCache,
      getViewSymbol() || "",
      structureCache,
    );
    resizeTradeChart();
  }
}

function setChartLoading(loading: boolean): void {
  const sk = $("river-chart-skeleton");
  const canvas = $("river-chart");
  if (sk) sk.classList.toggle("hidden", !loading);
  if (canvas) canvas.classList.toggle("chart-loading", loading);
}

function formatAtrToolbar(regime: string | undefined, atrPct: number | string | undefined): string {
  const atr =
    atrPct != null && atrPct !== ""
      ? `${Number(atrPct).toFixed(4)}%`
      : "—";
  const r = (regime || "").toLowerCase();
  let band = regime || "—";
  if (r.includes("low") || r.includes("baix")) band = "Baixa";
  else if (r.includes("high") || r.includes("alt")) band = "Alta";
  else if (r.includes("mid") || r.includes("méd")) band = "Média";
  return `${atr} (${band})`;
}

async function refreshAgentStudy(symbol: string): Promise<void> {
  const { study, notice } = await loadAgentStudy(symbol);
  renderAgentStudy(study, notice, {
    onOpenLibraryArticle: (id) => {
      sessionStorage.setItem("sala_pending_library_article", id);
      navigateToTab("biblioteca");
    },
  });
  applyStrategyBadge(ctx.agent, study);
  if (study?.indicators) {
    const regimeEl = $("chart-regime-label");
    if (regimeEl) {
      regimeEl.textContent = formatAtrToolbar(study.indicators.regime, study.indicators.atr_pct);
    }
  }
  const baseLevels = chartLevelsFromSignals(recentSignals, symbol);
  chartLevels = chartLevelsFromStudy(study, baseLevels);
  paintChartCanvas();
}

async function loadChart(symbol: string, tf = chartTimeframe): Promise<void> {
  const symEl = $("river-symbol");
  const regimeEl = $("chart-regime-label");
  if (symEl) symEl.textContent = symbol || "—";

  setChartLoading(true);
  try {
    const [ohlc, signals, series, structure] = await Promise.all([
      api.ohlc(symbol, tf, CHART_OHLC_LIMIT),
      api.signals(60),
      api.strategySeries(symbol, tf, CHART_OHLC_LIMIT).catch(() => null),
      api.marketStructure(symbol, tf, CHART_STRUCTURE_LIMIT).catch(() => null),
    ]);
    recentSignals = signals;
    chartMarkers = signalMarkersForSymbol(signals, symbol);
    chartLevels = chartLevelsFromSignals(signals, symbol);
    riverBarsCache = ohlc.bars;
    strategySeriesCache = series;
    structureCache = structure;
    if (regimeEl && series) regimeEl.textContent = formatAtrToolbar(series.regime, series.atr_pct_last);
    void refreshAgentStudy(symbol);
    paintChartCanvas();
    lastLoadedChartSymbol = symbol;
  } catch {
    riverBarsCache = [];
    chartMarkers = [];
    chartLevels = [];
    structureCache = null;
    paintChartCanvas();
  } finally {
    setChartLoading(false);
  }
}

async function loadInsights(
  pnl: PnlMetricsResponse | null,
  agent: AgentConfig | null,
): Promise<void> {
  let lastSignal: Signal | null = null;
  let lastAlert: AlertRead | null = null;
  let newsTitle: string | null = null;
  let libraryTip: { title: string; id: string } | null = null;
  let knowledgeLevel = await fetchKnowledgeLevel();
  const { agentKnowledgeLevel, agentLibraryStudy } = await refreshAgentLibraryProgress({
    journal: true,
  });
  const tradeLearning = await fetchTradeLearning();
  lastTradeLearning = tradeLearning;

  try {
    const signals = await api.signals(5);
    lastSignal = signals[0] ?? null;
  } catch {
    /* ignore */
  }
  try {
    const alerts = await api.alerts(3);
    lastAlert = alerts[0] ?? null;
  } catch {
    /* ignore */
  }
  try {
    const news = await api.news();
    newsTitle = news.items[0]?.title ?? null;
  } catch {
    /* ignore */
  }
  let libraryCount: number | null = null;
  try {
    const lib = await api.library();
    libraryCount = lib.articles.length;
    const strat = agent?.strategy_type || "volatility";
    const match =
      lib.articles.find((a) => a.id.includes(strat)) ||
      lib.articles.find((a) => a.category.toLowerCase().includes("risco")) ||
      lib.articles[0];
    if (match) libraryTip = { title: match.title, id: match.id };
  } catch {
    /* ignore */
  }
  try {
    const st = await api.libraryStats();
    const total = Number(st.catalog_total ?? st.article_count ?? libraryCount);
    if (!Number.isNaN(total)) libraryCount = total;
  } catch {
    /* ignore */
  }

  const agentLine = agent
    ? `${agent.active_symbol || agent.symbols?.[0] || "—"} · ${agent.strategy_type} · risco ${agent.risk_per_trade_pct}%`
    : null;

  const insightSym =
    getViewSymbol() || agent?.active_symbol || agent?.symbols?.[0] || "PETR4";
  const symbolStrategy = await fetchSymbolStrategyStats(insightSym);

  renderInsightDeck({
    pnl,
    agent,
    lastSignal,
    lastAlert,
    newsTitle,
    libraryTip,
    agentLine,
    libraryCount,
    knowledgeLevel,
    agentKnowledgeLevel,
    agentLibraryStudy,
    tradeLearning,
    execution: lastExecutionStatus,
    systemState: ctx.state,
    symbolStrategy,
    onOpenLibrary: () => navigateToTab("biblioteca"),
    onOpenLibraryArticle: (_id: string) => navigateToTab("biblioteca"),
  });
  syncInsightDeckLiveContext(ctx.state, lastExecutionStatus, tradeLearning);
  syncHeaderXrayPopovers(
    {
      knowledgeLevel,
      agentKnowledgeLevel,
      agentLibraryStudy,
      tradeLearning,
      pnl,
      agent,
      execution: lastExecutionStatus,
      systemState: ctx.state,
      libraryCount,
    },
    () => navigateToTab("biblioteca"),
  );
}

let lastLiveQuote: LiveOpsQuote = null;
let quoteMids: Record<string, number> = {};
let opsFilter: OpsFilter = "today";
let lastClosedTrades: import("./api/client").TradeMetricsItem[] = [];

async function refreshLiveOps(pnl: PnlMetricsResponse | null): Promise<void> {
  try {
    const [signals, quoteRes, midsRes, tradesRes] = await Promise.all([
      api.signals(opsFilter === "today" ? 120 : 200),
      api.quote().catch(() => null),
      api.marketMids().catch(() => ({ mids: {} })),
      api.trades(opsFilter === "today", 200).catch(() => ({
        trades: [],
        global_summary: { trades: 0, wins: 0, losses: 0, net_pnl_brl: 0 },
        by_symbol: [],
      })),
    ]);
    if (quoteRes) {
      const mid = asFiniteNumberOrNull(quoteRes.mid);
      if (mid != null) {
        lastLiveQuote = { symbol: quoteRes.symbol, mid };
      }
    }
    quoteMids = midsRes.mids || {};
    if (lastLiveQuote) {
      quoteMids[lastLiveQuote.symbol.toUpperCase()] = lastLiveQuote.mid;
    }
    syncMarketTicker(quoteMids);
    lastClosedTrades = tradesRes.trades || [];
    recentSignals = signals;
    const refClose =
      riverBarsCache.length > 0 ? Number(riverBarsCache[riverBarsCache.length - 1].close) : null;
    const viewMid = resolveDisplayMid(lastLiveQuote, quoteMids, refClose);
    syncChartPrice(viewMid, refClose);
    renderLiveOps(pnl, signals, lastLiveQuote, quoteMids, lastClosedTrades, opsFilter);
  } catch {
    renderLiveOps(pnl, [], lastLiveQuote, quoteMids, lastClosedTrades, opsFilter);
  }
}

async function refreshLucrosFast(pnl: PnlMetricsResponse | null): Promise<void> {
  if (getActiveTab() !== "lucros") return;
  const host = document.getElementById("tab-lucros-body");
  if (!host) return;
  if (!host.querySelector("#lucros-kpi-grid")) mountLucrosPanel(host);
  const cache = await fetchLucrosLiveData(true);
  syncLucrosLive(pnl, {
    ...cache,
    mids: quoteMids,
    quote: lastLiveQuote,
  });
}

async function refreshActiveTabPanel(): Promise<void> {
  const tab = getActiveTab();
  if (tab === "biblioteca" && document.getElementById("zone-library-agent-progress")) {
    await refreshAgentLibraryProgress({ journal: true });
    return;
  }
  if (tab === "lucros" || tab === "agente" || tab === "biblioteca" || tab === "sistema") {
    await refreshTabPanel(tab, ctx);
    if (tab === "lucros") await refreshLucrosFast(ctx.pnl);
  }
}

function openZone(zone: ZoneId): void {
  activeZone = zone;
  openSheet(zone, ctx);
}

function updateSplitLayout(): void {
  applyDeckStageLayout(getActiveTab());
}

async function refreshQuoteLine(): Promise<void> {
  const line = $("quote-line");
  if (!line) return;
  try {
    const q = await api.quote();
    const mid = asFiniteNumberOrNull(q.mid);
    line.textContent = `${q.symbol} · ${mid != null ? safeFixed(mid, 2) : "—"}`;
  } catch {
    line.textContent = "Cotação: engine parado";
  }
}

async function refreshChartData(symbol: string, fullReload: boolean): Promise<void> {
  if (fullReload || symbol !== getViewSymbol() || riverBarsCache.length === 0) {
    setViewSymbol(symbol);
    await loadChart(symbol, chartTimeframe);
    return;
  }
  try {
    const [ohlc, signals] = await Promise.all([
      api.ohlc(symbol, chartTimeframe, CHART_OHLC_LIMIT),
      api.signals(60),
    ]);
    recentSignals = signals;
    chartMarkers = signalMarkersForSymbol(signals, symbol);
    chartLevels = chartLevelsFromSignals(signals, symbol);
    riverBarsCache = ohlc.bars;
    void refreshAgentStudy(symbol);
    paintChartCanvas();
  } catch {
    /* keep frame */
  }
}

let lastLoggedSignalKey = "";
let lastExecPollKey = "";
let lastExecutionStatus: ExecutionStatusRead | null = null;
let lastTradeLearning: import("./pulse/tradeLearning").TradeLearningSnapshot | null = null;

async function refreshAgentLibraryProgress(opts?: { journal?: boolean }): Promise<{
  agentKnowledgeLevel: KnowledgeLevel | null;
  agentLibraryStudy: AgentLibraryStudyStatus | null;
}> {
  const [agentKnowledgeLevel, agentLibraryStudy] = await Promise.all([
    fetchAgentKnowledgeLevel(),
    fetchAgentLibraryStudyStatus(),
  ]);
  syncAgentStudy24hBadge(Boolean(agentLibraryStudy?.auto_study_enabled));
  syncAgentLibraryStudyDom(agentKnowledgeLevel, agentLibraryStudy);
  syncHeaderXrayLiveContext(
    { agentLibraryStudy, agentKnowledgeLevel },
    () => navigateToTab("biblioteca"),
  );
  if (opts?.journal !== false && getActiveTab() === "biblioteca") {
    syncAgentJournalDom(await fetchAgentJournal());
  }
  return { agentKnowledgeLevel, agentLibraryStudy };
}

const MT5_AUTOTRADING_HINT =
  "MT5: ative «Negociação algorítmica» na barra (botão verde). Desligado → retcode 10027 (AutoTrading disabled).";

function appendMt5AutotradingHintIfNeeded(...parts: (string | null | undefined)[]): void {
  const text = parts.filter(Boolean).join(" ");
  if (/10027|autotrading disabled/i.test(text)) {
    appendEngineLog("info", MT5_AUTOTRADING_HINT);
  }
}

async function handleBoletaExecute(
  side: "BUY" | "SELL",
  payload: { symbol: string; quantity: number; stop: number | null },
): Promise<void> {
  appendEngineLog("order", `${side === "BUY" ? "Compra" : "Venda"} ${payload.quantity} ${payload.symbol} enviada…`);
  try {
    const res = await api.executeOrder({
      symbol: payload.symbol,
      side,
      quantity: payload.quantity,
      stop: payload.stop,
    });
    const detail =
      res.mt5_sent && res.mt5_ok
        ? `MT5 OK · ${res.message || res.signal?.execution_message || ""}`
        : res.db_only
          ? `Somente SQLite · ${res.message || ""}`
          : res.message || `Ordem aceita · ${payload.symbol}`;
    appendEngineLog("order", detail);
    appendMt5AutotradingHintIfNeeded(detail, res.message, res.signal?.execution_message);
    if (res.mt5_sent) {
      appendEngineLog(
        "order",
        res.mt5_ok
          ? `ORDEM MT5 preenchida · ${payload.symbol} · ${res.signal?.status ?? ""}`
          : `ORDEM MT5 rejeitada · ${res.message ?? ""}`,
      );
      appendMt5AutotradingHintIfNeeded(res.message, res.signal?.execution_message);
    }
    await pollFast();
    await refreshLiveOps(ctx.pnl);
  } catch (err) {
    const msg = err instanceof Error ? err.message : "Falha ao executar ordem";
    appendEngineLog(
      "order",
      `POST /orders/execute indisponível (${msg}) — aguardando backend`,
    );
  }
}

function initChartTimeframes(): void {
  try {
    const stored = localStorage.getItem(TF_STORAGE_KEY);
    if (stored && document.querySelector(`[data-tf="${stored}"]`)) chartTimeframe = stored;
  } catch {
    /* ignore */
  }
  document.querySelectorAll<HTMLButtonElement>(".deck-tf-pill[data-tf]").forEach((btn) => {
    const tf = btn.dataset.tf;
    if (!tf) return;
    btn.classList.toggle("active", tf === chartTimeframe);
    btn.addEventListener("click", () => {
      if (tf === chartTimeframe) return;
      chartTimeframe = tf;
      try {
        localStorage.setItem(TF_STORAGE_KEY, tf);
      } catch {
        /* ignore */
      }
      document.querySelectorAll(".deck-tf-pill[data-tf]").forEach((b) =>
        b.classList.toggle("active", (b as HTMLButtonElement).dataset.tf === tf),
      );
      const sym = getViewSymbol() || ctx.agent?.active_symbol || "PETR4";
      resetChartViewForSymbol(sym);
      void loadChart(sym, tf);
      appendEngineLog("info", `Timeframe ${tf} · recarregando OHLC/SMC`);
    });
  });
}

async function pollFast(): Promise<void> {
  if (fastPollBusy) return;
  fastPollBusy = true;
  const banner = $("offline-banner");
  const t0 = performance.now();
  try {
    await api.health();
    setLatency(performance.now() - t0);
    logLatency(performance.now() - t0);
    setChip("chip-api", "API OK", true);
    banner?.classList.add("hidden");

    const [state, pnl, agent] = await Promise.all([
      api.systemState(),
      api.pnl(),
      api.agentConfig(),
    ]);
    ctx = { state, pnl, agent };
    logHeartbeat(Boolean(state.engine_online), state.last_heartbeat);
    syncWatchlistFromAgent(agent);
    applyStrategyBadge(agent, null);
    applyEngineUi(state);
    applyPnlDisplay(pnl);
    void refreshLiveOps(pnl);
    void refreshLucrosFast(pnl);
    void refreshMarketTickerSummary().then((ok) => {
      syncMarketTicker(quoteMids);
      if (isTickersSummaryApiAvailable() === false) {
        appendEngineLogOnce(
          "info",
          "Ticker tape: GET /market/tickers-summary ausente · usando fallback local + mids",
          "ticker-fallback",
        );
      } else if (ok) {
        appendEngineLogOnce("info", "Ticker tape sincronizado via /market/tickers-summary", "ticker-api");
      }
    });
    void refreshAgentStudy(getViewSymbol() || agent?.active_symbol || "PETR4");

    const sym = getViewSymbol() || agent?.active_symbol || agent?.symbols?.[0] || "PETR4";
    if (!getViewSymbol()) setViewSymbol(sym);
    void syncSymbolStrategyCard(sym);
    const symbolChanged = sym !== lastLoadedChartSymbol;
    await Promise.all([refreshChartData(sym, symbolChanged), refreshQuoteLine()]);
    const sig = pickLatestSignalForSymbol(recentSignals, sym);
    renderDecisionPanel(sym, sig);
    const sigKey = sig ? `${sig.id}:${sig.status}:${sig.side}` : "";
    if (sigKey && sigKey !== lastLoggedSignalKey) {
      lastLoggedSignalKey = sigKey;
      appendEngineLog("signal", `Sinal ${sig!.side} ${sig!.symbol} · ${sig!.status}`);
      if (sig!.status === "filled" || sig!.status === "sent") {
        const em = sig!.execution_message || "";
        if (sig!.status === "filled" || em.toLowerCase().includes("mt5")) {
          appendEngineLog("order", `ORDEM · ${sig!.side} ${sig!.symbol} · ${sig!.status} · ${em}`);
          appendMt5AutotradingHintIfNeeded(em);
        } else {
          appendEngineLog("order", `Ordem ${sig!.side} registrada · ${sig!.symbol}`);
        }
      }
    }

    try {
      const exec = await api.executionStatus();
      lastExecutionStatus = exec;
      applyBoletaExecutionGate(state, exec);
      syncOvernightBadge(Boolean((exec as { overnight_learning?: boolean }).overnight_learning));
      const e = exec as {
        engine_online?: boolean;
        operating_mode?: string;
        mt5_connected?: boolean;
      };
      const sb = exec.structured_blockers;
      const execKey = `${e.engine_online}:${e.operating_mode}:${e.mt5_connected}:${sb?.session_hours}:${sb?.mt5_trade_allowed}:${sb?.experts_ini_enabled}`;
      if (execKey !== lastExecPollKey) {
        lastExecPollKey = execKey;
        appendEngineLog(
          "heartbeat",
          `Exec · ${e.operating_mode ?? "—"} · MT5 ${e.mt5_connected ? "on" : "off"}`,
        );
        if (sb?.session_hours && sb.session_hours_message) {
          appendEngineLog("info", `Horário B3: ${sb.session_hours_message}`);
        }
        if (sb?.mt5_trade_allowed && sb.mt5_trade_allowed_message && !exec.can_send_orders) {
          appendEngineLog("info", sb.mt5_trade_allowed_message);
        }
        if (sb?.experts_ini_enabled && sb.experts_ini_message && !exec.can_send_orders) {
          appendEngineLog("info", sb.experts_ini_message);
        }
      }
    } catch {
      /* optional */
    }

    if (getActiveTab() === "painel") {
      syncInsightDeckLiveContext(ctx.state, lastExecutionStatus, lastTradeLearning);
    }
    syncHeaderXrayLiveContext(
      {
        systemState: ctx.state,
        execution: lastExecutionStatus,
        tradeLearning: lastTradeLearning,
        pnl: ctx.pnl,
        agent: ctx.agent,
      },
      () => navigateToTab("biblioteca"),
    );

    touchLastUpdate(true);
    void refreshAgentLibraryProgress({ journal: false });
  } catch {
    setLatency(null);
    setChip("chip-api", "API offline", false);
    banner?.classList.remove("hidden");
    applyEngineUi(null);
    appendEngineLog("info", "Falha na comunicação com a API");
    touchLastUpdate(false);
  } finally {
    fastPollBusy = false;
  }
}

async function pollSlow(): Promise<void> {
  if (slowPollBusy) return;
  slowPollBusy = true;
  try {
    if (!apiOnline) return;

    const sym = getViewSymbol() || ctx.agent?.active_symbol || ctx.agent?.symbols?.[0] || "PETR4";
    try {
      const [ohlc, signals, series, structure] = await Promise.all([
        api.ohlc(sym, chartTimeframe, CHART_OHLC_LIMIT),
        api.signals(60),
        api.strategySeries(sym, chartTimeframe, CHART_OHLC_LIMIT).catch(() => null),
        api.marketStructure(sym, chartTimeframe, CHART_STRUCTURE_LIMIT).catch(() => null),
      ]);
      recentSignals = signals;
      chartMarkers = signalMarkersForSymbol(signals, sym);
      chartLevels = chartLevelsFromSignals(signals, sym);
      riverBarsCache = ohlc.bars;
      strategySeriesCache = series;
      if (structure) structureCache = structure;
      void refreshAgentStudy(sym);
      paintChartCanvas();
    } catch {
      /* keep frame */
    }

    await loadInsights(ctx.pnl, ctx.agent);
    if (activeZone) await refreshSheetBody(activeZone, ctx);
    await refreshActiveTabPanel();
    await refreshTickerGrid(getWatchlistSymbols(), recentSignals);
    mountDayTimeline((z) => openZone(z));
  } finally {
    slowPollBusy = false;
  }
}

async function refresh(): Promise<void> {
  await pollFast();
  await pollSlow();
}

function initApiUrl(): void {
  const input = $("api-url") as HTMLInputElement | null;
  if (!input) return;
  if (!input.value) input.value = apiBase();
  input.addEventListener("change", () => {
    persistApiBase();
    refresh();
  });
}

function initControls(): void {
  document.querySelectorAll<HTMLButtonElement>("[data-chart-range]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const mode = btn.dataset.chartRange as "session" | "recent" | "all" | undefined;
      if (mode) setChartTimeRange(mode);
    });
  });
  const structToggle = $("chart-structure-toggle") as HTMLInputElement | null;
  if (structToggle) {
    structToggle.checked = readStructureToggleDefault();
    setStructureLayerEnabled(structToggle.checked);
    structToggle.addEventListener("change", () => {
      setStructureLayerEnabled(structToggle.checked);
      persistStructureToggle(structToggle.checked);
      paintChartCanvas();
    });
  }
  $("btn-pause")?.addEventListener("click", async () => {
    await api.patchState({ engine_paused: true });
    await refresh();
  });
  $("btn-resume")?.addEventListener("click", async () => {
    await api.patchState({ engine_paused: false });
    await refresh();
  });
  $("btn-flatten")?.addEventListener("click", async () => {
    if (
      !confirm(
        "Emergência: zerar posições abertas, cancelar pendentes e pausar o motor?\n\n" +
          "O REALIZADO do dia não zera — só o histórico de trades já fechados.",
      )
    ) {
      return;
    }
    try {
      const res = await api.flattenSystem();
      const closedToday = ctx.pnl ? resolveTodayClosedNet(ctx.pnl) : 0;
      clearPositionsAfterFlatten(closedToday);
      appendEngineLog("order", res.message || "ZERAR: posições encerradas · MTM zerado");
      appendEngineLog(
        "info",
        "Motor pausado após ZERAR — clique Retomar (menu) ou confirme abaixo para voltar a operar.",
      );
      await refresh();
      await pollFast();
      if (
        confirm(
          "Posições zeradas e motor pausado (segurança).\n\n" +
            "Clique OK para retomar agora e voltar a enviar ordens (boleta/MT5).\n" +
            "Cancelar mantém pausado — use Retomar quando quiser.",
        )
      ) {
        await api.patchState({ engine_paused: false });
        appendEngineLog("info", "Motor retomado — ordens liberadas (se política permitir).");
        await refresh();
        await pollFast();
      }
    } catch (e) {
      appendEngineLog("info", e instanceof Error ? e.message : "Falha no flatten");
    }
  });
}

async function boot(): Promise<void> {
  document.body.classList.add("deck-v2-body");
  window.PULSE_DECK_VERSION = PULSE_DECK_VERSION;

  mountMarketTicker();
  initEngineLog();
  appendEngineLog(
    "info",
    `[SYSTEM] Pulse Deck Pro v${PULSE_DECK_VERSION} iniciado. Motor SMC e conectores B3 ativos.`,
  );
  initDeckSplitResize();

  const canvas = $("river-chart") as HTMLCanvasElement | null;
  if (canvas) bindRiverChart(canvas);
  const tradeHost = $("trade-chart-host");
  if (tradeHost) {
    setStructureLayerEnabled(readStructureToggleDefault());
    bindTradeChart(tradeHost);
    useTradeChart = true;
    if (canvas) canvas.classList.add("hidden");
    requestAnimationFrame(() => {
      resizeTradeChart();
      paintChartCanvas();
    });
  }

  initWatchlist({
    onViewSymbol: (symbol) => {
      setViewSymbol(symbol);
      void loadChart(symbol);
    },
    onSetActiveSymbol: async (symbol) => {
      await api.patchAgentConfig({ active_symbol: symbol });
      const agent = await api.agentConfig();
      ctx.agent = agent;
      syncWatchlistFromAgent(agent);
      await refresh();
    },
    onSymbolsChange: async (symbols) => {
      await api.patchAgentConfig({ symbols });
      const agent = await api.agentConfig();
      ctx.agent = agent;
      syncWatchlistFromAgent(agent);
    },
  });

  bindTickerRailSymbol((symbol) => {
    const sym = symbol.toUpperCase();
    setViewSymbol(sym);
    void loadChart(sym);
  });

  initApiUrl();
  initControls();
  initHeaderXrayPopovers(() => navigateToTab("biblioteca"));
  initChartTimeframes();
  window.addEventListener("pulse-deck-metrics-reset", () => {
    void refresh();
    void pollFast();
  });
  window.addEventListener(LIBRARY_READ_CHANGED_EVENT, () => {
    void loadInsights(ctx.pnl, ctx.agent);
    if (getActiveTab() === "biblioteca") void refreshTabPanel("biblioteca", ctx);
  });
  void hydrateReadProgressFromApi().then(() => loadInsights(ctx.pnl, ctx.agent));
  bindBoleta(handleBoletaExecute, () =>
    applyBoletaExecutionGate(ctx.state, lastExecutionStatus),
  );
  initSheetChrome();

  bindOpsFilters((f) => {
    opsFilter = f;
    void refreshLiveOps(ctx.pnl);
  });

  initPulseTabs((tab) => {
    updateSplitLayout();
    requestAnimationFrame(() => resizeTradeChart());
    if (tab === "ops") void refreshLiveOps(ctx.pnl);
    if (tab === "painel") void loadInsights(ctx.pnl, ctx.agent);
    if (tab === "lucros" || tab === "agente" || tab === "biblioteca" || tab === "sistema") {
      void refreshTabPanel(tab, ctx);
      if (tab === "lucros") void refreshLucrosFast(ctx.pnl);
    }
  });
  updateSplitLayout();

  mountDayTimeline((z) => openZone(z));

  initCommandBar({
    onZone: (z) => openZone(z),
    onTab: (tab) => navigateToTab(tab),
    onTicker: async (symbol) => {
      setViewSymbol(symbol);
      await loadChart(symbol);
    },
    symbols: ["WINFUT", "PETR4", "VALE3", "ITUB4", "BBDC4"],
  });

  try {
    const agent = await api.agentConfig();
    setViewSymbol(agent.active_symbol || agent.symbols?.[0] || "PETR4");
    syncWatchlistFromAgent(agent);
  } catch {
    setViewSymbol("PETR4");
  }

  await refresh();
  void refreshActiveTabPanel();
  window.setInterval(() => pollFast(), POLL_FAST_MS);
  window.setInterval(() => pollSlow(), POLL_SLOW_MS);
  window.addEventListener("resize", () => resizeTradeChart());
}

boot();
