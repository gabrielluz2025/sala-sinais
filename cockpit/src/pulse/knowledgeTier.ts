import { formatWordCount } from "./knowledge";

export type KnowledgeTierInfo = {
  id: string;
  label: string;
  min_articles: number;
  min_words: number;
};

export type KnowledgeLevelView = {
  level_id: string;
  level_label: string;
  article_count: number;
  total_words: number;
  progress_pct: number;
  articles_progress_pct?: number;
  words_progress_pct?: number;
  next_level_id?: string | null;
  next_level_label?: string | null;
  articles_to_next: number;
  words_to_next: number;
  formula_note?: string;
  tiers?: KnowledgeTierInfo[];
};

export const DEFAULT_TIERS: KnowledgeTierInfo[] = [
  { id: "iniciante", label: "Iniciante", min_articles: 0, min_words: 0 },
  { id: "aprendiz", label: "Aprendiz", min_articles: 3, min_words: 2_000 },
  { id: "intermediario", label: "Intermediário", min_articles: 6, min_words: 5_000 },
  { id: "avancado", label: "Avançado", min_articles: 10, min_words: 10_000 },
];

function esc(s: string): string {
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

export function tierProgressPct(level: KnowledgeLevelView | null): number {
  if (!level) return 0;
  return level.progress_pct;
}

export function catalogProgressPct(studied: number, total: number): number {
  if (!total || total <= 0) return 0;
  return Math.round((studied / total) * 1000) / 10;
}

export function formatNextTierHint(level: KnowledgeLevelView): string {
  if (!level.next_level_label) {
    return "Nível máximo (Avançado) — faixa Especialista em roadmap";
  }
  const arts = level.articles_to_next;
  const words = formatWordCount(level.words_to_next);
  return `Próximo: ${level.next_level_label} — faltam ${arts} artigo${arts === 1 ? "" : "s"} e ${words} palavras`;
}

export function formatKnowledgeHeadline(level: KnowledgeLevelView): string {
  if (!level.next_level_label) {
    return `Nível: ${level.level_label} · máximo atingido`;
  }
  return `Nível: ${level.level_label} · ${level.progress_pct.toFixed(0)}% até ${level.next_level_label}`;
}

function tierRequirementLabel(t: KnowledgeTierInfo): string {
  if (t.min_articles <= 0 && t.min_words <= 0) return "início";
  return `${t.min_articles} art. · ${formatWordCount(t.min_words)} pal.`;
}

export function knowledgeTierLadderHtml(level: KnowledgeLevelView, ladderCompact = false): string {
  const ladderClass = ladderCompact
    ? "knowledge-tier-ladder knowledge-tier-ladder--compact"
    : "knowledge-tier-ladder";
  const tiers = level.tiers?.length ? level.tiers : DEFAULT_TIERS;
  const steps = tiers
    .map((t) => {
      const here = t.id === level.level_id;
      return `<li class="knowledge-tier-step${here ? " is-here" : ""}"${here ? ' aria-current="step"' : ""}>
        <span class="knowledge-tier-dot" aria-hidden="true"></span>
        <span class="knowledge-tier-name">${esc(t.label)}</span>
        <span class="knowledge-tier-req muted">${esc(tierRequirementLabel(t))}</span>
        ${here ? '<span class="knowledge-tier-you">você está aqui</span>' : ""}
      </li>`;
    })
    .join("");
  const future = `<li class="knowledge-tier-step is-future" title="Faixa futura — além de Avançado">
        <span class="knowledge-tier-dot" aria-hidden="true"></span>
        <span class="knowledge-tier-name">Especialista</span>
        <span class="knowledge-tier-req muted">em breve</span>
      </li>`;
  return `<ol class="${ladderClass}">${steps}${future}</ol>`;
}

function subProgressRow(label: string, pct: number, detail: string): string {
  return `<div class="knowledge-sub-progress">
    <div class="knowledge-sub-progress-head">
      <span>${esc(label)}</span>
      <span class="muted">${pct.toFixed(0)}%</span>
    </div>
    <div class="knowledge-progress knowledge-progress-thin" role="progressbar" aria-valuenow="${pct}" aria-valuemin="0" aria-valuemax="100">
      <div class="knowledge-progress-fill knowledge-progress-fill-dim" style="width:${pct}%"></div>
    </div>
    <span class="knowledge-sub-detail muted">${esc(detail)}</span>
  </div>`;
}

export type KnowledgeProgressPanelOpts = {
  tierBarClass?: string;
  tierFillClass?: string;
  tierBarDataAttrs?: string;
  tierFillDataAttrs?: string;
  catalogBarDataAttrs?: string;
  catalogFillDataAttrs?: string;
  showCatalog?: boolean;
  catalogStudied?: number;
  catalogTotal?: number;
  catalogLabel?: string;
  compact?: boolean;
  ladderCompact?: boolean;
};

export function knowledgeProgressPanelHtml(
  level: KnowledgeLevelView,
  opts: KnowledgeProgressPanelOpts = {},
): string {
  const tierPct = tierProgressPct(level);
  const artPct = level.articles_progress_pct ?? tierPct;
  const wordPct = level.words_progress_pct ?? tierPct;
  const headline = formatKnowledgeHeadline(level);
  const nextHint = formatNextTierHint(level);
  const ladder = opts.compact ? "" : knowledgeTierLadderHtml(level, opts.ladderCompact);

  const tierBarExtra = opts.tierBarDataAttrs ?? "";
  const tierFillExtra = opts.tierFillDataAttrs ?? "";
  const tierBarClass = ["knowledge-progress", opts.tierBarClass].filter(Boolean).join(" ");
  const tierFillClass = ["knowledge-progress-fill", opts.tierFillClass].filter(Boolean).join(" ");
  const showCatalog =
    opts.showCatalog && opts.catalogTotal != null && opts.catalogTotal > 0;
  const catStudied = opts.catalogStudied ?? 0;
  const catTotal = opts.catalogTotal ?? 0;
  const catPct = catalogProgressPct(catStudied, catTotal);
  const catLabel = opts.catalogLabel ?? "Catálogo estudado";

  const catalogBlock = showCatalog
    ? `<div class="knowledge-catalog-block">
      <div class="knowledge-sub-progress-head">
        <span>${esc(catLabel)}</span>
        <span class="muted">${catStudied}/${catTotal} · ${catPct.toFixed(0)}%</span>
      </div>
      <div class="knowledge-progress knowledge-progress-thin"${opts.catalogBarDataAttrs ?? ""} role="progressbar" aria-valuenow="${catPct}" aria-label="Cobertura do catálogo">
        <div class="knowledge-progress-fill knowledge-progress-fill-catalog"${opts.catalogFillDataAttrs ?? ""} style="width:${catPct}%"></div>
      </div>
    </div>`
    : "";

  const dual = opts.compact
    ? ""
    : `${subProgressRow(
        "Artigos (faixa)",
        artPct,
        `${level.article_count} estudados · meta próxima faixa via contagem`,
      )}
      ${subProgressRow(
        "Palavras (faixa)",
        wordPct,
        `${formatWordCount(level.total_words)} acumuladas`,
      )}`;

  return `<div class="knowledge-progress-panel">
    <p class="knowledge-headline">${esc(headline)}</p>
    ${ladder}
    <p class="knowledge-tier-main-label muted">Progresso até a próxima faixa</p>
    <div class="${tierBarClass}"${tierBarExtra} role="progressbar" aria-valuenow="${tierPct}" aria-valuemin="0" aria-valuemax="100" title="${esc(nextHint)}">
      <div class="${tierFillClass}"${tierFillExtra} style="width:${tierPct}%"></div>
    </div>
    <p class="knowledge-next muted">${esc(nextHint)}</p>
    ${catalogBlock}
    ${dual}
  </div>`;
}
