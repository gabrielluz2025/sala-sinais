import type { Signal, TradeMetricsItem } from "../api/client";
import { asFiniteNumberOrNull } from "../util/numbers";

export type LiveOpsQuote = { symbol: string; mid: number } | null;

export type RowPnL = {
  net: number | null;
  gross: number | null;
  fees: number | null;
  exitPx: number | null;
  isMtm: boolean;
};

function fmtBrl(n: number | null | undefined): string {
  if (n == null || Number.isNaN(n)) return "—";
  return n.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}

function isFutures(symbol: string): boolean {
  const s = symbol.toUpperCase();
  return s.startsWith("WIN") || s.startsWith("WDO");
}

function estimateMtm(
  side: string,
  entry: number,
  mid: number,
  contracts: number,
  symbol: string,
): number {
  const pts = side === "BUY" ? mid - entry : entry - mid;
  if (!isFutures(symbol)) return pts * contracts;
  return pts * 0.2 * contracts;
}

function estimateFees(entry: number, exit: number, contracts: number, symbol: string): number {
  if (!isFutures(symbol)) {
    const volume = (entry + exit) * contracts;
    return volume * 0.0003 + 0.5 * contracts;
  }
  return 0.65 * contracts;
}

/** Posição ainda sem PnL realizado na API (inclui FILLED em carteira). */
export function isOpenSignal(s: Signal): boolean {
  if (s.net_pnl_brl != null) return false;
  const st = (s.status || "").toLowerCase();
  return !["cancelled", "rejected", "closed"].includes(st);
}

export function resolveRowPnl(
  s: Signal,
  tradeById: Map<number, TradeMetricsItem>,
  mids: Record<string, number>,
  quote: LiveOpsQuote,
): RowPnL {
  const closed = tradeById.get(s.id);
  if (closed) {
    return {
      net: closed.net_pnl,
      gross: closed.gross_pnl,
      fees: closed.fees,
      exitPx: closed.exit,
      isMtm: false,
    };
  }
  if (s.net_pnl_brl != null) {
    const exitPx = s.exit_price ?? null;
    const fees =
      exitPx != null ? estimateFees(s.entry, exitPx, s.contracts ?? 1, s.symbol) : null;
    return {
      net: s.net_pnl_brl,
      gross: (s as Signal & { gross_pnl_brl?: number }).gross_pnl_brl ?? null,
      fees,
      exitPx,
      isMtm: false,
    };
  }
  const sym = s.symbol.toUpperCase();
  const midRaw =
    mids[sym] ?? (quote && quote.symbol.toUpperCase() === sym ? quote.mid : undefined);
  const mid = asFiniteNumberOrNull(midRaw);
  if (mid != null && isOpenSignal(s)) {
    const contracts = s.contracts ?? 1;
    const fees = estimateFees(s.entry, mid, contracts, s.symbol);
    const gross = estimateMtm(s.side, s.entry, mid, contracts, s.symbol);
    const net = gross - fees;
    return { net, gross, fees, exitPx: mid, isMtm: true };
  }
  return { net: null, gross: null, fees: null, exitPx: s.exit_price ?? null, isMtm: false };
}

/** Célula HTML consistente para coluna Resultado (Ops / Lucros). */
export function formatResultadoCellHtml(s: Signal, p: RowPnL): string {
  if (p.net != null) {
    const tone = p.net > 0 ? "positive" : p.net < 0 ? "negative" : "";
    const prefix = p.isMtm ? "MTM " : "";
    const title = p.isMtm ? ' title="Mark-to-market estimado (posição aberta)"' : "";
    return `<span class="mono-num ${tone}"${title}>${prefix}${fmtBrl(p.net)}</span>`;
  }

  const st = (s.status || "").toLowerCase();
  if (isOpenSignal(s)) {
    return '<span class="muted" title="Posição aberta — resultado líquido após fechamento">— (aberto)</span>';
  }
  if (st === "pending" || st === "sent") {
    return '<span class="muted" title="Aguardando execução ou fechamento na simulação">pendente</span>';
  }
  if (st === "cancelled" || st === "rejected") {
    return '<span class="muted" title="Operação cancelada ou rejeitada">—</span>';
  }
  return '<span class="muted" title="Fechado sem preço de saída — PnL indisponível">pendente</span>';
}

export function formatResultadoPlain(s: Signal, p: RowPnL): string {
  if (p.net != null) {
    const prefix = p.isMtm ? "MTM " : "";
    return `${prefix}${fmtBrl(p.net)}`;
  }
  if (isOpenSignal(s)) return "— (aberto)";
  const st = (s.status || "").toLowerCase();
  if (st === "pending" || st === "sent") return "pendente";
  return "—";
}
