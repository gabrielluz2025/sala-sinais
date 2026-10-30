"""Testes da lógica de patch em common.ini [Experts]."""

from __future__ import annotations

from engine.mt5_experts_ini import (
    TARGET_EXPERT_VALUES,
    find_terminal_data_folder,
    patch_common_ini_experts,
    paths_mismatch,
    read_experts_flags,
)


def test_patch_adds_experts_section():
    text, changes = patch_common_ini_experts("[Common]\nLogin=1\n")
    assert "[Experts]" in text
    assert "AllowLiveTrading=1" in text
    assert changes


def test_patch_updates_clear_like_ini():
    sample = """[Experts]
AllowDllImport=1
Enabled=0
Account=0
Api=0
[Common]
Login=1198507949
"""
    new_text, changes = patch_common_ini_experts(sample)
    assert "Enabled=1" in new_text
    assert "AllowLiveTrading=1" in new_text
    assert "Api=0" in new_text
    assert any("Enabled" in c for c in changes)
    assert any("AllowLiveTrading" in c for c in changes)


def test_patch_idempotent_when_already_ok():
    lines = ["[Experts]\n"]
    for key, val in TARGET_EXPERT_VALUES.items():
        lines.append(f"{key}={val}\n")
    text = "".join(lines)
    _, changes = patch_common_ini_experts(text)
    assert changes == []


def test_paths_mismatch_detects_different_install_dirs():
    a = r"C:\Program Files\Clear Investimentos MT5 Terminal\terminal64.exe"
    b = r"C:\Program Files\MetaTrader 5\terminal64.exe"
    assert paths_mismatch(a, b) is True


def test_paths_mismatch_same_clear_dir():
    exe = r"C:\Program Files\Clear Investimentos MT5 Terminal\terminal64.exe"
    folder = r"C:\Program Files\Clear Investimentos MT5 Terminal"
    assert paths_mismatch(exe, folder) is False


def test_find_terminal_by_server_substring(tmp_path, monkeypatch):
    data = tmp_path / "ABC123"
    cfg = data / "config"
    cfg.mkdir(parents=True)
    (data / "origin.txt").write_text(r"C:\Broker\MT5", encoding="utf-8")
    (cfg / "common.ini").write_text(
        "[Experts]\nEnabled=0\n[Common]\nServer=ClearInvestimentos-DEMO\n",
        encoding="utf-8",
    )
    found = find_terminal_data_folder(root=tmp_path, server_substring="ClearInvestimentos")
    assert found is not None
    assert found.data_dir == data
    assert read_experts_flags(cfg / "common.ini")["Enabled"] == "0"
