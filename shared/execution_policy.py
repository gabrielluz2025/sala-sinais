"""Política de execução automática (sem dependência do MT5)."""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

from shared.schemas import OperatingMode

_ROOT = Path(__file__).resolve().parents[1]


class ExecutionEnvSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    signal_mode: str = "paper"
    live_trading: bool = False
    allow_demo_live: bool = False
    auto_execute_orders: bool = True
    execute_on_demo: bool = True
    # Demo/paper: testes fora do pregão (noite). Ignorado quando LIVE_TRADING=true.
    b3_ignore_session_hours: bool = True
    # Aprendizado noturno: study + sinais simulados, sem exigir MT5 (Sala-Sinais.bat opção 7).
    overnight_learning: bool = False
    engine_mode: str = ""
    operating_mode: str = ""
    mt5_symbol: str = "WIN$"


def load_execution_env() -> ExecutionEnvSettings:
    return ExecutionEnvSettings()


def resolve_operating_mode_from_env(env: ExecutionEnvSettings | None = None) -> OperatingMode:
    env = env or load_execution_env()
    raw = (env.engine_mode or env.operating_mode or "").strip().lower()
    aliases: dict[str, OperatingMode] = {
        "simulation": OperatingMode.SIMULATION,
        "sim": OperatingMode.SIMULATION,
        "paper_mt5": OperatingMode.PAPER_MT5,
        "paper-mt5": OperatingMode.PAPER_MT5,
        "live_mt5": OperatingMode.LIVE_MT5,
        "live-mt5": OperatingMode.LIVE_MT5,
        "live": OperatingMode.LIVE_MT5,
    }
    if raw:
        return aliases.get(raw, OperatingMode.PAPER_MT5)
    if env.live_trading and env.signal_mode.lower() == "live":
        return OperatingMode.LIVE_MT5
    return OperatingMode.PAPER_MT5


def should_execute_orders(
    *,
    operating_mode: OperatingMode | None = None,
    engine_paused: bool = False,
    is_demo: bool | None = None,
    env: ExecutionEnvSettings | None = None,
) -> tuple[bool, str | None]:
    """
    Indica se o engine deve chamar place_market_order após registrar o sinal.
    Retorna (pode_executar, motivo_bloqueio_em_pt).
    """
    env = env or load_execution_env()
    op = operating_mode or resolve_operating_mode_from_env(env)

    if op == OperatingMode.SIMULATION:
        return False, "ENGINE_MODE=simulation — sem ordens no MT5"

    if op not in (OperatingMode.PAPER_MT5, OperatingMode.LIVE_MT5):
        return False, f"Modo {op.value} não envia ordens ao MT5"

    if not env.auto_execute_orders:
        return False, "AUTO_EXECUTE_ORDERS=false"

    if engine_paused:
        return False, "Engine pausado — clique Retomar no menu"

    if env.signal_mode.lower() != "live":
        return False, "SIGNAL_MODE≠live — apenas registro de sinal"

    if op == OperatingMode.PAPER_MT5 and env.execute_on_demo:
        if is_demo is False:
            return (
                False,
                "Conta REAL no MT5 — paper_mt5 + EXECUTE_ON_DEMO só envia ordens em conta demo",
            )
        return True, None

    demo = is_demo is True

    if demo:
        if env.live_trading and env.allow_demo_live:
            return True, None
        if not env.live_trading:
            return (
                False,
                "Conta demo — use ENGINE_MODE=paper_mt5 com EXECUTE_ON_DEMO=true "
                "ou LIVE_TRADING=true com ALLOW_DEMO_LIVE=true",
            )

    if env.live_trading:
        if demo and not env.allow_demo_live:
            return (
                False,
                "Conta DEMO com LIVE_TRADING=true — bloqueado (ALLOW_DEMO_LIVE=false)",
            )
        return True, None

    if op == OperatingMode.PAPER_MT5:
        return False, "LIVE_TRADING=false — cotação apenas (demo: EXECUTE_ON_DEMO=true)"

    return False, "LIVE_TRADING=false"


def collect_execution_blockers(
    *,
    engine_online: bool,
    engine_paused: bool,
    mt5_connected: bool | None,
    is_demo: bool | None,
    operating_mode: str | None,
    env: ExecutionEnvSettings | None = None,
) -> list[str]:
    """Lista motivos em português quando ordens não podem ser enviadas."""
    env = env or load_execution_env()
    op = resolve_operating_mode_from_env(env)
    if operating_mode:
        raw = operating_mode.strip().lower()
        op_aliases = {
            "simulation": OperatingMode.SIMULATION,
            "paper_mt5": OperatingMode.PAPER_MT5,
            "live_mt5": OperatingMode.LIVE_MT5,
        }
        op = op_aliases.get(raw, op)

    blockers: list[str] = []

    if not engine_online:
        blockers.append("Engine offline — inicie Sala-Sinais.bat (opção 3 ou engine)")
    if engine_paused:
        blockers.append("Engine pausado — clique Retomar no menu")
    if op == OperatingMode.SIMULATION:
        blockers.append("ENGINE_MODE=simulation — sem MT5")
    elif op in (OperatingMode.PAPER_MT5, OperatingMode.LIVE_MT5):
        if mt5_connected is False:
            blockers.append("MT5 desconectado")
        elif mt5_connected is None and not engine_online:
            blockers.append("MT5 desconectado")
    if not env.auto_execute_orders:
        blockers.append("AUTO_EXECUTE_ORDERS=false")
    if env.signal_mode.lower() != "live":
        blockers.append("SIGNAL_MODE≠live — só sinais, sem ordens")
    if op in (OperatingMode.PAPER_MT5, OperatingMode.LIVE_MT5):
        can, reason = should_execute_orders(
            operating_mode=op,
            engine_paused=engine_paused,
            is_demo=is_demo,
            env=env,
        )
        if not can and reason and reason not in blockers:
            blockers.append(reason)
    # Deduplicate preserving order
    seen: set[str] = set()
    unique: list[str] = []
    for b in blockers:
        if b not in seen:
            seen.add(b)
            unique.append(b)
    return unique


def auto_execute_enabled_display(
    *,
    engine_paused: bool,
    operating_mode: str | None,
    is_demo: bool | None,
    env: ExecutionEnvSettings | None = None,
) -> bool:
    """Estado do toggle read-only no painel (execução automática ligada)."""
    env = env or load_execution_env()
    op_raw = (operating_mode or env.engine_mode or "").strip().lower()
    if not op_raw:
        op = resolve_operating_mode_from_env(env)
        op_raw = op.value
    if op_raw == "simulation":
        return False
    if engine_paused:
        return False
    if not env.auto_execute_orders:
        return False
    if env.signal_mode.lower() != "live":
        return False
    if op_raw in ("paper_mt5", "live_mt5"):
        if is_demo and env.execute_on_demo and op_raw == "paper_mt5":
            return True
        if env.live_trading:
            return True
    return False


def execution_checklist_steps(
    *,
    engine_online: bool,
    engine_paused: bool,
    mt5_connected: bool | None,
    is_demo: bool | None,
    operating_mode: str | None,
    env: ExecutionEnvSettings | None = None,
    mt5_autotrading: bool | None = None,
) -> list[dict[str, object]]:
    env = env or load_execution_env()
    op = (operating_mode or env.engine_mode or resolve_operating_mode_from_env(env).value).lower()
    mt5_modes = op in ("paper_mt5", "live_mt5")
    steps: list[dict[str, object]] = [
        {
            "id": "broker_mt5",
            "label": "Corretora com MT5 instalado (Avenue não integra MT5 para B3)",
            "done": mt5_modes and (mt5_connected is True or engine_online),
        },
        {
            "id": "engine_mode",
            "label": "ENGINE_MODE=paper_mt5 ou live_mt5 no .env",
            "done": mt5_modes,
        },
        {
            "id": "signal_live",
            "label": "SIGNAL_MODE=live (estratégia pode enviar ordens)",
            "done": env.signal_mode.lower() == "live",
        },
        {
            "id": "mt5_online",
            "label": "MT5 aberto, logado e engine online (heartbeat)",
            "done": bool(engine_online and mt5_connected and not engine_paused),
        },
        {
            "id": "auto_flags",
            "label": "AUTO_EXECUTE_ORDERS=true e demo: EXECUTE_ON_DEMO=true",
            "done": env.auto_execute_orders
            and (
                (is_demo and env.execute_on_demo and op == "paper_mt5")
                or env.live_trading
            ),
        },
    ]
    if mt5_modes and mt5_autotrading is not None:
        steps.append(
            {
                "id": "mt5_autotrading",
                "label": "Negociação algorítmica (AlgoTrading) ligada no MT5",
                "done": bool(mt5_autotrading),
            }
        )
    return steps


def should_send_manual_order_to_mt5(
    *,
    operating_mode: OperatingMode | None = None,
    engine_paused: bool = False,
    is_demo: bool | None = None,
    env: ExecutionEnvSettings | None = None,
) -> tuple[bool, str | None]:
    """
    Boleta / POST /orders/execute — tenta MT5 sem exigir AUTO_EXECUTE_ORDERS.
    """
    env = env or load_execution_env()
    op = operating_mode or resolve_operating_mode_from_env(env)

    if op == OperatingMode.SIMULATION:
        return False, "ENGINE_MODE=simulation — sem ordens no MT5"

    if engine_paused:
        return False, "Engine pausado — clique Retomar no menu"

    if env.signal_mode.lower() != "live":
        return (
            False,
            "SIGNAL_MODE≠live — defina SIGNAL_MODE=live no .env e reinicie API + engine",
        )

    if op == OperatingMode.PAPER_MT5:
        if not env.execute_on_demo:
            return False, "EXECUTE_ON_DEMO=false — paper_mt5 demo não envia ao MT5"
        if is_demo is False:
            return (
                False,
                "Conta REAL no MT5 — paper_mt5 + EXECUTE_ON_DEMO só envia ordens em conta demo",
            )
        return True, None

    if op == OperatingMode.LIVE_MT5:
        return should_execute_orders(
            operating_mode=op,
            engine_paused=engine_paused,
            is_demo=is_demo,
            env=env,
        )

    return False, f"Modo {op.value} não envia ordens manuais ao MT5"


def can_submit_manual_order(
    *,
    operating_mode: OperatingMode | None = None,
    engine_paused: bool = False,
    is_demo: bool | None = None,
    env: ExecutionEnvSettings | None = None,
) -> tuple[bool, str | None]:
    """
    Ordens manuais da UI (POST /orders/execute).
    Permitido em simulation e paper_mt5; live_mt5 só se should_execute_orders permitir.
    """
    env = env or load_execution_env()
    op = operating_mode or resolve_operating_mode_from_env(env)

    if engine_paused:
        return False, "Engine pausado — clique Retomar no menu"

    if op == OperatingMode.SIMULATION:
        return True, None

    if op == OperatingMode.PAPER_MT5:
        return True, None

    if op == OperatingMode.LIVE_MT5:
        can, reason = should_execute_orders(
            operating_mode=op,
            engine_paused=False,
            is_demo=is_demo,
            env=env,
        )
        if can:
            return True, None
        return False, reason or "Ordem manual bloqueada — política live não permite execução"

    return False, f"Modo {op.value} não aceita ordens manuais"


def paper_mt5_env_snippet(env: ExecutionEnvSettings | None = None) -> str:
    env = env or load_execution_env()
    lines = [
        "# Execução automática em conta DEMO (paper_mt5)",
        "ENGINE_MODE=paper_mt5",
        "SIGNAL_MODE=live",
        "LIVE_TRADING=false",
        "AUTO_EXECUTE_ORDERS=true",
        "EXECUTE_ON_DEMO=true",
        "B3_IGNORE_SESSION_HOURS=true",
        "# MT5_PATH=C:\\Program Files\\Clear Investimentos MT5 Terminal\\terminal64.exe",
        f"MT5_SYMBOL={env.mt5_symbol}",
    ]
    return "\n".join(lines)
