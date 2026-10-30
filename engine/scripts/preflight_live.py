"""Pré-voo antes de ativar modo real. Uso: python -m engine.scripts.preflight_live"""

from __future__ import annotations

import sys

from engine.preflight_live import print_report, run_preflight


def main() -> int:
    try:
        result = run_preflight(mt5_required=True)
        print_report(result)
        return result.exit_code
    except KeyboardInterrupt:
        print("\nCancelado.", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"Preflight falhou inesperadamente: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
