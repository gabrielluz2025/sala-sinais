import { api } from "../api/client";
import type { KnowledgeLevel } from "./knowledge";
import {
  formatKnowledgeHeadline,
  catalogProgressPct,
} from "./knowledgeTier";
import { renderAgentJournalHtml } from "./agentJournalView";

export type AgentLibraryStudyStatus = {
  auto_study_enabled: boolean;
  state: string;
  studied_count: number;
  total_articles: number;
  level_id: string;
  level_label: string;
  progress_pct: number;
  last_studied_at: string | null;
  last_article_title: string | null;
  next_article_title: string | null;
  recently_active: boolean;
  studied_article_ids?: string[];
  operational_maturity_pct?: number;
  closed_trades_count?: number;
};

let lastAgentStudySnapshot: AgentLibraryStudyStatus | null = null;
let lastAgentLevelSnapshot: KnowledgeLevel | null = null;

export type AgentJournalSnapshot = {
  markdown: string;
  win_count: number;
  close_count?: number;
  loss_count?: number;
  saved_since_first_win?: boolean;
  updated_at: string | null;
  last_win_at: string | null;
  last_study_at: string | null;
};

export async function fetchAgentLibraryStudyStatus(): Promise<AgentLibraryStudyStatus | null> {
  try {
    return (await api.agentLibraryStudyStatus()) as AgentLibraryStudyStatus;
  } catch {
    return null;
  }
}

export async function fetchAgentJournal(): Promise<AgentJournalSnapshot | null> {
  try {
    return (await api.agentJournal()) as AgentJournalSnapshot;
  } catch {
    return null;
  }
}

export function agentStudyArticleProgressPct(status: AgentLibraryStudyStatus | null): number {
  if (!status?.total_articles) return 0;
  return Math.round((status.studied_count / status.total_articles) * 1000) / 10;
}

export function agentKnowledgeBarPct(
  agentLevel: KnowledgeLevel | null,
  agentStudy: AgentLibraryStudyStatus | null,
): number {
  if (agentLevel) return agentLevel.progress_pct;
  return agentStudy?.progress_pct ?? 0;
}

function formatStudyTimestamp(iso: string | null | undefined): string {
  if (!iso) return "—";
  try {
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return iso;
    return d.toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" });
  } catch {
    return iso;
  }
}

export function formatAgentStudyLine(status: AgentLibraryStudyStatus | null): string {
  if (!status) return "Agente: biblioteca indisponível";
  if (!status.auto_study_enabled) {
    return `Agente: ocioso · ${status.studied_count}/${status.total_articles} artigos · ${status.level_label}`;
  }
  const prefix = "Estudo 24h ativo · ";
  const lastAt = formatStudyTimestamp(status.last_studied_at);
  if (status.recently_active && status.last_article_title) {
    return `${prefix}Agente lendo: ${status.last_article_title} · ${status.studied_count}/${status.total_articles} · ${status.level_label} · ${lastAt}`;
  }
  if (status.state === "complete") {
    return `${prefix}Agente: biblioteca completa · ${status.level_label}`;
  }
  const next = status.next_article_title ? ` · próximo: ${status.next_article_title}` : "";
  return `${prefix}${status.studied_count}/${status.total_articles} artigos · ${status.level_label}${next} · último estudo ${lastAt}`;
}

export function agentStudiedIdSet(status: AgentLibraryStudyStatus | null): Set<string> {
  if (!status?.studied_article_ids?.length) return new Set();
  return new Set(status.studied_article_ids);
}

export function syncAgentLibraryStudyDom(
  agentLevel: KnowledgeLevel | null,
  agentStudy: AgentLibraryStudyStatus | null,
): void {
  if (agentStudy) lastAgentStudySnapshot = agentStudy;
  if (agentLevel) lastAgentLevelSnapshot = agentLevel;
  const study = agentStudy ?? lastAgentStudySnapshot;
  const level = agentLevel ?? lastAgentLevelSnapshot;
  const barPct = agentKnowledgeBarPct(level, study);
  document.querySelectorAll<HTMLElement>("[data-agent-study-line]").forEach((el) => {
    el.textContent = formatAgentStudyLine(study);
  });
  document.querySelectorAll<HTMLElement>("[data-agent-knowledge-bar]").forEach((el) => {
    el.setAttribute("aria-valuenow", String(barPct));
  });
  document.querySelectorAll<HTMLElement>("[data-agent-knowledge-fill]").forEach((el) => {
    el.style.width = `${barPct}%`;
  });
  document.querySelectorAll<HTMLElement>("[data-agent-library-fill]").forEach((el) => {
    el.style.width = `${barPct}%`;
  });
  document.querySelectorAll<HTMLElement>("[data-agent-catalog-fill]").forEach((el) => {
    const pct = catalogProgressPct(study?.studied_count ?? 0, study?.total_articles ?? 0);
    el.style.width = `${pct}%`;
  });
  document.querySelectorAll<HTMLElement>("[data-agent-catalog-bar]").forEach((el) => {
    const pct = catalogProgressPct(study?.studied_count ?? 0, study?.total_articles ?? 0);
    el.setAttribute("aria-valuenow", String(pct));
  });
  document.querySelectorAll<HTMLElement>("[data-agent-library-bar]").forEach((el) => {
    el.setAttribute("aria-valuenow", String(barPct));
  });
  syncAgentPracticeMaturityDom(study);
  const meta = document.querySelector("[data-agent-library-meta]");
  if (meta && study) {
    meta.textContent = `${study.studied_count}/${study.total_articles} artigos · ${study.level_label} · último estudo ${formatStudyTimestamp(study.last_studied_at)}`;
  }
  const levelTitle = document.querySelector("[data-agent-library-level]");
  if (levelTitle && level) {
    levelTitle.textContent = formatKnowledgeHeadline(level);
  } else if (levelTitle) {
    levelTitle.textContent = study?.level_label ?? "—";
  }
  const headlineEl = document.querySelector("[data-agent-knowledge-headline]");
  if (headlineEl && level) {
    headlineEl.textContent = formatKnowledgeHeadline(level);
  }
}

export function formatAgentJournalSubtitle(journal: AgentJournalSnapshot | null): string {
  if (journal?.saved_since_first_win) {
    const extra = journal.updated_at ? ` · ${formatStudyTimestamp(journal.updated_at)}` : "";
    return `Salvo desde primeiro acerto · erros visíveis${extra}`;
  }
  if ((journal?.close_count ?? 0) > 0) {
    return "Diário iniciado · aguardando primeiro acerto · erros visíveis";
  }
  return "Aguardando fechamentos — estudo da biblioteca preenche o cabeçalho";
}

export function syncAgentJournalDom(journal: AgentJournalSnapshot | null): void {
  const body = document.querySelector<HTMLElement>("[data-journal-body]");
  const sub = document.querySelector<HTMLElement>("[data-journal-updated]");
  if (!body && !sub) return;
  if (sub) {
    sub.textContent = formatAgentJournalSubtitle(journal);
  }
  if (body) {
    body.innerHTML = renderAgentJournalHtml(journal?.markdown);
  }
}

export function syncAgentPracticeMaturityDom(agentStudy: AgentLibraryStudyStatus | null): void {
  if (agentStudy) lastAgentStudySnapshot = agentStudy;
  const study = agentStudy ?? lastAgentStudySnapshot;
  if (!study) return;
  const pct = study.operational_maturity_pct ?? 0;
  document.querySelectorAll<HTMLElement>("[data-agent-practice-bar]").forEach((el) => {
    el.setAttribute("aria-valuenow", String(pct));
  });
  document.querySelectorAll<HTMLElement>("[data-agent-practice-fill]").forEach((el) => {
    el.style.width = `${pct}%`;
  });
  const label = document.querySelector<HTMLElement>("[data-agent-practice-label]");
  if (label) {
    const n = study.closed_trades_count ?? 0;
    label.textContent = `Experiência prática · ${pct.toFixed(0)}% · ${n} fechamento${n === 1 ? "" : "s"}`;
  }
}
