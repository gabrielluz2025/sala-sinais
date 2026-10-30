import { api, exportLibrary, importLibrary, type AgentConfig, type ExecutionStatusRead, type PnlMetricsResponse, type SystemState } from "../api/client";
import type { ZoneId } from "./zones";
import { fetchTradeLearning, tradeLearningCardHtml } from "../pulse/tradeLearning";
import { fetchSymbolStrategyStats, symbolStrategyCardHtml } from "../pulse/symbolStrategyStats";
import { isArticleRead, markArticleRead } from "../pulse/libraryReadProgress";
import {
  agentStudiedIdSet,
  fetchAgentJournal,
  formatAgentJournalSubtitle,
  fetchAgentLibraryStudyStatus,
  formatAgentStudyLine,
} from "../pulse/agentLibraryStudy";
import { fetchAgentKnowledgeLevel, fetchKnowledgeLevel, type KnowledgeLevel } from "../pulse/knowledge";
import { knowledgeProgressPanelHtml } from "../pulse/knowledgeTier";
import { renderAgentJournalHtml } from "../pulse/agentJournalView";
import { libraryFaqCalloutHtml } from "../pulse/libraryFaq";

function esc(s: string): string {
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

function fmtBrl(n: number | null | undefined): string {
  if (n == null || Number.isNaN(n)) return "—";
  return n.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}

export type PanelContext = {
  state: SystemState | null;
  pnl: PnlMetricsResponse | null;
  agent: AgentConfig | null;
};

const titles: Record<ZoneId, string> = {
  "zone-status": "Status do sistema",
  "zone-signals": "Sinais recentes",
  "zone-trades": "Métricas de trades",
  "zone-agent": "Configuração do agente",
  "zone-library": "Biblioteca de conhecimento",
  "zone-news": "Headlines",
};

export function panelTitle(zone: ZoneId): string {
  return titles[zone];
}

export async function renderPanel(zone: ZoneId, ctx: PanelContext): Promise<string> {
  switch (zone) {
    case "zone-status":
      return await renderStatus(ctx);
    case "zone-signals":
      return renderSignals();
    case "zone-trades":
      return await renderTrades(ctx.pnl);
    case "zone-agent": {
      const sym = ctx.agent?.active_symbol || ctx.agent?.symbols?.[0] || "PETR4";
      const [learning, stratSnap] = await Promise.all([
        fetchTradeLearning(),
        fetchSymbolStrategyStats(sym),
      ]);
      return renderAgent(
        ctx.agent,
        tradeLearningCardHtml(learning),
        symbolStrategyCardHtml(stratSnap),
      );
    }
    case "zone-library":
      return renderLibrary();
    case "zone-news":
      return renderNews();
    default:
      return "<p class='muted'>—</p>";
  }
}

async function renderStatus(ctx: PanelContext): Promise<string> {
  const s = ctx.state;
  const exHtml = await renderExecutionStatusBlock();
  const sym = ctx.agent?.active_symbol || ctx.agent?.symbols?.[0] || "PETR4";
  const [learning, stratSnap] = await Promise.all([
    fetchTradeLearning(),
    fetchSymbolStrategyStats(sym),
  ]);
  const learningCard = tradeLearningCardHtml(learning);
  const strategyCard = symbolStrategyCardHtml(stratSnap);
  const hb = s?.last_heartbeat ? new Date(s.last_heartbeat).toLocaleString("pt-BR") : "—";
  const pauseBanner =
    s?.engine_paused && s?.engine_online
      ? `<p class="exec-pause-banner" role="alert">
          <strong>Motor pausado</strong> — ordens e boleta ficam bloqueadas até você clicar
          <strong>Retomar</strong> no menu esquerdo (ZERAR TUDO pausa de propósito).
        </p>`
      : "";
  return `
    <section class="zone-section" id="zone-status">
      ${pauseBanner}
      <div class="pnl-grid">
        <div class="pnl-card"><span class="muted">Engine</span><strong>${s?.engine_online ? "Online" : "Offline"}</strong></div>
        <div class="pnl-card"><span class="muted">Pausado</span><strong>${s?.engine_paused ? "Sim" : "Não"}</strong></div>
        <div class="pnl-card"><span class="muted">Modo</span><strong>${esc(s?.mode || "—")}</strong></div>
        <div class="pnl-card"><span class="muted">MT5</span><strong>${s?.mt5_connected === true ? "Conectado" : s?.mt5_connected === false ? "Desconectado" : "—"}</strong></div>
      </div>
      <p class="muted">Último heartbeat: ${esc(hb)}</p>
      <p class="muted">Fonte: ${esc(s?.data_source || "—")} · ${esc(s?.operating_mode || "—")}</p>
      <div class="pnl-grid deck-learning-grid" style="margin-top:0.75rem">${learningCard}${strategyCard}</div>
      <div id="status-dashboard" class="exec-status-block" style="margin-top:0.75rem">${exHtml}</div>
    </section>`;
}

function renderMt5TerminalDiagnosticsHtml(
  ex: ExecutionStatusRead,
): string {
  if (ex.mt5_connected !== true) {
    return "";
  }
  const term = ex.mt5_terminal;
  if (!term) {
    return `<p class="muted">Diagnóstico MT5 indisponível — atualize a API.</p>`;
  }
  if (!term.available) {
    return `
      <section class="exec-terminal-diag exec-terminal-diag--bad" aria-labelledby="exec-terminal-title">
        <h3 id="exec-terminal-title" class="exec-terminal-title">Diagnóstico MT5 (API Python)</h3>
        <p class="exec-terminal-error">${esc(term.error || "Não foi possível ler terminal_info() neste processo.")}</p>
      </section>`;
  }
  const headBits = [term.company, term.name].filter(Boolean).join(" · ");
  const flagRow = (label: string, val: boolean | null | undefined, invert = false) => {
    if (val == null) return "";
    const ok = invert ? val === false : val === true;
    const cls = ok ? "exec-terminal-flag-ok" : "exec-terminal-flag-bad";
    const text = val ? "Sim" : "Não";
    return `<tr class="${cls}"><td>${esc(label)}</td><td><strong>${text}</strong></td></tr>`;
  };
  const checklistRows = (term.checklist || [])
    .map((step) => {
      const rowCls = step.blocked
        ? "exec-terminal-step-blocked"
        : step.done
          ? "exec-terminal-step-done"
          : "exec-terminal-step-pending";
      const status = step.blocked ? "Bloqueado" : step.done ? "OK" : "Pendente";
      const msg = step.message
        ? `<p class="exec-terminal-step-msg muted">${esc(step.message)}</p>`
        : "";
      return `<tr class="${rowCls}">
        <td aria-hidden="true">${step.done ? "✓" : step.blocked ? "✕" : "○"}</td>
        <td>${esc(step.label)}</td>
        <td>${status}</td>
      </tr>${msg ? `<tr class="${rowCls}"><td colspan="3">${msg}</td></tr>` : ""}`;
    })
    .join("");
  const anyBlocked = (term.checklist || []).some((s) => s.blocked);
  const sectionCls = anyBlocked ? "exec-terminal-diag--bad" : "exec-terminal-diag--ok";
  const clearIniHint =
    term.trade_allowed === false
      ? `<p class="exec-terminal-step-msg"><strong>Se a Clear não grava o checkbox</strong>, feche o MT5 e rode manualmente: <code>python scripts/fix_mt5_experts_ini.py</code> (<code>docs/MT5_EXECUCAO.md</code>).</p>`
      : "";
  return `
    <section class="exec-terminal-diag ${sectionCls}" aria-labelledby="exec-terminal-title">
      <h3 id="exec-terminal-title" class="exec-terminal-title">Diagnóstico MT5 (API Python)</h3>
      <p class="muted exec-terminal-sub">${esc(headBits || "Terminal conectado à API")}</p>
      <table class="exec-terminal-flags">
        <tbody>
          ${flagRow("trade_allowed (Permitir algotrading + barra)", term.trade_allowed)}
          ${flagRow("connected", term.connected)}
          ${flagRow("tradeapi_disabled (API Python bloqueada)", term.tradeapi_disabled, true)}
        </tbody>
      </table>
      <h4 class="muted">Checklist terminal</h4>
      <div class="exec-checklist-wrap">
        <table class="exec-checklist-table exec-terminal-checklist">
          <thead>
            <tr><th scope="col"></th><th scope="col">Verificação</th><th scope="col">Status</th></tr>
          </thead>
          <tbody>${checklistRows || `<tr><td colspan="3" class="muted">—</td></tr>`}</tbody>
        </table>
      </div>
      ${clearIniHint}
    </section>`;
}

function renderStructuredBlockersHtml(ex: ExecutionStatusRead): string {
  const sb = ex.structured_blockers;
  if (!sb) return "";
  const rows: string[] = [];
  if (sb.session_hours && sb.session_hours_message) {
    rows.push(
      `<tr><td class="mono-num">session_hours</td><td>${esc(sb.session_hours_message)}</td></tr>`,
    );
  }
  if (sb.mt5_trade_allowed && sb.mt5_trade_allowed_message) {
    rows.push(
      `<tr><td class="mono-num">mt5_trade_allowed</td><td>${esc(sb.mt5_trade_allowed_message)}</td></tr>`,
    );
  }
  if (sb.experts_ini_enabled && sb.experts_ini_message) {
    rows.push(
      `<tr><td class="mono-num">experts_ini_enabled</td><td>${esc(sb.experts_ini_message)}</td></tr>`,
    );
  }
  if (!rows.length) return "";
  const sessionNote =
    sb.session_hours && sb.session_hours_message
      ? `<p class="exec-blocker-note muted">session_hours bloqueia <strong>novas ordens/sinais MT5</strong> — estudo da biblioteca (agente 24h) e leitura no painel continuam.</p>`
      : "";
  return `
    <h3 class="muted">Bloqueios por categoria</h3>
    <table class="exec-checklist-table">
      <thead><tr><th scope="col">Tipo</th><th scope="col">Detalhe</th></tr></thead>
      <tbody>${rows.join("")}</tbody>
    </table>${sessionNote}`;
}

function renderExecutionStatusHtml(ex: ExecutionStatusRead): string {
  const mt5Label =
    ex.mt5_connected === true ? "Conectado" : ex.mt5_connected === false ? "Desconectado" : "—";
  const rows = ex.steps
    .map(
      (step) => `<tr class="${step.done ? "exec-step-done" : "exec-step-pending"}">
        <td aria-hidden="true">${step.done ? "✓" : "○"}</td>
        <td class="mono-num">${esc(step.id)}</td>
        <td>${esc(step.label)}</td>
        <td>${step.done ? "Concluído" : "Pendente"}</td>
      </tr>`,
    )
    .join("");
  const blockers =
    ex.blockers.length > 0
      ? `<ul class="exec-blockers">${ex.blockers.map((b) => `<li>${esc(b)}</li>`).join("")}</ul>`
      : `<p class="muted">Nenhum bloqueio ativo — ordens automáticas e boleta podem ir ao MT5 (se política permitir).</p>`;
  const liveWarn = ex.live_trading_warning
    ? `<p class="exec-live-warn">Atenção: LIVE_TRADING está ativo no .env.</p>`
    : "";
  const overnightBadge = ex.overnight_learning
    ? `<p class="exec-overnight-badge" role="status"><strong>Aprendizado 24h</strong> — sinais simulados e estudo até o pregão; sem ordens MT5.</p>`
    : "";
  const pathMismatch =
    ex.mt5_path_mismatch
      ? `<p class="exec-live-warn" role="alert">MT5_PATH no .env não bate com o terminal que a API conectou. Defina <code>MT5_PATH=C:\\Program Files\\Clear Investimentos MT5 Terminal\\terminal64.exe</code> (ajuste se necessário) e reinicie API + engine.</p>`
      : "";
  const snippet = ex.env_snippet_paper_demo || "";
  const note = ex.recommended_env_note || "";
  return `
    <header class="exec-mt5-head">
      <h2 class="exec-mt5-title">Execução MT5</h2>
      <p class="muted exec-mt5-sub">${esc(note)}</p>
    </header>
    ${overnightBadge}
    <div class="pnl-grid exec-status-kpis">
      <div class="pnl-card"><span class="muted">Aprendizado 24h</span><strong>${ex.overnight_learning ? "Ativo" : "Não"}</strong></div>
      <div class="pnl-card"><span class="muted">Execução automática</span><strong>${ex.auto_execute_enabled ? "Ligada" : "Desligada"}</strong></div>
      <div class="pnl-card"><span class="muted">Pode executar (MT5)</span><strong>${ex.can_execute || ex.can_send_orders ? "Sim" : "Não"}</strong></div>
      <div class="pnl-card"><span class="muted">MT5 (API)</span><strong>${mt5Label}</strong></div>
      <div class="pnl-card"><span class="muted">SIGNAL_MODE</span><strong>${esc(ex.signal_mode)}</strong></div>
    </div>
    ${renderMt5TerminalDiagnosticsHtml(ex)}
    <h3 class="muted" id="exec-mt5-checklist">Checklist MT5</h3>
    <div class="exec-checklist-wrap">
      <table class="exec-checklist-table">
        <thead>
          <tr><th scope="col"></th><th scope="col">ID</th><th scope="col">Passo</th><th scope="col">Status</th></tr>
        </thead>
        <tbody>${rows || `<tr><td colspan="4" class="muted">Nenhum passo retornado.</td></tr>`}</tbody>
      </table>
    </div>
    <h3 class="muted">Bloqueios</h3>
    ${blockers}
    ${renderStructuredBlockersHtml(ex)}
    <h3 class="muted">.env recomendado (demo Clear / paper_mt5)</h3>
    <div class="exec-env-snippet-row">
      <textarea id="exec-env-snippet" class="exec-env-snippet" readonly rows="7">${esc(snippet)}</textarea>
      <button type="button" id="exec-env-copy" class="deck-btn-secondary">Copiar bloco .env</button>
    </div>
    ${liveWarn}
    ${pathMismatch}
    ${libraryFaqCalloutHtml({ showLiveWarning: true, anchorId: "cockpit-faq-sistema" })}
    <div class="exec-session-reset" style="margin-top:1rem">
      <h3 class="muted">Métricas do painel (REALIZADO / fechados)</h3>
      <p class="muted">Use após correções ou testes antigos — não altera o MT5, SQLite completo nem biblioteca/diário/conhecimento.</p>
      <button type="button" id="btn-reset-session" class="deck-btn deck-btn-sm deck-btn-ghost">
        Limpar histórico de sessão
      </button>
    </div>`;
}

async function renderExecutionStatusBlock(): Promise<string> {
  try {
    const ex = await api.executionStatus();
    return renderExecutionStatusHtml(ex);
  } catch {
    return `<p class="muted">Checklist de execução indisponível (API offline).</p>`;
  }
}

function sidePt(side: string): string {
  return side === "BUY" ? "Compra" : side === "SELL" ? "Venda" : side;
}

async function renderSignals(): Promise<string> {
  try {
    const rows = await api.signals(40);
    const body = rows
      .map(
        (r) =>
          `<tr><td>${r.id}</td><td>${esc(r.symbol)}</td><td>${sidePt(r.side)}</td><td class="mono-num">${r.contracts ?? "—"}</td><td class="mono-num">${r.entry}</td><td>${esc(r.status)}</td><td>${esc(r.execution_message || "—")}</td><td>${fmtBrl(r.net_pnl_brl)}</td></tr>`,
      )
      .join("");
    return `
      <section class="zone-section" id="zone-signals">
        <table><thead><tr><th>#</th><th>Ativo</th><th>Lado</th><th>Qtd</th><th>Entrada</th><th>Status</th><th>Execução</th><th>PnL</th></tr></thead>
        <tbody>${body || "<tr><td colspan='8'>Nenhum sinal</td></tr>"}</tbody></table>
      </section>`;
  } catch {
    return `<section id="zone-signals"><p class="muted">Falha ao carregar sinais.</p></section>`;
  }
}

function fmtPct(n: number | null | undefined): string {
  if (n == null || Number.isNaN(n)) return "—";
  return `${n.toFixed(1)}%`;
}

async function renderTrades(pnl: PnlMetricsResponse | null): Promise<string> {
  const recent =
    pnl?.recent_closed
      ?.map(
        (t) =>
          `<tr><td>${esc(t.symbol)}</td><td>${fmtBrl(t.net_pnl_brl)}</td><td>${t.closed_at ? esc(new Date(t.closed_at).toLocaleString("pt-BR")) : "—"}</td></tr>`,
      )
      .join("") || "";
  const wins = pnl?.wins ?? pnl?.all_time?.wins ?? 0;
  const losses = pnl?.losses ?? pnl?.all_time?.losses ?? 0;

  let opsRows = "";
  try {
    const signals = await api.signals(30);
    opsRows = signals
      .map(
        (r) =>
          `<tr><td>${esc(new Date(r.created_at).toLocaleString("pt-BR"))}</td><td>${esc(r.symbol)}</td><td>${sidePt(r.side)}</td><td class="mono-num">${r.contracts ?? "—"}</td><td class="mono-num">${r.entry}</td><td>${esc(r.status)}</td><td>${fmtBrl(r.net_pnl_brl)}</td></tr>`,
      )
      .join("");
  } catch {
    opsRows = "";
  }

  return `
    <section class="zone-section" id="zone-trades">
      <div class="pnl-grid" id="trades-kpi-grid">
        <div class="pnl-card"><span class="muted">Hoje (líquido)</span><strong>${fmtBrl(pnl?.today_net ?? pnl?.daily?.net_pnl_brl)}</strong></div>
        <div class="pnl-card"><span class="muted">Win rate hoje</span><strong>${fmtPct(pnl?.daily?.win_rate_pct)}</strong></div>
        <div class="pnl-card"><span class="muted">Fechados hoje</span><strong>${pnl?.daily?.closed_trades ?? "—"}</strong></div>
        <div class="pnl-card"><span class="muted">Abertas (est.)</span><strong>${fmtBrl(pnl?.open_positions_estimated_pnl)}</strong></div>
        <div class="pnl-card"><span class="muted">Mês</span><strong>${fmtBrl(pnl?.monthly?.net_pnl_brl)}</strong></div>
        <div class="pnl-card"><span class="muted">All-time</span><strong>${fmtBrl(pnl?.all_time?.net_pnl_brl)}</strong></div>
        <div class="pnl-card"><span class="muted">Vitórias / derrotas</span><strong>${wins} / ${losses}</strong></div>
        <div class="pnl-card"><span class="muted">Taxas (est.)</span><strong>${fmtBrl(pnl?.fees_paid_brl)}</strong></div>
      </div>
      <h3 class="muted">Linha do tempo (sinais)</h3>
      <table><thead><tr><th>Hora</th><th>Ativo</th><th>Lado</th><th>Qtd</th><th>Entrada</th><th>Status</th><th>PnL</th></tr></thead>
      <tbody>${opsRows || "<tr><td colspan='7'>—</td></tr>"}</tbody></table>
      <h3 class="muted">Fechados recentes</h3>
      <table><thead><tr><th>Ativo</th><th>Líquido</th><th>Fechado</th></tr></thead>
      <tbody>${recent || "<tr><td colspan='3'>—</td></tr>"}</tbody></table>
    </section>`;
}

function renderAgent(agent: AgentConfig | null, learningCard = "", strategyCard = ""): string {
  const sym = agent?.active_symbol || agent?.symbols?.[0] || "";
  const syms = (agent?.symbols || [sym]).join(", ");
  const asset = agent?.asset_class || "acoes";
  const st = agent?.strategy_type || "volatility";
  return `
    <section class="zone-section" id="zone-agent">
      <div class="preset-row" id="agent-presets">
        <button type="button" data-preset="conservador">Conservador</button>
        <button type="button" data-preset="moderado">Moderado</button>
        <button type="button" data-preset="agressivo">Agressivo</button>
      </div>
      <div class="strategy-picker" id="agent-strategy-picker" role="group" aria-label="Estratégia">
        <button type="button" class="strategy-card ${st === "volatility" ? "active" : ""}" data-strategy="volatility">Volatilidade</button>
        <button type="button" class="strategy-card ${st === "breakout" ? "active" : ""}" data-strategy="breakout">Breakout</button>
      </div>
      <form class="agent-form" id="agent-form">
        <label>Ativo operado <input name="active_symbol" value="${esc(sym)}" /></label>
        <label>Watchlist (vírgula) <input name="symbols_csv" value="${esc(syms)}" placeholder="PETR4, VALE3" /></label>
        <label class="checkbox-row"><input type="checkbox" name="rotate_symbols" ${agent?.rotate_symbols ? "checked" : ""} /> Rotacionar símbolos</label>
        <label>Classe <select name="asset_class">
          <option value="acoes" ${asset === "acoes" ? "selected" : ""}>Ações</option>
          <option value="win" ${asset === "win" ? "selected" : ""}>WIN/WDO</option>
          <option value="mixed" ${asset === "mixed" ? "selected" : ""}>Misto</option>
        </select></label>
        <label>Capital (R$) <input name="capital_brl" type="number" step="100" value="${agent?.capital_brl ?? 10000}" /></label>
        <label>Risco % <input name="risk_per_trade_pct" type="number" step="0.1" value="${agent?.risk_per_trade_pct ?? 1}" /></label>
        <label>Stop loss % <input name="stop_loss_pct" type="number" step="0.1" value="${agent?.stop_loss_pct ?? 2}" /></label>
        <label>Take profit % <input name="take_profit_pct" type="number" step="0.1" value="${agent?.take_profit_pct ?? 3}" /></label>
        <label>Stop pontos (WIN) <input name="stop_points" type="number" value="${agent?.stop_points ?? 80}" /></label>
        <label>Alvo pontos (WIN) <input name="target_points" type="number" value="${agent?.target_points ?? 120}" /></label>
        <label>Lote ações <input name="shares_per_order" type="number" step="100" value="${agent?.shares_per_order ?? 100}" /></label>
        <input type="hidden" name="strategy_type" id="agent-strategy-type" value="${esc(st)}" />
        <label class="checkbox-row"><input type="checkbox" name="use_news_filter" ${agent?.use_news_filter !== false ? "checked" : ""} /> Filtro de notícias</label>
        <button type="submit" class="cmd-btn" style="margin-top:0.5rem">Salvar agente</button>
      </form>
      <p class="muted">Preset ativo: ${esc(agent?.applied_preset || "—")} · Shift+clique na watchlist define ativo operado</p>
      <div class="pnl-grid deck-learning-grid">${learningCard}${strategyCard}</div>
    </section>`;
}

async function renderLibrary(): Promise<string> {
  try {
    const [idx, level, agentLevel, agentStudy, journal, stats] = await Promise.all([
      api.library(),
      fetchKnowledgeLevel(),
      fetchAgentKnowledgeLevel(),
      fetchAgentLibraryStudyStatus(),
      fetchAgentJournal(),
      api.libraryStats().catch(() => null),
    ]);
    const agentStudied = agentStudiedIdSet(agentStudy);
    const statusLine = agentStudy
      ? `<p class="library-agent-status muted" data-agent-study-line role="status">${esc(formatAgentStudyLine(agentStudy))}</p>`
      : "";
    const artN = stats?.article_count ?? idx.articles.filter((a) => a.source !== "news").length;
    const newsN = stats?.news_count ?? idx.articles.filter((a) => a.source === "news").length;
    const catalogN = stats?.catalog_total ?? idx.articles.length;
    const baseHeader = `<p class="library-base-summary muted" data-library-base-summary>Base: <strong>${artN}</strong> artigos + <strong>${newsN}</strong> notícias · catálogo do agente: ${catalogN}</p>
    <p class="library-sources-line muted">Fontes externas: RSS + API (ver doc <code>BIBLIOTECA_FONTES_EXTERNAS.md</code>)</p>`;
    const catFilters = [
      `<button type="button" class="cmd-btn library-cat-filter active" data-lib-cat="">Todos</button>`,
      ...idx.categories.map(
        (c) =>
          `<button type="button" class="cmd-btn library-cat-filter" data-lib-cat="${esc(c.id)}">${esc(c.label)}</button>`,
      ),
    ].join("");
    const catLabelById = new Map(idx.categories.map((c) => [c.id, c.label]));
    const userBlock = level
      ? `<div class="knowledge-sheet-card library-user-knowledge" id="zone-library-knowledge">
          <h3>Seu progresso</h3>
          ${knowledgeProgressPanelHtml(level, { showCatalog: false, ladderCompact: true })}
        </div>`
      : "";
    const agentLevelView: KnowledgeLevel =
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
    const agentBlock =
      agentLevel || agentStudy
        ? `<div class="knowledge-sheet-card library-agent-knowledge" id="zone-library-agent-progress">
          <h3>Conhecimento do agente</h3>
          ${statusLine}
          ${knowledgeProgressPanelHtml(agentLevelView, {
            showCatalog: Boolean(agentStudy?.total_articles),
            catalogStudied: agentStudy?.studied_count,
            catalogTotal: agentStudy?.total_articles,
            tierBarDataAttrs: " data-agent-library-bar",
            tierFillDataAttrs: " data-agent-library-fill",
            catalogBarDataAttrs: " data-agent-catalog-bar",
            catalogFillDataAttrs: " data-agent-catalog-fill",
            tierFillClass: "agent-knowledge-fill",
            ladderCompact: true,
          })}
          <p class="muted library-agent-meta" data-agent-library-meta>${agentStudy ? `${agentStudy.studied_count}/${agentStudy.total_articles} artigos · ${agentStudy.level_label}` : `${agentLevel?.article_count ?? 0} artigos estudados · ${(agentLevel?.total_words ?? 0).toLocaleString("pt-BR")} palavras`}</p>
          <div class="knowledge-sub-progress agent-practice-block">
            <div class="knowledge-sub-progress-head">
              <span data-agent-practice-label>Experiência prática</span>
            </div>
            <div class="knowledge-progress knowledge-progress-thin" data-agent-practice-bar role="progressbar" aria-valuenow="${agentStudy?.operational_maturity_pct ?? 0}" aria-label="Experiência prática com fechamentos reais">
              <div class="knowledge-progress-fill knowledge-progress-fill-practice" data-agent-practice-fill style="width:${agentStudy?.operational_maturity_pct ?? 0}%"></div>
            </div>
          </div>
        </div>`
        : "";
    const journalSub = esc(formatAgentJournalSubtitle(journal));
    const journalMd = journal?.markdown?.trim() || "";
    const journalBlock = `<div class="knowledge-sheet-card library-agent-journal" id="zone-library-journal">
          <h3>Diário do agente</h3>
          <p class="muted library-journal-sub" data-journal-updated>${journalSub}</p>
          <div class="agent-journal-preview" data-journal-body>${renderAgentJournalHtml(journalMd || null)}</div>
        </div>`;
    const progressStack =
      userBlock || agentBlock
        ? `<div class="library-progress-stack">${userBlock}${agentBlock}</div>`
        : "";
    const cards = idx.articles
      .map((a) => {
        const read = isArticleRead(a.id);
        const agentBadge = agentStudied.has(a.id)
          ? `<span class="library-badge library-badge-agent">Estudado pelo agente</span>`
          : "";
        const readBadge = read ? `<span class="library-badge library-badge-read">Lido</span>` : "";
        const src = (a as { source?: string }).source ?? "curated";
        const newsBadge = src === "news" ? `<span class="library-badge library-badge-news">Notícia</span>` : "";
        const catLabel = catLabelById.get(a.category) ?? a.category;
        return `<button type="button" class="library-card${read ? " library-card-read" : ""}${agentStudied.has(a.id) ? " library-card-agent-studied" : ""}" data-article-id="${esc(a.id)}" data-lib-category="${esc(a.category)}" data-lib-source="${esc(src)}">
          <div class="library-card-head">
            <span class="library-cat-chip">${esc(catLabel)}</span>
            <div class="library-card-badges">${readBadge}${agentBadge}${newsBadge}</div>
          </div>
          <h4>${esc(a.title)}</h4>
        </button>`;
      })
      .join("");
    return `
      <section class="zone-section" id="zone-library">
        ${libraryFaqCalloutHtml({ anchorId: "cockpit-faq-biblioteca" })}
        ${progressStack}
        ${journalBlock}
        ${baseHeader}
        <div class="library-cat-filters">${catFilters}</div>
        <div class="library-actions">
          <button type="button" id="lib-export" class="cmd-btn">Exportar ZIP</button>
          <label class="cmd-btn library-import-label"><input type="file" id="lib-import" accept=".zip" hidden />Importar ZIP</label>
        </div>
        <div id="library-cards" class="library-articles-grid">${cards}</div>
        <dialog id="library-dialog" style="max-width:90vw;background:var(--void-mid);color:var(--text);border:1px solid var(--glass-border)">
          <h3 id="library-article-title"></h3>
          <div id="library-article-body" class="muted"></div>
          <button type="button" onclick="this.closest('dialog')?.close()">Fechar</button>
        </dialog>
      </section>`;
  } catch {
    return `<section id="zone-library"><p class="muted">Biblioteca indisponível.</p></section>`;
  }
}

async function renderNews(): Promise<string> {
  try {
    const feed = await api.news();
    const items = feed.items
      .map((i) => `<li><a href="${esc(i.url)}" target="_blank" rel="noopener">${esc(i.title)}</a></li>`)
      .join("");
    return `<section class="zone-section" id="zone-news"><ul>${items}</ul></section>`;
  } catch {
    return `<section id="zone-news"><p class="muted">News indisponível.</p></section>`;
  }
}

async function refreshAgentPanel(root: HTMLElement): Promise<void> {
  const agent = await api.agentConfig();
  const sym = agent?.active_symbol || agent?.symbols?.[0] || "PETR4";
  const [learning, stratSnap] = await Promise.all([
    fetchTradeLearning(),
    fetchSymbolStrategyStats(sym),
  ]);
  root.innerHTML = renderAgent(
    agent,
    tradeLearningCardHtml(learning),
    symbolStrategyCardHtml(stratSnap),
  );
  wirePanelInteractions(root);
  const tabHost = document.getElementById("tab-agente-body");
  if (tabHost && root !== tabHost) {
    tabHost.innerHTML = root.innerHTML;
    wirePanelInteractions(tabHost);
  }
}

export async function showLibraryArticleInRoot(root: HTMLElement, id: string): Promise<void> {
  const dialog = root.querySelector("#library-dialog") as HTMLDialogElement | null;
  const titleEl = root.querySelector("#library-article-title");
  const bodyEl = root.querySelector("#library-article-body");
  if (!dialog || !bodyEl) return;
  const art = await api.libraryArticle(id);
  if (titleEl) titleEl.textContent = art.title;
  bodyEl.textContent = art.markdown;
  markArticleRead(id);
  dialog.showModal();
}

export function wirePanelInteractions(root: HTMLElement): void {
  root.querySelector("#agent-presets")?.querySelectorAll("button").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const name = btn.getAttribute("data-preset");
      if (!name) return;
      await api.applyPreset(name);
      await refreshAgentPanel(root);
    });
  });

  root.querySelectorAll("#agent-strategy-picker .strategy-card").forEach((btn) => {
    btn.addEventListener("click", () => {
      const st = btn.getAttribute("data-strategy") || "volatility";
      const hidden = root.querySelector("#agent-strategy-type") as HTMLInputElement | null;
      if (hidden) hidden.value = st;
      root.querySelectorAll("#agent-strategy-picker .strategy-card").forEach((b) => {
        b.classList.toggle("active", b === btn);
      });
    });
  });

  const form = root.querySelector("#agent-form") as HTMLFormElement | null;
  form?.addEventListener("submit", async (e) => {
    e.preventDefault();
    const fd = new FormData(form);
    const symbolsCsv = String(fd.get("symbols_csv") || "");
    const symbols = symbolsCsv
      .split(/[,;\s]+/)
      .map((s) => s.trim().toUpperCase())
      .filter(Boolean);
    await api.patchAgentConfig({
      active_symbol: String(fd.get("active_symbol") || ""),
      symbols: symbols.length ? symbols : undefined,
      rotate_symbols: fd.get("rotate_symbols") === "on",
      asset_class: String(fd.get("asset_class") || "acoes"),
      capital_brl: Number(fd.get("capital_brl")),
      risk_per_trade_pct: Number(fd.get("risk_per_trade_pct")),
      stop_loss_pct: Number(fd.get("stop_loss_pct")),
      take_profit_pct: Number(fd.get("take_profit_pct")),
      stop_points: Number(fd.get("stop_points")),
      target_points: Number(fd.get("target_points")),
      shares_per_order: Number(fd.get("shares_per_order")),
      strategy_type: String(fd.get("strategy_type") || "volatility"),
      use_news_filter: fd.get("use_news_filter") === "on",
    });
    alert("Configuração salva.");
  });

  root.querySelector("#lib-export")?.addEventListener("click", async () => {
    const blob = await exportLibrary();
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = "sala_sinais_conhecimento.zip";
    a.click();
    URL.revokeObjectURL(a.href);
  });

  const importInput = root.querySelector("#lib-import") as HTMLInputElement | null;
  importInput?.addEventListener("change", async () => {
    const file = importInput.files?.[0];
    if (!file) return;
    await importLibrary(file, "merge");
    alert("Importação concluída (merge).");
    importInput.value = "";
  });

  root.querySelectorAll(".library-cat-filter").forEach((btn) => {
    btn.addEventListener("click", () => {
      const cat = btn.getAttribute("data-lib-cat") || "";
      root.querySelectorAll(".library-cat-filter").forEach((b) => b.classList.toggle("active", b === btn));
      root.querySelectorAll(".library-card").forEach((card) => {
        const cc = card.getAttribute("data-lib-category") || "";
        const show = !cat || cc === cat;
        (card as HTMLElement).style.display = show ? "" : "none";
      });
    });
  });

  root.querySelectorAll(".library-card").forEach((card) => {
    card.addEventListener("click", async () => {
      const id = card.getAttribute("data-article-id");
      if (!id) return;
      await showLibraryArticleInRoot(root, id);
    });
  });

  root.querySelector("#exec-env-copy")?.addEventListener("click", async () => {
    const ta = root.querySelector("#exec-env-snippet") as HTMLTextAreaElement | null;
    const text = ta?.value?.trim();
    if (!text) return;
    try {
      await navigator.clipboard.writeText(text);
      alert(".env copiado — cole no arquivo .env e reinicie API + engine.");
    } catch {
      ta?.select();
      document.execCommand("copy");
      alert("Texto selecionado — copie manualmente (Ctrl+C).");
    }
  });

  root.querySelector("#btn-reset-session")?.addEventListener("click", async () => {
    if (
      !confirm(
        "Limpar histórico de sessão nos KPIs?\n\n" +
          "REALIZADO, fechados e curvas passam a contar só sinais novos a partir de agora.\n" +
          "O MT5 e os registros no banco não são apagados.",
      )
    ) {
      return;
    }
    try {
      const res = await api.resetSession();
      alert(res.message || "Sessão de métricas reiniciada.");
      window.dispatchEvent(new CustomEvent("pulse-deck-metrics-reset"));
    } catch (e) {
      const msg =
        e instanceof Error ? e.message : "Falha ao limpar histórico de sessão";
      const is404 =
        /\b404\b/.test(msg) ||
        (msg.includes("/system/reset-session") && /not found/i.test(msg));
      if (is404) {
        alert(
          `${msg}\n\n` +
            "A API em execução não expõe POST /system/reset-session — processo provavelmente desatualizado.\n" +
            "Reinicie a janela «Sala de Sinais - API» (Sala-Sinais.bat opção 1/2 ou pare e suba o uvicorn de novo).",
        );
      } else {
        alert(msg);
      }
    }
  });
}
