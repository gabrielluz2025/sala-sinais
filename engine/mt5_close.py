"""Sincroniza fechamento de posição MT5 com o sinal na API."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from zoneinfo import ZoneInfo

import MetaTrader5 as mt5

from engine.api_client import SignalApiClient
from shared.schemas import SignalOutcome, SignalSide

log = logging.getLogger("engine.mt5_close")
TZ_BR = ZoneInfo("America/Sao_Paulo")
MAGIC = 88001


@dataclass
class Mt5OpenLink:
    signal_id: int
    symbol: str
    side: SignalSide
    entry: float
    position_ticket: Optional[int]
    opened_at: datetime


def _position_type(side: SignalSide) -> int:
    return mt5.POSITION_TYPE_BUY if side == SignalSide.BUY else mt5.POSITION_TYPE_SELL


def find_position_ticket(symbol: str, side: SignalSide, volume: float) -> Optional[int]:
    positions = mt5.positions_get(symbol=symbol)
    if not positions:
        return None
    want = _position_type(side)
    matches = [
        p
        for p in positions
        if p.magic == MAGIC and p.type == want and abs(float(p.volume) - volume) < 1e-6
    ]
    if not matches:
        matches = [p for p in positions if p.magic == MAGIC and p.type == want]
    if not matches:
        return None
    return int(matches[-1].ticket)


def _exit_price_from_deals(link: Mt5OpenLink) -> Optional[float]:
    deals = mt5.history_deals_get(link.opened_at, datetime.now(TZ_BR))
    if not deals:
        return None
    outs = [
        d
        for d in deals
        if d.symbol == link.symbol
        and d.magic == MAGIC
        and d.entry == mt5.DEAL_ENTRY_OUT
    ]
    if not outs:
        return None
    return float(outs[-1].price)


class Mt5SignalCloseTracker:
    def __init__(self, api: SignalApiClient) -> None:
        self._api = api
        self._open: list[Mt5OpenLink] = []

    def register_fill(
        self,
        signal_id: int,
        symbol: str,
        side: SignalSide,
        entry: float,
        volume: float,
    ) -> None:
        ticket = find_position_ticket(symbol, side, volume)
        self._open.append(
            Mt5OpenLink(
                signal_id=signal_id,
                symbol=symbol,
                side=side,
                entry=entry,
                position_ticket=ticket,
                opened_at=datetime.now(TZ_BR),
            )
        )

    def tick(self) -> None:
        still: list[Mt5OpenLink] = []
        for link in self._open:
            open_pos = False
            if link.position_ticket is not None:
                pos = mt5.positions_get(ticket=link.position_ticket)
                open_pos = bool(pos)
            else:
                positions = mt5.positions_get(symbol=link.symbol)
                open_pos = any(p.magic == MAGIC for p in (positions or []))

            if open_pos:
                still.append(link)
                continue

            exit_px = _exit_price_from_deals(link)
            if exit_px is None:
                tick = mt5.symbol_info_tick(link.symbol)
                if tick:
                    exit_px = float(tick.bid if link.side == SignalSide.BUY else tick.ask)

            if exit_px is None:
                still.append(link)
                continue

            gross_move = (
                (exit_px - link.entry)
                if link.side == SignalSide.BUY
                else (link.entry - exit_px)
            )
            if gross_move > 0:
                outcome = SignalOutcome.WIN
            elif gross_move < 0:
                outcome = SignalOutcome.LOSS
            else:
                outcome = SignalOutcome.BREAKEVEN

            try:
                self._api.close_signal(
                    link.signal_id,
                    exit_price=round(exit_px, 2),
                    outcome=outcome,
                    exit_reason="Posição MT5 encerrada (sync deal/tick)",
                    closed_at=datetime.now(TZ_BR),
                )
                log.info(
                    "MT5 fechou sinal id=%s @ %s (ticket=%s)",
                    link.signal_id,
                    exit_px,
                    link.position_ticket,
                )
            except Exception as exc:
                log.warning("Falha ao fechar sinal %s na API: %s", link.signal_id, exc)
                still.append(link)
        self._open = still
