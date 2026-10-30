"""Curva de patrimônio (capital inicial + PnL líquido fechado)."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

from api.pnl import (
    estimate_open_pnl_brl,
    is_open_row,
    latest_open_positions,
    load_quote_mid_map,
    resolved_pnl_for_row,
    row_closed_timestamp,
)

if TYPE_CHECKING:
    from api.database import SignalRow

TZ_BR = ZoneInfo("America/Sao_Paulo")


def _closed_date_key(row: SignalRow) -> str:
    ts = row_closed_timestamp(row)
    if not ts:
        return datetime.now(TZ_BR).date().isoformat()
    if len(ts) >= 10 and ts[4] == "-" and ts[7] == "-":
        return ts[:10]
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=TZ_BR)
        return dt.astimezone(TZ_BR).date().isoformat()
    except ValueError:
        return datetime.now(TZ_BR).date().isoformat()


def build_equity_curve(
    rows: list[SignalRow],
    capital_brl: float,
    quote_mids: dict[str, float] | None = None,
    now: datetime | None = None,
) -> dict:
    """Monta série diária e resumo; sem persistência em equity_snapshots."""
    capital = round(float(capital_brl), 2)
    now_dt = now or datetime.now(TZ_BR)
    today = now_dt.astimezone(TZ_BR).date().isoformat()

    closed_events: list[tuple[str, float]] = []
    for row in rows:
        _, net, _ = resolved_pnl_for_row(row)
        if net is None:
            continue
        closed_events.append((_closed_date_key(row), round(net, 2)))

    closed_events.sort(key=lambda t: t[0])

    if quote_mids is None:
        quote_mids = load_quote_mid_map()
    open_rows = [r for r in rows if is_open_row(r)]
    portfolio_open = latest_open_positions(open_rows)
    open_mtm = round(
        sum(estimate_open_pnl_brl(r, quote_mids) for r in portfolio_open),
        2,
    )

    message: str | None = None
    points: list[dict] = []

    if not closed_events:
        equity = round(capital + open_mtm, 2)
        points.append(
            {
                "date": today,
                "equity_brl": equity,
                "daily_pnl_net": 0.0,
                "cumulative_pnl_net": 0.0,
                "drawdown_pct": 0.0,
            }
        )
        message = (
            "Nenhuma operação fechada ainda — patrimônio reflete o capital inicial da configuração."
        )
        summary = _summary_from_points(points, capital, open_mtm > 0)
        return {
            "initial_capital_brl": capital,
            "points": points,
            "summary": summary,
            "message": message,
        }

    daily: dict[str, float] = defaultdict(float)
    for d, net in closed_events:
        daily[d] += net

    cumulative = 0.0
    peak = capital
    for day in sorted(daily.keys()):
        daily_net = round(daily[day], 2)
        cumulative = round(cumulative + daily_net, 2)
        equity = round(capital + cumulative, 2)
        peak = max(peak, equity)
        dd = round(((equity - peak) / peak) * 100, 4) if peak > 0 else 0.0
        points.append(
            {
                "date": day,
                "equity_brl": equity,
                "daily_pnl_net": daily_net,
                "cumulative_pnl_net": cumulative,
                "drawdown_pct": dd,
            }
        )

    if open_rows:
        last = points[-1]
        base_equity = last["equity_brl"]
        equity_est = round(base_equity + open_mtm, 2)
        peak_est = max(peak, equity_est)
        dd_est = round(((equity_est - peak_est) / peak_est) * 100, 4) if peak_est > 0 else 0.0
        if points[-1]["date"] == today:
            points[-1] = {
                **last,
                "equity_brl": equity_est,
                "drawdown_pct": dd_est,
            }
        else:
            points.append(
                {
                    "date": today,
                    "equity_brl": equity_est,
                    "daily_pnl_net": 0.0,
                    "cumulative_pnl_net": last["cumulative_pnl_net"],
                    "drawdown_pct": dd_est,
                }
            )
        peak = peak_est

    summary = _summary_from_points(points, capital, open_mtm != 0.0)
    return {
        "initial_capital_brl": capital,
        "points": points,
        "summary": summary,
        "message": message,
    }


def _summary_from_points(points: list[dict], capital: float, includes_open_mtm: bool) -> dict:
    equities = [p["equity_brl"] for p in points] if points else [capital]
    current = equities[-1]
    peak = max(equities)
    minimum = min(equities)
    change_pct = round(((current - capital) / capital) * 100, 2) if capital > 0 else 0.0
    return {
        "initial_capital_brl": capital,
        "current_equity_brl": round(current, 2),
        "peak_equity_brl": round(peak, 2),
        "min_equity_brl": round(minimum, 2),
        "change_pct": change_pct,
        "includes_open_mtm": includes_open_mtm,
    }
