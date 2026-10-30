"""Helpers compartilhados: gravar digest em library/news/."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NEWS_DIR = ROOT / "library" / "news"


def slugify(text: str, max_len: int = 60) -> str:
    s = text.lower().strip()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = s.strip("-")
    return (s[:max_len] or "item").strip("-")


def item_date_slug(pub: str) -> str:
    if pub:
        try:
            dt = parsedate_to_datetime(pub)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc).strftime("%Y-%m-%d")
        except Exception:
            pass
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", " ", text).replace("&nbsp;", " ").strip()


def write_news_md(
    *,
    title: str,
    link: str,
    snippet: str,
    pub: str,
    feed_url: str,
    source_tag: str = "rss",
    script_name: str = "ingest_library_news.py",
) -> Path | None:
    if not title:
        return None
    day = item_date_slug(pub)
    base_id = slugify(title)
    NEWS_DIR.mkdir(parents=True, exist_ok=True)
    path = NEWS_DIR / f"{day}-{base_id}.md"
    n = 1
    while path.exists():
        path = NEWS_DIR / f"{day}-{base_id}-{n}.md"
        n += 1
    body = snippet or "(Sem resumo na fonte.)"
    if len(body) > 1200:
        body = body[:1197] + "..."
    safe_title = title.replace('"', "'")[:200]
    md = f"""---
title: "{safe_title}"
category: noticias
tags: {source_tag}, digest
updated: {day}
source_url: {link or feed_url}
disclaimer: Resumo automático para estudo; confirme na fonte original antes de operar.
source: news
---

# {title}

{body}

---

**Fonte:** {link or feed_url}

*Este arquivo foi gerado por `{script_name}`. Não é recomendação de investimento.*
"""
    path.write_text(md, encoding="utf-8")
    return path
