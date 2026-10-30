"""GET /system/execution-status — estado de execução automática."""

from __future__ import annotations

from engine.config import settings
from engine.mt5_runtime import mt5_autotrading_enabled
from engine.mt5_experts_ini import paths_mismatch
from engine.mt5_terminal_diagnostics import (
    collect_mt5_terminal_diagnostics,
    terminal_blockers_from_diagnostics,
)

from shared.execution_policy import (
    auto_execute_enabled_display,
    collect_execution_blockers,
    execution_checklist_steps,
    load_execution_env,
    paper_mt5_env_snippet,
    resolve_operating_mode_from_env,
    should_execute_orders,
)
from shared.session_hours import (
    b3_session_block_reason,
    resolve_enforce_b3_session_hours,
)
from shared.schemas import (
    ExecutionBlockersStructured,
    ExecutionChecklistStep,
    ExecutionStatusRead,
    Mt5TerminalChecklistStep,
    Mt5TerminalDiagnosticsRead,
    OperatingMode,
)


def build_execution_status(
    *,
    engine_online: bool,
    engine_paused: bool,
    mt5_connected: bool | None,
    is_demo: bool | None,
    operating_mode: str | None,
    mode: str,
) -> ExecutionStatusRead:
    env = load_execution_env()
    op = resolve_operating_mode_from_env(env)
    if operating_mode:
        raw = operating_mode.strip().lower()
        for candidate in OperatingMode:
            if candidate.value == raw:
                op = candidate
                break

    can_send, _ = should_execute_orders(
        operating_mode=op,
        engine_paused=engine_paused,
        is_demo=is_demo,
        env=env,
    )
    if not engine_online or engine_paused:
        can_send = False
    if op in (OperatingMode.PAPER_MT5, OperatingMode.LIVE_MT5) and mt5_connected is not True:
        can_send = False

    blockers = collect_execution_blockers(
        engine_online=engine_online,
        engine_paused=engine_paused,
        mt5_connected=mt5_connected,
        is_demo=is_demo,
        operating_mode=operating_mode or op.value,
        env=env,
    )
    if can_send:
        blockers = []

    structured = ExecutionBlockersStructured()
    enforce_hours = resolve_enforce_b3_session_hours(
        live_trading=env.live_trading,
        execute_on_demo=env.execute_on_demo,
        b3_ignore_session_hours=env.b3_ignore_session_hours,
        operating_mode=op,
        overnight_learning=env.overnight_learning,
    )
    session_msg = b3_session_block_reason(
        trade_start_hour=settings.trade_start_hour,
        trade_end_hour=settings.trade_end_hour,
        enforce=enforce_hours,
    )
    if session_msg:
        structured.session_hours = True
        structured.session_hours_message = session_msg
        if session_msg not in blockers:
            blockers.append(session_msg)
        if enforce_hours:
            can_send = False

    mt5_terminal: Mt5TerminalDiagnosticsRead | None = None
    mt5_path_env = (settings.mt5_path or "").strip() or None
    mt5_path_mismatch = False
    if op in (OperatingMode.PAPER_MT5, OperatingMode.LIVE_MT5) and not env.overnight_learning:
        diag_raw = collect_mt5_terminal_diagnostics(log_enabled0=False)
        connected_dir = diag_raw.get("terminal_executable_dir")
        if mt5_path_env and connected_dir and paths_mismatch(mt5_path_env, connected_dir):
            mt5_path_mismatch = True
            mismatch_msg = (
                f"MT5_PATH no .env ({mt5_path_env}) não corresponde ao terminal conectado à API "
                f"({connected_dir}). Ajuste MT5_PATH ou feche outros terminais."
            )
            can_send = False
            if mismatch_msg not in blockers:
                blockers.append(mismatch_msg)
        mt5_terminal = Mt5TerminalDiagnosticsRead(
            available=bool(diag_raw.get("available")),
            error=diag_raw.get("error"),
            trade_allowed=diag_raw.get("trade_allowed"),
            connected=diag_raw.get("connected"),
            tradeapi_disabled=diag_raw.get("tradeapi_disabled"),
            company=diag_raw.get("company"),
            name=diag_raw.get("name"),
            terminal_executable_dir=diag_raw.get("terminal_executable_dir"),
            data_path=diag_raw.get("data_path"),
            checklist=[
                Mt5TerminalChecklistStep(**item) for item in (diag_raw.get("checklist") or [])
            ],
        )
        term_blockers = terminal_blockers_from_diagnostics(diag_raw)
        if diag_raw.get("trade_allowed") is False and not can_send:
            structured.mt5_trade_allowed = True
            structured.mt5_trade_allowed_message = (
                "MT5 trade_allowed=False — ligue o botão verde «Negociação algorítmica» na barra "
                "e confira Opções → Expert Advisors («Permitir algotrading», API Python ativa)."
            )
        experts_ini = diag_raw.get("experts_ini") or {}
        if experts_ini.get("Enabled") == "0" and not can_send:
            structured.experts_ini_enabled = True
            structured.experts_ini_message = (
                "common.ini [Experts] Enabled=0 (MT5 pode sobrescrever ao sair). "
                "Clique o botão verde «Negociação algorítmica» na barra — não basta só Opções → EA. "
                "Se persistir: python scripts/fix_mt5_experts_ini.py com MT5 fechado (docs/MT5_EXECUCAO.md)."
            )
            if structured.experts_ini_message not in blockers:
                blockers.append(structured.experts_ini_message)
        if term_blockers:
            can_send = False
            for tb in term_blockers:
                if tb not in blockers:
                    blockers.append(tb)

    algo = mt5_autotrading_enabled()
    steps_raw = execution_checklist_steps(
        engine_online=engine_online,
        engine_paused=engine_paused,
        mt5_connected=mt5_connected,
        is_demo=is_demo,
        operating_mode=operating_mode or op.value,
        env=env,
        mt5_autotrading=algo,
    )

    return ExecutionStatusRead(
        can_send_orders=can_send,
        can_execute=can_send,
        engine_online=engine_online,
        auto_execute_enabled=auto_execute_enabled_display(
            engine_paused=engine_paused,
            operating_mode=operating_mode or op.value,
            is_demo=is_demo,
            env=env,
        ),
        mode=mode,
        live_trading=env.live_trading,
        engine_paused=engine_paused,
        mt5_connected=mt5_connected,
        operating_mode=operating_mode or op.value,
        auto_execute_orders=env.auto_execute_orders,
        execute_on_demo=env.execute_on_demo,
        signal_mode=env.signal_mode,
        blockers=blockers,
        structured_blockers=structured,
        steps=[ExecutionChecklistStep(**s) for s in steps_raw],
        env_snippet_paper_demo=paper_mt5_env_snippet(env),
        recommended_env_note=(
            "Modo aprendizado 24h (OVERNIGHT_LEARNING=true): engine simula sinais e estudo "
            "sem exigir MT5; ordens reais só com paper_mt5/live e flags de execução."
            if env.overnight_learning
            else (
                "Reinicie API e engine após editar .env. MT5 aberto, logado na demo Clear e "
                "Negociação algorítmica (botão verde na barra) ligada — senão retcode 10027. "
                "Teste noturno demo: EXECUTE_ON_DEMO=true e B3_IGNORE_SESSION_HOURS=true (padrão)."
            )
        ),
        live_trading_warning=env.live_trading,
        overnight_learning=env.overnight_learning,
        mt5_path_env=mt5_path_env,
        mt5_path_mismatch=mt5_path_mismatch,
        mt5_terminal=mt5_terminal,
    )
