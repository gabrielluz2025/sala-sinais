#!/usr/bin/env python3
"""Ingestão v1 de notícias RSS → library/news/*.md (catálogo dinâmico)."""

from __future__ import annotations

import argparse
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
NEWS_DIR = ROOT / "library" / "news"
TEMPLATE = NEWS_DIR / "_TEMPLATE.md"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.library_news_io import (  # noqa: E402
    strip_html as _strip_html,
    write_news_md as _write_news_md,
)

USER_AGENT = "SalaSinais-LibraryNews/1.0 (+local ingest; educational)"
MIN_INTERVAL_SEC = 2.0


def _parse_rss(xml_bytes: bytes) -> list[dict]:
    root = ET.fromstring(xml_bytes)
    items: list[dict] = []
    for item in root.iter("item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        desc = (item.findtext("description") or item.findtext("{http://purl.org/rss/1.0/}description") or "").strip()
        pub = item.findtext("pubDate") or item.findtext("published") or ""
        items.append({"title": title, "link": link, "description": desc, "pubDate": pub})
    return items


def fetch_feed(url: str, timeout: int = 20) -> bytes:
    req = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(req, timeout=timeout) as resp:
        return resp.read()


def ingest_urls(urls: list[str], *, max_per_feed: int = 5, dry_run: bool = False) -> list[str]:
    written: list[str] = []
    for url in urls:
        url = url.strip()
        if not url:
            continue
        try:
            raw = fetch_feed(url)
        except (URLError, TimeoutError, OSError) as exc:
            print(f"[warn] Falha ao buscar {url}: {exc}", file=sys.stderr)
            continue
        try:
            items = _parse_rss(raw)[:max_per_feed]
        except ET.ParseError as exc:
            print(f"[warn] RSS inválido {url}: {exc}", file=sys.stderr)
            continue
        for it in items:
            snippet = _strip_html(it.get("description") or "")
            if dry_run:
                print(f"[dry-run] {it.get('title')}")
                continue
            path = _write_news_md(
                title=it.get("title") or "",
                link=it.get("link") or "",
                snippet=snippet,
                pub=it.get("pubDate") or "",
                feed_url=url,
                source_tag="rss",
                script_name="scripts/ingest_library_news.py",
            )
            if path:
                written.append(str(path.relative_to(ROOT)).replace("\\", "/"))
        time.sleep(MIN_INTERVAL_SEC)
    return written


def copy_template() -> Path:
    NEWS_DIR.mkdir(parents=True, exist_ok=True)
    if not TEMPLATE.is_file():
        TEMPLATE.write_text(
            """---
title: "Título da notícia (manual)"
category: noticias
tags: manual
updated: 2026-10-29
source_url: https://
disclaimer: Cole snippet ou resumo; confirme na fonte.
---

# Título

Resumo em 2–4 parágrafos para estudo do agente.

**Fonte:** link
""",
            encoding="utf-8",
        )
    return TEMPLATE


def main() -> int:
    parser = argparse.ArgumentParser(description="Ingest RSS → library/news/")
    parser.add_argument("--dry-run", action="store_true", help="Só listar itens, não gravar")
    parser.add_argument("--template", action="store_true", help="Criar/atualizar _TEMPLATE.md")
    parser.add_argument("--url", action="append", dest="urls", help="URL RSS (repita ou use env)")
    parser.add_argument("--max-per-feed", type=int, default=5)
    args = parser.parse_args()

    if args.template:
        p = copy_template()
        print(f"Template: {p}")
        return 0

    urls = list(args.urls or [])
    if not urls:
        import os

        env = os.environ.get("LIBRARY_NEWS_RSS_URLS", "")
        urls = [u.strip() for u in env.split(",") if u.strip()]

    if not urls:
        copy_template()
        print(
            "Nenhuma URL. Defina LIBRARY_NEWS_RSS_URLS no .env ou use --url.\n"
            "Ingestão manual: copie library/news/_TEMPLATE.md para YYYY-MM-DD-slug.md"
        )
        return 1

    written = ingest_urls(urls, max_per_feed=args.max_per_feed, dry_run=args.dry_run)
    print(f"Gravados: {len(written)}")
    for w in written:
        print(f"  - {w}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
