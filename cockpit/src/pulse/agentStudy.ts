import type { AgentStudyResponse, CandlePatternHit } from "../api/client";

function esc(s: string): string {
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

export type AgentStudyRenderOptions = {
  onOpenLibraryArticle?: (articleId: string) => void;
};

function fmtNum(n: number | null | undefined, d = 2): string {
  if (n == null || Number.isNaN(n)) return "—";
  return n.toFixed(d);
}

function sidePt(side: string | null | undefined): string {
  if (side === "BUY") return "Compra";
  if (side === "SELL") return "Venda";
  return side || "—";
}

function stratName(t: string): string {
  return t === "breakout" ? "Breakout" : t === "volatility" ? "Volatilidade" : t;
}

function biasClass(bias: string): string {
  if (bias === "bullish") return "study-candle-bull";
  if (bias === "bearish") return "study-candle-bear";
  return "study-candle-neutral";
}

function renderPatternChip(p: CandlePatternHit, withLink: boolean): string {
  const link =
    withLink && p.library_article_id
      ? ` <button type="button" class="study-candle-lib" data-library-article="${esc(p.library_article_id)}" title="Abrir na biblioteca">📖</button>`
      : "";
  return `<span class="study-candle-chip ${biasClass(p.bias)}">${esc(p.label_pt)}${link}</span>`;
}

function renderTradePlaybookBlock(study: AgentStudyResponse): string {
  const tp = study.trade_playbook;
  if (!tp) return "";

  const chips = tp.summary_chips
    .map(
      (c) =>
        `<div class="study-playbook-chip" data-chip="${esc(c.key)}"><span>${esc(c.label)}</span><strong>${esc(c.text)}</strong></div>`,
    )
    .join("");

  const pillars = tp.playbook.pillars
    .map(
      (p) =>
        `<tr><td>${esc(p.label_pt)}</td><td>${esc(p.rule_pt)}</td></tr>`,
    )
    .join("");

  const libLinks = tp.playbook.library_article_ids
    .map(
      (id) =>
        `<button type="button" class="study-candle-lib study-playbook-lib" data-library-article="${esc(id)}" title="Biblioteca">${esc(id)}</button>`,
    )
    .join(" ");

  const ex = tp.example_levels;
  const rr =
    ex.risk_reward_ratio != null ? `${ex.risk_reward_ratio}:1` : "—";

  return `<section class="study-block study-playbook">
      <h4 class="study-h4">Playbook day trade · ${esc(tp.playbook.title_pt)}</h4>
      <div class="study-playbook-chips">${chips}</div>
      <p class="study-note muted">${esc(ex.entry_zone_pt)} · R:R ${rr} · ${ex.aligned_with_engine ? "Níveis do sinal ativo" : "Exemplo se romper compra"}</p>
      <table class="study-table study-playbook-table">
        <thead><tr><th>Pilar</th><th>Regra operacional</th></tr></thead>
        <tbody>${pillars}</tbody>
      </table>
      <p class="study-note muted">${esc(tp.forced_flat_note_pt)}</p>
      <p class="study-note muted">Biblioteca: ${libLinks || "—"}</p>
    </section>`;
}

function renderMarketStructureBlock(study: AgentStudyResponse): string {
  const ms = study.market_structure;
  if (!ms?.narrative_pt) return "";
  const bias =
    ms.trend_bias === "bullish"
      ? "viés compra"
      : ms.trend_bias === "bearish"
        ? "viés venda"
        : "neutro";
  return `<section class="study-block study-structure">
      <h4 class="study-h4">Estrutura SMC (M5)</h4>
      <p class="study-note">${esc(ms.narrative_pt)} · ${esc(bias)}</p>
      <p class="study-note muted">Cruze com o playbook: respeite CHoCH e zonas antes de forçar entrada contra a estrutura.</p>
    </section>`;
}

function renderCandlePatternsBlock(study: AgentStudyResponse): string {
  const cp = study.candle_patterns;
  if (!cp) return "";

  const last = cp.last_bar?.patterns ?? [];
  const lastRow =
    last.length > 0
      ? `<p class="study-note">${last.map((p) => renderPatternChip(p, true)).join(" ")}</p>`
      : `<p class="study-note muted">Nenhum padrão clássico na última barra.</p>`;

  const recent = (cp.hits || [])
    .slice(-6)
    .reverse()
    .map((h) => {
      const off = h.bar_offset === 0 ? "atual" : `${h.bar_offset}`;
      const chips = h.patterns.map((p) => renderPatternChip(p, false)).join(" ");
      return `<li><span class="mono-num">${esc(off)}</span> · ${chips}</li>`;
    })
    .join("");

  const histList = recent ? `<ul class="study-candle-list">${recent}</ul>` : "";

  return `<section class="study-block study-candles">
      <h4 class="study-h4">Padrões de candle (${esc(cp.timeframe || "M5")})</h4>
      <p class="study-note muted">${esc(cp.summary_pt || "")} · Motor: ${esc(cp.engine)}</p>
      ${lastRow}
      ${histList ? `<p class="study-note muted">Barras recentes com padrão:</p>${histList}` : ""}
    </section>`;
}

function wireLibraryArticleButtons(root: HTMLElement, opts?: AgentStudyRenderOptions): void {
  root.querySelectorAll<HTMLButtonElement>("[data-library-article]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const id = btn.getAttribute("data-library-article");
      if (id && opts?.onOpenLibraryArticle) opts.onOpenLibraryArticle(id);
    });
  });
}

export function renderAgentStudy(
  study: AgentStudyResponse | null,
  notice?: string | null,
  opts?: AgentStudyRenderOptions,
): void {
  const root = document.getElementById("agent-study-panel");
  if (!root) return;

  if (!study) {
    root.innerHTML = `<div class="study-error"><p><strong>Estudo indisponível</strong></p><p class="muted">${esc(notice || "Verifique API e engine.")}</p></div>`;
    return;
  }

  const noticeBlock = notice
    ? `<div class="study-notice" role="status">${esc(notice)}</div>`
    : "";

  const sess = study.session;
  const rec = study.recommendation;
  const ind = study.indicators;
  const sz = study.sizing;
  const active = study.strategies[study.active_strategy];
  const otherKey = study.active_strategy === "breakout" ? "volatility" : "breakout";
  const other = study.strategies[otherKey];
  const last = study.last_order;
  const hist = study.history;
  const candlesBlock = renderCandlePatternsBlock(study);
  const structureBlock = renderMarketStructureBlock(study);
  const playbookBlock = renderTradePlaybookBlock(study);

  const historyBlock =
    hist && hist.has_data
      ? `<section class="study-block study-history">
      <h4 class="study-h4">Perfil histórico do ativo</h4>
      <p class="study-note">${esc(hist.narrative || "—")}</p>
      <div class="study-grid">
        <div class="study-cell"><span>Barras M1</span><strong class="mono-num">${hist.m1_bars_count ?? "—"}</strong></div>
        <div class="study-cell"><span>Faixa no período</span><strong class="mono-num">${fmtNum(hist.period_low, 2)} – ${fmtNum(hist.period_high, 2)}</strong></div>
        <div class="study-cell"><span>Variação período</span><strong class="mono-num">${fmtNum(hist.period_return_pct, 2)}%</strong></div>
        <div class="study-cell"><span>Vol. diária (est.)</span><strong class="mono-num">${fmtNum(hist.vol_daily_pct, 2)}%</strong></div>
      </div>
      ${
        hist.today_session?.open != null
          ? `<p class="study-note muted">Pregão hoje: abertura ${fmtNum(hist.today_session.open)} · faixa ${fmtNum(hist.today_session.low)}–${fmtNum(hist.today_session.high)} · ${hist.today_session.m1_bars} barras M1</p>`
          : ""
      }
      ${hist.fundamentals?.note ? `<p class="study-note muted">${esc(hist.fundamentals.note)}</p>` : ""}
    </section>`
      : hist && !hist.has_data
        ? `<section class="study-block"><p class="study-note study-warn-text">${esc(hist.message || "Sem histórico acumulado.")}</p></section>`
        : "";

  const sessionOk = sess.in_session_window && sess.engine_may_trade;
  const sessionClass = sessionOk ? "study-ok" : "study-warn";

  const actionClass =
    rec.action === "enter_buy" ? "study-action-buy" : rec.action === "enter_sell" ? "study-action-sell" : "study-action-wait";

  root.innerHTML = `
    ${noticeBlock}
    <section class="study-block">
      <header class="study-block-head">
        <h3>Estudo ao vivo · ${esc(study.symbol)}</h3>
        <span class="study-tag ${sessionClass}">${esc(sess.phase_label)} · ${esc(sess.now_brt)}</span>
      </header>
      <p class="study-lead ${actionClass}"><strong>${esc(rec.action_label)}</strong></p>
      ${sess.engine_block_reason && !sess.engine_may_trade ? `<p class="study-note study-warn-text">Engine: ${esc(sess.engine_block_reason)}</p>` : ""}
      <p class="study-note muted">Horário operacional ${esc(sess.trade_hours)} · Mid ${fmtNum(study.market.mid)} (bid ${fmtNum(study.market.bid)} / ask ${fmtNum(study.market.ask)})</p>
    </section>

    ${historyBlock}

    ${candlesBlock}
    ${structureBlock}
    ${playbookBlock}

    <section class="study-block">
      <h4 class="study-h4">Estratégia configurada: ${esc(stratName(study.active_strategy))}</h4>
      <div class="study-grid">
        <div class="study-cell"><span>Regime</span><strong>${esc(ind.regime)}</strong></div>
        <div class="study-cell"><span>ATR %</span><strong class="mono-num">${fmtNum(ind.atr_pct, 3)}</strong></div>
        <div class="study-cell"><span>BB width %</span><strong class="mono-num">${fmtNum(ind.bb_width_pct, 2)}</strong></div>
        <div class="study-cell"><span>Tamanho</span><strong>${esc(sz.label)}</strong></div>
        <div class="study-cell"><span>Risco / capital</span><strong>${fmtNum(sz.risk_per_trade_pct, 1)}% · R$ ${fmtNum(sz.capital_brl, 0)}</strong></div>
        <div class="study-cell"><span>Stop / alvo (cfg)</span><strong class="mono-num">${fmtNum(sz.stop_loss_pct, 1)}% / ${fmtNum(sz.take_profit_pct, 1)}%</strong></div>
      </div>
      <p class="study-reason">${esc(rec.entry_reason || "—")}</p>
      ${rec.alternative_note ? `<p class="study-note">${esc(rec.alternative_note)}</p>` : ""}
    </section>

    <section class="study-block study-proposal">
      <h4 class="study-h4">Proposta de ordem (mercado atual)</h4>
      <div class="study-grid study-grid-trade">
        <div class="study-cell"><span>Lado</span><strong>${rec.side ? sidePt(rec.side) : "—"}</strong></div>
        <div class="study-cell"><span>Entrada</span><strong class="mono-num">${rec.entry ?? "—"}</strong></div>
        <div class="study-cell"><span>Stop (saída loss)</span><strong class="mono-num">${rec.stop ?? "—"}</strong></div>
        <div class="study-cell"><span>Alvo (saída gain)</span><strong class="mono-num">${rec.target ?? "—"}</strong></div>
        <div class="study-cell"><span>Quantidade</span><strong>${rec.contracts ?? sz.contracts}</strong></div>
      </div>
    </section>

    <section class="study-block">
      <h4 class="study-h4">Comparativo de estratégias</h4>
      <table class="study-table">
        <thead><tr><th></th><th>Ativa</th><th>Alternativa</th></tr></thead>
        <tbody>
          <tr><td>Sinal pronto?</td><td>${active.signal_ready ? "Sim" : "Não"}</td><td>${other.signal_ready ? "Sim" : "Não"}</td></tr>
          <tr><td>Lado</td><td>${active.side ? sidePt(active.side) : "—"}</td><td>${other.side ? sidePt(other.side) : "—"}</td></tr>
          <tr><td>Range máx / mín</td><td class="mono-num">${active.levels?.range_high ?? "—"} / ${active.levels?.range_low ?? "—"}</td><td class="mono-num">${other.levels?.range_high ?? "—"} / ${other.levels?.range_low ?? "—"}</td></tr>
        </tbody>
      </table>
    </section>

    ${
      last
        ? `<section class="study-block study-last-order">
      <h4 class="study-h4">Última ordem registrada ${last.is_demo ? '<span class="study-demo-badge">Demo/sim</span>' : ""}</h4>
      <p class="study-note muted">Pode diferir do preço do gráfico se for sinal antigo ou simulado.</p>
      <div class="study-grid study-grid-trade">
        <div class="study-cell"><span>Status</span><strong>${esc(last.status)}</strong></div>
        <div class="study-cell"><span>Lado</span><strong>${sidePt(last.side)}</strong></div>
        <div class="study-cell"><span>Entrada</span><strong class="mono-num">${last.entry}</strong></div>
        <div class="study-cell"><span>Stop / alvo</span><strong class="mono-num">${last.stop} / ${last.target}</strong></div>
      </div>
      <p class="study-reason">${esc(last.entry_reason || "—")}</p>
    </section>`
        : ""
    }`;

  wireLibraryArticleButtons(root, opts);
}
