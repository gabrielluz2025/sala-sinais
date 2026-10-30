import type { AgentConfig, AlertRead, ExecutionStatusRead, PnlMetricsResponse, Signal, SystemState } from "../api/client";
import { agentXrayCardHtml, agentXrayExecStripHtml } from "./agentXray";
import { navigateToTab } from "./tabs";
import type { AgentLibraryStudyStatus } from "./agentLibraryStudy";
import type { KnowledgeLevel } from "./knowledge";
import type { TradeLearningSnapshot } from "./tradeLearning";
import { resolveOpenMtmBrl, resolveTodayClosedNet } from "./pnlDisplay";
import {
  symbolStrategyCardHtml,
  type SymbolStrategySnapshot,
} from "./symbolStrategyStats";

function esc(s: string): string {
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

function fmtBrl(n: number | null | undefined): string {
  if (n == null || Number.isNaN(n)) return "—";
  return n.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}

export type InsightPayload = {
  pnl: PnlMetricsResponse | null;
  agent: AgentConfig | null;
  lastSignal: Signal | null;
  lastAlert: AlertRead | null;
  newsTitle: string | null;
  libraryTip: { title: string; id: string } | null;
  agentLine: string | null;
  libraryCount: number | null;
  knowledgeLevel: KnowledgeLevel | null;
  agentKnowledgeLevel: KnowledgeLevel | null;
  agentLibraryStudy: AgentLibraryStudyStatus | null;
  tradeLearning: TradeLearningSnapshot | null;
  execution: ExecutionStatusRead | null;
  systemState: SystemState | null;
  symbolStrategy: SymbolStrategySnapshot | null;
  onOpenLibrary: () => void;
  onOpenLibraryArticle: (id: string) => void;
};

function fmtPct(v: number | null | undefined): string {
  if (v == null || Number.isNaN(v)) return "—";
  return `${v.toFixed(1)}%`;
}

function b3SessionLabel(execution: ExecutionStatusRead | null): string {
  const sb = execution?.structured_blockers;
  if (!sb) return "B3 —";
  const msg = sb.session_hours_message?.trim();
  if (msg) {
    return msg;
  }
  return sb.session_hours ? "Pregão B3 aberto" : "Fora do pregão B3";
}

function agentCardBody(agent: AgentConfig | null, agentLine: string | null): string {
  if (!agent) {
    return agentLine
      ? `<span class="kpi-sub">${esc(agentLine)}</span>`
      : '<span class="kpi-sub muted">Configure o agente na aba Agente ou via API</span>';
  }
  const sym = agent.active_symbol || agent.symbols?.[0] || "—";
  const preset = agent.applied_preset ? `Preset ${agent.applied_preset}` : "Sem preset";
  const rotate = agent.rotate_symbols ? "Rotação ligada" : "Ativo fixo";
  const shares =
    agent.shares_per_order != null ? `${agent.shares_per_order} ações/ordem` : "Tamanho padrão";
  return `<span class="kpi-sub"><strong>${esc(sym)}</strong> · ${esc(agent.strategy_type)} · ${esc(preset)}</span>
    <span class="kpi-sub muted">Capital ${fmtBrl(agent.capital_brl)} · risco ${fmtPct(agent.risk_per_trade_pct)}/trade · ${esc(shares)} · ${esc(rotate)}</span>
    ${
      agentLine
        ? `<span class="kpi-sub muted">${esc(agentLine)}</span>`
        : ""
    }`;
}

export function syncInsightDeckLiveContext(
  state: SystemState | null,
  execution: ExecutionStatusRead | null,
  tradeLearning: TradeLearningSnapshot | null,
): void {
  const strip = document.getElementById("agent-xray-exec-strip");
  if (strip) {
    strip.outerHTML = agentXrayExecStripHtml(state, execution, tradeLearning);
  }
}

export function renderInsightDeck(payload: InsightPayload): void {
  const deck = document.getElementById("insight-deck");
  if (!deck) return;

  const today = resolveTodayClosedNet(payload.pnl);
  const openRisk = resolveOpenMtmBrl(payload.pnl);
  const dayTotal = today + openRisk;
  const openCount = payload.pnl?.open_positions_count ?? 0;
  const winRate = payload.pnl?.daily?.win_rate_pct;
  const closed = payload.pnl?.daily?.closed_trades ?? 0;

  const heroTone = dayTotal > 0 ? "kpi-hero-up" : dayTotal < 0 ? "kpi-hero-down" : "";

  let activityLabel = "Atividade";
  let activityBody = '<span class="kpi-sub muted">Nenhum sinal recente — motor gera entradas quando há setup</span>';
  if (payload.lastSignal) {
    const s = payload.lastSignal;
    activityLabel = "Último sinal";
    activityBody = `<span class="kpi-sub"><strong>${esc(s.symbol)}</strong> ${esc(s.side)} · ${esc(s.status)}</span><span class="kpi-value kpi-value-sm mono-num">${fmtBrl(s.net_pnl_brl)}</span>`;
  } else if (payload.lastAlert) {
    const a = payload.lastAlert;
    activityLabel = "Alerta";
    activityBody = `<span class="kpi-sub"><strong>${esc(a.symbol)}</strong> ${esc(a.alert_type)} @ ${a.price.toFixed(2)}</span>`;
  } else if (payload.newsTitle) {
    activityLabel = "News";
    activityBody = `<span class="kpi-sub">${esc(payload.newsTitle)}</span>`;
  }

  const agentTitle = payload.agent?.active_symbol || payload.agent?.symbols?.[0] || "Agente";
  const agentBody = agentCardBody(payload.agent, payload.agentLine);

  const exposureHint =
    openCount > 0
      ? `${openCount} posição${openCount === 1 ? "" : "ões"} · risco MTM`
      : closed > 0
        ? `${closed} fechado${closed === 1 ? "" : "s"} hoje · sem posição aberta`
        : "Sem posição aberta · PnL só após fechamentos ou MTM";

  const quickCards = [
    `<article class="kpi-card">
      <h4 class="kpi-label">Exposição aberta</h4>
      <p class="kpi-value mono-num">${fmtBrl(openRisk)}</p>
      <span class="kpi-sub">${exposureHint}</span>
    </article>`,
    `<article class="kpi-card">
      <h4 class="kpi-label">${esc(activityLabel)}</h4>
      ${activityBody}
    </article>`,
    `<article class="kpi-card" data-kpi="agent">
      <h4 class="kpi-label">${esc(agentTitle)}</h4>
      ${agentBody}
    </article>`,
  ].join("");

  const b3Label = b3SessionLabel(payload.execution);
  const b3Title =
    payload.execution?.structured_blockers?.session_hours_message?.trim() ||
    (payload.execution?.structured_blockers?.session_hours
      ? "Horário de pregão B3"
      : "Fora do horário de negociação B3");

  deck.innerHTML = [
    `<article class="kpi-card kpi-hero ${heroTone}">
      <div class="kpi-hero-top">
        <h4 class="kpi-label">P&amp;L do dia (est.)</h4>
        <span class="kpi-hero-b3" title="${esc(b3Title)}">${esc(b3Label)}</span>
      </div>
      <p class="kpi-hero-value mono-num${dayTotal > 0 ? " positive" : dayTotal < 0 ? " negative" : ""}">${fmtBrl(dayTotal)}</p>
      <div class="kpi-hero-stats">
        <div class="kpi-hero-stat">
          <span class="kpi-hero-stat-label">Realizado</span>
          <span class="kpi-hero-stat-val mono-num">${fmtBrl(today)}</span>
        </div>
        <div class="kpi-hero-stat">
          <span class="kpi-hero-stat-label">MTM aberto</span>
          <span class="kpi-hero-stat-val mono-num">${fmtBrl(openRisk)}</span>
        </div>
        <div class="kpi-hero-stat">
          <span class="kpi-hero-stat-label">Fechados</span>
          <span class="kpi-hero-stat-val mono-num">${closed}</span>
        </div>
        <div class="kpi-hero-stat">
          <span class="kpi-hero-stat-label">Abertas</span>
          <span class="kpi-hero-stat-val mono-num">${openCount}</span>
        </div>
      </div>
      <p class="kpi-hero-foot muted">${winRate != null ? `WR hoje ${winRate.toFixed(0)}%` : closed === 0 && openCount === 0 ? "Sem trades hoje — simulação ou Ops" : `${closed} fechado${closed === 1 ? "" : "s"} hoje`}</p>
    </article>`,
    `<div class="insight-deck-cluster">${quickCards}</div>`,
    agentXrayCardHtml({
      knowledgeLevel: payload.knowledgeLevel,
      agentKnowledgeLevel: payload.agentKnowledgeLevel,
      agentLibraryStudy: payload.agentLibraryStudy,
      tradeLearning: payload.tradeLearning,
      pnl: payload.pnl,
      agent: payload.agent,
      execution: payload.execution,
      systemState: payload.systemState,
      libraryCount: payload.libraryCount,
    }),
    symbolStrategyCardHtml(payload.symbolStrategy, payload.agent?.strategy_type),
  ].join("");
  deck.classList.add("deck-kpi-grid", "insight-deck");

  deck.querySelectorAll("[data-open-library]").forEach((btn) => {
    btn.addEventListener("click", () => payload.onOpenLibrary());
  });
  deck.querySelectorAll("[data-open-agent]").forEach((btn) => {
    btn.addEventListener("click", () => navigateToTab("agente"));
  });
  deck.querySelectorAll("[data-open-sistema]").forEach((btn) => {
    btn.addEventListener("click", () => navigateToTab("sistema"));
  });

  if (payload.libraryTip) {
    const tip = payload.libraryTip;
    const tipBtn = document.createElement("button");
    tipBtn.type = "button";
    tipBtn.className = "kpi-library-link";
    tipBtn.textContent = tip.title;
    tipBtn.addEventListener("click", () => payload.onOpenLibraryArticle(tip.id));
    deck.querySelector('[data-kpi="agent"]')?.appendChild(tipBtn);
  }
}
