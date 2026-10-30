"""Mapeamento de símbolos MT5."""

from __future__ import annotations

from shared.mt5_symbols import mt5_symbol_candidates, resolve_mt5_symbol


def test_petr4_candidates_include_plain_ticker():
    cands = mt5_symbol_candidates("PETR4")
    assert cands[0] == "PETR4"
    assert "PETR4F" in cands


def test_resolve_mt5_symbol_first_match():
    seen: dict[str, object] = {"PETR4F": object(), "VALE3": object()}

    def info(name: str):
        return seen.get(name)

    assert resolve_mt5_symbol("PETR4", symbol_info=info) == "PETR4F"


def test_resolve_mt5_symbol_raises_when_missing():
    try:
        resolve_mt5_symbol("ZZZZ9", symbol_info=lambda _n: None)
        assert False, "expected RuntimeError"
    except RuntimeError as exc:
        assert "ZZZZ9" in str(exc)
