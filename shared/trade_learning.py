"""Agregados e insights a partir de trades fechados (sem ML)."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LEARNING_JSON = ROOT / "data" / "trade_learning.json"

TZ_BR = ZoneInfo("America/Sao_Paulo")
ROLLING_N = 20
LOSS_STREAK_GUARD = 3
LOW_WIN_RATE_PCT = 40.0
MIN_TRADES_FOR_GUARD = 8

SESSION_HOUR_BUCKETS: tuple[tuple[str, int, int], ...] = (
    ("pre_10", 0, 10),
    ("10_12", 10, 12),
    ("12_14", 12, 14),
    ("14_16", 14, 16),
    ("16_17", 16, 17),
    ("pos_17", 17, 24),
)

STRATEGY_LABEL_PT = {
    "breakout": "breakout",
    "volatility": "volatilidade",
}


def session_hour_bucket(dt: datetime | None) -> str:
    """Faixa horária BRT do fechamento (ou abertura se fechamento ausente)."""
    if dt is None:
        return "unknown"
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=TZ_BR)
    else:
        dt = dt.astimezone(TZ_BR)
    h = dt.hour
    for bucket_id, start, end in SESSION_HOUR_BUCKETS:
        if start <= h < end:
            return bucket_id
    return "unknown"


def session_hour_bucket_label(bucket_id: str) -> str:
    labels = {
        "pre_10": "antes das 10h",
        "10_12": "10h–12h",
        "12_14": "12h–14h",
        "14_16": "14h–16h",
        "16_17": "16h–17h",
        "pos_17": "após 17h",
        "unknown": "horário indefinido",
    }
    return labels.get(bucket_id, bucket_id)


def trade_duration_minutes(opened_at: datetime | None, closed_at: datetime | None) -> float | None:
    if opened_at is None or closed_at is None:
        return None
    if opened_at.tzinfo is None:
        opened_at = opened_at.replace(tzinfo=TZ_BR)
    if closed_at.tzinfo is None:
        closed_at = closed_at.replace(tzinfo=TZ_BR)
    sec = (closed_at - opened_at).total_seconds()
    if sec < 0:
        return None
    return round(sec / 60.0, 1)


def enrich_closed_trade(trade: dict[str, Any]) -> dict[str, Any]:
    """Campos derivados para aprendizado (a partir de row_to_trade_dict)."""
    opened = trade.get("opened_at")
    closed = trade.get("closed_at")
    if isinstance(opened, str):
        opened = datetime.fromisoformat(opened)
    if isinstance(closed, str):
        closed = datetime.fromisoformat(closed)
    bucket = session_hour_bucket(closed or opened)
    duration = trade_duration_minutes(opened, closed)
    st = (trade.get("strategy_type") or "volatility").strip().lower()
    if st not in ("breakout", "volatility"):
        st = "volatility"
    return {
        **trade,
        "strategy_type": st,
        "session_hour_bucket": bucket,
        "duration_minutes": duration,
    }


def _win_rate(wins: int, total: int) -> float | None:
    if total <= 0:
        return None
    return round(wins / total * 100.0, 2)


def _avg(values: list[float]) -> float | None:
    if not values:
        return None
    return round(sum(values) / len(values), 2)


def expectancy(avg_win: float | None, avg_loss: float | None, win_rate_pct: float | None) -> float | None:
    """Expectativa por trade (R$): WR*avg_win + (1-WR)*avg_loss (avg_loss negativo)."""
    if avg_win is None or avg_loss is None or win_rate_pct is None:
        return None
    wr = win_rate_pct / 100.0
    return round(wr * avg_win + (1.0 - wr) * avg_loss, 2)


def _bucket_stats(trades: list[dict[str, Any]]) -> dict[str, Any]:
    wins = sum(1 for t in trades if t.get("win"))
    losses = len(trades) - wins
    nets = [float(t["net_pnl"]) for t in trades]
    win_nets = [float(t["net_pnl"]) for t in trades if t.get("win")]
    loss_nets = [float(t["net_pnl"]) for t in trades if not t.get("win")]
    wr = _win_rate(wins, len(trades))
    return {
        "trades": len(trades),
        "wins": wins,
        "losses": losses,
        "win_rate_pct": wr,
        "net_pnl_brl": round(sum(nets), 2) if nets else 0.0,
        "avg_win_brl": _avg(win_nets),
        "avg_loss_brl": _avg(loss_nets),
        "expectancy_brl": expectancy(_avg(win_nets), _avg(loss_nets), wr),
    }


def aggregate_by_strategy(trades: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for t in trades:
        st = t.get("strategy_type") or "volatility"
        groups.setdefault(st, []).append(t)
    return {k: _bucket_stats(v) for k, v in sorted(groups.items())}


def aggregate_by_symbol(trades: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for t in trades:
        sym = (t.get("symbol") or "").upper()
        if not sym:
            continue
        groups.setdefault(sym, []).append(t)
    return {k: _bucket_stats(v) for k, v in sorted(groups.items())}


def aggregate_by_session_hour(trades: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for t in trades:
        b = t.get("session_hour_bucket") or "unknown"
        groups.setdefault(b, []).append(t)
    return {k: _bucket_stats(v) for k, v in sorted(groups.items())}


def rolling_last_n(trades: list[dict[str, Any]], n: int = ROLLING_N) -> dict[str, Any]:
    """Trades já ordenados do mais recente para o mais antigo."""
    window = trades[:n]
    base = _bucket_stats(window)
    base["window"] = n
    streak = 0
    for t in window:
        if t.get("win"):
            break
        streak += 1
    base["loss_streak"] = streak
    return base


def compute_performance_learning(
    enriched: list[dict[str, Any]],
    *,
    rolling_n: int = ROLLING_N,
) -> dict[str, Any]:
    by_strategy = aggregate_by_strategy(enriched)
    by_symbol = aggregate_by_symbol(enriched)
    by_hour = aggregate_by_session_hour(enriched)
    rolling = rolling_last_n(enriched, rolling_n)
    global_stats = _bucket_stats(enriched)
    window = enriched[:rolling_n]
    combo_groups: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for t in window:
        sym = (t.get("symbol") or "").upper()
        st = t.get("strategy_type") or "volatility"
        combo_groups.setdefault((sym, st), []).append(t)
    rolling_combos = [
        {"symbol": sym, "strategy_type": st, **_bucket_stats(items)}
        for (sym, st), items in sorted(combo_groups.items())
        if sym and items
    ]
    best_strategy = None
    worst_strategy = None
    if by_strategy:
        ranked = sorted(
            by_strategy.items(),
            key=lambda x: (x[1].get("win_rate_pct") or 0, x[1].get("net_pnl_brl") or 0),
            reverse=True,
        )
        best_strategy = {"id": ranked[0][0], **ranked[0][1]}
        worst_strategy = {"id": ranked[-1][0], **ranked[-1][1]}
    return {
        "trade_count": len(enriched),
        "rolling_n": rolling_n,
        "global": global_stats,
        "rolling": rolling,
        "rolling_combos": rolling_combos,
        "by_strategy": by_strategy,
        "by_symbol": by_symbol,
        "by_session_hour": by_hour,
        "best_strategy": best_strategy,
        "worst_strategy": worst_strategy,
        "updated_at": datetime.now(TZ_BR).isoformat(),
    }


def generate_insights_pt(perf: dict[str, Any], *, rolling_n: int = ROLLING_N) -> list[str]:
    insights: list[str] = []
    rolling = perf.get("rolling") or {}
    wr = rolling.get("win_rate_pct")
    if rolling.get("trades", 0) >= 3 and wr is not None:
        insights.append(
            f"Últimos {min(rolling.get('trades', 0), rolling_n)} trades: "
            f"{wr:.0f}% acerto · PnL {rolling.get('net_pnl_brl', 0):+.2f} R$"
        )
    streak = rolling.get("loss_streak") or 0
    if streak >= LOSS_STREAK_GUARD:
        insights.append(
            f"Sequência de {streak} perdas recentes — motor pode aumentar cooldown e filtrar sinais fracos."
        )
    for combo in perf.get("rolling_combos") or []:
        if combo.get("trades", 0) < 3:
            continue
        label = STRATEGY_LABEL_PT.get(combo.get("strategy_type") or "", combo.get("strategy_type") or "")
        swr = combo.get("win_rate_pct")
        if swr is None:
            continue
        insights.append(
            f"{label} em {combo['symbol']}: {swr:.0f}% acerto últimos {combo['trades']}"
        )
        break
    by_sym = perf.get("by_symbol") or {}
    for sym, stats in sorted(by_sym.items(), key=lambda x: x[1].get("trades", 0), reverse=True):
        if stats.get("trades", 0) < 5:
            continue
        swr = stats.get("win_rate_pct")
        if swr is None:
            continue
        insights.append(f"{sym}: {swr:.0f}% acerto em {stats['trades']} fechados")
        break
    by_st = perf.get("by_strategy") or {}
    for st, stats in by_st.items():
        if stats.get("trades", 0) < MIN_TRADES_FOR_GUARD:
            continue
        label = STRATEGY_LABEL_PT.get(st, st)
        swr = stats.get("win_rate_pct")
        if swr is not None:
            insights.append(
                f"{label}: {swr:.0f}% acerto · expectativa {stats.get('expectancy_brl', 0):+.2f} R$/trade"
            )
    exp = rolling.get("expectancy_brl")
    if exp is not None and rolling.get("trades", 0) >= MIN_TRADES_FOR_GUARD:
        if exp < 0:
            insights.append(f"Expectativa negativa ({exp:+.2f} R$/trade) — reduza tamanho ou pause setups fracos.")
        elif exp > 0:
            insights.append(f"Expectativa positiva ({exp:+.2f} R$/trade) nos últimos trades.")
    if not insights:
        insights.append("Poucos trades fechados — opere ou simule mais para o agente aprender padrões.")
    return insights[:8]


def compute_soft_guards(
    perf: dict[str, Any],
    active_strategy: str,
    *,
    base_cooldown_sec: int,
) -> dict[str, Any]:
    """
    Guardas conservadoras: não bloqueiam boleta manual.
    - cooldown_extra quando WR baixo ou sequência de perdas
    - skip_weak_signals: sinais com regime fraco (volatility) quando guarda ativa
    - qty_factor: reduz contratos sugeridos no estudo / auto (mín. 1)
    """
    active = (active_strategy or "volatility").strip().lower()
    rolling = perf.get("rolling") or {}
    st_stats = (perf.get("by_strategy") or {}).get(active) or {}
    reasons: list[str] = []
    guarded = False

    streak = int(rolling.get("loss_streak") or 0)
    if streak >= LOSS_STREAK_GUARD:
        guarded = True
        reasons.append(f"{streak} perdas seguidas")

    wr_roll = rolling.get("win_rate_pct")
    if rolling.get("trades", 0) >= MIN_TRADES_FOR_GUARD and wr_roll is not None and wr_roll < LOW_WIN_RATE_PCT:
        guarded = True
        reasons.append(f"WR {wr_roll:.0f}% últimos {rolling.get('window', ROLLING_N)}")

    wr_st = st_stats.get("win_rate_pct")
    if st_stats.get("trades", 0) >= MIN_TRADES_FOR_GUARD and wr_st is not None and wr_st < LOW_WIN_RATE_PCT:
        guarded = True
        reasons.append(f"estratégia {active} WR {wr_st:.0f}%")

    cooldown_sec = base_cooldown_sec
    qty_factor = 1.0
    skip_weak = False
    if guarded:
        cooldown_sec = int(base_cooldown_sec * 2)
        qty_factor = 0.5
        skip_weak = True

    return {
        "active": guarded,
        "reasons": reasons,
        "cooldown_sec": cooldown_sec,
        "skip_weak_signals": skip_weak,
        "qty_factor": qty_factor,
    }


def load_learning_file(path: Path | None = None) -> dict[str, Any]:
    p = path or DEFAULT_LEARNING_JSON
    if not p.is_file():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def save_learning_file(payload: dict[str, Any], path: Path | None = None) -> Path:
    p = path or DEFAULT_LEARNING_JSON
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return p


def refresh_persisted_learning(
    enriched: list[dict[str, Any]],
    *,
    path: Path | None = None,
    rolling_n: int = ROLLING_N,
    max_recent: int = 40,
) -> dict[str, Any]:
    perf = compute_performance_learning(enriched, rolling_n=rolling_n)
    insights = generate_insights_pt(perf, rolling_n=rolling_n)
    recent_records = [
        {
            "symbol": t.get("symbol"),
            "side": t.get("side"),
            "strategy_type": t.get("strategy_type"),
            "entry_reason": (t.get("entry_reason") or "")[:160],
            "net_pnl": t.get("net_pnl"),
            "win": t.get("win"),
            "duration_minutes": t.get("duration_minutes"),
            "session_hour_bucket": t.get("session_hour_bucket"),
            "closed_at": t.get("closed_at").isoformat()
            if isinstance(t.get("closed_at"), datetime)
            else t.get("closed_at"),
        }
        for t in enriched[:max_recent]
    ]
    payload = {
        "version": 1,
        "performance_learning": perf,
        "insights_pt": insights,
        "last_insight": insights[0] if insights else None,
        "recent_closed": recent_records,
        "updated_at": perf.get("updated_at"),
    }
    save_learning_file(payload, path)
    return payload
