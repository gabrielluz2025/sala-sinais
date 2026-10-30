import type { AgentConfig, ExecutionStatusRead, PnlMetricsResponse, SystemState } from "../api/client";
import { formatWordCount, type KnowledgeLevel } from "./knowledge";
import {
  formatKnowledgeHeadline,
  formatNextTierHint,
  knowledgeProgressPanelHtml,
} from "./knowledgeTier";
import { formatAgentStudyLine, type AgentLibraryStudyStatus } from "./agentLibraryStudy";
import { resolveOpenMtmBrl, resolveTodayClosedNet } from "./pnlDisplay";
import type { TradeLearningSnapshot } from "./tradeLearning";
import { libraryFaqPopoverSnippetHtml, modoRealChecklistLinkHtml } from "./libraryFaq";

function esc(s: string): string {
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

function fmtBrl(n: number | null | undefined): string {
  if (n == null || Number.isNaN(n)) return "—";
  return n.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}

function fmtPct(v: number | null | undefined, digits = 0): string {
  if (v == null || Number.isNaN(v)) return "—";
  return `${v.toFixed(digits)}%`;
}

export type AgentXrayInput = {
  knowledgeLevel: KnowledgeLevel | null;
  agentKnowledgeLevel: KnowledgeLevel | null;
  agentLibraryStudy: AgentLibraryStudyStatus | null;
  tradeLearning: TradeLearningSnapshot | null;
  pnl: PnlMetricsResponse | null;
  agent: AgentConfig | null;
  execution: ExecutionStatusRead | null;
  systemState: SystemState | null;
  libraryCount: number | null;
};

export function executionHonestyLabel(ex: ExecutionStatusRead | null): {
  mode: string;
  detail: string;
} {
  if (!ex) {
    return {
      mode: "Painel offline",
      detail: "Métricas locais/simuladas até a API responder.",
    };
  }
  if (ex.live_trading) {
    return {
      mode: "Conta real (LIVE)",
      detail: "LIVE_TRADING ativo — risco de capital real na corretora.",
    };
  }
  if (ex.overnight_learning) {
    return {
      mode: "Aprendizado 24h",
      detail: "Sinais simulados e estudo; sem ordens MT5 até o pregão.",
    };
  }
  if (ex.execute_on_demo || ex.mode?.toLowerCase().includes("demo")) {
    return {
      mode: "Demo MT5",
      detail: "Execução em conta demo; PnL do painel ≠ extrato real.",
    };
  }
  if (ex.can_execute) {
    return {
      mode: "Paper / MT5",
      detail: "Ordens podem ir ao terminal; confira SIGNAL_MODE e .env.",
    };
  }
  return {
    mode: ex.signal_mode || "Simulação",
    detail: "Sem execução MT5 — números são do motor de sinais do painel.",
  };
}

type RollingStats = {
  trades?: number;
  wins?: number;
  losses?: number;
  win_rate_pct?: number | null;
  net_pnl_brl?: number;
};

export function rollingFromLearning(data: TradeLearningSnapshot | null): RollingStats | null {
  const pl = data?.performance_learning;
  if (!pl) return null;
  const r = pl.rolling;
  if (r && (r.trades ?? 0) > 0) return r as RollingStats;
  const g = pl.global;
  if (g && (g.trades ?? 0) > 0) return g as RollingStats;
  return null;
}

function stratLabel(id: string | null | undefined): string {
  const s = (id || "").toLowerCase();
  if (s === "breakout") return "Breakout";
  if (s === "volatility") return "Volatilidade";
  return id || "—";
}

function heartbeatAgeLabel(iso: string | null | undefined): string {
  if (!iso) return "sem heartbeat";
  const t = Date.parse(iso);
  if (Number.isNaN(t)) return "heartbeat inválido";
  const sec = Math.max(0, Math.round((Date.now() - t) / 1000));
  if (sec < 60) return `há ${sec}s`;
  const min = Math.round(sec / 60);
  if (min < 120) return `há ${min} min`;
  return `há ${Math.round(min / 60)} h`;
}

function xrayRow(label: string, valueHtml: string, subHtml = "", title = ""): string {
  const t = title ? ` title="${esc(title)}"` : "";
  return `<div class="agent-xray-row"${t}>
    <span class="agent-xray-dt">${esc(label)}</span>
    <span class="agent-xray-dd">${valueHtml}${subHtml ? `<span class="agent-xray-sub">${subHtml}</span>` : ""}</span>
  </div>`;
}

export function agentXrayExecStripHtml(
  state: SystemState | null,
  execution: ExecutionStatusRead | null,
  tradeLearning: TradeLearningSnapshot | null,
  opts?: { domId?: string | null },
): string {
  const online = state?.engine_online ?? execution?.engine_online ?? false;
  const paused = Boolean(state?.engine_paused ?? execution?.engine_paused);
  const hb = heartbeatAgeLabel(state?.last_heartbeat ?? null);
  const autoOn = Boolean(
    execution?.auto_execute_enabled ?? execution?.auto_execute_orders ?? false,
  );
  const guards = tradeLearning?.performance_learning?.soft_guards;
  const guardOn = Boolean(guards?.active);
  const guardLabel = guardOn ? "Guardas ON" : "Guardas OFF";
  const guardTitle = guardOn
    ? "Guardas de aprendizado ativas — reduz agressividade após sequência ruim"
    : "Guardas de aprendizado desligadas";
  const engineChip = !online
    ? "Motor offline"
    : paused
      ? "Motor pausado"
      : "Motor online";
  return `<div class="agent-xray-exec-strip"${opts?.domId === null ? "" : ` id="${opts?.domId ?? "agent-xray-exec-strip"}"`}>
    <span class="agent-xray-chip${online && !paused ? " ok" : ""}">${esc(engineChip)}</span>
    <span class="agent-xray-chip muted" id="agent-xray-heartbeat" title="Último heartbeat do engine">HB ${esc(hb)}</span>
    <span class="agent-xray-chip${autoOn ? " ok" : ""}">AUTO ${autoOn ? "ON" : "OFF"}</span>
    <span class="agent-xray-chip${guardOn ? " warn" : " muted"}" title="${esc(guardTitle)}">${esc(guardLabel)}</span>
  </div>`;
}

function agentSnapshotHtml(agent: AgentConfig | null): string {
  if (!agent) {
    return `<p class="agent-xray-snapshot muted">Agente não carregado — confira API e aba Agente</p>`;
  }
  const sym = agent.active_symbol || agent.symbols?.[0] || "—";
  const rotate = agent.rotate_symbols
    ? "rotação"
    : agent.symbols?.length
      ? `${agent.symbols.length} ativos`
      : "fixo";
  const shares =
    agent.shares_per_order != null ? `${agent.shares_per_order} ações` : "lote padrão";
  return `<dl class="agent-xray-snapshot-dl">
    ${xrayRow("Operação", `<strong>${esc(sym)}</strong> · ${esc(stratLabel(agent.strategy_type))}`)}
    ${xrayRow("Risco", `${fmtBrl(agent.capital_brl)} · ${agent.risk_per_trade_pct.toFixed(1)}%/trade · ${esc(shares)} · ${esc(rotate)}`)}
  </dl>`;
}

/** Projeção educativa: capital configurado + PnL fechado acumulado (+ MTM aberto opcional). */
export function simulatedRealMoneyView(
  agent: AgentConfig | null,
  pnl: PnlMetricsResponse | null,
  includeOpenMtm: boolean,
): {
  capitalBrl: number;
  riskPerTradeBrl: number;
  riskPct: number;
  closedNetAllTime: number;
  openMtm: number;
  equityEst: number;
  todayTotal: number;
  drawdownTodayBrl: number | null;
  drawdownTodayPct: number | null;
} {
  const capitalBrl = agent?.capital_brl ?? 0;
  const riskPct = agent?.risk_per_trade_pct ?? 0;
  const riskPerTradeBrl = capitalBrl > 0 ? (capitalBrl * riskPct) / 100 : 0;
  const closedNetAllTime = pnl?.all_time?.net_pnl_brl ?? 0;
  const openMtm = includeOpenMtm ? resolveOpenMtmBrl(pnl) : 0;
  const todayClosed = resolveTodayClosedNet(pnl);
  const todayTotal = todayClosed + (includeOpenMtm ? openMtm : 0);
  const equityEst = capitalBrl + closedNetAllTime + openMtm;
  const drawdownTodayBrl = todayTotal < 0 ? Math.abs(todayTotal) : null;
  const drawdownTodayPct =
    drawdownTodayBrl != null && capitalBrl > 0
      ? (drawdownTodayBrl / capitalBrl) * 100
      : null;
  return {
    capitalBrl,
    riskPerTradeBrl,
    riskPct,
    closedNetAllTime,
    openMtm,
    equityEst,
    todayTotal,
    drawdownTodayBrl,
    drawdownTodayPct,
  };
}

export function agentXrayKnowledgeHtml(
  userLevel: KnowledgeLevel | null,
  agentLevel: KnowledgeLevel | null,
  agentStudy: AgentLibraryStudyStatus | null,
  libraryCount: number | null,
): string {
  const parts: string[] = [];
  const userHasReads = Boolean(userLevel && (userLevel.article_count > 0 || userLevel.progress_pct > 0));

  if (agentLevel || agentStudy) {
    const levelView: KnowledgeLevel =
      agentLevel ??
      ({
        level_id: agentStudy?.level_id ?? "iniciante",
        level_label: agentStudy?.level_label ?? "Iniciante",
        article_count: agentStudy?.studied_count ?? 0,
        total_words: 0,
        progress_pct: agentStudy?.progress_pct ?? 0,
        next_level_label: null,
        articles_to_next: 0,
        words_to_next: 0,
        formula_note: "",
      } as KnowledgeLevel);
    const panel = knowledgeProgressPanelHtml(levelView, {
      showCatalog: Boolean(agentStudy?.total_articles),
      catalogStudied: agentStudy?.studied_count,
      catalogTotal: agentStudy?.total_articles,
      catalogLabel: "Artigos estudados (catálogo)",
      tierBarClass: "agent-xray-progress",
      tierFillClass: "agent-knowledge-fill",
      tierBarDataAttrs: " data-agent-knowledge-bar",
      tierFillDataAttrs: " data-agent-knowledge-fill",
      catalogBarDataAttrs: " data-agent-catalog-bar",
      catalogFillDataAttrs: " data-agent-catalog-fill",
      compact: false,
    });
    parts.push(`<p class="agent-xray-sub muted" data-agent-study-line title="Progresso autônomo do motor">${esc(formatAgentStudyLine(agentStudy))}</p>
      <p class="agent-xray-sub muted">Conhecimento do agente (biblioteca 24h)</p>
      ${panel}
      ${xrayRow(
        "Detalhe",
        `${agentLevel?.article_count ?? agentStudy?.studied_count ?? 0} artigos · ${formatWordCount(agentLevel?.total_words ?? 0)} palavras`,
        agentStudy?.last_article_title ? esc(`Último: ${agentStudy.last_article_title}`) : "",
      )}`);
  }

  if (userHasReads && userLevel) {
    const nextHint = formatNextTierHint(userLevel);
    parts.push(`<p class="agent-xray-sub muted" style="margin-top:0.65rem">Seu progresso na biblioteca</p>
      ${knowledgeProgressPanelHtml(userLevel, { compact: true, showCatalog: false })}
      ${xrayRow(
        "Você leu",
        `${userLevel.article_count} artigos · ${formatWordCount(userLevel.total_words)} palavras`,
        `<button type="button" class="kpi-inline-link" data-open-library>Ler</button>`,
        nextHint,
      )}`);
  } else if (!parts.length && userLevel) {
    const nextHint = formatNextTierHint(userLevel);
    parts.push(`${knowledgeProgressPanelHtml(userLevel, { compact: true, showCatalog: false })}
      <p class="agent-xray-sub muted">Seu progresso na biblioteca</p>
      ${xrayRow(
        "Você leu",
        `${userLevel.article_count} artigos · ${formatWordCount(userLevel.total_words)} palavras`,
        `<button type="button" class="kpi-inline-link" data-open-library>Ler</button>`,
        nextHint,
      )}`);
  }

  if (parts.length) return `${libraryFaqPopoverSnippetHtml()}${parts.join("")}`;

  if (libraryCount != null && libraryCount > 0) {
    return `${libraryFaqPopoverSnippetHtml()}${xrayRow(
      "Biblioteca",
      `${libraryCount} artigos indexados`,
      `<button type="button" class="kpi-inline-link" data-open-library>Abrir</button>`,
      "Leia artigos para subir de nível day trade",
    )}`;
  }
  return `${libraryFaqPopoverSnippetHtml()}<p class="agent-xray-sub muted">Biblioteca indisponível — API offline ou índice vazio</p>`;
}

export function agentXrayHitsHtml(
  rolling: RollingStats | null,
  daily: PnlMetricsResponse["daily"] | undefined,
  pnl: PnlMetricsResponse | null,
  tradeLearning: TradeLearningSnapshot | null,
): string {
  const openCount = pnl?.open_positions_count ?? 0;
  const allTimeClosed = pnl?.all_time?.closed_trades ?? 0;

  if (rolling && (rolling.trades ?? 0) > 0) {
    const wr = rolling.win_rate_pct;
    const wins = rolling.wins;
    const losses = rolling.losses;
    const lossPct =
      wr != null
        ? 100 - wr
        : wins != null && losses != null && rolling.trades
          ? (losses / rolling.trades) * 100
          : null;
    const dailySub =
      daily && (daily.closed_trades ?? 0) > 0
        ? `Hoje WR ${fmtPct(daily.win_rate_pct)} (${daily.closed_trades} fech.)`
        : "";
    return `<p class="agent-xray-big">Acertos ${fmtPct(wr)} <span class="agent-xray-big-muted">· Erros ${fmtPct(lossPct)}</span></p>
      ${xrayRow(
        "Janela",
        `${rolling.trades} fech. · ${wins ?? "—"}W/${losses ?? "—"}L · ${fmtBrl(rolling.net_pnl_brl)}`,
        dailySub,
      )}`;
  }
  if (daily && (daily.closed_trades ?? 0) > 0) {
    const wr = daily.win_rate_pct;
    const w = daily.wins ?? pnl?.wins;
    const l = daily.losses ?? pnl?.losses;
    const lossPct =
      wr != null ? 100 - wr : w != null && l != null && daily.closed_trades
        ? (l / daily.closed_trades) * 100
        : null;
    return `<p class="agent-xray-big">Hoje ${fmtPct(wr)} <span class="agent-xray-big-muted">· Erros ${fmtPct(lossPct)}</span></p>
      ${xrayRow("Pregão", `${daily.closed_trades} fechados · ${w ?? "—"}W / ${l ?? "—"}L`)}`;
  }

  const insight =
    tradeLearning?.last_insight || tradeLearning?.insights_pt?.[0] || null;
  const openBit =
    openCount > 0
      ? ` · ${openCount} aberta${openCount === 1 ? "" : "s"} (MTM no P&L)`
      : "";
  return `<p class="agent-xray-big agent-xray-big-muted">—</p>
    ${xrayRow(
      "Histórico",
      `${allTimeClosed} fechados no total${openBit}`,
      "0 na janela recente",
      "Rode simulação ou feche posições na aba Ops para WR e PnL",
    )}${insight ? `<p class="agent-xray-sub muted" title="${esc(insight)}">${esc(insight.length > 80 ? `${insight.slice(0, 77)}…` : insight)}</p>` : ""}`;
}

export function agentXrayRiskHtml(
  agent: AgentConfig | null,
  sim: ReturnType<typeof simulatedRealMoneyView>,
): string {
  if (agent == null) {
    return `<p class="agent-xray-sub muted">Defina capital e risco % na aba Agente.</p>`;
  }
  const equityTitle = `Capital ${fmtBrl(sim.capitalBrl)} + fechados ${fmtBrl(sim.closedNetAllTime)}${
    sim.openMtm !== 0 ? ` + MTM ${fmtBrl(sim.openMtm)}` : ""
  }`;
  const dayRow =
    sim.drawdownTodayBrl != null
      ? xrayRow(
          "Dia (est.)",
          `<span class="negative">${fmtBrl(sim.drawdownTodayBrl)}</span>`,
          sim.drawdownTodayPct != null ? `perda · ${sim.drawdownTodayPct.toFixed(1)}% cap.` : "perda",
        )
      : xrayRow("Dia (est.)", fmtBrl(sim.todayTotal), "zero ou positivo");
  return `<p class="agent-xray-big mono-num">${fmtBrl(sim.equityEst)}</p>
    <p class="agent-xray-sub" title="${esc(equityTitle)}">${fmtBrl(sim.capitalBrl)} + fech. ${fmtBrl(sim.closedNetAllTime)}${
      sim.openMtm !== 0 ? ` + MTM ${fmtBrl(sim.openMtm)}` : ""
    }</p>
    ${xrayRow("Risco/trade", `${fmtBrl(sim.riskPerTradeBrl)} (${sim.riskPct.toFixed(1)}%)`)}
    ${dayRow}`;
}

export type AgentXrayChipSummaries = {
  conhecimento: string;
  acertos: string;
  risco: string;
  modo: string;
};

export function agentXrayChipSummaries(input: AgentXrayInput): AgentXrayChipSummaries {
  const rolling = rollingFromLearning(input.tradeLearning);
  const daily = input.pnl?.daily;
  const sim = simulatedRealMoneyView(input.agent, input.pnl, true);
  const honesty = executionHonestyLabel(input.execution);

  let conhecimento = "—";
  if (input.agentKnowledgeLevel) {
    conhecimento = formatKnowledgeHeadline(input.agentKnowledgeLevel);
  } else if (input.agentLibraryStudy) {
    conhecimento = `${input.agentLibraryStudy.studied_count}/${input.agentLibraryStudy.total_articles} · ${input.agentLibraryStudy.level_label}`;
  } else if (input.knowledgeLevel) {
    conhecimento = formatKnowledgeHeadline(input.knowledgeLevel);
  } else if (input.libraryCount != null && input.libraryCount > 0) {
    conhecimento = `${input.libraryCount} artigos`;
  }

  let acertos = "—";
  if (rolling && (rolling.trades ?? 0) > 0 && rolling.win_rate_pct != null) {
    acertos = `${rolling.win_rate_pct.toFixed(0)}% WR`;
  } else if (daily && (daily.closed_trades ?? 0) > 0 && daily.win_rate_pct != null) {
    acertos = `Hoje ${daily.win_rate_pct.toFixed(0)}%`;
  }

  let risco = "—";
  if (input.agent) {
    risco = fmtBrl(sim.equityEst);
  }

  return {
    conhecimento,
    acertos,
    risco,
    modo: honesty.mode,
  };
}

export function agentXrayModeHtml(input: AgentXrayInput): string {
  const honesty = executionHonestyLabel(input.execution);
  const execStrip = agentXrayExecStripHtml(input.systemState, input.execution, input.tradeLearning, {
    domId: null,
  });
  const snapshot = agentSnapshotHtml(input.agent);
  return `<div class="header-popover-mode">
    <p class="header-popover-lead"><strong>${esc(honesty.mode)}</strong></p>
    <p class="agent-xray-sub muted">${esc(honesty.detail)}</p>
    ${execStrip}
    ${snapshot}
    ${modoRealChecklistLinkHtml()}
  </div>`;
}

export function buildAgentXraySections(input: AgentXrayInput): {
  knowledge: string;
  hits: string;
  risk: string;
  mode: string;
  chips: AgentXrayChipSummaries;
} {
  const rolling = rollingFromLearning(input.tradeLearning);
  const daily = input.pnl?.daily;
  const sim = simulatedRealMoneyView(input.agent, input.pnl, true);
  return {
    knowledge: agentXrayKnowledgeHtml(
      input.knowledgeLevel,
      input.agentKnowledgeLevel,
      input.agentLibraryStudy,
      input.libraryCount,
    ),
    hits: agentXrayHitsHtml(rolling, daily, input.pnl, input.tradeLearning),
    risk: agentXrayRiskHtml(input.agent, sim),
    mode: agentXrayModeHtml(input),
    chips: agentXrayChipSummaries(input),
  };
}

export function agentXrayCardHtml(input: AgentXrayInput): string {
  const honesty = executionHonestyLabel(input.execution);
  const rolling = rollingFromLearning(input.tradeLearning);
  const daily = input.pnl?.daily;
  const sim = simulatedRealMoneyView(input.agent, input.pnl, true);

  const execStrip = agentXrayExecStripHtml(input.systemState, input.execution, input.tradeLearning);
  const snapshot = agentSnapshotHtml(input.agent);

  const populateHints = `<details class="agent-xray-populate">
    <summary>Como popular dados</summary>
    <ul class="agent-xray-populate-list">
      <li>Aprendizado 24h ou motor ligado gera sinais simulados (aba Sistema).</li>
      <li>Fechamentos e WR vêm da aba Ops / métricas de trades.</li>
      <li>Nível day trade sobe lendo artigos na Biblioteca.</li>
    </ul>
  </details>`;

  return `<article class="kpi-card kpi-agent-xray" id="agent-xray-card" data-kpi="agent-xray">
    <header class="agent-xray-head">
      <h4 class="kpi-label">Raio-X do agente</h4>
      <span class="agent-xray-mode" title="${esc(honesty.detail)}">${esc(honesty.mode)}</span>
    </header>
    <p class="agent-xray-header-hint muted">Detalhes rápidos no cabeçalho · Conhecimento, Acertos, Risco e Modo</p>
    ${execStrip}
    ${snapshot}
    <div class="agent-xray-grid">
      <section class="agent-xray-col">
        <h5 class="agent-xray-col-title">Conhecimento</h5>
        ${agentXrayKnowledgeHtml(
          input.knowledgeLevel,
          input.agentKnowledgeLevel,
          input.agentLibraryStudy,
          input.libraryCount,
        )}
      </section>
      <section class="agent-xray-col">
        <h5 class="agent-xray-col-title">Acertos e erros</h5>
        ${agentXrayHitsHtml(rolling, daily, input.pnl, input.tradeLearning)}
      </section>
      <section class="agent-xray-col">
        <h5 class="agent-xray-col-title">Se fosse dinheiro real</h5>
        ${agentXrayRiskHtml(input.agent, sim)}
      </section>
    </div>
    ${populateHints}
    <p class="agent-xray-disclaimer muted" title="Simulação educativa — não é recomendação financeira. Risco real depende de margem, slippage e regras da corretora.">Educativo · não é recomendação</p>
    <div class="agent-xray-actions">
      <button type="button" class="agent-xray-action" data-open-agent>Abrir Agente</button>
      <button type="button" class="agent-xray-action" data-open-sistema title="Motor, aprendizado 24h e modo simulação">Iniciar simulação</button>
      <button type="button" class="agent-xray-action" data-open-library>Biblioteca</button>
    </div>
  </article>`;
}
