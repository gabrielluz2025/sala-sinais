"""Heartbeat, cotação e leitura de flags de controle da API."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx

from engine.config import settings

log = logging.getLogger("engine.control")
TZ_BR = ZoneInfo("America/Sao_Paulo")
_ROOT = Path(__file__).resolve().parents[1]
_QUOTE_PATH = _ROOT / "data" / "last_quote.json"
_QUOTE_HISTORY_PATH = _ROOT / "data" / "quote_history.json"
_QUOTE_HISTORY_MAX = 100


def fetch_agent_config() -> dict:
    base = settings.api_base_url.rstrip("/")
    try:
        with httpx.Client(timeout=8.0) as client:
            resp = client.get(f"{base}/agent/config")
            resp.raise_for_status()
            return resp.json()
    except Exception as exc:
        log.warning("Não foi possível ler agent config: %s", exc)
        from engine.agent_runtime import default_agent_config

        return default_agent_config()


def fetch_system_state() -> dict:
    base = settings.api_base_url.rstrip("/")
    try:
        with httpx.Client(timeout=8.0) as client:
            resp = client.get(f"{base}/system/state/raw")
            resp.raise_for_status()
            return resp.json()
    except Exception as exc:
        log.warning("Não foi possível ler system state: %s", exc)
        return {
            "engine_paused": False,
            "emergency_flatten": False,
            "last_heartbeat": None,
            "mode": "paper",
        }


def send_heartbeat(
    mode: str,
    account_login: int | None = None,
    is_demo: bool | None = None,
    account_server: str | None = None,
    data_source: str | None = None,
    mt5_connected: bool | None = None,
    operating_mode: str | None = None,
) -> None:
    base = settings.api_base_url.rstrip("/")
    headers = {"X-Webhook-Secret": settings.webhook_secret}
    params: dict[str, str | int] = {"mode": mode}
    if account_login is not None:
        params["account_login"] = account_login
    if is_demo is not None:
        params["is_demo"] = str(is_demo).lower()
    if account_server:
        params["account_server"] = account_server
    if data_source:
        params["data_source"] = data_source
    if mt5_connected is not None:
        params["mt5_connected"] = str(mt5_connected).lower()
    if operating_mode:
        params["operating_mode"] = operating_mode
    try:
        with httpx.Client(timeout=8.0) as client:
            client.post(
                f"{base}/system/heartbeat",
                params=params,
                headers=headers,
            )
    except Exception as exc:
        log.debug("Heartbeat falhou: %s", exc)


def clear_emergency_flatten() -> None:
    base = settings.api_base_url.rstrip("/")
    try:
        with httpx.Client(timeout=8.0) as client:
            client.patch(f"{base}/system/state", json={"emergency_flatten": False})
    except Exception as exc:
        log.warning("Não foi possível limpar emergency_flatten: %s", exc)


def write_last_quote(
    symbol: str,
    bid: float,
    ask: float,
    source: str = "engine",
) -> None:
    _QUOTE_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "symbol": symbol,
        "bid": bid,
        "ask": ask,
        "timestamp": datetime.now(TZ_BR).isoformat(),
        "source": source,
    }
    _QUOTE_PATH.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    try:
        history: list[dict] = []
        if _QUOTE_HISTORY_PATH.is_file():
            raw = json.loads(_QUOTE_HISTORY_PATH.read_text(encoding="utf-8"))
            if isinstance(raw, list):
                history = raw
        history.append(payload)
        if len(history) > _QUOTE_HISTORY_MAX:
            history = history[-_QUOTE_HISTORY_MAX :]
        _QUOTE_HISTORY_PATH.write_text(
            json.dumps(history, ensure_ascii=False), encoding="utf-8"
        )
    except Exception as exc:
        log.debug("quote_history não gravado: %s", exc)
