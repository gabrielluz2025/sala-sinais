import { api } from "../api/client";
import { getReadArticleIds } from "./libraryReadProgress";
import {
  knowledgeProgressPanelHtml,
} from "./knowledgeTier";

export type KnowledgeLevel = {
  level_id: string;
  level_label: string;
  article_count: number;
  total_words: number;
  progress_pct: number;
  articles_progress_pct?: number;
  words_progress_pct?: number;
  next_level_id?: string | null;
  next_level_label: string | null;
  articles_to_next: number;
  words_to_next: number;
  formula_note: string;
  progress_scope?: string;
  tiers?: { id: string; label: string; min_articles: number; min_words: number }[];
};

export async function fetchKnowledgeLevel(): Promise<KnowledgeLevel | null> {
  try {
    const readIds = getReadArticleIds();
    return (await api.knowledgeLevel(readIds)) as KnowledgeLevel;
  } catch {
    return null;
  }
}

export async function fetchAgentKnowledgeLevel(): Promise<KnowledgeLevel | null> {
  try {
    return (await api.knowledgeLevelAgent()) as KnowledgeLevel;
  } catch {
    return null;
  }
}

export function formatWordCount(n: number): string {
  if (n >= 10_000) return `${Math.round(n / 1000)} mil`;
  return n.toLocaleString("pt-BR");
}

export function knowledgeCardHtml(level: KnowledgeLevel | null): string {
  if (!level) {
    return `<article class="kpi-card" id="knowledge-level-card">
      <h4 class="kpi-label">Conhecimento</h4>
      <p class="kpi-sub muted">Biblioteca indisponível</p>
    </article>`;
  }
  return `<article class="kpi-card kpi-knowledge" id="knowledge-level-card">
    <h4 class="kpi-label">Seu progresso</h4>
    ${knowledgeProgressPanelHtml(level, { compact: true, showCatalog: false })}
    <span class="kpi-sub">${level.article_count} artigos lidos · ${formatWordCount(level.total_words)} palavras</span>
    <button type="button" class="kpi-library-link" data-open-library>Abrir biblioteca</button>
  </article>`;
}
