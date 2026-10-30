import type { Signal } from "../api/client";
import { isOpenSignal, riskRewardRatio } from "./chartOverlays";

function esc(s: string): string {
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

function fmtBrl(n: number | null | undefined): string {
  if (n == null || Number.isNaN(n)) return "—";
  return n.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}

function strategyLabel(t: string | null | undefined): string {
  if (t === "breakout") return "Breakout";
  if (t === "volatility") return "Volatilidade";
  return t || "—";
}

export function renderDecisionPanel(symbol: string, signal: Signal | null): void {
  const root = document.getElementById("decision-panel");
  if (!root) return;

  if (!signal || signal.symbol.toUpperCase() !== symbol.toUpperCase()) {
    root.innerHTML = `
      <div class="decision-strip">
        <div class="decision-chip decision-chip-wide">
          <span class="decision-chip-label">Decisão · ${esc(symbol)}</span>
          <span class="decision-chip-value muted">Aguardando sinal do agente</span>
        </div>
      </div>`;
    return;
  }

  const sideClass = signal.side === "BUY" ? "side-buy" : signal.side === "SELL" ? "side-sell" : "";
  const sideText = signal.side === "BUY" ? "Compra" : signal.side === "SELL" ? "Venda" : esc(signal.side);
  const resultTone =
    signal.net_pnl_brl != null && signal.net_pnl_brl > 0
      ? "positive"
      : signal.net_pnl_brl != null && signal.net_pnl_brl < 0
        ? "negative"
        : "";

  const rr =
    signal.entry != null && signal.stop != null && signal.target != null
      ? riskRewardRatio(signal.entry, signal.stop, signal.target)
      : null;

  root.innerHTML = `
    <div class="decision-strip">
      <div class="decision-chip">
        <span class="decision-chip-label">Estratégia</span>
        <span class="decision-chip-value">${esc(strategyLabel(signal.strategy_type))}</span>
      </div>
      <div class="decision-chip ${sideClass}">
        <span class="decision-chip-label">Lado</span>
        <span class="decision-chip-value">${sideText}</span>
      </div>
      <div class="decision-chip">
        <span class="decision-chip-label">Status</span>
        <span class="decision-chip-value">${esc(signal.status)}</span>
      </div>
      <div class="decision-chip">
        <span class="decision-chip-label">Entrada</span>
        <span class="decision-chip-value mono-num">${signal.entry}</span>
      </div>
      <div class="decision-chip">
        <span class="decision-chip-label">Stop / alvo</span>
        <span class="decision-chip-value mono-num">${signal.stop ?? "—"} · ${signal.target ?? "—"}</span>
      </div>
      <div class="decision-chip">
        <span class="decision-chip-label">R:R</span>
        <span class="decision-chip-value mono-num">${rr ?? "—"}</span>
      </div>
      <div class="decision-chip">
        <span class="decision-chip-label">Regime</span>
        <span class="decision-chip-value">${esc(signal.regime || "—")}</span>
      </div>
      <div class="decision-chip">
        <span class="decision-chip-label">Resultado</span>
        <span class="decision-chip-value mono-num ${resultTone}">${fmtBrl(signal.net_pnl_brl)}</span>
      </div>
      <div class="decision-chip decision-chip-wide">
        <span class="decision-chip-label">Motivo</span>
        <span class="decision-chip-value">${esc(signal.entry_reason || signal.note || "—")}</span>
      </div>
    </div>`;
}

export function pickLatestSignalForSymbol(signals: Signal[], symbol: string): Signal | null {
  const sym = symbol.toUpperCase();
  const symSignals = signals.filter((s) => s.symbol.toUpperCase() === sym);
  return symSignals.find(isOpenSignal) ?? symSignals[0] ?? null;
}
