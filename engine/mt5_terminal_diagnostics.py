"""Diagnóstico do terminal MT5 (trade_allowed, API Python, etc.)."""

from __future__ import annotations

from typing import Any

import MetaTrader5 as mt5

from engine.mt5_experts_ini import read_experts_flags_for_data_dir
from engine.mt5_runtime import ensure_mt5_session

RETCODE_AUTOTRADING_DISABLED = getattr(
    mt5, "TRADE_RETCODE_CLIENT_DISABLES_AT", 10027
)


def mt5_retcode_10027_hint() -> str:
    return (
        "Negociação algorítmica desligada no MT5 (retcode 10027). "
        "Ferramentas → Opções → Expert Advisors: marque «Permitir algotrading», "
        "desmarque «Desativar API Python externa», clique OK e só então ligue o botão "
        "verde «Negociação algorítmica» na barra. "
        "Clear/demo: se o checkbox não grava, veja docs/MT5_EXECUCAO.md "
        "(«Clear / MT5 não grava Permitir algotrading»)."
    )


def format_mt5_rejection_hint(retcode: int | None) -> str:
    if retcode is None:
        return ""
    if int(retcode) == int(RETCODE_AUTOTRADING_DISABLED):
        return mt5_retcode_10027_hint()
    return ""


def _bool_attr(info: Any, name: str) -> bool | None:
    if info is None:
        return None
    raw = getattr(info, name, None)
    if raw is None:
        return None
    return bool(raw)


def collect_mt5_terminal_diagnostics(
    *,
    try_session: bool = True,
    log_enabled0: bool = True,
) -> dict[str, Any]:
    """
    Lê terminal_info() após ensure_mt5_session (processo API/engine).
    Retorna flags + checklist com done/blocked/message em português.
    """
    error: str | None = None
    if try_session:
        try:
            ensure_mt5_session(log_enabled0=log_enabled0)
        except Exception as exc:
            error = str(exc)

    info = None
    if error is None:
        try:
            info = mt5.terminal_info()
        except Exception as exc:
            error = str(exc)
        if info is None and error is None:
            code, msg = mt5.last_error()
            error = f"terminal_info indisponível ({code} {msg})"

    if error is not None or info is None:
        return {
            "available": False,
            "error": error or "terminal_info indisponível",
            "trade_allowed": None,
            "connected": None,
            "tradeapi_disabled": None,
            "company": None,
            "name": None,
            "checklist": [
                {
                    "id": "mt5_session",
                    "label": "Sessão MT5 acessível pela API Python",
                    "done": False,
                    "blocked": True,
                    "message": error or "Abra o MetaTrader 5 e confira login.",
                }
            ],
        }

    trade_allowed = _bool_attr(info, "trade_allowed")
    connected = _bool_attr(info, "connected")
    tradeapi_disabled = _bool_attr(info, "tradeapi_disabled")
    company = getattr(info, "company", None)
    name = getattr(info, "name", None)
    terminal_path = getattr(info, "path", None)
    data_path = getattr(info, "data_path", None)
    company_s = str(company) if company else None
    name_s = str(name) if name else None
    terminal_path_s = str(terminal_path) if terminal_path else None
    data_path_s = str(data_path) if data_path else None

    checklist: list[dict[str, Any]] = []

    checklist.append(
        {
            "id": "terminal_connected",
            "label": "Terminal conectado ao servidor da corretora",
            "done": connected is True,
            "blocked": connected is False,
            "message": (
                ""
                if connected is not False
                else "MT5 offline ou sem login — abra o terminal e entre na conta demo Clear."
            ),
        }
    )

    trade_allowed_msg = (
        "Marque «Permitir algotrading» (Expert Advisors), confirme OK, "
        "depois ligue o botão verde «Negociação algorítmica» na barra. "
        "Se a Clear não grava o checkbox, siga docs/MT5_EXECUCAO.md."
    )
    checklist.append(
        {
            "id": "trade_allowed",
            "label": "Permitir algotrading (Opções → Expert Advisors)",
            "done": trade_allowed is True,
            "blocked": trade_allowed is False,
            "message": "" if trade_allowed is not False else trade_allowed_msg,
        }
    )

    if tradeapi_disabled is not None:
        checklist.append(
            {
                "id": "tradeapi_disabled",
                "label": "API Python externa permitida",
                "done": not tradeapi_disabled,
                "blocked": bool(tradeapi_disabled),
                "message": (
                    ""
                    if not tradeapi_disabled
                    else "Desmarque «Desativar API Python externa» em Expert Advisors e clique OK."
                ),
            }
        )

    api_ok = tradeapi_disabled is not True
    experts_ini: dict[str, str | None] = {}
    if data_path_s and trade_allowed is False:
        experts_ini = read_experts_flags_for_data_dir(data_path_s)
        enabled_raw = experts_ini.get("Enabled")
        if enabled_raw == "0":
            allow_raw = experts_ini.get("AllowLiveTrading")
            detail = (
                f"common.ini tem Enabled=0"
                + (f" mas AllowLiveTrading={allow_raw}" if allow_raw else "")
                + " — típico da Clear quando o checkbox não persiste. "
                "Ligue o botão verde «Negociação algorítmica» na barra (não só Opções → EA). "
                "Feche o MT5 (Arquivo → Sair) e rode: python scripts/fix_mt5_experts_ini.py"
            )
            checklist.append(
                {
                    "id": "experts_ini_enabled",
                    "label": "common.ini [Experts] Enabled=1",
                    "done": False,
                    "blocked": True,
                    "message": detail,
                }
            )

    algo_ready = trade_allowed is True and api_ok
    checklist.append(
        {
            "id": "autotrading_ready",
            "label": "Pronto para order_send via Python (sem retcode 10027)",
            "done": algo_ready,
            "blocked": not algo_ready and (trade_allowed is False or tradeapi_disabled is True),
            "message": (
                ""
                if algo_ready
                else mt5_retcode_10027_hint()
                if trade_allowed is False or tradeapi_disabled is True
                else "Confira Opções → Expert Advisors e o botão verde na barra."
            ),
        }
    )

    return {
        "available": True,
        "error": None,
        "trade_allowed": trade_allowed,
        "connected": connected,
        "tradeapi_disabled": tradeapi_disabled,
        "company": company_s,
        "name": name_s,
        "terminal_executable_dir": terminal_path_s,
        "data_path": data_path_s,
        "experts_ini": experts_ini or None,
        "checklist": checklist,
    }


def terminal_blockers_from_diagnostics(diag: dict[str, Any]) -> list[str]:
    """Mensagens curtas para blockers[] do execution-status."""
    if not diag.get("available"):
        err = diag.get("error")
        if err:
            return [f"MT5 (API): {err}"]
        return ["MT5 (API): terminal indisponível"]
    out: list[str] = []
    for item in diag.get("checklist") or []:
        if not item.get("blocked"):
            continue
        msg = (item.get("message") or item.get("label") or "").strip()
        if msg and msg not in out:
            out.append(msg if len(msg) < 240 else msg[:237] + "…")
    return out
