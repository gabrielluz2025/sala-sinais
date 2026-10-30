"""Feed RSS público — cache em memória para evitar hammering."""

from __future__ import annotations

import time
import xml.etree.ElementTree as ET
from typing import Any

import httpx

from api.config import settings

_cache: dict[str, Any] = {"items": [], "fetched_at": 0.0, "error": None}

RSS_URL = (
    "https://news.google.com/rss/search?"
    "q=economia+brasil+mercado+financeiro&hl=pt-BR&gl=BR&ceid=BR:pt-419"
)


def _parse_rss(xml_text: str, limit: int) -> list[dict[str, str]]:
    root = ET.fromstring(xml_text)
    channel = root.find("channel")
    if channel is None:
        return []
    items: list[dict[str, str]] = []
    for item in channel.findall("item")[:limit]:
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        pub = (item.findtext("pubDate") or "").strip()
        if title and link:
            items.append({"title": title, "link": link, "published": pub})
    return items


def get_headlines(limit: int = 8) -> dict[str, Any]:
    now = time.time()
    ttl = settings.news_cache_sec
    if _cache["items"] and (now - _cache["fetched_at"]) < ttl:
        return {"items": _cache["items"][:limit], "cached": True, "error": None}

    try:
        with httpx.Client(timeout=12.0, follow_redirects=True) as client:
            resp = client.get(RSS_URL, headers={"User-Agent": "SalaSinais/1.0"})
            resp.raise_for_status()
        items = _parse_rss(resp.text, limit=max(limit, 10))
        _cache["items"] = items
        _cache["fetched_at"] = now
        _cache["error"] = None
        return {"items": items[:limit], "cached": False, "error": None}
    except Exception as exc:
        _cache["error"] = str(exc)
        if _cache["items"]:
            return {"items": _cache["items"][:limit], "cached": True, "error": str(exc)}
        return {"items": [], "cached": False, "error": str(exc)}
