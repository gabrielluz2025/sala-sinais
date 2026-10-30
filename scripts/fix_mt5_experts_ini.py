#!/usr/bin/env python3
"""Corrige [Experts] em common.ini quando a Clear não grava «Permitir algotrading».

IMPORTANTE: feche o MetaTrader 5 antes de executar. Este script NÃO é chamado automaticamente.

Uso:
  python scripts/fix_mt5_experts_ini.py
  python scripts/fix_mt5_experts_ini.py --dry-run
  python scripts/fix_mt5_experts_ini.py --data-dir "%APPDATA%\\MetaQuotes\\Terminal\\<hash>"

Variáveis de ambiente:
  MT5_PATH — pasta ou terminal64.exe da Clear (mesmo valor do .env da Sala de Sinais)
  MT5_DATA_DIR — pasta de dados do perfil (opcional; sobrescreve busca automática)
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from engine.config import settings  # noqa: E402
from engine.mt5_experts_ini import (  # noqa: E402
    TARGET_EXPERT_VALUES,
    apply_experts_ini_fix,
    count_running_terminal64,
    find_terminal_data_folder,
    list_running_terminal64_paths,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Ajusta common.ini [Experts] para algotrading + API Python.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Mostra alterações sem gravar (não cria backup).",
    )
    parser.add_argument(
        "--data-dir",
        default=os.environ.get("MT5_DATA_DIR", "").strip() or None,
        help="Pasta %APPDATA%\\MetaQuotes\\Terminal\\<id> (opcional).",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Executa mesmo com terminal64.exe em execução (não recomendado).",
    )
    args = parser.parse_args()

    mt5_path = os.environ.get("MT5_PATH", "").strip() or settings.mt5_path or None
    running = count_running_terminal64()
    if running and not args.force:
        paths = list_running_terminal64_paths()
        print("ERRO: MetaTrader 5 parece estar aberto.")
        print(f"  Processos terminal64.exe: {running}")
        for p in paths:
            print(f"    - {p}")
        print("Feche o MT5 (Arquivo → Sair) e rode este script de novo.")
        print("Use --force apenas se souber que o terminal está fechado e o processo ficou preso.")
        return 2

    folder = find_terminal_data_folder(
        mt5_path=mt5_path,
        data_dir_override=args.data_dir,
    )
    if folder is None:
        print("ERRO: não encontrei pasta de dados MT5 (config/common.ini).")
        print("  Defina MT5_PATH no .env apontando para o terminal64.exe da Clear, ou passe --data-dir.")
        print(f"  Procurado MT5_PATH={mt5_path or '(vazio)'}")
        return 1

    print("=== fix_mt5_experts_ini (manual) ===")
    print(f"Pasta de dados: {folder.data_dir}")
    print(f"Arquivo:        {folder.common_ini}")
    if folder.origin_exe_dir:
        print(f"Origin:         {folder.origin_exe_dir}")
    if folder.server:
        print(f"Servidor:       {folder.server}")
    print()
    print("Chaves alvo em [Experts] (build Clear verificado + documentação MetaQuotes):")
    for key, val in TARGET_EXPERT_VALUES.items():
        print(f"  {key}={val}")
    print()

    try:
        changes = apply_experts_ini_fix(folder.common_ini, dry_run=args.dry_run)
    except OSError as exc:
        print(f"ERRO ao editar ini: {exc}")
        return 1

    for line in changes:
        print(f"  • {line}")

    if args.dry_run:
        print("\n[dry-run] Nada foi gravado.")
    else:
        print("\nBackup criado ao lado de common.ini (common.ini.bak-<UTC>).")
        print("Abra o MT5 Clear, confirme Opções → Expert Advisors e ligue o botão verde AlgoTrading.")
        print("Valide: python scripts/check_mt5_trading.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
