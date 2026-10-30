"""Verificações antes de operar com LIVE_TRADING=true (reutilizado pelo CLI e pelo engine)."""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import httpx
import MetaTrader5 as mt5

from engine.config import settings
from engine.mt5_connection import (
    account_trade_context,
    ensure_symbol,
    initialize,
    shutdown,
)

EXIT_OK_PAPER = 0
EXIT_BLOCKED = 1
EXIT_READY_LIVE = 2


class Verdict(str, Enum):
    SAFE_PAPER = "SAFE for paper"
    READY_LIVE = "READY for live"
    BLOCKED = "BLOCKED"


@dataclass
class PreflightResult:
    verdict: Verdict
    exit_code: int
    issues: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    account: dict[str, Any] | None = None
    api_health: bool = False
    system_state: dict[str, Any] | None = None
    symbol: str | None = None
    signal_mode: str = ""
    live_trading: bool = False
    allow_demo_live: bool = False


def trade_mode_label(trade_mode: int) -> str:
    mapping = {
        mt5.ACCOUNT_TRADE_MODE_DEMO: "demo",
        mt5.ACCOUNT_TRADE_MODE_CONTEST: "contest",
        mt5.ACCOUNT_TRADE_MODE_REAL: "real",
    }
    return mapping.get(trade_mode, f"unknown({trade_mode})")


def is_demo_trade_mode(trade_mode: int) -> bool:
    return trade_mode != mt5.ACCOUNT_TRADE_MODE_REAL


def live_orders_blocked_reason() -> str | None:
    """Retorna mensagem se ordens live não devem ser enviadas; None se permitido."""
    if not settings.live_trading:
        return None
    if settings.signal_mode.lower() != "live":
        return None
    if settings.allow_demo_live:
        return None
    try:
        ctx = account_trade_context()
    except Exception as exc:
        return f"Conta MT5 indisponível — ordem bloqueada: {exc}"
    if ctx.get("is_demo"):
        return (
            "Conta DEMO no MT5 com LIVE_TRADING=true — ordem bloqueada. "
            "Use conta real ou defina ALLOW_DEMO_LIVE=true (não recomendado)."
        )
    return None


def run_preflight(mt5_required: bool = True) -> PreflightResult:
    symbol = settings.mt5_symbol
    signal_mode = settings.signal_mode.lower()
    live_trading = settings.live_trading
    allow_demo = settings.allow_demo_live

    result = PreflightResult(
        verdict=Verdict.SAFE_PAPER,
        exit_code=EXIT_OK_PAPER,
        symbol=symbol,
        signal_mode=signal_mode,
        live_trading=live_trading,
        allow_demo_live=allow_demo,
    )

    mt5_ok = False
    if mt5_required:
        try:
            initialize()
            ctx = account_trade_context()
            result.account = ctx
            ensure_symbol(symbol)
            mt5_ok = True
        except Exception as exc:
            msg = f"MT5: {exc}"
            if live_trading:
                result.issues.append(msg)
            else:
                result.warnings.append(msg)
        finally:
            shutdown()
    else:
        result.warnings.append("MT5 não verificado (mt5_required=false)")

    base = settings.api_base_url.rstrip("/")
    try:
        with httpx.Client(timeout=8.0) as client:
            health = client.get(f"{base}/health")
            result.api_health = health.is_success and health.json().get("status") == "ok"
            if not result.api_health:
                result.issues.append("API /health não retornou ok")
            state_resp = client.get(f"{base}/system/state/raw")
            if state_resp.is_success:
                result.system_state = state_resp.json()
            else:
                result.warnings.append(f"API system/state indisponível ({state_resp.status_code})")
    except Exception as exc:
        result.issues.append(f"API inacessível em {base}: {exc}")

    if signal_mode == "live" and not live_trading:
        result.warnings.append("SIGNAL_MODE=live mas LIVE_TRADING=false — ordens não serão enviadas")

    if live_trading and signal_mode != "live":
        result.warnings.append("LIVE_TRADING=true mas SIGNAL_MODE≠live — ordens não serão enviadas")

    if result.system_state:
        if result.system_state.get("engine_paused"):
            result.warnings.append("Engine está PAUSADO na API")
        if result.system_state.get("emergency_flatten"):
            result.warnings.append("emergency_flatten ativo na API")

    acc = result.account
    is_demo = bool(acc and acc.get("is_demo")) if acc else None

    wants_live_orders = live_trading and signal_mode == "live"

    if live_trading and is_demo and not allow_demo and mt5_ok:
        result.issues.append(
            "LIVE_TRADING=true com conta DEMO/contest — bloqueado. "
            "Faça login na conta REAL no MT5 ou use ALLOW_DEMO_LIVE=true apenas para testes."
        )

    if not mt5_ok and live_trading:
        result.verdict = Verdict.BLOCKED
        result.exit_code = EXIT_BLOCKED
    elif result.issues and live_trading:
        result.verdict = Verdict.BLOCKED
        result.exit_code = EXIT_BLOCKED
    elif wants_live_orders and is_demo is False and mt5_ok:
        if result.issues:
            result.verdict = Verdict.BLOCKED
            result.exit_code = EXIT_BLOCKED
        else:
            result.verdict = Verdict.READY_LIVE
            result.exit_code = EXIT_READY_LIVE
            if not result.api_health:
                result.warnings.append("API offline — engine pode não registrar sinais")
    elif live_trading and is_demo is None and mt5_ok:
        result.warnings.append("Não foi possível confirmar tipo de conta")
        result.verdict = Verdict.BLOCKED
        result.exit_code = EXIT_BLOCKED
    else:
        result.verdict = Verdict.SAFE_PAPER
        result.exit_code = EXIT_OK_PAPER

    return result


def print_report(result: PreflightResult, file: Any = None) -> None:
    out = file or sys.stdout
    print("=" * 60, file=out)
    print("  PREFLIGHT — Sala de Sinais (modo real)", file=out)
    print("=" * 60, file=out)
    print(f"  .env SIGNAL_MODE={result.signal_mode}", file=out)
    print(f"  .env LIVE_TRADING={result.live_trading}", file=out)
    print(f"  .env ALLOW_DEMO_LIVE={result.allow_demo_live}", file=out)
    print(f"  .env MT5_SYMBOL={result.symbol}", file=out)
    print("-" * 60, file=out)

    if result.account:
        acc = result.account
        tm = acc.get("trade_mode")
        print(f"  MT5 login:    {acc.get('login')}", file=out)
        print(f"  MT5 server:   {acc.get('server')}", file=out)
        print(
            f"  trade_mode:   {trade_mode_label(tm)} (ACCOUNT_TRADE_MODE={tm})",
            file=out,
        )
        print(f"  is_demo:      {acc.get('is_demo')}", file=out)
        print(f"  balance:      {acc.get('balance')}", file=out)
    else:
        print("  MT5:          (não conectado ou falhou)", file=out)

    print(f"  API health:   {'OK' if result.api_health else 'FALHOU'}", file=out)
    if result.system_state:
        st = result.system_state
        print(
            f"  System state: mode={st.get('mode')} paused={st.get('engine_paused')} "
            f"flatten={st.get('emergency_flatten')}",
            file=out,
        )

    if result.warnings:
        print("-" * 60, file=out)
        print("  AVISOS:", file=out)
        for w in result.warnings:
            print(f"    ! {w}", file=out)

    if result.issues:
        print("-" * 60, file=out)
        print("  PROBLEMAS:", file=out)
        for i in result.issues:
            print(f"    X {i}", file=out)

    print("=" * 60, file=out)
    banner = f"  VEREDITO: {result.verdict.value} (exit {result.exit_code})"
    print(banner, file=out)
    print("=" * 60, file=out)


def assert_engine_may_start_live() -> None:
    """Chamado no startup do engine quando LIVE_TRADING=true."""
    if not settings.live_trading:
        return
    result = run_preflight(mt5_required=True)
    print_report(result)
    if result.exit_code == EXIT_BLOCKED:
        raise RuntimeError(
            "Preflight BLOCKED — engine não inicia com LIVE_TRADING=true. "
            "Corrija o .env ou a conta MT5 e rode: python -m engine.scripts.preflight_live"
        )
