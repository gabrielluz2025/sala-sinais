import {
  asFiniteNumberOrNull,
  sanitizeMidMap,
} from "../util/numbers";

const STORAGE_KEY = "sala_api_base";

export function apiBase(): string {
  const el = document.getElementById("api-url") as HTMLInputElement | null;
  const fromInput = el?.value?.trim();
  if (fromInput) return fromInput.replace(/\/$/, "");
  const stored = localStorage.getItem(STORAGE_KEY);
  if (stored) return stored.replace(/\/$/, "");
  return `${window.location.protocol}//${window.location.host}`;
}

export function persistApiBase(): void {
  const el = document.getElementById("api-url") as HTMLInputElement | null;
  if (el?.value) localStorage.setItem(STORAGE_KEY, el.value.trim());
}

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${apiBase()}${path}`, { cache: "no-store" });
  if (!res.ok) throw new Error(`${path} ${res.status}`);
  return res.json() as Promise<T>;
}

async function putJson<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${apiBase()}${path}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error((err as { detail?: string }).detail || `PUT ${path}`);
  }
  return res.json() as Promise<T>;
}

async function patch<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${apiBase()}${path}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error((err as { detail?: string }).detail || `PATCH ${path}`);
  }
  return res.json() as Promise<T>;
}

async function postQuery<T>(path: string, query: Record<string, string>): Promise<T> {
  const qs = new URLSearchParams(query).toString();
  const res = await fetch(`${apiBase()}${path}?${qs}`, { method: "POST" });
  if (!res.ok) throw new Error(`POST ${path}`);
  return res.json() as Promise<T>;
}

async function postJson<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${apiBase()}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    const raw = (err as { detail?: unknown }).detail;
    let detail = "";
    if (typeof raw === "string") {
      detail = raw;
    } else if (raw && typeof raw === "object" && "message" in raw) {
      const msg = (raw as { message?: unknown }).message;
      detail = typeof msg === "string" ? msg : JSON.stringify(raw);
    } else if (raw != null) {
      detail = JSON.stringify(raw);
    }
    const summary = `POST ${path} → HTTP ${res.status}`;
    throw new Error(detail ? `${summary}: ${detail}` : summary);
  }
  return res.json() as Promise<T>;
}

export type SystemState = {
  engine_paused: boolean;
  emergency_flatten: boolean;
  engine_online: boolean;
  mode: string;
  data_source?: string | null;
  mt5_connected?: boolean | null;
  operating_mode?: string | null;
  last_heartbeat?: string | null;
};

export type SystemFlattenResponse = {
  ok: boolean;
  message: string;
  emergency_flatten: boolean;
  engine_paused: boolean;
  positions_closed: number;
  signals_cancelled: number;
  state: SystemState;
};

export type PnlPeriodMetrics = {
  net_pnl_brl: number;
  closed_trades: number;
  wins?: number;
  losses?: number;
  win_rate_pct: number | null;
  fees_brl?: number;
};

export type SessionActivitySummary = {
  buys: number;
  sells: number;
  volume_shares: number;
  closed_net_brl: number;
  open_mtm_brl: number;
  fees_open_est_brl: number;
  estimated_ir_brl: number;
};

export type PnlMetricsResponse = {
  today_net: number;
  open_positions_estimated_pnl: number;
  open_positions_count: number;
  daily: PnlPeriodMetrics;
  monthly: PnlPeriodMetrics;
  all_time: PnlPeriodMetrics & { wins: number; losses: number };
  wins: number;
  losses: number;
  fees_paid_brl?: number;
  estimated_ir_brl?: number;
  net_after_tax_estimated_brl?: number;
  session_today?: SessionActivitySummary;
  recent_closed: Array<{
    id: number;
    symbol: string;
    net_pnl_brl: number;
    closed_at: string | null;
  }>;
};

export type TradeMetricsItem = {
  id: number;
  symbol: string;
  side: string;
  entry: number;
  exit: number;
  shares: number;
  gross_pnl: number;
  fees: number;
  net_pnl: number;
  opened_at: string;
  closed_at?: string | null;
  strategy_type?: string | null;
  entry_reason?: string | null;
  exit_reason?: string | null;
  win: boolean;
};

export type TradesMetricsResponse = {
  trades: TradeMetricsItem[];
  global_summary: {
    trades: number;
    wins: number;
    losses: number;
    net_pnl_brl: number;
  };
  by_symbol: Array<{
    symbol: string;
    trades: number;
    wins: number;
    losses: number;
    net_pnl_brl: number;
    win_rate?: number | null;
  }>;
};

export type Signal = {
  id: number;
  symbol: string;
  side: string;
  entry: number;
  stop?: number;
  target?: number;
  status: string;
  contracts?: number;
  mode?: string;
  execution_message?: string | null;
  exit_price?: number | null;
  gross_pnl_brl?: number | null;
  net_pnl_brl: number | null;
  created_at: string;
  closed_at?: string | null;
  strategy_type?: string | null;
  strategy_version?: string | null;
  entry_reason?: string | null;
  exit_reason?: string | null;
  regime?: string | null;
  note?: string | null;
};

export type StrategySeriesResponse = {
  symbol: string;
  timeframe: string;
  times: Array<number | null | undefined>;
  bb_upper: Array<number | null>;
  bb_mid: Array<number | null>;
  bb_lower: Array<number | null>;
  atr_pct_last: number;
  regime: string;
  regime_score: number;
  source?: string;
};

export type MarketStructureSwing = {
  time: number;
  price: number;
  kind: "high" | "low";
  label: string;
};

export type MarketStructureZone = {
  type: "supply" | "demand";
  price_top: number;
  price_bottom: number;
  time_start: number;
  time_end: number;
  label_pt: string;
};

export type MarketStructureFvg = {
  direction: "bullish" | "bearish";
  top: number;
  bottom: number;
  time: number;
  label_pt: string;
};

export type MarketStructureChoch = {
  direction: "bullish" | "bearish";
  price: number;
  time: number;
  label_pt: string;
  broken_swing_label?: string;
};

export type MarketStructureResponse = {
  symbol: string;
  timeframe: string;
  bars_analyzed: number;
  bars_total?: number;
  source?: string;
  swings: MarketStructureSwing[];
  zones: MarketStructureZone[];
  fvgs: MarketStructureFvg[];
  choch: MarketStructureChoch | null;
  trend_bias: "bullish" | "bearish" | "neutral";
  narrative_pt: string;
};

export type MarketStructureStudySnippet = {
  narrative_pt: string | null;
  trend_bias: string | null;
  choch: MarketStructureChoch | null;
};

export type AgentStudyResponse = {
  symbol: string;
  market: { bid: number; ask: number; mid: number };
  session: {
    now_brt: string;
    date_brt: string;
    phase: string;
    phase_label: string;
    in_session_window: boolean;
    engine_may_trade: boolean;
    engine_block_reason: string | null;
    trade_hours: string;
  };
  indicators: {
    atr_pct: number;
    bb_width_pct: number;
    regime: string;
    regime_score: number;
  };
  active_strategy: "breakout" | "volatility";
  sizing: {
    contracts: number;
    label: string;
    risk_per_trade_pct?: number;
    capital_brl?: number;
    stop_loss_pct?: number;
    take_profit_pct?: number;
    stop_points?: number;
    target_points?: number;
  };
  strategies: Record<
    string,
    {
      strategy_type: string;
      signal_ready: boolean;
      side: string | null;
      entry: number | null;
      stop: number | null;
      target: number | null;
      contracts: number;
      entry_reason: string;
      regime?: string | null;
      levels?: {
        range_high?: number;
        range_low?: number;
        last_close?: number;
        dist_to_buy_pct?: number;
        dist_to_sell_pct?: number;
      };
    }
  >;
  recommendation: {
    action: string;
    action_label: string;
    strategy_type: string;
    side: string | null;
    entry: number | null;
    stop: number | null;
    target: number | null;
    contracts: number | null;
    entry_reason: string | null;
    alternative_note: string | null;
  };
  last_order: {
    id: number;
    side: string;
    entry: number;
    stop: number;
    target: number;
    contracts: number;
    status: string;
    strategy_type: string | null;
    regime: string | null;
    entry_reason: string | null;
    created_at: string;
    is_demo: boolean;
  } | null;
  history?: {
    has_data: boolean;
    message?: string;
    m1_bars_count?: number;
    first_brt?: string;
    last_brt?: string;
    span_days?: number;
    period_low?: number;
    period_high?: number;
    period_return_pct?: number;
    vol_daily_pct?: number;
    narrative?: string;
    today_session?: {
      open: number | null;
      high: number | null;
      low: number | null;
      close: number | null;
      m1_bars: number;
    };
    fundamentals?: {
      name?: string;
      listed_b3?: string;
      sector?: string;
      note?: string;
    } | null;
  };
  candle_patterns?: CandlePatternsSection;
  market_structure?: MarketStructureStudySnippet | null;
  trade_playbook?: TradePlaybookSection;
};

export type TradePlaybookPillar = {
  stage: string;
  label_pt: string;
  rule_pt: string;
  detail_pt?: string;
};

export type TradePlaybookSection = {
  playbook: {
    strategy_type: string;
    title_pt: string;
    pillars: TradePlaybookPillar[];
    library_article_ids: string[];
    config_fields: string[];
  };
  example_levels: {
    scenario: string;
    side: string;
    entry_zone_pt: string;
    entry: number;
    stop: number;
    target: number;
    risk_distance: number;
    reward_distance: number;
    risk_reward_ratio: number | null;
    range_high?: number | null;
    range_low?: number | null;
    aligned_with_engine: boolean;
  };
  summary_chips: Array<{ key: string; label: string; text: string }>;
  forced_flat_note_pt: string;
};

export type CandlePatternHit = {
  id: string;
  label_pt: string;
  bias: string;
  library_article_id: string;
  strength?: number;
};

export type CandlePatternsSection = {
  symbol?: string;
  timeframe: string;
  engine: string;
  bars_analyzed: number;
  hits: Array<{
    bar_offset: number;
    time: number | null;
    patterns: CandlePatternHit[];
  }>;
  last_bar: {
    time?: number;
    open: number;
    high: number;
    low: number;
    close: number;
    patterns: CandlePatternHit[];
  } | null;
  summary_pt: string;
  talib_available?: boolean;
};

export type KnowledgeLevelResponse = {
  level_id: string;
  level_label: string;
  article_count: number;
  total_words: number;
  progress_pct: number;
  articles_progress_pct?: number;
  words_progress_pct?: number;
  next_level_id: string | null;
  next_level_label: string | null;
  articles_to_next: number;
  words_to_next: number;
  formula_note: string;
  progress_scope?: string;
  tiers?: { id: string; label: string; min_articles: number; min_words: number }[];
};

export type AgentLibraryStudyStatusResponse = {
  auto_study_enabled: boolean;
  state: string;
  studied_count: number;
  total_articles: number;
  level_id: string;
  level_label: string;
  progress_pct: number;
  last_studied_at: string | null;
  last_article_title: string | null;
  next_article_title: string | null;
  recently_active: boolean;
  studied_article_ids?: string[];
  operational_maturity_pct?: number;
  closed_trades_count?: number;
};

export type AgentConfig = {
  symbols: string[];
  active_symbol: string | null;
  rotate_symbols?: boolean;
  capital_brl: number;
  risk_per_trade_pct: number;
  max_position_brl?: number;
  shares_per_order?: number;
  stop_loss_pct?: number;
  take_profit_pct?: number;
  stop_points?: number;
  target_points?: number;
  asset_class?: string;
  use_news_filter?: boolean;
  strategy_type: string;
  applied_preset: string | null;
};

export type AgentTickerItem = { symbol: string; name: string };

export type LibraryIndex = {
  articles: Array<{ id: string; title: string; category: string; source?: string }>;
  categories: Array<{ id: string; label: string }>;
};

export type LibraryStatsResponse = {
  article_count: number;
  curated_count?: number;
  imported_count?: number;
  news_count: number;
  catalog_total: number;
  total_words?: number;
  categories?: Array<{ id: string; label: string; count: number }>;
};

export type OhlcResponse = {
  symbol: string;
  timeframe: string;
  bars: Array<{ time?: number; open: number; high: number; low: number; close: number }>;
  source?: string;
};

export type MarketTickerSummaryItem = {
  symbol: string;
  label?: string | null;
  price: number;
  change_pct: number;
};

export type MarketTickersSummaryResponse = {
  tickers: MarketTickerSummaryItem[];
  updated_at?: string | null;
};

export type Mt5TerminalChecklistStep = {
  id: string;
  label: string;
  done: boolean;
  blocked: boolean;
  message: string;
};

export type Mt5TerminalDiagnosticsRead = {
  available: boolean;
  error?: string | null;
  trade_allowed?: boolean | null;
  connected?: boolean | null;
  tradeapi_disabled?: boolean | null;
  company?: string | null;
  name?: string | null;
  terminal_executable_dir?: string | null;
  data_path?: string | null;
  checklist: Mt5TerminalChecklistStep[];
};

export type ExecutionChecklistStep = {
  id: string;
  label: string;
  done: boolean;
};

export type ExecutionBlockersStructured = {
  session_hours: boolean;
  session_hours_message?: string | null;
  mt5_trade_allowed: boolean;
  mt5_trade_allowed_message?: string | null;
  experts_ini_enabled: boolean;
  experts_ini_message?: string | null;
};

export type ExecutionStatusRead = {
  can_send_orders: boolean;
  can_execute: boolean;
  engine_online?: boolean;
  auto_execute_enabled: boolean;
  mode: string;
  live_trading: boolean;
  engine_paused: boolean;
  mt5_connected?: boolean | null;
  operating_mode?: string | null;
  auto_execute_orders: boolean;
  execute_on_demo: boolean;
  signal_mode: string;
  blockers: string[];
  structured_blockers?: ExecutionBlockersStructured;
  steps: ExecutionChecklistStep[];
  env_snippet_paper_demo: string;
  recommended_env_note?: string;
  live_trading_warning: boolean;
  overnight_learning?: boolean;
  mt5_path_env?: string | null;
  mt5_path_mismatch?: boolean;
  mt5_terminal?: Mt5TerminalDiagnosticsRead | null;
};

export type MarketQuoteResponse = {
  symbol: string;
  bid?: number;
  ask?: number;
  mid?: number;
  timestamp?: string;
  source?: string;
};

/** Normalize quote payload: prefer mid, else (bid+ask)/2. */
export function parseMarketQuote(raw: MarketQuoteResponse): { symbol: string; mid: number | null } {
  const mid = asFiniteNumberOrNull(raw.mid);
  if (mid != null) return { symbol: raw.symbol, mid };
  const bid = asFiniteNumberOrNull(raw.bid);
  const ask = asFiniteNumberOrNull(raw.ask);
  if (bid != null && ask != null) return { symbol: raw.symbol, mid: (bid + ask) / 2 };
  if (bid != null) return { symbol: raw.symbol, mid: bid };
  if (ask != null) return { symbol: raw.symbol, mid: ask };
  return { symbol: raw.symbol, mid: null };
}

export type OrderExecuteRequest = {
  symbol: string;
  side: "BUY" | "SELL";
  /** Ações/contratos (enviado como contracts no POST). */
  quantity: number;
  contracts?: number;
  stop?: number | null;
};

export type SystemResetSessionResponse = {
  ok: boolean;
  message: string;
  epoch_at: string;
  previous_epoch_at?: string | null;
};

export type OrderExecuteResponse = {
  ok: boolean;
  message: string;
  operating_mode: string;
  signal: Signal;
  mt5_sent?: boolean;
  mt5_ok?: boolean | null;
  db_only?: boolean;
};

export type AlertRead = {
  id: number;
  alert_type: "entry" | "exit";
  symbol: string;
  side?: string;
  price: number;
  note?: string | null;
  created_at: string;
  signal_id?: number | null;
};

export const api = {
  health: () => get<{ status: string }>("/health"),
  systemState: () => get<SystemState>("/system/state"),
  executionStatus: () => get<ExecutionStatusRead>("/system/execution-status"),
  patchState: (body: Partial<SystemState>) => patch<SystemState>("/system/state", body),
  flattenSystem: () => postJson<SystemFlattenResponse>("/system/flatten", {}),
  resetSession: () => postJson<SystemResetSessionResponse>("/system/reset-session", {}),
  pnl: () => get<PnlMetricsResponse>("/metrics/pnl"),
  signals: (limit = 80) => get<Signal[]>(`/signals?limit=${limit}`),
  trades: (
    todayOnlyOrOpts:
      | boolean
      | { todayOnly?: boolean; limit?: number; symbol?: string } = false,
    limit = 120,
  ) => {
    let todayOnly = false;
    let lim = limit;
    let symbol: string | undefined;
    if (typeof todayOnlyOrOpts === "object") {
      todayOnly = todayOnlyOrOpts.todayOnly ?? false;
      lim = todayOnlyOrOpts.limit ?? 120;
      symbol = todayOnlyOrOpts.symbol;
    } else {
      todayOnly = todayOnlyOrOpts;
      lim = limit;
    }
    const params = new URLSearchParams({
      limit: String(lim),
      today_only: String(todayOnly),
    });
    if (symbol) params.set("symbol", symbol.toUpperCase());
    return get<TradesMetricsResponse>(`/metrics/trades?${params}`);
  },
  marketMids: () =>
    get<{ mids: Record<string, number> }>("/market/mids").then((res) => ({
      mids: sanitizeMidMap(res.mids),
    })),
  tickersSummary: () => get<MarketTickersSummaryResponse>("/market/tickers-summary"),
  executeOrder: (body: OrderExecuteRequest) =>
    postJson<OrderExecuteResponse>("/orders/execute", {
      symbol: body.symbol,
      side: body.side,
      contracts: body.contracts ?? body.quantity,
      stop: body.stop ?? undefined,
    }),
  agentConfig: () => get<AgentConfig>("/agent/config"),
  patchAgentConfig: (body: Record<string, unknown>) =>
    patch<AgentConfig>("/agent/config", body),
  applyPreset: (name: string) => postQuery<AgentConfig>("/agent/config/apply-preset", { name }),
  library: () => get<LibraryIndex>("/library"),
  libraryArticle: (id: string) =>
    get<{ title: string; markdown: string }>(`/library/articles/${encodeURIComponent(id)}`),
  libraryStats: () => get<LibraryStatsResponse>("/library/stats"),
  knowledgeLevel: (readIds: string[] = []) => {
    const q =
      readIds.length > 0
        ? `?read_ids=${readIds.map((id) => encodeURIComponent(id)).join(",")}`
        : "?read_ids=";
    return get<KnowledgeLevelResponse>(`/library/knowledge-level${q}`);
  },
  knowledgeLevelAgent: () =>
    get<KnowledgeLevelResponse>("/library/knowledge-level?agent=true"),
  agentLibraryStudyStatus: () =>
    get<AgentLibraryStudyStatusResponse>("/library/agent-study-status"),
  agentJournal: () =>
    get<{
      markdown: string;
      win_count: number;
      close_count?: number;
      loss_count?: number;
      saved_since_first_win?: boolean;
      updated_at: string | null;
      last_win_at: string | null;
      last_study_at: string | null;
    }>("/library/agent-journal"),
  libraryReadProgress: () => get<{ read_article_ids: string[] }>("/library/read-progress"),
  putLibraryReadProgress: (readIds: string[], merge = true) =>
    putJson<{ read_article_ids: string[] }>("/library/read-progress", {
      read_article_ids: readIds,
      merge,
    }),
  learningStats: () => get<Record<string, unknown>>("/agent/learning-stats"),
  learningInsights: () => get<Record<string, unknown>>("/library/learning-insights"),
  quote: () =>
    get<MarketQuoteResponse>("/market/quote").then((raw) => {
      const parsed = parseMarketQuote(raw);
      return {
        symbol: parsed.symbol,
        mid: parsed.mid,
        bid: asFiniteNumberOrNull(raw.bid) ?? undefined,
        ask: asFiniteNumberOrNull(raw.ask) ?? undefined,
      };
    }),
  stats: () => get<{ total_signals: number; today_signals: number }>("/stats"),
  news: () => get<{ items: Array<{ title: string; url: string }> }>("/news/headlines?limit=6"),
  ohlc: (symbol: string, tf = "M5", limit = 100) =>
    get<OhlcResponse>(
      `/market/ohlc?symbol=${encodeURIComponent(symbol)}&tf=${encodeURIComponent(tf)}&limit=${limit}`,
    ),
  strategySeries: (symbol: string, tf = "M5", limit = 100) =>
    get<StrategySeriesResponse>(
      `/market/strategy-series?symbol=${encodeURIComponent(symbol)}&tf=${encodeURIComponent(tf)}&limit=${limit}`,
    ),
  marketStructure: (symbol: string, tf = "M5", limit = 280) =>
    get<MarketStructureResponse>(
      `/market/structure?symbol=${encodeURIComponent(symbol)}&tf=${encodeURIComponent(tf)}&limit=${limit}`,
    ),
  agentStudy: (symbol: string) =>
    get<AgentStudyResponse>(`/agent/study?symbol=${encodeURIComponent(symbol)}`),
  candlePatterns: (symbol: string, tf = "M5", lookback = 24) =>
    get<CandlePatternsSection & { symbol: string }>(
      `/agent/candle-patterns?symbol=${encodeURIComponent(symbol)}&tf=${encodeURIComponent(tf)}&lookback=${lookback}`,
    ),
  searchTickers: (q: string) =>
    get<{ tickers: AgentTickerItem[] }>(`/agent/tickers?q=${encodeURIComponent(q)}`),
  alerts: (limit = 12) => get<AlertRead[]>(`/alerts/recent?limit=${limit}`),
};

export async function exportLibrary(): Promise<Blob> {
  const res = await fetch(`${apiBase()}/library/export`, { cache: "no-store" });
  if (!res.ok) throw new Error("export failed");
  return res.blob();
}

export async function importLibrary(file: File, mode: "merge" | "replace"): Promise<unknown> {
  const fd = new FormData();
  fd.append("file", file);
  const res = await fetch(`${apiBase()}/library/import?mode=${mode}`, {
    method: "POST",
    body: fd,
  });
  if (!res.ok) throw new Error("import failed");
  return res.json();
}
