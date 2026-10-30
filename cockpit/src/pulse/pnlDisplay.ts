import type { PnlMetricsResponse } from "../api/client";
import { asFiniteNumber, asFiniteNumberOrNull } from "../util/numbers";

/** MTM de carteira (1 linha por símbolo) — espelha `open_positions_estimated_pnl`. */
export function resolveOpenMtmBrl(pnl: PnlMetricsResponse | null | undefined): number {
  if (!pnl) return 0;
  const portfolio = asFiniteNumberOrNull(pnl.open_positions_estimated_pnl);
  if (portfolio != null) return portfolio;
  return asFiniteNumber(pnl.session_today?.open_mtm_brl, 0);
}

export function resolveTodayClosedNet(pnl: PnlMetricsResponse | null | undefined): number {
  if (!pnl) return 0;
  const today = asFiniteNumberOrNull(pnl.today_net);
  if (today != null) return today;
  return asFiniteNumber(pnl.daily?.net_pnl_brl, 0);
}

export function openPositionsSubLabel(openCount: number): string {
  if (openCount <= 0) return "Sem posição aberta";
  return `${openCount} posição${openCount === 1 ? "" : "ões"} aberta${openCount === 1 ? "" : "s"}`;
}
