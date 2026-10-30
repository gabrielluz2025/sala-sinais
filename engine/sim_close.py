"""Monitora stop/alvo na simulação e fecha sinais na API com motivo de saída."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Literal, Optional
from zoneinfo import ZoneInfo

from engine.api_client import SignalApiClient
from shared.schemas import SignalOutcome, SignalSide, SignalStatus

log = logging.getLogger("engine.sim_close")
TZ_BR = ZoneInfo("America/Sao_Paulo")


@dataclass
class SimOpenTrade:
    signal_id: int
    side: SignalSide
    entry: float
    stop: float
    target: float
    strategy_type: str
    strategy_version: str
    regime: Optional[str] = None


def _exit_reason(
    hit: Literal["target", "stop"],
    trade: SimOpenTrade,
    agent_cfg: dict | None,
) -> str:
    cfg = agent_cfg or {}
    st = (trade.strategy_type or "volatility").lower()
    if hit == "target":
        tp = float(cfg.get("take_profit_pct") or 3.0)
        if st == "volatility":
            return f"Alvo atingido (~{tp:.1f}% configurado, stops vol adaptativos)"
        return f"Alvo atingido ({tp:.1f}% configurado)"
    sl = float(cfg.get("stop_loss_pct") or 2.0)
    if st == "volatility":
        reg = trade.regime or "vol moderada"
        return f"Stop vol adaptativo atingido ({reg}, base ~{sl:.1f}%)"
    return f"Stop loss atingido ({sl:.1f}% configurado)"


def _check_hit(trade: SimOpenTrade, bid: float, ask: float) -> tuple[Optional[float], Optional[Literal["target", "stop"]]]:
    if trade.side == SignalSide.BUY:
        if ask <= trade.stop:
            return trade.stop, "stop"
        if bid >= trade.target:
            return trade.target, "target"
    else:
        if ask >= trade.stop:
            return trade.stop, "stop"
        if bid <= trade.target:
            return trade.target, "target"
    return None, None


class SimPositionTracker:
    def __init__(self, api: SignalApiClient) -> None:
        self._api = api
        self._open: list[SimOpenTrade] = []

    def register(self, trade: SimOpenTrade) -> None:
        self._open.append(trade)

    def tick(self, bid: float, ask: float, agent_cfg: dict | None) -> None:
        still_open: list[SimOpenTrade] = []
        for trade in self._open:
            exit_px, hit = _check_hit(trade, bid, ask)
            if exit_px is None or hit is None:
                still_open.append(trade)
                continue
            reason = _exit_reason(hit, trade, agent_cfg)
            side = trade.side
            gross_move = (exit_px - trade.entry) if side == SignalSide.BUY else (trade.entry - exit_px)
            if gross_move > 0:
                outcome = SignalOutcome.WIN
            elif gross_move < 0:
                outcome = SignalOutcome.LOSS
            else:
                outcome = SignalOutcome.BREAKEVEN
            try:
                self._api.close_signal(
                    trade.signal_id,
                    exit_price=round(exit_px, 2),
                    outcome=outcome,
                    exit_reason=reason,
                    closed_at=datetime.now(TZ_BR),
                )
                log.info(
                    "Sim fechou sinal id=%s @ %s — %s",
                    trade.signal_id,
                    exit_px,
                    reason,
                )
            except Exception as exc:
                log.warning("Falha ao fechar sinal %s na API: %s", trade.signal_id, exc)
                still_open.append(trade)
        self._open = still_open
