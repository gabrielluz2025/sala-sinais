"""GET /market/tickers-summary — cotações rápidas do Pulse Deck."""

from __future__ import annotations

import json
from datetime import datetime
from zoneinfo import ZoneInfo

from pathlib import Path

from api.market_ohlc import load_m1_bars
from api.pnl import _mid_from_quote_point
from shared.schemas import MarketTickerSummaryItem, MarketTickersSummaryResponse

_ROOT = Path(__file__).resolve().parents[1]
_QUOTE_FILE = _ROOT / "data" / "last_quote.json"
_QUOTE_HISTORY_FILE = _ROOT / "data" / "quote_history.json"

TZ_BR = ZoneInfo("America/Sao_Paulo")

PULSE_DECK_TICKERS: list[str] = [
    "IBOV",
    "PETR4",
    "VALE3",
    "WIN$",
    "WDO$",
    "ITUB4",
    "BBDC4",
]

TICKER_LABELS: dict[str, str] = {
    "IBOV": "IBOV",
    "PETR4": "PETR4",
    "VALE3": "VALE3",
    "WIN$": "WIN$ (Mini Índice)",
    "WDO$": "WDO$ (Mini Dólar)",
    "ITUB4": "ITUB4",
    "BBDC4": "BBDC4",
}

_DATA = _ROOT / "data"

from shared.mt5_symbols import mt5_symbol_candidates


def _bars_file_exists(symbol: str) -> bool:
    return (_DATA / f"bars_{symbol.upper()}.json").is_file()


def _load_history_points() -> list[dict]:
    if not _QUOTE_HISTORY_FILE.is_file():
        return []
    try:
        raw = json.loads(_QUOTE_HISTORY_FILE.read_text(encoding="utf-8"))
        if isinstance(raw, list):
            return [p for p in raw if isinstance(p, dict)]
    except Exception:
        pass
    return []


def _latest_quote_per_symbol(points: list[dict]) -> dict[str, dict]:
    latest: dict[str, dict] = {}
    for p in points:
        sym = (p.get("symbol") or "").upper()
        if sym:
            latest[sym] = p
    return latest


def _session_reference_price(symbol: str, today: str) -> float | None:
    bars = load_m1_bars(symbol)
    if not bars:
        return None
    for b in bars:
        try:
            dt = datetime.fromtimestamp(int(b["time"]), tz=TZ_BR)
        except (TypeError, ValueError, KeyError):
            continue
        if dt.date().isoformat() == today:
            return float(b["open"])
    if bars:
        return float(bars[0]["open"])
    return None


def _reference_from_history(points: list[dict], symbol: str, today: str) -> float | None:
    sym_points = [p for p in points if (p.get("symbol") or "").upper() == symbol.upper()]
    if not sym_points:
        return None
    first_today: dict | None = None
    for p in sym_points:
        ts = p.get("timestamp") or ""
        if str(ts).startswith(today):
            first_today = p
            break
    ref_point = first_today or sym_points[0]
    return _mid_from_quote_point(ref_point)


def _try_mt5_quote(symbol: str) -> dict | None:
    try:
        import MetaTrader5 as mt5
    except ImportError:
        return None
    try:
        if not mt5.terminal_info():
            return None
    except Exception:
        return None
    candidates = mt5_symbol_candidates(symbol.upper())
    for sym in candidates:
        tick = mt5.symbol_info_tick(sym)
        if tick is None:
            continue
        bid = float(tick.bid or 0)
        ask = float(tick.ask or 0)
        last = float(tick.last or 0)
        if bid <= 0 and ask <= 0 and last <= 0:
            continue
        mid = (bid + ask) / 2 if bid and ask else last or bid or ask
        return {
            "symbol": symbol.upper(),
            "bid": bid or None,
            "ask": ask or None,
            "last": last or mid,
            "mid": mid,
            "timestamp": datetime.now(TZ_BR).isoformat(),
            "source": "mt5",
        }
    return None


def _resolve_ticker_quote(
    symbol: str,
    *,
    history_latest: dict[str, dict],
    last_quote: dict | None,
) -> tuple[dict | None, str | None]:
    sym = symbol.upper()
    if sym in history_latest:
        return history_latest[sym], "quote_history"
    if last_quote and (last_quote.get("symbol") or "").upper() == sym:
        return last_quote, "last_quote"
    if _bars_file_exists(sym):
        bars = load_m1_bars(sym)
        if bars:
            close = float(bars[-1]["close"])
            return {
                "symbol": sym,
                "bid": close,
                "ask": close,
                "last": close,
                "mid": close,
                "timestamp": datetime.fromtimestamp(int(bars[-1]["time"]), tz=TZ_BR).isoformat(),
                "source": "bars_file",
            }, "bars_file"
    mt5_q = _try_mt5_quote(sym)
    if mt5_q:
        return mt5_q, "mt5"
    return None, None


def _pct_change(mid: float | None, reference: float | None) -> float | None:
    if mid is None or reference is None or reference == 0:
        return None
    return round((mid - reference) / reference * 100.0, 2)


def get_tickers_summary() -> MarketTickersSummaryResponse:
    now = datetime.now(TZ_BR)
    today = now.date().isoformat()
    points = _load_history_points()
    history_latest = _latest_quote_per_symbol(points)

    last_quote: dict | None = None
    if _QUOTE_FILE.is_file():
        try:
            raw = json.loads(_QUOTE_FILE.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                last_quote = raw
        except Exception:
            pass

    items: list[MarketTickerSummaryItem] = []
    latest_ts: datetime | None = None

    for sym in PULSE_DECK_TICKERS:
        quote, source = _resolve_ticker_quote(
            sym,
            history_latest=history_latest,
            last_quote=last_quote,
        )
        if quote is None:
            items.append(
                MarketTickerSummaryItem(
                    symbol=sym,
                    label=TICKER_LABELS.get(sym, sym),
                    available=False,
                )
            )
            continue

        mid = _mid_from_quote_point(quote)
        bid = quote.get("bid")
        ask = quote.get("ask")
        last = quote.get("last")
        ts = quote.get("timestamp")
        if ts:
            try:
                parsed = datetime.fromisoformat(str(ts))
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=TZ_BR)
                if latest_ts is None or parsed > latest_ts:
                    latest_ts = parsed
            except ValueError:
                pass

        ref = _session_reference_price(sym, today)
        if ref is None:
            ref = _reference_from_history(points, sym, today)

        items.append(
            MarketTickerSummaryItem(
                symbol=sym,
                label=TICKER_LABELS.get(sym, sym),
                bid=float(bid) if bid is not None else None,
                ask=float(ask) if ask is not None else None,
                last=float(last) if last is not None else mid,
                mid=mid,
                change_pct=_pct_change(mid, ref),
                reference_price=ref,
                available=mid is not None,
                source=source or quote.get("source"),
                timestamp=str(ts) if ts else None,
            )
        )

    return MarketTickersSummaryResponse(as_of=latest_ts or now, tickers=items)
