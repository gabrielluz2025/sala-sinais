"""Catálogo v2 — mescla index.json curado + imported/*.md + news/*.md."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

from fastapi import HTTPException

_ROOT = Path(__file__).resolve().parents[1]
_LIBRARY_DIR = _ROOT / "library"
_INDEX_FILE = _LIBRARY_DIR / "index.json"
_IMPORTED_DIR = _LIBRARY_DIR / "imported"
_NEWS_DIR = _LIBRARY_DIR / "news"

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)

DEFAULT_CATEGORIES: dict[str, str] = {
    "fundamentos": "Fundamentos",
    "risco": "Risco",
    "estrategias": "Estratégias",
    "candles": "Candlesticks",
    "fontes": "Fontes abertas",
    "acoes-b3": "Ações B3",
    "noticias": "Notícias",
    "psicologia": "Psicologia",
    "macro": "Macro",
    "imported": "Importados",
}


def _load_index_raw() -> dict:
    if not _INDEX_FILE.is_file():
        raise HTTPException(503, "Biblioteca indisponível — index.json ausente")
    try:
        return json.loads(_INDEX_FILE.read_text(encoding="utf-8"))
    except Exception as exc:
        raise HTTPException(500, f"Erro ao ler biblioteca: {exc}") from exc


def _parse_frontmatter(text: str) -> tuple[dict[str, str], str]:
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return {}, text
    meta: dict[str, str] = {}
    for line in m.group(1).splitlines():
        if ":" not in line:
            continue
        key, _, val = line.partition(":")
        key = key.strip().lower()
        val = val.strip().strip('"').strip("'")
        if key:
            meta[key] = val
    body = text[m.end() :]
    return meta, body


def _title_from_body(body: str, fallback: str) -> str:
    for line in body.splitlines():
        if line.startswith("# "):
            return line[2:].strip()[:200] or fallback
    return fallback


def _tags_from_meta(meta: dict[str, str]) -> list[str]:
    raw = meta.get("tags") or ""
    if not raw:
        return []
    return [t.strip() for t in raw.split(",") if t.strip()]


def _entry_from_md_file(
    path: Path,
    *,
    source: str,
    rel_prefix: str,
    default_category: str,
) -> dict:
    text = path.read_text(encoding="utf-8", errors="replace")
    meta, body = _parse_frontmatter(text)
    stem = path.stem
    article_id = meta.get("id") or stem
    title = meta.get("title") or _title_from_body(body, stem.replace("-", " ").title())
    category = meta.get("category") or default_category
    updated = meta.get("updated") or datetime.fromtimestamp(
        path.stat().st_mtime, tz=timezone.utc
    ).strftime("%Y-%m-%d")
    rel = f"{rel_prefix}{path.name}"
    entry: dict = {
        "id": article_id,
        "title": title,
        "category": category,
        "tags": _tags_from_meta(meta),
        "path": rel,
        "updated": updated,
        "source": source,
    }
    if meta.get("source_url"):
        entry["source_url"] = meta["source_url"]
    if meta.get("disclaimer"):
        entry["disclaimer"] = meta["disclaimer"]
    return entry


def _glob_layer_entries() -> list[dict]:
    entries: list[dict] = []
    if _IMPORTED_DIR.is_dir():
        for path in sorted(_IMPORTED_DIR.glob("*.md")):
            if path.name.upper().startswith("README") or path.name.startswith("_"):
                continue
            entries.append(
                _entry_from_md_file(
                    path,
                    source="imported",
                    rel_prefix="imported/",
                    default_category="imported",
                )
            )
    if _NEWS_DIR.is_dir():
        for path in sorted(_NEWS_DIR.glob("*.md")):
            if path.name.upper().startswith("README") or path.name.startswith("_"):
                continue
            entries.append(
                _entry_from_md_file(
                    path,
                    source="news",
                    rel_prefix="news/",
                    default_category="noticias",
                )
            )
    return entries


def load_merged_catalog() -> dict:
    """Retorna {categories, articles} com todas as camadas."""
    raw = _load_index_raw()
    cat_by_id: dict[str, dict] = {}
    for c in raw.get("categories") or []:
        cid = c.get("id")
        if cid:
            cat_by_id[cid] = {"id": cid, "label": c.get("label") or cid}
    for cid, label in DEFAULT_CATEGORIES.items():
        if cid not in cat_by_id:
            cat_by_id[cid] = {"id": cid, "label": label}

    articles: list[dict] = []
    seen_ids: set[str] = set()
    for a in raw.get("articles") or []:
        aid = a.get("id")
        if not aid or aid in seen_ids:
            continue
        seen_ids.add(aid)
        item = dict(a)
        item.setdefault("source", "curated")
        articles.append(item)

    for entry in _glob_layer_entries():
        aid = entry.get("id")
        if not aid or aid in seen_ids:
            continue
        seen_ids.add(aid)
        articles.append(entry)
        cat = entry.get("category") or ""
        if cat and cat not in cat_by_id:
            cat_by_id[cat] = {"id": cat, "label": DEFAULT_CATEGORIES.get(cat, cat)}

    return {
        "categories": sorted(cat_by_id.values(), key=lambda x: x["id"]),
        "articles": articles,
    }


def catalog_article_by_id(article_id: str) -> dict | None:
    for a in load_merged_catalog().get("articles") or []:
        if a.get("id") == article_id:
            return a
    return None


def catalog_counts() -> dict[str, int]:
    articles = load_merged_catalog().get("articles") or []
    curated = imported = news = 0
    for a in articles:
        src = a.get("source") or "curated"
        if src == "news":
            news += 1
        elif src == "imported":
            imported += 1
        else:
            curated += 1
    article_like = curated + imported
    return {
        "curated_count": curated,
        "imported_count": imported,
        "news_count": news,
        "article_count": article_like,
        "catalog_total": len(articles),
    }
