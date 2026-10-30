import type { AgentStudyResponse, Signal } from "../api/client";
import type { ChartLevelLine, ChartMarker } from "./riverChart";
import { isOpenSignal } from "./signalRowPnl";

export { isOpenSignal } from "./signalRowPnl";

export function brtDateKeyFromNow(): string {
  return new Date().toLocaleDateString("en-CA", { timeZone: "America/Sao_Paulo" });
}

export function brtDateKeyFromIso(iso: string): string {
  return new Date(iso).toLocaleDateString("en-CA", { timeZone: "America/Sao_Paulo" });
}

function fmtPnlTooltip(s: Signal): string {
  const pnl = s.net_pnl_brl;
  if (pnl == null) return s.exit_reason || s.note || "";
  const brl = pnl.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
  return pnl >= 0 ? `Acerto ${brl}` : `Erro ${brl}`;
}

const STOP_COLOR = "rgba(248, 113, 113, 0.92)";
const TARGET_COLOR = "rgba(52, 211, 153, 0.92)";
const ENTRY_COLOR = "rgba(56, 189, 248, 0.92)";
const RANGE_COLOR = "rgba(251, 191, 36, 0.78)";

function levelLine(
  price: number,
  label: string,
  color: string,
  style: "solid" | "dashed" = "solid",
  width: 1 | 2 = 2,
): ChartLevelLine {
  return { price, label, color, style, width };
}

export function chartLevelsFromSignals(signals: Signal[], symbol: string): ChartLevelLine[] {
  const sym = symbol.toUpperCase();
  const open = signals.find((s) => s.symbol.toUpperCase() === sym && isOpenSignal(s));
  if (!open) return [];

  const lines: ChartLevelLine[] = [];
  if (Number.isFinite(open.entry)) {
    lines.push(levelLine(open.entry, "Entrada", ENTRY_COLOR, "solid", 2));
  }
  if (open.stop != null) lines.push(levelLine(open.stop, "Stop", STOP_COLOR, "solid", 2));
  if (open.target != null) lines.push(levelLine(open.target, "Alvo", TARGET_COLOR, "solid", 2));
  return lines;
}

export function chartLevelsFromStudy(study: AgentStudyResponse | null, existing: ChartLevelLine[]): ChartLevelLine[] {
  if (!study) return existing;
  const lines = [...existing];
  const hasStopTarget = lines.some((l) => l.label === "Stop" || l.label === "Alvo");

  const rec = study.recommendation;
  if (!hasStopTarget && rec.stop != null && rec.target != null) {
    if (rec.entry != null) lines.push(levelLine(rec.entry, "Entrada", ENTRY_COLOR, "solid", 2));
    lines.push(levelLine(rec.stop, "Stop", STOP_COLOR, "solid", 2));
    lines.push(levelLine(rec.target, "Alvo", TARGET_COLOR, "solid", 2));
  } else if (rec.entry != null && !lines.some((l) => l.label === "Entrada")) {
    lines.push(levelLine(rec.entry, "Entrada", ENTRY_COLOR, "dashed", 1));
  }

  const stratKey = study.active_strategy || rec.strategy_type;
  const strat = stratKey ? study.strategies[stratKey] : undefined;
  const playbook = study.trade_playbook?.example_levels;
  const isBreakout = stratKey === "breakout" || rec.strategy_type === "breakout";

  if (isBreakout) {
    const rh = strat?.levels?.range_high ?? playbook?.range_high;
    const rl = strat?.levels?.range_low ?? playbook?.range_low;
    if (rh != null && !lines.some((l) => l.label.startsWith("Topo"))) {
      lines.push(levelLine(rh, "Topo range", RANGE_COLOR, "dashed", 1));
    }
    if (rl != null && !lines.some((l) => l.label.startsWith("Fundo"))) {
      lines.push(levelLine(rl, "Fundo range", RANGE_COLOR, "dashed", 1));
    }
  }

  return lines;
}

export function signalMarkersForSymbol(signals: Signal[], symbol: string): ChartMarker[] {
  const sym = symbol.toUpperCase();
  const today = brtDateKeyFromNow();
  const symSignals = signals.filter((x) => x.symbol.toUpperCase() === sym);
  const out: ChartMarker[] = [];

  const open = symSignals.find(isOpenSignal);
  if (open) {
    const t = new Date(open.created_at).getTime() / 1000;
    out.push({
      time: t,
      price: open.entry,
      kind: "entry",
      side: open.side === "SELL" ? "SELL" : "BUY",
    });
  }

  const closedToday = symSignals.filter(
    (s) =>
      (s.status || "").toLowerCase() === "closed" &&
      brtDateKeyFromIso(s.created_at) === today &&
      s.net_pnl_brl != null,
  );

  for (const s of closedToday.slice(0, 6)) {
    const win = (s.net_pnl_brl ?? 0) > 0;
    const outcome = win ? ("win" as const) : ("loss" as const);
    const tip = fmtPnlTooltip(s);
    const t = new Date(s.created_at).getTime() / 1000;
    out.push({
      time: t,
      price: s.entry,
      kind: "entry",
      side: s.side === "SELL" ? "SELL" : "BUY",
      outcome,
      tooltip: tip,
    });
    const exitPx = s.exit_price ?? s.target ?? s.entry;
    const closedT = s.closed_at ? new Date(s.closed_at).getTime() / 1000 : t + 300;
    out.push({
      time: closedT,
      price: exitPx,
      kind: "exit",
      side: s.side === "SELL" ? "SELL" : "BUY",
      outcome,
      tooltip: tip,
    });
  }

  return out;
}

export function riskRewardRatio(entry: number, stop: number, target: number): string | null {
  const risk = Math.abs(entry - stop);
  const reward = Math.abs(target - entry);
  if (!Number.isFinite(risk) || risk < 1e-9) return null;
  return `${(reward / risk).toFixed(1)}:1`;
}
