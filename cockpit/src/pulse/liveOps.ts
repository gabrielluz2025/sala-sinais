import type { PnlMetricsResponse, Signal, TradeMetricsItem } from "../api/client";
import { asFiniteNumber, asFiniteNumberOrNull, safeFixed } from "../util/numbers";
import { resetOpenMtmUi } from "./headerKpis";
import { resolveOpenMtmBrl, resolveTodayClosedNet } from "./pnlDisplay";
import { renderDepthBook } from "./depthBook";
import { getViewSymbol } from "./watchlist";
import {
  formatResultadoCellHtml,
  isOpenSignal,
  resolveRowPnl,
  type LiveOpsQuote,
} from "./signalRowPnl";

export type { LiveOpsQuote };
export type OpsFilter = "today" | "all";

function esc(s: string): string {
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

function fmtBrl(n: number | null | undefined): string {
  if (n == null || Number.isNaN(n)) return "—";
  return n.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}

function sideLabelPt(side: string): string {
  return side === "BUY" ? "Compra" : side === "SELL" ? "Venda" : side || "—";
}

function todayBrtPrefix(): string {
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: "America/Sao_Paulo",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(new Date());
  const y = parts.find((p) => p.type === "year")?.value ?? "";
  const m = parts.find((p) => p.type === "month")?.value ?? "";
  const d = parts.find((p) => p.type === "day")?.value ?? "";
  return `${y}-${m}-${d}`;
}

function executionMeta(s: Signal): { label: string; cls: string } {
  const st = (s.status || "").toLowerCase();
  const mode = ((s as Signal & { mode?: string }).mode || "paper").toLowerCase();
  if (st === "filled") return { label: "Executado", cls: "exec-filled" };
  if (st === "closed") return { label: "Encerrado", cls: "exec-closed" };
  if (st === "cancelled" || st === "rejected") return { label: st, cls: "exec-bad" };
  if (isOpenSignal(s)) return { label: "Aberta", cls: "exec-pending" };
  if (mode === "paper" && (st === "pending" || st === "sent"))
    return { label: "Simulado", cls: "exec-sim" };
  if (st === "pending" || st === "sent") return { label: "Pendente", cls: "exec-pending" };
  return { label: s.status || "—", cls: "exec-neutral" };
}

function formatTime(iso: string): string {
  try {
    return new Date(iso).toLocaleString("pt-BR", {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    });
  } catch {
    return iso;
  }
}

let lastMidForTone: number | null = null;

export function resolveViewMid(
  quote: LiveOpsQuote,
  mids: Record<string, number>,
): number | null {
  const view = getViewSymbol()?.toUpperCase();
  if (view && mids[view] != null) {
    const n = asFiniteNumberOrNull(mids[view]);
    if (n != null) return n;
  }
  if (view && quote?.symbol.toUpperCase() === view && quote.mid != null) {
    const n = asFiniteNumberOrNull(quote.mid);
    if (n != null) return n;
  }
  if (quote?.mid != null) {
    const n = asFiniteNumberOrNull(quote.mid);
    if (n != null) return n;
  }
  return null;
}

export function resolveDisplayMid(
  quote: LiveOpsQuote,
  mids: Record<string, number>,
  lastBarClose?: number | null,
): number | null {
  const mid = resolveViewMid(quote, mids);
  if (mid != null) return mid;
  if (lastBarClose != null && Number.isFinite(lastBarClose)) return lastBarClose;
  return null;
}

export function syncChartPrice(mid: number | null, refClose?: number | null): void {
  const priceEl = document.getElementById("current-price-display");
  const priceWrap = priceEl?.closest("strong");
  const depthMid = document.getElementById("depth-mid-price");
  const validMid = asFiniteNumberOrNull(mid);
  const displayMid = validMid ?? lastMidForTone;
  if (displayMid == null) {
    if (depthMid) depthMid.textContent = "—";
    if (priceEl) priceEl.textContent = "—";
    priceWrap?.classList.remove("positive", "negative");
    renderDepthBook(null);
    return;
  }
  const text = safeFixed(displayMid, 2);
  if (depthMid) depthMid.textContent = text;
  renderDepthBook(displayMid);
  if (priceEl) priceEl.textContent = text;
  const toneEl = priceWrap ?? priceEl;
  if (toneEl) {
    toneEl.classList.remove("positive", "negative");
    const ref = asFiniteNumberOrNull(refClose) ?? lastMidForTone;
    if (ref != null && displayMid > ref) toneEl.classList.add("positive");
    else if (ref != null && displayMid < ref) toneEl.classList.add("negative");
    else toneEl.classList.add("positive");
  }
  if (validMid != null) lastMidForTone = validMid;
}

export function clearPositionsAfterFlatten(closedTodayNet = 0): void {
  const list = document.getElementById("trade-positions-list");
  if (list) {
    list.innerHTML = `<p class="trade-pos-empty muted">Nenhuma posição aberta.</p>`;
  }
  const openEl = document.getElementById("live-ops-open");
  if (openEl) {
    openEl.classList.add("hidden");
    openEl.innerHTML = "";
  }
  resetOpenMtmUi(closedTodayNet);
}

function openPositionCardsHtml(
  openSignals: Signal[],
  tradeById: Map<number, TradeMetricsItem>,
  mids: Record<string, number>,
  quote: LiveOpsQuote,
): string {
  if (!openSignals.length) {
    return `<p class="trade-pos-empty muted">Nenhuma posição aberta.</p>`;
  }
  return openSignals
    .map((s) => {
      const p = resolveRowPnl(s, tradeById, mids, quote);
      const contracts = s.contracts ?? 1;
      const sideCls = s.side === "BUY" ? "side-buy" : "side-sell";
      const pnlTone = p.net != null && p.net >= 0 ? "positive" : p.net != null ? "negative" : "";
      const pnlText = p.net != null ? fmtBrl(p.net) : "—";
      return `<article class="trade-pos-card ${pnlTone}">
        <div class="trade-pos-head">
          <strong class="mono-num">${esc(s.symbol)}</strong>
          <span class="trade-pos-side ${sideCls}">${sideLabelPt(s.side)}</span>
          <span class="trade-pos-pnl mono-num">${pnlText}</span>
        </div>
        <div class="trade-pos-meta muted">
          <span>Entrada <span class="mono-num">${safeFixed(s.entry, 2)}</span></span>
          <span>Atual <span class="mono-num">${p.exitPx != null ? safeFixed(p.exitPx, 2) : "—"}</span></span>
          <span>Qtd <span class="mono-num">${contracts}</span></span>
        </div>
        <button type="button" class="deck-btn deck-btn-sm trade-pos-close" disabled title="Em breve">Fechar</button>
      </article>`;
    })
    .join("");
}

function renderTotals(pnl: PnlMetricsResponse | null): void {
  const el = document.getElementById("live-ops-totals");
  if (!el) return;
  const s = pnl?.session_today;
  if (!s) {
    el.innerHTML = "";
    return;
  }
  const closed = resolveTodayClosedNet(pnl);
  const mtm = resolveOpenMtmBrl(pnl);
  el.innerHTML = `
    <div class="ops-total-card"><span class="muted">Fechado hoje</span><strong class="mono-num">${fmtBrl(closed)}</strong></div>
    <div class="ops-total-card"><span class="muted">MTM aberto</span><strong class="mono-num">${fmtBrl(mtm)}</strong></div>
    <div class="ops-total-card"><span class="muted">Compras / vendas</span><strong>${s.buys} / ${s.sells}</strong></div>
    <div class="ops-total-card"><span class="muted">Volume (ações)</span><strong class="mono-num">${asFiniteNumber(s.volume_shares, 0).toLocaleString("pt-BR")}</strong></div>
    <div class="ops-total-card"><span class="muted">Taxas (est. abertas)</span><strong class="mono-num">${fmtBrl(s.fees_open_est_brl)}</strong></div>
    <div class="ops-total-card"><span class="muted">IR est. (dia)</span><strong class="mono-num">${fmtBrl(s.estimated_ir_brl)}</strong></div>
  `;
}

export function renderLiveOps(
  pnl: PnlMetricsResponse | null,
  signals: Signal[],
  quote: LiveOpsQuote,
  mids: Record<string, number>,
  closedTrades: TradeMetricsItem[],
  filter: OpsFilter,
): void {
  const todayEl = document.getElementById("live-ops-today-net");
  const openEl = document.getElementById("live-ops-open");
  const body = document.getElementById("live-ops-body");
  if (!todayEl || !body) return;

  const closedToday = resolveTodayClosedNet(pnl);
  const openMtm = resolveOpenMtmBrl(pnl);
  todayEl.textContent = `${fmtBrl(closedToday)} · MTM ${fmtBrl(openMtm)}`;
  todayEl.classList.remove("positive", "negative");
  const combined = closedToday + openMtm;
  if (combined > 0) todayEl.classList.add("positive");
  if (combined < 0) todayEl.classList.add("negative");

  renderTotals(pnl);

  const tradeById = new Map(closedTrades.map((t) => [t.id, t]));
  const openSignals = signals.filter(isOpenSignal);
  const tradePosList = document.getElementById("trade-positions-list");
  if (tradePosList) {
    tradePosList.innerHTML = openPositionCardsHtml(openSignals, tradeById, mids, quote);
  }
  const dayPnlEl = document.getElementById("trade-pos-day-pnl");
  if (dayPnlEl) {
    dayPnlEl.textContent = fmtBrl(combined);
    dayPnlEl.classList.remove("positive", "negative");
    if (combined > 0) dayPnlEl.classList.add("positive");
    if (combined < 0) dayPnlEl.classList.add("negative");
  }

  if (openEl) {
    if (!openSignals.length) {
      openEl.classList.add("hidden");
      openEl.innerHTML = "";
    } else {
      openEl.classList.remove("hidden");
      const cards = openSignals
        .map((s) => {
          const p = resolveRowPnl(s, tradeById, mids, quote);
          const contracts = s.contracts ?? 1;
          const exec = executionMeta(s);
          const mtm =
            p.net != null
              ? fmtBrl(p.net)
              : "—";
          return `<div class="live-open-card">
            <span class="live-open-badge">Aberta</span>
            <strong>${esc(s.symbol)}</strong> ${sideLabelPt(s.side)} · ${contracts} @ ${safeFixed(s.entry, 2)}
            <span class="exec-pill ${exec.cls}">${exec.label}</span>
            <span class="muted">Saída est.</span> <span class="mono-num">${p.exitPx != null ? safeFixed(p.exitPx, 2) : "—"}</span>
            <span class="muted">MTM est.</span> <span class="mono-num">${mtm}</span>
          </div>`;
        })
        .join("");
      openEl.innerHTML = `<h3 class="muted live-open-title">Posições abertas</h3>${cards}`;
    }
  }

  const todayPrefix = todayBrtPrefix();
  let filtered = [...signals];
  if (filter === "today") {
    filtered = filtered.filter((s) => (s.created_at || "").startsWith(todayPrefix));
  }
  const sorted = filtered.sort(
    (a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime(),
  );

  if (!sorted.length) {
    body.innerHTML = `<tr><td colspan="10" class="muted">Nenhuma operação${filter === "today" ? " hoje" : ""}.</td></tr>`;
    return;
  }

  let cumulative = 0;
  const withCum = sorted.map((s) => {
    const p = resolveRowPnl(s, tradeById, mids, quote);
    if (p.net != null) cumulative += p.net;
    return { s, p, cum: p.net != null ? cumulative : null };
  });
  const rowsHtml = [...withCum]
    .reverse()
    .slice(0, 80)
    .map(({ s, p, cum }) => {
      const exec = executionMeta(s);
      const contracts = s.contracts ?? "—";
      const pnlCell = formatResultadoCellHtml(s, p);
      const exitCell =
        p.exitPx != null
          ? `<span class="mono-num">${safeFixed(p.exitPx, 2)}${p.isMtm ? "*" : ""}</span>`
          : '<span class="muted">—</span>';
      const msg = (s as Signal & { execution_message?: string }).execution_message;
      const execTitle = msg ? ` title="${esc(msg)}"` : "";
      return `<tr>
        <td class="mono-num">${formatTime(s.created_at)}</td>
        <td>${esc(s.symbol)}</td>
        <td class="${s.side === "BUY" ? "side-buy" : "side-sell"}">${sideLabelPt(s.side)}</td>
        <td class="mono-num">${contracts}</td>
        <td class="mono-num">${safeFixed(s.entry, 2)}</td>
        <td>${exitCell}</td>
        <td class="mono-num">${p.fees != null ? fmtBrl(p.fees) : "—"}</td>
        <td><span class="exec-pill ${exec.cls}"${execTitle}>${exec.label}</span></td>
        <td>${pnlCell}</td>
        <td class="mono-num">${cum != null ? fmtBrl(cum) : "—"}</td>
      </tr>`;
    })
    .join("");

  body.innerHTML = rowsHtml;
}

export function bindOpsFilters(onChange: (f: OpsFilter) => void): void {
  document.querySelectorAll<HTMLButtonElement>("[data-ops-filter]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const f = btn.getAttribute("data-ops-filter") as OpsFilter;
      document.querySelectorAll("[data-ops-filter]").forEach((b) =>
        b.classList.toggle("active", b === btn),
      );
      onChange(f);
    });
  });
}

function parseStopInput(raw: string): number | null {
  const t = raw.trim().replace(",", ".");
  if (!t) return null;
  const n = Number(t);
  return Number.isFinite(n) && n > 0 ? n : null;
}

export type BoletaExecuteHandler = (
  side: "BUY" | "SELL",
  payload: { symbol: string; quantity: number; stop: number | null },
) => Promise<void>;

export function bindBoleta(onExecute: BoletaExecuteHandler, onAfter?: () => void): void {
  const qtyEl = document.getElementById("boleta-qty") as HTMLInputElement | null;
  const stopEl = document.getElementById("boleta-stop") as HTMLInputElement | null;
  const buyBtn = document.getElementById("boleta-buy");
  const sellBtn = document.getElementById("boleta-sell");

  const run = async (side: "BUY" | "SELL") => {
    const symbol = getViewSymbol()?.toUpperCase();
    if (!symbol) return;
    const qty = Math.max(1, Math.floor(Number(qtyEl?.value) || 0));
    const stop = stopEl ? parseStopInput(stopEl.value) : null;
    buyBtn?.toggleAttribute("disabled", true);
    sellBtn?.toggleAttribute("disabled", true);
    try {
      await onExecute(side, { symbol, quantity: qty, stop });
    } finally {
      onAfter?.();
    }
  };

  buyBtn?.addEventListener("click", () => void run("BUY"));
  sellBtn?.addEventListener("click", () => void run("SELL"));
}
