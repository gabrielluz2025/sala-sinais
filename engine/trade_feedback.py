"""Feedback conservador do motor a partir de GET /agent/learning-stats."""

from __future__ import annotations

import logging
import time
from dataclasses import replace
from typing import TYPE_CHECKING

from engine.config import settings

if TYPE_CHECKING:
    from engine.api_client import SignalApiClient
    from engine.strategy import StrategyResult

log = logging.getLogger("engine.trade_feedback")

_CACHE_TTL_SEC = 90.0
_cache_mono = 0.0
_cache_guards: dict | None = None


def _learning_enabled() -> bool:
    return bool(settings.auto_learn_from_trades)


def _fetch_guards(api: SignalApiClient, active_strategy: str) -> dict:
    global _cache_mono, _cache_guards
    now = time.monotonic()
    if _cache_guards is not None and now - _cache_mono < _CACHE_TTL_SEC:
        return _cache_guards
    try:
        data = api.get_learning_stats()
        perf = data.get("performance_learning") or {}
        guards = perf.get("soft_guards")
        if not guards:
            from shared.trade_learning import compute_soft_guards

            guards = compute_soft_guards(
                perf,
                active_strategy,
                base_cooldown_sec=int(settings.signal_cooldown_sec),
            )
        _cache_guards = guards
        _cache_mono = now
        return guards
    except Exception as exc:
        log.debug("Learning stats indisponível: %s", exc)
        return {
            "active": False,
            "reasons": [],
            "cooldown_sec": settings.signal_cooldown_sec,
            "skip_weak_signals": False,
            "qty_factor": 1.0,
        }


def is_weak_signal(signal: StrategyResult) -> bool:
    """
    Sinal fraco (heurística): volatilidade sem regime favorável ou rompimento marginal.
    Documentado — não bloqueia manual.
    """
    regime = (signal.regime or "").lower()
    if signal.strategy_type == "volatility":
        if not regime or "baixa" in regime or regime.strip() in ("—", "-"):
            return True
    if signal.strategy_type == "breakout":
        reason = (signal.entry_reason or "").lower()
        if "sem rompimento" in reason:
            return True
    return False


def effective_cooldown_sec(api: SignalApiClient, active_strategy: str) -> int:
    if not _learning_enabled():
        return int(settings.signal_cooldown_sec)
    guards = _fetch_guards(api, active_strategy)
    return int(guards.get("cooldown_sec") or settings.signal_cooldown_sec)


def learning_qty_factor(api: SignalApiClient, active_strategy: str) -> float:
    if not _learning_enabled():
        return 1.0
    guards = _fetch_guards(api, active_strategy)
    return float(guards.get("qty_factor") or 1.0)


def apply_before_auto_signal(
    api: SignalApiClient,
    signal: StrategyResult,
    agent_cfg: dict,
) -> tuple[StrategyResult | None, str | None]:
    """
    Soft guards pós-estratégia, pré-POST /signals.
    Retorna (None, motivo) se o sinal automático for suprimido.
    """
    if not _learning_enabled():
        return signal, None

    active = (agent_cfg.get("strategy_type") or "volatility").strip().lower()
    guards = _fetch_guards(api, active)
    if not guards.get("active"):
        return signal, None

    if guards.get("skip_weak_signals") and is_weak_signal(signal):
        reason = "Aprendizado: sinal fraco filtrado (" + ", ".join(guards.get("reasons") or []) + ")"
        log.info(reason)
        return None, reason

    qty_factor = float(guards.get("qty_factor") or 1.0)
    if qty_factor < 1.0:
        payload = signal.payload
        old_qty = payload.contracts
        new_qty = max(1, int(old_qty * qty_factor))
        if new_qty < old_qty:
            payload = payload.model_copy(update={"contracts": new_qty})
            signal = replace(signal, payload=payload)
            log.info(
                "Aprendizado: qty %s → %s (%s)",
                old_qty,
                new_qty,
                ", ".join(guards.get("reasons") or []),
            )

    return signal, None
