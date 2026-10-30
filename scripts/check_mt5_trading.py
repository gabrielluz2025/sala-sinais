#!/usr/bin/env python3
"""Imprime flags do terminal MT5 para suporte (trade_allowed, API Python).

Uso:
  python scripts/check_mt5_trading.py
"""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from engine.mt5_terminal_diagnostics import collect_mt5_terminal_diagnostics  # noqa: E402
from engine.mt5_experts_ini import (  # noqa: E402
    count_running_terminal64,
    list_running_terminal64_paths,
    read_experts_flags_for_data_dir,
)


def main() -> int:
    running = count_running_terminal64()
    if running > 1:
        print(f"AVISO: {running} processos terminal64.exe em execução — a API Python anexa a um deles.")
        for p in list_running_terminal64_paths():
            print(f"  - {p}")
        print("  Feche instâncias extras ou defina MT5_PATH no .env para a Clear.")
        print()

    diag = collect_mt5_terminal_diagnostics()
    print("=== MT5 terminal (API Python) ===")
    if not diag.get("available"):
        print(f"ERRO: {diag.get('error')}")
        for item in diag.get("checklist") or []:
            if item.get("message"):
                print(f"  - {item['message']}")
        return 1

    print(f"company: {diag.get('company')}")
    print(f"name: {diag.get('name')}")
    print(f"connected: {diag.get('connected')}")
    print(f"trade_allowed: {diag.get('trade_allowed')}")
    print(f"tradeapi_disabled: {diag.get('tradeapi_disabled')}")
    if diag.get("terminal_executable_dir"):
        print(f"terminal_dir: {diag.get('terminal_executable_dir')}")
    if diag.get("data_path"):
        print(f"data_path: {diag.get('data_path')}")
    if diag.get("trade_allowed") is False and diag.get("data_path"):
        flags = read_experts_flags_for_data_dir(diag["data_path"])
        if flags:
            print("common.ini [Experts]:")
            for key in ("Enabled", "AllowLiveTrading", "Api"):
                if key in flags:
                    print(f"  {key}={flags[key]}")
            if flags.get("Enabled") == "0":
                print(
                    "  → Enabled=0 explica trade_allowed=False (10027). "
                    "Feche o MT5 e rode: python scripts/fix_mt5_experts_ini.py"
                )
            elif flags.get("Enabled") == "1" and flags.get("AllowLiveTrading") == "1":
                print(
                    "  → ini OK (Enabled=1) mas trade_allowed=False — ligue o botão verde "
                    "«Negociação algorítmica» / AlgoTrading na barra do MT5 (ou reinicie o terminal)."
                )
    print()
    print("Checklist:")
    for item in diag.get("checklist") or []:
        status = "OK" if item.get("done") else ("BLOCKED" if item.get("blocked") else "pending")
        print(f"  [{status}] {item.get('id')}: {item.get('label')}")
        if item.get("message"):
            print(f"         {item['message']}")

    blocked = any(i.get("blocked") for i in (diag.get("checklist") or []))
    return 1 if blocked else 0


if __name__ == "__main__":
    raise SystemExit(main())
