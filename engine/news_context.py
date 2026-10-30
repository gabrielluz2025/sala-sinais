"""Filtro heurístico de manchetes (PT) — não é NLP nem recomendação de investimento."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Literal, Optional

import httpx

from engine.config import settings

log = logging.getLogger("engine.news_context")

NewsBias = Literal["neutral", "cautious", "slight_aggressive"]

CAUTIOUS_KEYWORDS = (
    "copom",
    "selic",
    "inflação",
    "inflacao",
    "crise",
    "queda forte",
    "recessão",
    "recessao",
    "default",
    "falência",
    "falencia",
)

AGGRESSIVE_KEYWORDS = (
    "alta",
    "recorde",
    "rally",
    "superávit",
    "superavit",
)

# Artigos da biblioteca referenciados no log quando a regra dispara
LIB_ARTICLE_CAUTION = "04"
LIB_ARTICLE_NEWS = "07"


@dataclass
class NewsContext:
    bias: NewsBias
    matched_title: str | None
    headline_count: int


def _normalize(text: str) -> str:
    return (text or "").lower()


def bias_from_headlines(headlines: list[dict[str, Any]]) -> NewsContext:
    cautious_hit: str | None = None
    aggressive_hit: str | None = None
    for item in headlines:
        title = _normalize(str(item.get("title") or ""))
        if not title:
            continue
        for kw in CAUTIOUS_KEYWORDS:
            if kw in title:
                cautious_hit = str(item.get("title") or title)
                break
        if cautious_hit:
            break
        for kw in AGGRESSIVE_KEYWORDS:
            if kw in title:
                aggressive_hit = str(item.get("title") or title)
                break
    if cautious_hit:
        return NewsContext(bias="cautious", matched_title=cautious_hit, headline_count=len(headlines))
    if aggressive_hit:
        return NewsContext(
            bias="slight_aggressive",
            matched_title=aggressive_hit,
            headline_count=len(headlines),
        )
    return NewsContext(bias="neutral", matched_title=None, headline_count=len(headlines))


def fetch_headlines(limit: int = 8) -> list[dict[str, Any]]:
    base = settings.api_base_url.rstrip("/")
    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(f"{base}/news/headlines", params={"limit": limit})
            resp.raise_for_status()
            data = resp.json()
            items = data.get("items") or []
            return items if isinstance(items, list) else []
    except Exception as exc:
        log.debug("headlines indisponíveis: %s", exc)
        return []


def load_news_context() -> NewsContext:
    return bias_from_headlines(fetch_headlines())


def _use_news_filter(agent_config: dict | None) -> bool:
    if agent_config is None:
        return True
    val = agent_config.get("use_news_filter")
    if val is None:
        return True
    return bool(val)


def filter_strategy_result(result, agent_config: dict | None):
    """Aplica regras de manchetes ao sinal; pode bloquear entrada ou ajustar stops."""
    if result is None or not _use_news_filter(agent_config):
        return result

    ctx = load_news_context()
    if ctx.bias == "neutral":
        return result

    payload = result.payload
    note_suffix = ""

    if ctx.bias == "cautious" and ctx.matched_title:
        short = ctx.matched_title[:120]
        note_suffix = (
            f" Notícia: {short} (cautela) — ver biblioteca art. {LIB_ARTICLE_CAUTION}/{LIB_ARTICLE_NEWS}."
        )
        # Reduz sinais: não abre nova posição em clima de cautela heurística
        log.info("Sinal bloqueado por filtro de notícias (cautela): %s", short)
        return None

    if ctx.bias == "slight_aggressive" and ctx.matched_title:
        short = ctx.matched_title[:120]
        note_suffix = f" Notícia: {short} (viés levemente otimista — heurística, art. {LIB_ARTICLE_NEWS})."
        entry_reason = (result.entry_reason or "") + note_suffix
        payload.entry_reason = entry_reason
        return type(result)(
            payload=payload,
            entry_reason=entry_reason,
            strategy_type=result.strategy_type,
            strategy_version=result.strategy_version,
            regime=getattr(result, "regime", None),
        )

    return result
