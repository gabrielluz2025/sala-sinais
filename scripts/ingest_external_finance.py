#!/usr/bin/env python3
"""Ingestão v1: Finnhub + NewsAPI (+ RSS opcional) → library/news/*.md."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.ingest_library_news import ingest_urls  # noqa: E402
from scripts.library_news_io import strip_html, write_news_md  # noqa: E402

USER_AGENT = "SalaSinais-LibraryIngest/1.0 (+local; educational)"
MIN_INTERVAL_SEC = 2.0


def _get_json(url: str, timeout: int = 25) -> object | None:
    req = Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8", errors="replace"))
    except (HTTPError, URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
        print(f"[warn] GET falhou {url}: {exc}", file=sys.stderr)
        return None


def ingest_finnhub(api_key: str, *, max_items: int = 5, dry_run: bool = False) -> list[str]:
    if not api_key.strip():
        return []
    q = urlencode({"category": "general", "token": api_key.strip()})
    url = f"https://finnhub.io/api/v1/news?{q}"
    data = _get_json(url)
    if not isinstance(data, list):
        return []
    written: list[str] = []
    for item in data[:max_items]:
        if not isinstance(item, dict):
            continue
        title = str(item.get("headline") or item.get("title") or "").strip()
        link = str(item.get("url") or item.get("source") or "").strip()
        summary = strip_html(str(item.get("summary") or ""))
        pub = ""
        ts = item.get("datetime")
        if isinstance(ts, (int, float)) and ts > 0:
            from datetime import datetime, timezone

            pub = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%a, %d %b %Y %H:%M:%S %z")
        if dry_run:
            print(f"[dry-run][finnhub] {title}")
            continue
        path = write_news_md(
            title=title,
            link=link,
            snippet=summary,
            pub=pub,
            feed_url="https://finnhub.io/api/v1/news",
            source_tag="finnhub",
            script_name="ingest_external_finance.py",
        )
        if path:
            written.append(str(path.relative_to(ROOT)).replace("\\", "/"))
        time.sleep(MIN_INTERVAL_SEC)
    return written


def ingest_newsapi(api_key: str, *, max_items: int = 5, dry_run: bool = False) -> list[str]:
    if not api_key.strip():
        return []
    params = {
        "country": "br",
        "category": "business",
        "pageSize": str(max(1, min(max_items, 20))),
        "apiKey": api_key.strip(),
    }
    url = f"https://newsapi.org/v2/top-headlines?{urlencode(params)}"
    data = _get_json(url)
    if not isinstance(data, dict):
        return []
    articles = data.get("articles")
    if not isinstance(articles, list):
        return []
    written: list[str] = []
    for item in articles[:max_items]:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or "").strip()
        link = str(item.get("url") or "").strip()
        summary = strip_html(str(item.get("description") or item.get("content") or ""))
        pub = str(item.get("publishedAt") or "")
        if dry_run:
            print(f"[dry-run][newsapi] {title}")
            continue
        path = write_news_md(
            title=title,
            link=link,
            snippet=summary,
            pub=pub,
            feed_url="https://newsapi.org/v2/top-headlines",
            source_tag="newsapi",
            script_name="ingest_external_finance.py",
        )
        if path:
            written.append(str(path.relative_to(ROOT)).replace("\\", "/"))
        time.sleep(MIN_INTERVAL_SEC)
    return written


def run_all_ingest(
    *,
    rss_urls: list[str] | None = None,
    finnhub_key: str | None = None,
    newsapi_key: str | None = None,
    max_per_source: int = 5,
    dry_run: bool = False,
) -> dict[str, list[str]]:
    rss = rss_urls if rss_urls is not None else []
    fh = finnhub_key if finnhub_key is not None else os.environ.get("FINNHUB_API_KEY", "")
    na = newsapi_key if newsapi_key is not None else os.environ.get("NEWSAPI_KEY", "")
    if not rss:
        env_rss = os.environ.get("LIBRARY_NEWS_RSS_URLS", "")
        rss = [u.strip() for u in env_rss.split(",") if u.strip()]

    out: dict[str, list[str]] = {"rss": [], "finnhub": [], "newsapi": []}
    if rss:
        out["rss"] = ingest_urls(rss, max_per_feed=max_per_source, dry_run=dry_run)
    out["finnhub"] = ingest_finnhub(fh or "", max_items=max_per_source, dry_run=dry_run)
    out["newsapi"] = ingest_newsapi(na or "", max_items=max_per_source, dry_run=dry_run)
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Ingest RSS + Finnhub + NewsAPI → library/news/")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--max-per-source", type=int, default=5)
    parser.add_argument("--rss-only", action="store_true", help="Só RSS (LIBRARY_NEWS_RSS_URLS)")
    parser.add_argument("--api-only", action="store_true", help="Só Finnhub/NewsAPI")
    args = parser.parse_args()

    rss_urls: list[str] | None = [] if args.api_only else None
    fh = "" if args.rss_only else None
    na = "" if args.rss_only else None

    result = run_all_ingest(
        rss_urls=rss_urls,
        finnhub_key=fh,
        newsapi_key=na,
        max_per_source=args.max_per_source,
        dry_run=args.dry_run,
    )
    total = sum(len(v) for v in result.values())
    print(f"Gravados: {total} (rss={len(result['rss'])}, finnhub={len(result['finnhub'])}, newsapi={len(result['newsapi'])})")
    for layer, paths in result.items():
        for p in paths:
            print(f"  [{layer}] {p}")
    if total == 0 and not args.dry_run:
        print(
            "Nenhum arquivo. Configure LIBRARY_NEWS_RSS_URLS, FINNHUB_API_KEY e/ou NEWSAPI_KEY no .env.\n"
            "Ver docs/BIBLIOTECA_FONTES_EXTERNAS.md",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
