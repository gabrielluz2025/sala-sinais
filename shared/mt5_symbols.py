"""Ticker lógico (painel) → candidatos no Market Watch do MT5."""

from __future__ import annotations

from typing import Callable, Protocol


class _SymbolInfoFn(Protocol):
    def __call__(self, name: str) -> object | None: ...


# Nomes comuns em corretoras BR (Clear, XP, etc.). Ordem: mais provável primeiro.
MT5_SYMBOL_CANDIDATES: dict[str, list[str]] = {
    "IBOV": ["IBOV", "IBOV$", "IBOVF"],
    "PETR4": ["PETR4", "PETR4F", "PETR4$", "PETR4N", "PETR3"],
    "VALE3": ["VALE3", "VALE3F", "VALE3$"],
    "ITUB4": ["ITUB4", "ITUB4F", "ITUB4$"],
    "BBDC4": ["BBDC4", "BBDC4F", "BBDC4$"],
    "WINFUT": ["WIN$", "WIN$N", "WINM25", "WING25"],
    "WDOFUT": ["WDO$", "WDO$N"],
}


def mt5_symbol_candidates(logical: str) -> list[str]:
    key = (logical or "").strip().upper()
    if not key:
        return []
    if key in MT5_SYMBOL_CANDIDATES:
        seen: set[str] = set()
        out: list[str] = []
        for sym in MT5_SYMBOL_CANDIDATES[key]:
            u = sym.upper()
            if u not in seen:
                seen.add(u)
                out.append(sym)
        return out
    if key.startswith("WIN") and not key.endswith("$"):
        return mt5_symbol_candidates("WINFUT") + [key]
    if key.startswith("WDO") and not key.endswith("$"):
        return mt5_symbol_candidates("WDOFUT") + [key]
    return [key]


def resolve_mt5_symbol(
    logical: str,
    *,
    symbol_info: _SymbolInfoFn,
) -> str:
    """
    Retorna o primeiro candidato existente no MT5.
    Levanta RuntimeError se nenhum nome funcionar.
    """
    tried: list[str] = []
    for candidate in mt5_symbol_candidates(logical):
        tried.append(candidate)
        if symbol_info(candidate) is not None:
            return candidate
    raise RuntimeError(
        f"Símbolo '{logical}' não encontrado no MT5 (tentativas: {', '.join(tried)}). "
        "Abra o ativo no Market Watch e confira o nome exato."
    )


def pick_mt5_symbol_from_module(logical: str) -> str:
    """Atalho quando MetaTrader5 já está importado."""
    import MetaTrader5 as mt5

    return resolve_mt5_symbol(logical, symbol_info=mt5.symbol_info)
