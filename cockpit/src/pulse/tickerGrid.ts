import { api, type Signal } from "../api/client";
import { renderRiverOnCanvas, type ChartLevelLine, type ChartMarker, type OhlcBar } from "./riverChart";

function esc(s: string): string {
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

function sideShort(side: string): string {
  return side === "BUY" ? "C" : side === "SELL" ? "V" : "—";
}

export async function refreshTickerGrid(symbols: string[], signals: Signal[]): Promise<void> {
  const grid = document.getElementById("ticker-grid");
  if (!grid) return;
  const slice = symbols.slice(0, 4);
  if (!slice.length) {
    grid.innerHTML = `<p class="muted">Adicione ativos na watchlist.</p>`;
    return;
  }

  grid.innerHTML = slice
    .map(
      (sym) => `
    <article class="ticker-grid-card" data-symbol="${esc(sym)}">
      <header><strong class="mono-num">${esc(sym)}</strong><span class="ticker-grid-status muted" id="tgs-${esc(sym)}">—</span></header>
      <canvas class="ticker-grid-canvas" id="tgc-${esc(sym)}" width="280" height="88" role="img"></canvas>
    </article>`,
    )
    .join("");

  await Promise.all(
    slice.map(async (sym) => {
      const statusEl = document.getElementById(`tgs-${sym}`);
      const canvas = document.getElementById(`tgc-${sym}`) as HTMLCanvasElement | null;
      const last = signals.find((s) => s.symbol.toUpperCase() === sym.toUpperCase());
      if (statusEl && last) {
        statusEl.textContent = `${sideShort(last.side)} · ${last.status}${last.net_pnl_brl != null ? ` · ${last.net_pnl_brl.toFixed(2)}` : ""}`;
      }
      if (!canvas) return;
      try {
        const ohlc = await api.ohlc(sym, "M5", 40);
        const markers: ChartMarker[] = last
          ? [{ time: new Date(last.created_at).getTime() / 1000, price: last.entry, kind: "entry", side: last.side as "BUY" | "SELL" }]
          : [];
        renderRiverOnCanvas(canvas, ohlc.bars as OhlcBar[], markers, [] as ChartLevelLine[]);
      } catch {
        renderRiverOnCanvas(canvas, [], [], []);
      }
    }),
  );
}
