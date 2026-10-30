"""Valida MT5 + símbolo WIN. Uso: python -m engine.scripts.check_mt5"""

from engine.mt5_connection import diagnose

if __name__ == "__main__":
    raise SystemExit(diagnose())
