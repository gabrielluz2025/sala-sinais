"""Estudo autônomo da biblioteca pelo agente (marca leitura + nível, sem LLM)."""

from __future__ import annotations

import json
import re
import threading
from datetime import datetime, timezone
from pathlib import Path

from api.library import _article_markdown_path, _word_count_file, get_knowledge_counts_for_read_ids
from api.library_catalog import load_merged_catalog
from api.library_knowledge import AGENT_STUDY_FORMULA_NOTE, compute_knowledge_level
from api.config import settings

_ROOT = Path(__file__).resolve().parents[1]
_PROGRESS_FILE = _ROOT / "data" / "agent_library_progress.json"
_MAX_LOG_ENTRIES = 80
_TICK_LOCK = threading.Lock()

_HEADING_RE = re.compile(r"^#\s+(.+)$", re.MULTILINE)


def is_auto_study_enabled() -> bool:
    return bool(settings.agent_auto_study_library)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_agent_library_progress() -> dict:
    if not _PROGRESS_FILE.is_file():
        return {
            "read_article_ids": [],
            "last_studied_at": None,
            "study_log": [],
            "operational_maturity_pct": 0.0,
            "closed_trades_count": 0,
            "journal_win_count": 0,
        }
    try:
        data = json.loads(_PROGRESS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {
            "read_article_ids": [],
            "last_studied_at": None,
            "study_log": [],
            "operational_maturity_pct": 0.0,
            "closed_trades_count": 0,
            "journal_win_count": 0,
        }
    ids = data.get("read_article_ids") or []
    log = data.get("study_log") or []
    return {
        "read_article_ids": [str(x) for x in ids if x],
        "last_studied_at": data.get("last_studied_at"),
        "study_log": log if isinstance(log, list) else [],
        "operational_maturity_pct": float(data.get("operational_maturity_pct") or 0),
        "closed_trades_count": int(data.get("closed_trades_count") or 0),
        "journal_win_count": int(data.get("journal_win_count") or 0),
    }


def save_agent_library_progress(payload: dict) -> None:
    _PROGRESS_FILE.parent.mkdir(parents=True, exist_ok=True)
    prev = load_agent_library_progress()
    out = {
        "read_article_ids": list(payload.get("read_article_ids") or prev.get("read_article_ids") or []),
        "last_studied_at": payload.get("last_studied_at", prev.get("last_studied_at")),
        "study_log": list(payload.get("study_log") or prev.get("study_log") or [])[-_MAX_LOG_ENTRIES:],
        "operational_maturity_pct": payload.get(
            "operational_maturity_pct", prev.get("operational_maturity_pct", 0)
        ),
        "closed_trades_count": payload.get(
            "closed_trades_count", prev.get("closed_trades_count", 0)
        ),
        "journal_win_count": payload.get("journal_win_count", prev.get("journal_win_count", 0)),
        "updated_at": _now_iso(),
    }
    _PROGRESS_FILE.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")


def _ordered_articles() -> list[dict]:
    raw = load_merged_catalog()
    return list(raw.get("articles") or [])


def _studied_set(read_ids: list[str]) -> set[str]:
    valid = {a.get("id") for a in _ordered_articles() if a.get("id")}
    return {rid for rid in read_ids if rid in valid}


def next_unread_article(read_ids: list[str]) -> dict | None:
    studied = _studied_set(read_ids)
    for article in _ordered_articles():
        aid = article.get("id")
        if aid and aid not in studied:
            return article
    return None


def _first_heading_digest(markdown: str, fallback_title: str) -> str:
    m = _HEADING_RE.search(markdown)
    heading = (m.group(1).strip() if m else fallback_title)[:120]
    return f"Estudado: {heading}"


def agent_knowledge_level():
    progress = load_agent_library_progress()
    article_count, total_words = get_knowledge_counts_for_read_ids(progress["read_article_ids"])
    return compute_knowledge_level(
        article_count,
        total_words,
        formula_note=AGENT_STUDY_FORMULA_NOTE,
    )


def _last_log_entry(progress: dict) -> dict | None:
    log = progress.get("study_log") or []
    if not log:
        return None
    last = log[-1]
    return last if isinstance(last, dict) else None


def get_agent_study_status() -> dict:
    articles = _ordered_articles()
    total = len(articles)
    progress = load_agent_library_progress()
    read_ids = progress["read_article_ids"]
    studied_count = len(_studied_set(read_ids))
    level = agent_knowledge_level()
    last_log = _last_log_entry(progress)
    last_id = last_log.get("article_id") if last_log else None
    last_title = last_log.get("title") if last_log else None
    if not last_title and read_ids:
        by_id = {a.get("id"): a for a in articles if a.get("id")}
        prev = read_ids[-1]
        last_id = last_id or prev
        last_title = (by_id.get(prev) or {}).get("title") or prev

    nxt = next_unread_article(read_ids)
    auto_on = is_auto_study_enabled()
    complete = studied_count >= total and total > 0

    recently_active = False
    last_at = progress.get("last_studied_at")
    if last_at and auto_on:
        try:
            ts = datetime.fromisoformat(str(last_at).replace("Z", "+00:00"))
            age = (datetime.now(timezone.utc) - ts.astimezone(timezone.utc)).total_seconds()
            recently_active = age <= max(30, settings.agent_study_interval_sec * 2)
        except Exception:
            recently_active = False

    if not auto_on:
        state = "idle"
    elif complete:
        state = "complete"
    elif recently_active and nxt:
        state = "studying"
    elif nxt:
        state = "active"
    else:
        state = "idle"

    op_pct = float(progress.get("operational_maturity_pct") or 0)
    closed_trades = int(progress.get("closed_trades_count") or 0)

    return {
        "auto_study_enabled": auto_on,
        "state": state,
        "studied_count": studied_count,
        "total_articles": total,
        "level_id": level.level_id,
        "level_label": level.level_label,
        "progress_pct": level.progress_pct,
        "article_count": level.article_count,
        "total_words": level.total_words,
        "last_studied_at": last_at,
        "last_article_id": last_id,
        "last_article_title": last_title,
        "next_article_id": nxt.get("id") if nxt else None,
        "next_article_title": nxt.get("title") if nxt else None,
        "recently_active": recently_active,
        "formula_note": AGENT_STUDY_FORMULA_NOTE,
        "studied_article_ids": sorted(_studied_set(read_ids)),
        "operational_maturity_pct": op_pct,
        "closed_trades_count": closed_trades,
    }


def agent_study_tick(*, force: bool = False) -> dict:
    """Marca o próximo artigo como estudado. Retorna dict serializável."""
    with _TICK_LOCK:
        if not force and not is_auto_study_enabled():
            status = get_agent_study_status()
            return {
                "ticked": False,
                "article_id": None,
                "title": None,
                "digest": None,
                "studied_count": status["studied_count"],
                "total_articles": status["total_articles"],
                "complete": status["studied_count"] >= status["total_articles"],
                "message": "Estudo autônomo desligado (AGENT_AUTO_STUDY_LIBRARY=false).",
            }

        articles = _ordered_articles()
        total = len(articles)
        progress = load_agent_library_progress()
        read_ids = list(progress["read_article_ids"])
        nxt = next_unread_article(read_ids)
        if not nxt:
            studied = len(_studied_set(read_ids))
            return {
                "ticked": False,
                "article_id": None,
                "title": None,
                "digest": None,
                "studied_count": studied,
                "total_articles": total,
                "complete": True,
                "message": "Biblioteca completa — todos os artigos já estudados pelo agente.",
            }

        aid = str(nxt["id"])
        title = str(nxt.get("title") or aid)
        path = _article_markdown_path(nxt)
        if not path.is_file():
            return {
                "ticked": False,
                "article_id": aid,
                "title": title,
                "digest": None,
                "studied_count": len(_studied_set(read_ids)),
                "total_articles": total,
                "complete": False,
                "message": f"Arquivo ausente para artigo {aid}.",
            }

        markdown = path.read_text(encoding="utf-8", errors="replace")
        words = _word_count_file(path)
        digest = _first_heading_digest(markdown, title)
        studied_at = _now_iso()

        if aid not in read_ids:
            read_ids.append(aid)
        log = list(progress.get("study_log") or [])
        log.append(
            {
                "article_id": aid,
                "title": title,
                "studied_at": studied_at,
                "word_count": words,
                "digest": digest,
            }
        )
        save_agent_library_progress(
            {
                "read_article_ids": read_ids,
                "last_studied_at": studied_at,
                "study_log": log,
            }
        )
        studied_count = len(_studied_set(read_ids))
        try:
            from api.agent_journal import on_library_study_tick

            on_library_study_tick(
                article_id=aid,
                title=title,
                studied_count=studied_count,
                total_articles=total,
            )
        except Exception:
            pass
        return {
            "ticked": True,
            "article_id": aid,
            "title": title,
            "digest": digest,
            "studied_count": studied_count,
            "total_articles": total,
            "complete": studied_count >= total,
            "message": f"Agente estudou «{title}» ({studied_count}/{total}).",
        }
