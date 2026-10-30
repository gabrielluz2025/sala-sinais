import { api } from "../api/client";

export const LIBRARY_READ_STORAGE_KEY = "sala_sinais_library_read_v1";
export const LIBRARY_READ_CHANGED_EVENT = "library-read-progress-changed";

type StoredProgress = {
  readIds: string[];
};

function loadStored(): StoredProgress {
  try {
    const raw = localStorage.getItem(LIBRARY_READ_STORAGE_KEY);
    if (!raw) return { readIds: [] };
    const parsed = JSON.parse(raw) as StoredProgress;
    const readIds = Array.isArray(parsed.readIds)
      ? parsed.readIds.filter((id): id is string => typeof id === "string" && id.length > 0)
      : [];
    return { readIds: [...new Set(readIds)] };
  } catch {
    return { readIds: [] };
  }
}

function persistStored(data: StoredProgress): void {
  localStorage.setItem(LIBRARY_READ_STORAGE_KEY, JSON.stringify(data));
}

export function getReadArticleIds(): string[] {
  return loadStored().readIds;
}

export function isArticleRead(id: string): boolean {
  return loadStored().readIds.includes(id);
}

/** Marca artigo como lido (local + sync opcional na API). Retorna true se era novo. */
export function markArticleRead(articleId: string): boolean {
  const trimmed = articleId.trim();
  if (!trimmed) return false;
  const stored = loadStored();
  if (stored.readIds.includes(trimmed)) return false;
  stored.readIds.push(trimmed);
  persistStored(stored);
  void syncReadProgressToApi(stored.readIds).catch(() => undefined);
  window.dispatchEvent(new CustomEvent(LIBRARY_READ_CHANGED_EVENT));
  return true;
}

export async function syncReadProgressToApi(readIds?: string[]): Promise<void> {
  const ids = readIds ?? getReadArticleIds();
  await api.putLibraryReadProgress(ids, true);
}

export async function hydrateReadProgressFromApi(): Promise<void> {
  try {
    const remote = await api.libraryReadProgress();
    const local = loadStored();
    const merged = [...new Set([...local.readIds, ...(remote.read_article_ids || [])])];
    if (merged.length !== local.readIds.length) {
      persistStored({ readIds: merged });
    }
  } catch {
    /* offline */
  }
}
