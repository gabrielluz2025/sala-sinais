import type { PnlMetricsResponse, SystemState } from "../api/client";
import { asFiniteNumber } from "../util/numbers";
import { openPositionsSubLabel, resolveOpenMtmBrl, resolveTodayClosedNet } from "./pnlDisplay";

function fmtBrl(n: number | null | undefined): string {
  if (n == null || Number.isNaN(n)) return "—";
  return n.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}

function fmtPct(n: number | null | undefined): string {
  if (n == null || Number.isNaN(n)) return "—";
  return `${asFiniteNumber(n, 0).toFixed(1)}%`;
}

function setText(id: string, text: string): void {
  const el = document.getElementById(id);
  if (el && el.textContent !== text) el.textContent = text;
}

function toneEl(el: HTMLElement | null, value: number): void {
  if (!el) return;
  el.classList.remove("positive", "negative", "neutral");
  if (value > 0) el.classList.add("positive");
  else if (value < 0) el.classList.add("negative");
  else el.classList.add("neutral");
}

function toneBubble(id: string, value: number): void {
  const el = document.getElementById(id);
  if (!el) return;
  el.classList.remove("kpi-up", "kpi-down", "kpi-flat");
  el.classList.add(value > 0 ? "kpi-up" : value < 0 ? "kpi-down" : "kpi-flat");
}

let lastClosedText = "";

export function syncOvernightBadge(active: boolean): void {
  const el = document.getElementById("chip-overnight");
  if (!el) return;
  el.classList.toggle("hidden", !active);
  el.classList.toggle("chip-live", active);
  el.classList.toggle("chip-neutral", !active);
  el.title = active
    ? "Aprendizado 24h — sinais sim e estudo até o pregão B3"
    : "Modo aprendizado até pregão B3";
}

/** Badge quando AGENT_AUTO_STUDY_LIBRARY=true (biblioteca; independente de pregão e live). */
export function syncAgentStudy24hBadge(active: boolean): void {
  const el = document.getElementById("chip-agent-study");
  if (!el) return;
  el.classList.toggle("hidden", !active);
  el.classList.toggle("chip-live", active);
  el.classList.toggle("chip-neutral", !active);
  el.textContent = "Estudo 24h ativo";
  el.title = active
    ? "Agente estudando library/articles (somente leitura; não envia ordens)"
    : "Estudo autônomo da biblioteca desligado (AGENT_AUTO_STUDY_LIBRARY=false)";
}

/** Single header flag: MODO LIVE / MODO SIMULAÇÃO (no duplicated suffix). */
export function syncModeBadge(state: SystemState | null): void {
  const el = document.getElementById("chip-modo");
  if (!el) return;
  const mode = (state?.mode ?? "").toString().trim().toLowerCase();
  let label = "MODO —";
  let live = false;
  if (/live|auto_mt5|live_mt5/.test(mode) && !/sim|paper|simulation/.test(mode)) {
    label = "MODO LIVE";
    live = true;
  } else if (/sim|paper|simulation/.test(mode)) {
    label = "MODO SIMULAÇÃO";
  } else if (mode) {
    label = `MODO ${mode.toUpperCase()}`;
  }
  el.textContent = label;
  el.classList.remove("chip-ok", "chip-bad", "chip-neutral", "chip-live");
  el.classList.add(live ? "chip-live" : "chip-neutral");
}

export function resetOpenMtmUi(closedTodayNet = 0): void {
  const mtm = 0;
  const dayTotal = closedTodayNet + mtm;
  const mtmEl = document.getElementById("today-mtm-amount");
  if (mtmEl) {
    mtmEl.textContent = fmtBrl(mtm);
    toneEl(mtmEl, mtm);
  }
  toneBubble("kpi-bubble-mtm", mtm);
  toneBubble("kpi-bubble-day-total", dayTotal);
  setText("kpi-day-total", fmtBrl(dayTotal));
  setText("kpi-open-pos", openPositionsSubLabel(0));
  const posDayReset = document.getElementById("trade-pos-day-pnl");
  if (posDayReset) {
    posDayReset.textContent = fmtBrl(closedTodayNet);
    toneEl(posDayReset, closedTodayNet);
  }
  const todayEl = document.getElementById("live-ops-today-net");
  if (todayEl) {
    todayEl.textContent = `${fmtBrl(closedTodayNet)} · MTM ${fmtBrl(mtm)}`;
    todayEl.classList.remove("positive", "negative");
    if (closedTodayNet > 0) todayEl.classList.add("positive");
    if (closedTodayNet < 0) todayEl.classList.add("negative");
  }
}

export function syncHeaderKpis(pnl: PnlMetricsResponse | null): void {
  const today = resolveTodayClosedNet(pnl);
  const mtm = resolveOpenMtmBrl(pnl);
  const dayTotal = today + mtm;
  const sess = pnl?.session_today;
  const closed = pnl?.daily?.closed_trades ?? 0;
  const dailyWins = pnl?.daily?.wins;
  const dailyLosses = pnl?.daily?.losses;
  const w = dailyWins ?? null;
  const l = dailyLosses ?? null;
  const winRate = pnl?.daily?.win_rate_pct;
  const fees = pnl?.fees_paid_brl ?? sess?.fees_open_est_brl ?? 0;
  const openCount = pnl?.open_positions_count ?? 0;
  const buys = sess?.buys ?? 0;
  const sells = sess?.sells ?? 0;
  const ir = sess?.estimated_ir_brl ?? pnl?.estimated_ir_brl;

  const closedEl = document.getElementById("today-result-amount");
  const closedText = fmtBrl(today);
  if (closedEl) {
    if (closedText !== lastClosedText) {
      closedEl.classList.add("bump");
      window.setTimeout(() => closedEl.classList.remove("bump"), 220);
      lastClosedText = closedText;
    }
    closedEl.textContent = closedText;
    toneEl(closedEl, today);
  }

  toneBubble("kpi-bubble-closed", today);
  toneBubble("kpi-bubble-mtm", mtm);
  toneBubble("kpi-bubble-day-total", dayTotal);

  const mtmEl = document.getElementById("today-mtm-amount");
  if (mtmEl) {
    mtmEl.textContent = fmtBrl(mtm);
    toneEl(mtmEl, mtm);
  }

  setText("kpi-day-total", fmtBrl(dayTotal));
  const posDay = document.getElementById("trade-pos-day-pnl");
  if (posDay) {
    posDay.textContent = fmtBrl(dayTotal);
    toneEl(posDay, dayTotal);
  }
  setText("kpi-closed-sub", `${closed} trade${closed === 1 ? "" : "s"} fechado${closed === 1 ? "" : "s"} hoje`);
  setText("kpi-open-pos", openPositionsSubLabel(openCount));
  setText("kpi-win-rate", closed > 0 && winRate != null ? `${fmtPct(winRate)} (${w ?? 0}/${closed})` : closed > 0 ? "—" : "0%");
  setText("kpi-wl", w != null && l != null ? `${w} / ${l}` : closed > 0 ? "—" : "0 / 0");
  setText("kpi-fees", fmtBrl(fees));
  setText("kpi-flow", `${buys} compras · ${sells} vendas`);
  setText("kpi-ir", ir != null && ir !== 0 ? fmtBrl(ir) : fmtBrl(0));
  setText("kpi-month", fmtBrl(pnl?.monthly?.net_pnl_brl ?? 0));

  const orbit = document.querySelector(".deck-kpi-orbit");
  orbit?.classList.remove("day-up", "day-down", "day-flat");
  orbit?.classList.add(dayTotal > 0 ? "day-up" : dayTotal < 0 ? "day-down" : "day-flat");
}
