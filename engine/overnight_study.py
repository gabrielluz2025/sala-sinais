"""Passagens periódicas de estudo (GET /agent/study) no modo aprendizado 24h."""

from __future__ import annotations

import logging

from engine.api_client import SignalApiClient
from engine.agent_runtime import default_agent_config

log = logging.getLogger("engine.overnight")


def symbols_for_study(agent_cfg: dict) -> list[str]:
    raw = agent_cfg.get("symbols") or default_agent_config()["symbols"]
    seen: set[str] = set()
    out: list[str] = []
    for sym in raw:
        s = str(sym).strip().upper()
        if not s or s in seen:
            continue
        seen.add(s)
        out.append(s)
    return out[:12]


def run_study_pass(api: SignalApiClient, agent_cfg: dict) -> None:
    symbols = symbols_for_study(agent_cfg)
    if not symbols:
        return
    for sym in symbols:
        try:
            study = api.get_agent_study(sym)
            phase = (study.get("session") or {}).get("phase") or "—"
            log.info("Aprendizado 24h · estudo %s · fase=%s", sym, phase)
        except Exception as exc:
            log.debug("Estudo %s indisponível: %s", sym, exc)


def run_trade_learning_pass(api: SignalApiClient) -> None:
    """Recalcula agregados de trades fechados e persiste insights (data/trade_learning.json)."""
    try:
        data = api.get_learning_stats()
        insight = (data.get("last_insight") or "—")[:120]
        wr = ((data.get("performance_learning") or {}).get("rolling") or {}).get("win_rate_pct")
        log.info(
            "Aprendizado 24h · trades · insight=%s · WR rolling=%s",
            insight,
            wr if wr is not None else "—",
        )
    except Exception as exc:
        log.debug("Passagem trade learning: %s", exc)
