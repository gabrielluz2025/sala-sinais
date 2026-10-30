import type { PnlMetricsResponse, TradeMetricsItem } from "../api/client";

function fmtBrl(n: number): string {
  return n.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}

export type ClosedTradeStats = {
  avgWin: number | null;
  avgLoss: number | null;
  totalFees: number;
  wins: number;
  losses: number;
};

export function computeClosedTradeStats(trades: TradeMetricsItem[]): ClosedTradeStats {
  const closed = trades.filter((t) => t.closed_at);
  let winSum = 0;
  let winN = 0;
  let lossSum = 0;
  let lossN = 0;
  let totalFees = 0;
  for (const t of closed) {
    totalFees += t.fees ?? 0;
    if (t.net_pnl > 0) {
      winSum += t.net_pnl;
      winN += 1;
    } else if (t.net_pnl < 0) {
      lossSum += t.net_pnl;
      lossN += 1;
    }
  }
  return {
    avgWin: winN ? winSum / winN : null,
    avgLoss: lossN ? lossSum / lossN : null,
    totalFees,
    wins: winN,
    losses: lossN,
  };
}

export type EquityCurvePoint = {
  cum: number;
  closedAt: string;
  index: number;
};

export type EquityDayStats = {
  points: EquityCurvePoint[];
  current: number;
  peak: number;
  maxDrawdown: number;
};

export function buildEquityCurve(trades: TradeMetricsItem[]): EquityDayStats {
  const closed = [...trades]
    .filter((t) => t.closed_at)
    .sort((a, b) => String(a.closed_at).localeCompare(String(b.closed_at)));
  let cum = 0;
  const points: EquityCurvePoint[] = closed.map((t, index) => {
    cum += t.net_pnl;
    return { cum, closedAt: String(t.closed_at), index: index + 1 };
  });
  let peak = 0;
  let maxDrawdown = 0;
  for (const p of points) {
    if (p.cum > peak) peak = p.cum;
    const dd = peak - p.cum;
    if (dd > maxDrawdown) maxDrawdown = dd;
  }
  const current = points.length ? points[points.length - 1].cum : 0;
  if (points.length === 0) {
    peak = 0;
  }
  return { points, current, peak, maxDrawdown };
}

export function formatEquityCaption(stats: EquityDayStats): string {
  if (stats.points.length < 2) {
    return "Curva disponível com 2+ trades fechados hoje.";
  }
  return `Pico ${fmtBrl(stats.peak)} · Drawdown máx. ${fmtBrl(stats.maxDrawdown)} · Atual ${fmtBrl(stats.current)}`;
}

export function buildHeroContext(pnl: PnlMetricsResponse | null): string {
  const closed = pnl?.daily?.closed_trades ?? 0;
  const wr = pnl?.daily?.win_rate_pct;
  const wrTxt = wr != null && !Number.isNaN(wr) ? `${wr.toFixed(1)}% WR` : "WR —";
  return `${closed} fechados · ${wrTxt}`;
}

export function buildDayReading(
  pnl: PnlMetricsResponse | null,
  trades: TradeMetricsItem[],
  todayNet: number,
): string {
  const stats = computeClosedTradeStats(trades);
  const fees =
    pnl?.fees_paid_brl ??
    pnl?.daily?.fees_brl ??
    (stats.totalFees > 0 ? stats.totalFees : null);
  const closedN = pnl?.daily?.closed_trades ?? trades.filter((t) => t.closed_at).length;

  if (!closedN) {
    return "Nenhum trade fechado hoje ainda. O líquido e a curva de equity aparecem conforme as operações forem encerradas.";
  }

  const tone =
    todayNet > 0
      ? "sessão positiva"
      : todayNet < 0
        ? "sessão negativa"
        : "sessão neutra";

  const parts: string[] = [
    `Hoje: ${fmtBrl(todayNet)} (${tone}) em ${closedN} trade${closedN === 1 ? "" : "s"} fechado${closedN === 1 ? "" : "s"}.`,
  ];

  if (fees != null && fees > 0) {
    const feePct =
      todayNet !== 0
        ? Math.abs((fees / (Math.abs(todayNet) + fees)) * 100)
        : null;
    parts.push(
      feePct != null && Number.isFinite(feePct)
        ? `Taxas estimadas ${fmtBrl(fees)} (~${feePct.toFixed(0)}% do movimento bruto aprox.).`
        : `Taxas estimadas ${fmtBrl(fees)} no período.`,
    );
  }

  if (stats.avgWin != null && stats.avgLoss != null) {
    parts.push(
      `Média ganho ${fmtBrl(stats.avgWin)} vs perda ${fmtBrl(stats.avgLoss)} (${stats.wins}W / ${stats.losses}L).`,
    );
  } else if (stats.avgWin != null) {
    parts.push(`Média dos ganhos ${fmtBrl(stats.avgWin)} (${stats.wins} vitória${stats.wins === 1 ? "" : "s"}).`);
  } else if (stats.avgLoss != null) {
    parts.push(`Média das perdas ${fmtBrl(stats.avgLoss)} (${stats.losses} perda${stats.losses === 1 ? "" : "s"}).`);
  }

  const mtm = pnl?.open_positions_estimated_pnl ?? pnl?.session_today?.open_mtm_brl;
  if (mtm != null && Math.abs(mtm) > 0.01) {
    parts.push(`Aberto (MTM est.): ${fmtBrl(mtm)} — não entra no líquido de fechados.`);
  }

  return parts.join(" ");
}

export function directionBadge(net: number | null | undefined): { glyph: string; label: string } | null {
  if (net == null || Number.isNaN(net) || net === 0) return null;
  return net > 0
    ? { glyph: "↑", label: "Resultado positivo" }
    : { glyph: "↓", label: "Resultado negativo" };
}
