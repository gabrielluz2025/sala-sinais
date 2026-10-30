"""API: estatísticas de aprendizado a partir de trades fechados no SQLite."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy.orm import Session

from api.agent_config import get_or_create_config
from api.trades_metrics import filter_trade_rows, row_to_trade_dict
from api.database import SignalRow
from shared.trade_learning import (
    ROLLING_N,
    compute_performance_learning,
    compute_soft_guards,
    enrich_closed_trade,
    generate_insights_pt,
    load_learning_file,
    refresh_persisted_learning,
)

ROOT = Path(__file__).resolve().parents[1]


def _load_enriched_closed_trades(db: Session, *, limit: int = 500) -> list[dict]:
    from datetime import datetime
    from zoneinfo import ZoneInfo

    rows = db.query(SignalRow).order_by(SignalRow.id.desc()).limit(limit * 3).all()
    today = datetime.now(ZoneInfo("America/Sao_Paulo")).date().isoformat()
    filtered = filter_trade_rows(rows, symbol=None, today_only=False, today=today)
    enriched: list[dict] = []
    for r in filtered:
        item = row_to_trade_dict(r)
        if item:
            enriched.append(enrich_closed_trade(item))
        if len(enriched) >= limit:
            break
    return enriched


def build_performance_learning(
    db: Session,
    enriched: list[dict] | None = None,
    *,
    rolling_n: int = ROLLING_N,
) -> dict:
    if enriched is None:
        enriched = _load_enriched_closed_trades(db)
    cfg = get_or_create_config(db)
    active = (cfg.strategy_type or "volatility").strip().lower()
    perf = compute_performance_learning(enriched, rolling_n=rolling_n)
    from engine.config import settings

    guards = compute_soft_guards(
        perf,
        active,
        base_cooldown_sec=int(settings.signal_cooldown_sec),
    )
    perf["soft_guards"] = guards
    perf["active_strategy"] = active
    return perf


def get_learning_stats_response(db: Session) -> dict:
    enriched = _load_enriched_closed_trades(db)
    perf = build_performance_learning(db, enriched)
    insights = generate_insights_pt(perf)
    if _auto_learn_enabled():
        refresh_persisted_learning(enriched)
    return {
        "performance_learning": perf,
        "insights_pt": insights,
        "last_insight": insights[0] if insights else None,
        "auto_learn_enabled": _auto_learn_enabled(),
    }


def get_learning_insights_response(db: Session) -> dict:
    cached = load_learning_file()
    if cached.get("insights_pt") and cached.get("performance_learning"):
        return {
            "insights_pt": cached.get("insights_pt") or [],
            "last_insight": cached.get("last_insight"),
            "updated_at": cached.get("updated_at"),
            "performance_learning": cached.get("performance_learning"),
        }
    stats = get_learning_stats_response(db)
    return {
        "insights_pt": stats["insights_pt"],
        "last_insight": stats["last_insight"],
        "updated_at": stats["performance_learning"].get("updated_at"),
        "performance_learning": stats["performance_learning"],
    }


def maybe_refresh_trade_learning_db(db: Session) -> None:
    if not _auto_learn_enabled():
        return
    enriched = _load_enriched_closed_trades(db)
    refresh_persisted_learning(enriched)


def refresh_trade_learning_from_db(db: Session) -> dict:
    enriched = _load_enriched_closed_trades(db)
    return refresh_persisted_learning(enriched)


def _auto_learn_enabled() -> bool:
    try:
        from api.config import settings

        return bool(settings.auto_learn_from_trades)
    except Exception:
        return True
