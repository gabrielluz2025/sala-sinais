"""Métricas por trade fechado (compra/venda) a partir dos sinais."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from api.pnl import closed_in_today, resolved_pnl_for_row, row_closed_timestamp
from shared.schemas import SignalSide

if TYPE_CHECKING:
    from api.database import SignalRow


def is_closed_trade_row(row: SignalRow) -> bool:
    """Trade encerrado: tem preço de saída ou status closed com PnL resolvível."""
    if row.exit_price is not None:
        return True
    st = (row.status or "").lower()
    if st == "closed":
        return row.exit_price is not None or row.net_pnl_brl is not None
    if st == "filled" and row.closed_at and row.exit_price is not None:
        return True
    _, net, _ = resolved_pnl_for_row(row)
    return net is not None


def trade_is_win(row: SignalRow, net: float) -> bool:
    if row.outcome == "win":
        return True
    if row.outcome == "loss":
        return False
    if row.outcome == "breakeven":
        return False
    return net > 0


def row_to_trade_dict(row: SignalRow) -> dict | None:
    gross, net, fees = resolved_pnl_for_row(row)
    if net is None or gross is None or row.exit_price is None:
        return None
    closed_raw = row_closed_timestamp(row)
    opened_raw = row.created_at
    return {
        "id": row.id,
        "symbol": row.symbol,
        "side": row.side,
        "entry": float(row.entry),
        "exit": float(row.exit_price),
        "shares": int(row.contracts),
        "gross_pnl": round(gross, 2),
        "fees": round(fees, 2),
        "net_pnl": round(net, 2),
        "opened_at": datetime.fromisoformat(opened_raw),
        "closed_at": datetime.fromisoformat(row.closed_at) if row.closed_at else None,
        "strategy_type": row.strategy_type,
        "entry_reason": row.entry_reason,
        "exit_reason": row.exit_reason,
        "win": trade_is_win(row, net),
    }


def filter_trade_rows(
    rows: list[SignalRow],
    *,
    symbol: str | None,
    today_only: bool,
    today: str,
) -> list[SignalRow]:
    out: list[SignalRow] = []
    sym_u = (symbol or "").upper().strip() or None
    for r in rows:
        if not is_closed_trade_row(r):
            continue
        if sym_u and (r.symbol or "").upper() != sym_u:
            continue
        if today_only and not closed_in_today(r, today):
            continue
        out.append(r)
    out.sort(key=lambda r: row_closed_timestamp(r), reverse=True)
    return out


def build_trade_summaries(trades: list[dict]) -> tuple[dict, list[dict]]:
    """Retorna (global_summary, by_symbol)."""
    by_sym: dict[str, dict] = {}
    wins = losses = 0
    net_sum = 0.0
    best_net: float | None = None
    worst_net: float | None = None

    for t in trades:
        net = float(t["net_pnl"])
        net_sum += net
        if t["win"]:
            wins += 1
        else:
            losses += 1
        if best_net is None or net > best_net:
            best_net = net
        if worst_net is None or net < worst_net:
            worst_net = net

        sym = (t["symbol"] or "").upper()
        bucket = by_sym.setdefault(
            sym,
            {"symbol": sym, "trades": 0, "wins": 0, "losses": 0, "net_pnl_brl": 0.0},
        )
        bucket["trades"] += 1
        bucket["net_pnl_brl"] = round(bucket["net_pnl_brl"] + net, 2)
        if t["win"]:
            bucket["wins"] += 1
        else:
            bucket["losses"] += 1

    by_symbol = []
    for b in sorted(by_sym.values(), key=lambda x: x["symbol"]):
        n = b["trades"]
        wr = round(b["wins"] / n * 100, 2) if n else None
        by_symbol.append({**b, "win_rate": wr})

    global_summary = {
        "trades": len(trades),
        "wins": wins,
        "losses": losses,
        "net_pnl_brl": round(net_sum, 2),
        "best_trade_net": best_net,
        "worst_trade_net": worst_net,
    }
    return global_summary, by_symbol
