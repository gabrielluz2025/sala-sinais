import { api } from "../api/client";

export type TradeLearningRolling = {
  win_rate_pct?: number | null;
  trades?: number;
  wins?: number;
  losses?: number;
  net_pnl_brl?: number;
  window?: number;
};

export type TradeLearningSnapshot = {
  performance_learning?: {
    rolling?: TradeLearningRolling;
    global?: TradeLearningRolling;
    best_strategy?: { id?: string; win_rate_pct?: number | null } | null;
    worst_strategy?: { id?: string; win_rate_pct?: number | null } | null;
    soft_guards?: { active?: boolean; reasons?: string[] };
  };
  insights_pt?: string[];
  last_insight?: string | null;
  auto_learn_enabled?: boolean;
};

export async function fetchTradeLearning(): Promise<TradeLearningSnapshot | null> {
  try {
    return (await api.learningStats()) as TradeLearningSnapshot;
  } catch {
    return null;
  }
}

function fmtPct(v: number | null | undefined): string {
  if (v == null || Number.isNaN(v)) return "—";
  return `${v.toFixed(0)}%`;
}

function stratLabel(id: string | undefined): string {
  if (id === "breakout") return "Breakout";
  if (id === "volatility") return "Volatilidade";
  return id || "—";
}

function pickRollingStats(data: TradeLearningSnapshot | null): TradeLearningRolling | null {
  const pl = data?.performance_learning;
  if (!pl) return null;
  const rolling = pl.rolling;
  if (rolling && (rolling.trades ?? 0) > 0) return rolling;
  const global = pl.global;
  if (global && (global.trades ?? 0) > 0) return global;
  return null;
}

export function tradeLearningCardHtml(data: TradeLearningSnapshot | null): string {
  const stats = pickRollingStats(data);
  if (!data?.performance_learning || !stats) {
    return `<article class="kpi-card kpi-trade-learning" id="trade-learning-card">
      <h4 class="kpi-label">Aprendizado com trades</h4>
      <p class="kpi-sub muted">0 fechados no histórico — rode simulação ou feche posições na Ops</p>
    </article>`;
  }
  const rolling = stats;
  const wr = fmtPct(rolling.win_rate_pct);
  const best = data.performance_learning.best_strategy;
  const worst = data.performance_learning.worst_strategy;
  const insight = data.last_insight || data.insights_pt?.[0] || "—";
  const guard = data.performance_learning.soft_guards?.active
    ? `<span class="kpi-sub muted">Guarda ativa: cooldown↑ · filtro de sinais fracos</span>`
    : "";
  return `<article class="kpi-card kpi-trade-learning" id="trade-learning-card">
    <h4 class="kpi-label">Aprendizado com trades</h4>
    <p class="kpi-value kpi-value-sm">WR ${wr}</p>
    <span class="kpi-sub">Últimos ${rolling?.trades ?? "—"} fechados</span>
    <span class="kpi-sub">Melhor: ${stratLabel(best?.id)} ${fmtPct(best?.win_rate_pct)} · Pior: ${stratLabel(worst?.id)} ${fmtPct(worst?.win_rate_pct)}</span>
    <span class="kpi-sub muted trade-learning-insight">${insight}</span>
    ${guard}
  </article>`;
}
