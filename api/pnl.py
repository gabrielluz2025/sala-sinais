"""PnL líquido estimado — WIN/WDO (pontos) e ações B3 (preço × quantidade)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

from api.config import settings
from shared.schemas import SignalSide

if TYPE_CHECKING:
    from api.database import SignalRow

_ROOT = Path(__file__).resolve().parents[1]
_QUOTE_FILE = _ROOT / "data" / "last_quote.json"
_QUOTE_HISTORY_FILE = _ROOT / "data" / "quote_history.json"

# R$ por ponto por contrato (WIN futuro)
WIN_POINT_VALUE_BRL = 0.20


def is_futures_symbol(symbol: str) -> bool:
    s = (symbol or "").upper()
    return s.startswith("WIN") or s.startswith("WDO")


def points_delta(side: SignalSide, entry: float, exit_price: float) -> float:
    if side == SignalSide.BUY:
        return exit_price - entry
    return entry - exit_price


def gross_pnl_brl(
    side: SignalSide,
    entry: float,
    exit_price: float,
    contracts: int,
    symbol: str | None = None,
) -> float:
    pts = points_delta(side, entry, exit_price)
    if symbol and not is_futures_symbol(symbol):
        return pts * contracts
    return pts * WIN_POINT_VALUE_BRL * contracts


def fees_per_contract_round() -> float:
    return settings.b3_fee_per_contract_round + settings.broker_fee_per_contract


def trade_fees_brl(
    entry: float,
    exit_price: float,
    contracts: int,
    symbol: str | None = None,
) -> float:
    """Taxas estimadas na ida+volta (B3/corretagem ou emolumentos % em ações)."""
    if symbol and not is_futures_symbol(symbol) and settings.equity_emolument_pct > 0:
        volume = (float(entry) + float(exit_price)) * int(contracts)
        emoluments = volume * settings.equity_emolument_pct
        broker = settings.broker_fee_per_contract * int(contracts)
        return emoluments + broker
    return fees_per_contract_round() * int(contracts)


def net_pnl_brl(
    side: SignalSide,
    entry: float,
    exit_price: float,
    contracts: int,
    symbol: str | None = None,
) -> float:
    gross = gross_pnl_brl(side, entry, exit_price, contracts, symbol=symbol)
    fees = trade_fees_brl(entry, exit_price, contracts, symbol=symbol)
    return gross - fees


def fees_for_row(row: SignalRow, exit_price: float | None = None) -> float:
    exit_px = exit_price if exit_price is not None else row.exit_price
    if exit_px is not None:
        return trade_fees_brl(row.entry, float(exit_px), row.contracts, symbol=row.symbol)
    # Aberto: estima taxa na entrada + mesma saída (proxy)
    return trade_fees_brl(row.entry, row.entry, row.contracts, symbol=row.symbol)


def estimated_ir_brl(net_before_tax_brl: float) -> float:
    """IR day trade estimado (educacional) — não é retido automaticamente."""
    if net_before_tax_brl <= 0:
        return 0.0
    return round(net_before_tax_brl * settings.day_trade_ir_rate, 2)


def pnl_tax_breakdown(net_before_tax_brl: float) -> tuple[float, float]:
    ir = estimated_ir_brl(net_before_tax_brl)
    after = round(net_before_tax_brl - ir, 2)
    return ir, after


def resolved_pnl_for_row(row: SignalRow) -> tuple[float | None, float | None, float]:
    """Gross, net e taxas; None se operação ainda aberta."""
    if row.exit_price is not None:
        fees = fees_for_row(row, row.exit_price)
    else:
        fees = fees_for_row(row)
    if row.gross_pnl_brl is not None and row.net_pnl_brl is not None:
        return row.gross_pnl_brl, row.net_pnl_brl, fees
    if row.exit_price is not None:
        side = SignalSide(row.side)
        gross = gross_pnl_brl(side, row.entry, row.exit_price, row.contracts, symbol=row.symbol)
        net = net_pnl_brl(side, row.entry, row.exit_price, row.contracts, symbol=row.symbol)
        return gross, net, fees
    return None, None, fees


def _mid_from_quote_point(p: dict) -> float | None:
    mid = p.get("mid")
    if mid is not None:
        try:
            return float(mid)
        except (TypeError, ValueError):
            pass
    bid, ask = p.get("bid"), p.get("ask")
    if bid is not None and ask is not None:
        return (float(bid) + float(ask)) / 2.0
    last = p.get("last")
    if last is not None:
        try:
            return float(last)
        except (TypeError, ValueError):
            pass
    return None


def load_quote_mid_map() -> dict[str, float]:
    """Último mid (bid+ask)/2 por símbolo a partir do histórico e last_quote."""
    mids: dict[str, float] = {}
    if _QUOTE_HISTORY_FILE.is_file():
        try:
            raw = json.loads(_QUOTE_HISTORY_FILE.read_text(encoding="utf-8"))
            if isinstance(raw, list):
                for p in raw:
                    if not isinstance(p, dict):
                        continue
                    sym = (p.get("symbol") or "").upper()
                    px = _mid_from_quote_point(p)
                    if sym and px is not None:
                        mids[sym] = px
        except Exception:
            pass
    if _QUOTE_FILE.is_file():
        try:
            p = json.loads(_QUOTE_FILE.read_text(encoding="utf-8"))
            if isinstance(p, dict):
                sym = (p.get("symbol") or "").upper()
                px = _mid_from_quote_point(p)
                if sym and px is not None:
                    mids[sym] = px
        except Exception:
            pass
    return mids


def estimate_open_pnl_brl(row: SignalRow, quote_mids: dict[str, float]) -> float:
    mid = quote_mids.get((row.symbol or "").upper())
    if mid is None:
        return 0.0
    side = SignalSide(row.side)
    gross = gross_pnl_brl(side, row.entry, mid, row.contracts, symbol=row.symbol)
    return gross - fees_for_row(row, mid)


def is_closed_row(row: SignalRow) -> bool:
    _, net, _ = resolved_pnl_for_row(row)
    return net is not None


def row_closed_timestamp(row: SignalRow) -> str:
    return row.closed_at or row.created_at


def closed_in_today(row: SignalRow, today: str) -> bool:
    if not is_closed_row(row):
        return False
    return row_closed_timestamp(row).startswith(today)


def closed_in_month(row: SignalRow, month_prefix: str) -> bool:
    if not is_closed_row(row):
        return False
    return row_closed_timestamp(row).startswith(month_prefix)


def is_open_row(row: SignalRow) -> bool:
    """Sinal/posição ainda sem PnL realizado (inclui FILLED em carteira)."""
    if is_closed_row(row):
        return False
    st = (row.status or "").lower()
    if st in ("cancelled", "rejected", "closed"):
        return False
    return st in ("filled", "pending", "sent", "open")


def latest_open_positions(open_rows: list[SignalRow]) -> list[SignalRow]:
    """Uma linha por símbolo — sinal aberto mais recente (evita 100+ duplicatas legadas)."""
    latest: dict[str, SignalRow] = {}
    for row in open_rows:
        sym = (row.symbol or "").upper()
        if not sym:
            continue
        prev = latest.get(sym)
        if prev is None or (row.created_at or "") >= (prev.created_at or ""):
            latest[sym] = row
    return list(latest.values())


def count_open_positions(open_rows: list[SignalRow]) -> int:
    """Conta posições únicas (1 por símbolo — sinal aberto mais recente)."""
    return len(latest_open_positions(open_rows))
