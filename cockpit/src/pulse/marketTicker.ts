import { api, type MarketTickerSummaryItem } from "../api/client";
import { asFiniteNumber, safeFixed } from "../util/numbers";

/** Pregão regular B3 no ticker (10h–17h seg–sex BRT), só exibição. */
function b3PregaoRegularOpen(now = new Date()): boolean {
  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone: "America/Sao_Paulo",
    weekday: "short",
    hour: "numeric",
    minute: "numeric",
    hour12: false,
  }).formatToParts(now);
  const wd = parts.find((p) => p.type === "weekday")?.value ?? "";
  if (wd === "Sat" || wd === "Sun") return false;
  const hour = Number(parts.find((p) => p.type === "hour")?.value ?? "0");
  const minute = Number(parts.find((p) => p.type === "minute")?.value ?? "0");
  const mins = hour * 60 + minute;
  return mins >= 10 * 60 && mins < 17 * 60;
}

export type TickerRow = { sym: string; label: string; price: string | number; pct: number };

const DEFAULT_TICKERS: TickerRow[] = [
  { sym: "IBOV", label: "IBOV", price: "128.450", pct: 0.84 },
  { sym: "PETR4", label: "PETR4", price: "38,92", pct: 1.22 },
  { sym: "VALE3", label: "VALE3", price: "62,15", pct: -0.45 },
  { sym: "WIN$", label: "WIN$ (Mini Índice)", price: "129.110", pct: 0.95 },
  { sym: "WDO$", label: "WDO$ (Mini Dólar)", price: "5.642,5", pct: -0.32 },
];

let rowsCache: TickerRow[] = [...DEFAULT_TICKERS];
let overlayMids: Record<string, number> = {};
let clockTimer: number | null = null;
let summaryApiAvailable: boolean | null = null;

function fmtPct(n: number): string {
  const v = asFiniteNumber(n, 0);
  const sign = v >= 0 ? "+" : "";
  return `${sign}${safeFixed(v, 2, "0.00")}%`;
}

function fmtPrice(sym: string, price: string | number): string {
  if (typeof price === "string") return price;
  const key = sym.toUpperCase();
  const px = asFiniteNumber(price, 0);
  const isIndex = key.startsWith("WIN") || key === "IBOV" || key.startsWith("WDO");
  return isIndex
    ? px.toLocaleString("pt-BR", { maximumFractionDigits: 3 })
    : `R$ ${safeFixed(px, 2, "0,00")}`;
}

function renderItem(row: TickerRow): string {
  const tone = row.pct >= 0 ? "up" : "down";
  const priceLabel =
    typeof row.price === "number"
      ? fmtPrice(row.sym, row.price)
      : row.sym === "IBOV" || row.sym.startsWith("WIN")
        ? row.price
        : row.price.startsWith("R$")
          ? row.price
          : `R$ ${row.price}`;
  return `<div class="deck-ticker-item" data-ticker="${row.sym}">
    <span class="deck-ticker-sym">${row.label}</span>
    <span class="deck-ticker-px mono-num">${priceLabel}</span>
    <span class="deck-ticker-chg mono-num ${tone}">${fmtPct(row.pct)}</span>
  </div>`;
}

function applyOverlayMids(mids: Record<string, number>): boolean {
  if (!Object.keys(mids).length) return false;
  let changed = false;
  for (const [sym, mid] of Object.entries(mids)) {
    const key = sym.toUpperCase();
    if (!Number.isFinite(mid)) continue;
    const row = rowsCache.find((r) => r.sym === key);
    if (row) {
      if (row.price !== mid) {
        row.price = mid;
        changed = true;
      }
      continue;
    }
    rowsCache.push({ sym: key, label: key, price: mid, pct: 0 });
    changed = true;
  }
  return changed;
}

function paintTrack(): void {
  const track = document.getElementById("ticker-track");
  if (!track) return;
  applyOverlayMids(overlayMids);
  const html = rowsCache.map(renderItem).join("");
  track.innerHTML = html + html;
}

function rowsFromApi(items: MarketTickerSummaryItem[]): TickerRow[] {
  return items.map((t) => ({
    sym: t.symbol.toUpperCase(),
    label: (t.label || t.symbol).toUpperCase(),
    price: asFiniteNumber(t.price, 0),
    pct: asFiniteNumber(t.change_pct, 0),
  }));
}

function updateB3Clock(): void {
  const el = document.getElementById("b3-clock-time");
  if (!el) return;
  el.textContent = new Date().toLocaleTimeString("pt-BR", {
    timeZone: "America/Sao_Paulo",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
  const pregao = document.getElementById("b3-pregao-label");
  if (!pregao) return;
  const open = b3PregaoRegularOpen();
  pregao.textContent = open ? "PREGÃO B3" : "FORA DO PREGÃO";
  pregao.classList.toggle("deck-ticker-pregao-live", open);
  pregao.classList.toggle("deck-ticker-pregao-closed", !open);
  pregao.setAttribute("title", open ? "Pregão regular (10h–17h BRT)" : "Fora do horário regular B3");
}

export function mountMarketTicker(): void {
  const root = document.getElementById("market-ticker");
  if (!root || root.dataset.mounted === "1") return;
  root.dataset.mounted = "1";
  root.innerHTML = `
    <div class="deck-ticker-scroll">
      <div class="ticker-wrap">
        <div class="ticker-track" id="ticker-track"></div>
      </div>
    </div>
    <div class="deck-ticker-rail" aria-label="Pregão B3">
      <div class="deck-ticker-clock mono-num" id="b3-clock">
        <span id="b3-clock-time">—</span>
      </div>
      <span class="deck-ticker-pregao" id="b3-pregao-label">PREGÃO B3</span>
    </div>`;
  paintTrack();
  updateB3Clock();
  if (clockTimer == null) {
    clockTimer = window.setInterval(updateB3Clock, 1000);
  }
}

/** GET /market/tickers-summary when available; otherwise keep local defaults. */
export async function refreshMarketTickerSummary(): Promise<boolean> {
  try {
    const res = await api.tickersSummary();
    if (res.tickers?.length) {
      rowsCache = rowsFromApi(res.tickers);
      summaryApiAvailable = true;
      applyOverlayMids(overlayMids);
      paintTrack();
      return true;
    }
  } catch {
    summaryApiAvailable = false;
  }
  return false;
}

export function isTickersSummaryApiAvailable(): boolean | null {
  return summaryApiAvailable;
}

/** @deprecated Rail selector removed — chart symbol is chosen via search/watchlist. */
export function bindTickerRailSymbol(_onSelect: (symbol: string) => void): void {}

/** @deprecated */
export function syncTickerRailSymbol(_viewSymbol: string, _symbols: string[]): void {}

/** Overlay watchlist mids on known symbols when API provides quotes. */
export function syncMarketTicker(mids: Record<string, number>): void {
  if (!Object.keys(mids).length) return;
  overlayMids = { ...overlayMids, ...mids };
  if (applyOverlayMids(overlayMids)) paintTrack();
}
