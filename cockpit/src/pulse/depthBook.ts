import { getViewSymbol } from "./watchlist";

const DEPTH_LEVELS = 3;
const STOCK_TICK = 0.01;

function fmtPx(n: number): string {
  return n.toFixed(2);
}

function fmtVol(w: number): string {
  const lots = Math.round(w * 1200 + 400);
  if (lots >= 1000) return `${(lots / 1000).toFixed(1)}K`;
  return String(lots);
}

function esc(s: string): string {
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

/** Synthetic size weights — farther from mid, slightly smaller bar. */
function levelWeight(level: number, side: "ask" | "bid"): number {
  const base = side === "ask" ? [0.92, 0.74, 0.58] : [0.55, 0.68, 0.82];
  return base[level] ?? 0.5;
}

export function renderDepthBook(mid: number | null | undefined): void {
  const root = document.getElementById("depth-book");
  const asksEl = document.getElementById("depth-asks");
  const bidsEl = document.getElementById("depth-bids");
  const midEl = document.getElementById("depth-mid-price");
  if (!asksEl || !bidsEl || !midEl) return;

  if (mid == null || !Number.isFinite(Number(mid))) {
    midEl.textContent = "—";
    asksEl.innerHTML = "";
    bidsEl.innerHTML = "";
    root?.classList.remove("depth-live");
    return;
  }

  const m = Number(mid);
  midEl.textContent = fmtPx(m);
  root?.classList.add("depth-live");

  const sym = getViewSymbol()?.toUpperCase() ?? "";
  const tick = sym.startsWith("WIN") || sym.startsWith("WDO") ? 5 : STOCK_TICK;

  const askRows: { px: number; w: number }[] = [];
  const bidRows: { px: number; w: number }[] = [];
  for (let i = DEPTH_LEVELS; i >= 1; i -= 1) {
    askRows.push({ px: m + tick * i, w: levelWeight(i - 1, "ask") });
  }
  for (let i = 1; i <= DEPTH_LEVELS; i += 1) {
    bidRows.push({ px: m - tick * i, w: levelWeight(i - 1, "bid") });
  }

  const maxW = Math.max(...askRows.map((r) => r.w), ...bidRows.map((r) => r.w), 0.01);

  const rowHtml = (r: { px: number; w: number }, side: "ask" | "bid") =>
    `<div class="deck-depth-row ${side}">
      <span class="deck-depth-px mono-num">${esc(fmtPx(r.px))}</span>
      <span class="deck-depth-vol mono-num">(${esc(fmtVol(r.w))})</span>
      <div class="deck-depth-bar ${side}" style="--w: ${Math.round((r.w / maxW) * 100)}%"></div>
    </div>`;

  asksEl.innerHTML = askRows.map((r) => rowHtml(r, "ask")).join("");
  bidsEl.innerHTML = bidRows.map((r) => rowHtml(r, "bid")).join("");
}
