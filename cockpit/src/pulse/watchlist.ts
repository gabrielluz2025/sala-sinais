import { api, type AgentConfig } from "../api/client";

export type WatchlistHandlers = {
  onViewSymbol: (symbol: string) => void;
  onSetActiveSymbol: (symbol: string) => Promise<void>;
  onSymbolsChange: (symbols: string[]) => Promise<void>;
};

let handlers: WatchlistHandlers | null = null;
let viewSymbol = "";
let activeSymbol = "";
let symbols: string[] = [];

function esc(s: string): string {
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

export function initWatchlist(h: WatchlistHandlers): void {
  handlers = h;
  const search = document.getElementById("ticker-search") as HTMLInputElement | null;
  const results = document.getElementById("ticker-search-results");
  let debounce: number | undefined;

  search?.addEventListener("input", () => {
    window.clearTimeout(debounce);
    debounce = window.setTimeout(async () => {
      const q = search.value.trim();
      if (!results) return;
      if (q.length < 2) {
        results.innerHTML = "";
        results.classList.add("hidden");
        return;
      }
      try {
        const res = await api.searchTickers(q);
        results.innerHTML = res.tickers
          .map(
            (t) =>
              `<button type="button" class="ticker-result" data-symbol="${esc(t.symbol)}">${esc(t.symbol)} <span class="muted">${esc(t.name)}</span></button>`,
          )
          .join("");
        results.classList.remove("hidden");
      } catch {
        results.innerHTML = `<p class="muted">Busca indisponível</p>`;
      }
    }, 220);
  });

  results?.addEventListener("click", async (ev) => {
    const btn = (ev.target as HTMLElement).closest("[data-symbol]") as HTMLElement | null;
    if (!btn || !handlers) return;
    const sym = btn.getAttribute("data-symbol");
    if (!sym) return;
    await addSymbol(sym);
    handlers.onViewSymbol(sym);
    if (search) search.value = "";
    results.innerHTML = "";
    results.classList.add("hidden");
  });

  document.getElementById("watchlist-bar")?.addEventListener("click", async (ev) => {
    const chip = (ev.target as HTMLElement).closest(".watchlist-chip") as HTMLElement | null;
    if (!chip || !handlers) return;
    const sym = chip.getAttribute("data-symbol");
    if (!sym) return;
    if ((ev.target as HTMLElement).closest(".watchlist-remove")) {
      ev.stopPropagation();
      await removeSymbol(sym);
      return;
    }
    if (ev.shiftKey) {
      await handlers.onSetActiveSymbol(sym);
    } else {
      handlers.onViewSymbol(sym);
    }
    paintWatchlist();
  });
}

export function syncWatchlistFromAgent(agent: AgentConfig | null): void {
  symbols = agent?.symbols?.length ? [...agent.symbols] : ["PETR4"];
  activeSymbol = agent?.active_symbol || symbols[0] || "PETR4";
  if (!viewSymbol) viewSymbol = activeSymbol;
  paintWatchlist();
}

export function getViewSymbol(): string {
  return viewSymbol || activeSymbol || "PETR4";
}

export function setViewSymbol(sym: string): void {
  viewSymbol = sym.toUpperCase();
  paintWatchlist();
}

async function addSymbol(sym: string): Promise<void> {
  const s = sym.toUpperCase();
  if (!symbols.includes(s)) {
    symbols = [...symbols, s];
    if (handlers) await handlers.onSymbolsChange(symbols);
  }
}

async function removeSymbol(sym: string): Promise<void> {
  const s = sym.toUpperCase();
  if (symbols.length <= 1) return;
  symbols = symbols.filter((x) => x !== s);
  if (viewSymbol === s) viewSymbol = symbols[0];
  if (activeSymbol === s && handlers) await handlers.onSetActiveSymbol(symbols[0]);
  if (handlers) await handlers.onSymbolsChange(symbols);
  paintWatchlist();
}

function paintWatchlist(): void {
  const bar = document.getElementById("watchlist-bar");
  if (!bar) return;
  if (symbols.length <= 1) {
    bar.classList.add("hidden");
    bar.innerHTML = "";
    return;
  }
  bar.classList.remove("hidden");
  bar.innerHTML = symbols
    .map((sym) => {
      const isView = sym === viewSymbol;
      const isActive = sym === activeSymbol;
      return `<button type="button" class="watchlist-chip ${isView ? "view" : ""} ${isActive ? "active-op" : ""}" data-symbol="${esc(sym)}" title="Clique: ver gráfico · Shift+clique: operar">
        ${esc(sym)}${isActive ? '<span class="watchlist-op" aria-label="ativo engine">●</span>' : ""}
        <span class="watchlist-remove" aria-label="Remover">×</span>
      </button>`;
    })
    .join("");
}

export function getWatchlistSymbols(): string[] {
  return [...symbols];
}
