/** FAQ compacto (PT) — conhecimento, simulador e modo real. */

function esc(s: string): string {
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

const FAQ_ITEMS: { q: string; a: string }[] = [
  {
    q: "O conhecimento zera na abertura do pregão?",
    a: "Não. Artigos lidos, estudo do agente, diário e experiência prática ficam em arquivos persistentes. Só o PnL do dia reinicia visualmente à meia-noite (BRT) — e o botão «Limpar histórico de sessão» zera KPIs de trades, não a biblioteca.",
  },
  {
    q: "Simulador usa dinheiro real?",
    a: "Não na corretora. Os valores «se fosse real» usam capital_brl e risco do agente — projeção educativa, não saldo MT5.",
  },
  {
    q: "Como ativar modo real?",
    a: "Preflight READY → .env com ENGINE_MODE=live_mt5, SIGNAL_MODE=live, LIVE_TRADING=true → MT5 conta real, AlgoTrading verde → Sala-Sinais.bat (opção real). Veja docs/MODO_REAL.md na aba Sistema.",
  },
];

export function libraryFaqCalloutHtml(opts?: { showLiveWarning?: boolean; anchorId?: string }): string {
  const id = opts?.anchorId ? ` id="${esc(opts.anchorId)}"` : "";
  const items = FAQ_ITEMS.map(
    (it) =>
      `<li><strong>${esc(it.q)}</strong> ${esc(it.a)}</li>`,
  ).join("");
  const warn = opts?.showLiveWarning
    ? `<p class="library-faq-warn">Modo real = risco de perda total do capital. Teste em demo antes.</p>`
    : "";
  return `<aside class="library-faq-callout"${id} role="note" aria-label="Perguntas frequentes sobre conhecimento e modos">
    <p class="library-faq-title">Perguntas frequentes</p>
    <ul class="library-faq-list">${items}</ul>
    ${warn}
  </aside>`;
}

/** Balão Conhecimento / Raio-X — versão curta. */
export function libraryFaqPopoverSnippetHtml(): string {
  return `<div class="library-faq-snippet muted">
    <p><strong>Conhecimento não zera</strong> no pregão — só o PnL <em>do dia</em> reinicia na virada.</p>
    <p>Simulador: equity educativa com <code>capital_brl</code>, não extrato MT5.</p>
  </div>`;
}

export function modoRealChecklistLinkHtml(): string {
  return `<p class="header-popover-actions">
    <button type="button" class="kpi-inline-link" data-open-sistema data-scroll-exec-checklist title="Abrir checklist MT5 e .env na aba Sistema">
      Checklist modo real (MODO_REAL.md)
    </button>
  </p>`;
}
