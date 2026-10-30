import { api, type TradeMetricsItem } from "../api/client";

export type StrategyBucket = {
  trades: number;
  win_rate_pct: number | null;
  net_pnl_brl: number;
};

export type SymbolStrategySnapshot = {
  symbol: string;
  breakout: StrategyBucket | null;
  volatility: StrategyBucket | null;
};

function esc(s: string): string {
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

function fmtBrl(n: number | null | undefined): string {
  if (n == null || Number.isNaN(n)) return "—";
  return n.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}

function fmtPct(n: number | null | undefined): string {
  if (n == null || Number.isNaN(n)) return "—";
  return `${n.toFixed(0)}%`;
}

function normalizeStrategy(st: string | null | undefined): "breakout" | "volatility" {
  const s = (st || "volatility").trim().toLowerCase();
  return s === "breakout" ? "breakout" : "volatility";
}

export function aggregateTradesByStrategy(
  trades: TradeMetricsItem[],
): Record<"breakout" | "volatility", StrategyBucket | null> {
  const groups: Record<"breakout" | "volatility", TradeMetricsItem[]> = {
    breakout: [],
    volatility: [],
  };
  for (const t of trades) {
    groups[normalizeStrategy(t.strategy_type)].push(t);
  }
  const bucket = (items: TradeMetricsItem[]): StrategyBucket | null => {
    if (!items.length) return null;
    const wins = items.filter((t) => t.win).length;
    const net = items.reduce((s, t) => s + t.net_pnl, 0);
    return {
      trades: items.length,
      win_rate_pct: items.length ? (wins / items.length) * 100 : null,
      net_pnl_brl: Math.round(net * 100) / 100,
    };
  };
  return {
    breakout: bucket(groups.breakout),
    volatility: bucket(groups.volatility),
  };
}

export async function fetchSymbolStrategyStats(symbol: string): Promise<SymbolStrategySnapshot> {
  const sym = (symbol || "PETR4").toUpperCase().trim();
  try {
    const res = await api.trades({ symbol: sym, limit: 200, todayOnly: false });
    const by = aggregateTradesByStrategy(res.trades || []);
    return { symbol: sym, breakout: by.breakout, volatility: by.volatility };
  } catch {
    return { symbol: sym, breakout: null, volatility: null };
  }
}

function rowHtml(label: string, b: StrategyBucket | null, isActive: boolean): string {
  if (!b || b.trades <= 0) {
    const hint = isActive ? " · estratégia ativa do agente" : "";
    return `<div class="kpi-strat-row"><span class="kpi-sub">${esc(label)}</span><span class="kpi-sub muted">0 fechados${hint}</span></div>`;
  }
  const tone = b.net_pnl_brl > 0 ? "positive" : b.net_pnl_brl < 0 ? "negative" : "";
  return `<div class="kpi-strat-row">
    <span class="kpi-sub">${esc(label)}</span>
    <span class="kpi-sub">${b.trades} trade${b.trades === 1 ? "" : "s"} · WR ${fmtPct(b.win_rate_pct)} · <span class="mono-num ${tone}">${fmtBrl(b.net_pnl_brl)}</span></span>
  </div>`;
}

export function symbolStrategyCardHtml(
  data: SymbolStrategySnapshot | null,
  activeStrategy?: string | null,
): string {
  const sym = esc(data?.symbol || "—");
  const strat = (activeStrategy || "").toLowerCase();
  const body =
    data == null
      ? '<p class="kpi-sub muted">Sem histórico ou API indisponível</p>'
      : `${rowHtml("Breakout", data.breakout, strat === "breakout")}${rowHtml("Volatilidade", data.volatility, strat === "volatility")}`;
  const emptyBoth =
    data != null && !data.breakout?.trades && !data.volatility?.trades
      ? `<p class="kpi-sub muted">Nenhum trade fechado em ${sym} ainda — histórico aparece após simulação ou fechamentos na Ops.</p>`
      : "";
  return `<details class="kpi-card kpi-symbol-strategy kpi-strategy-fold" id="symbol-strategy-card">
    <summary class="kpi-strategy-fold-summary">
      <span class="kpi-label">${sym}: breakout vs volatilidade</span>
      <span class="kpi-strategy-fold-hint muted">Histórico por estratégia</span>
    </summary>
    <div class="kpi-strategy-fold-body">
      <h4 class="kpi-label kpi-strategy-fold-title">${sym}: breakout vs volatilidade</h4>
      ${emptyBoth}
      ${body}
      <span class="kpi-sub muted">Trades fechados deste ativo (histórico)</span>
    </div>
  </details>`;
}

let lastSymbolStrategyKey = "";

/** Atualiza só o card no painel sem re-renderizar o deck inteiro. */
export async function syncSymbolStrategyCard(symbol: string): Promise<void> {
  const host = document.getElementById("symbol-strategy-card");
  if (!host) return;
  const snap = await fetchSymbolStrategyStats(symbol);
  const key = `${snap.symbol}:${snap.breakout?.trades}:${snap.volatility?.trades}:${snap.breakout?.net_pnl_brl}:${snap.volatility?.net_pnl_brl}`;
  if (key === lastSymbolStrategyKey) return;
  lastSymbolStrategyKey = key;
  host.outerHTML = symbolStrategyCardHtml(snap);
}
