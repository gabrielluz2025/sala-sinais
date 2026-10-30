"""Diário do agente — acertos, erros e endpoint."""

from __future__ import annotations

import json

import pytest


@pytest.fixture
def journal_paths(tmp_path, monkeypatch):
    journal_dir = tmp_path / "agent_journal"
    journal_file = journal_dir / "agente-aprendizado.md"
    meta_file = journal_dir / "journal_meta.json"
    progress_file = tmp_path / "agent_library_progress.json"
    monkeypatch.setattr("api.agent_journal._JOURNAL_DIR", journal_dir)
    monkeypatch.setattr("api.agent_journal._JOURNAL_FILE", journal_file)
    monkeypatch.setattr("api.agent_journal._META_FILE", meta_file)
    monkeypatch.setattr("api.agent_library_study._PROGRESS_FILE", progress_file)
    return journal_file, meta_file, progress_file


def _mock_row(monkeypatch, *, symbol, net, win, strategy="volatility", entry_reason="motivo"):
    from types import SimpleNamespace

    from api.agent_journal import on_trade_closed_row

    row = SimpleNamespace(
        symbol=symbol,
        side="BUY",
        strategy_type=strategy,
        entry_reason=entry_reason,
        exit_reason="stop" if not win else "alvo",
        exit_price=30.5,
        entry=29.8,
        contracts=100,
        outcome="win" if win else "loss",
        closed_at="2026-10-29T15:00:00-03:00",
        created_at="2026-10-29T14:50:00-03:00",
        net_pnl_brl=net,
    )
    monkeypatch.setattr(
        "api.agent_journal.resolved_pnl_for_row",
        lambda _r: (abs(net) + 10.0, net, 10.0),
    )
    on_trade_closed_row(row)
    return row


def test_agent_journal_endpoint_empty(journal_paths):
    from fastapi.testclient import TestClient

    import api.main as main_mod

    client = TestClient(main_mod.app)
    res = client.get("/library/agent-journal")
    assert res.status_code == 200
    data = res.json()
    assert "Diário de aprendizado do agente" in data["markdown"]
    assert data["win_count"] == 0
    assert data["close_count"] == 0


def test_agent_journal_updates_on_study_tick(journal_paths, monkeypatch):
    monkeypatch.setattr("api.agent_library_study.settings.agent_auto_study_library", True)
    from api.agent_library_study import agent_study_tick
    from api.agent_journal import get_agent_journal

    agent_study_tick(force=True)
    journal = get_agent_journal()
    assert "Biblioteca estudada" in journal["markdown"]
    assert journal["last_study_at"]


def test_agent_journal_win_increments(journal_paths, monkeypatch):
    from api.agent_journal import get_agent_journal

    _mock_row(monkeypatch, symbol="PETR4", net=70.0, win=True, entry_reason="squeeze M1")
    journal = get_agent_journal()
    assert journal["win_count"] == 1
    assert journal["saved_since_first_win"] is True
    assert "Acerto #1" in journal["markdown"]
    assert "PETR4" in journal["markdown"]
    assert "Salvo desde o primeiro acerto" in journal["markdown"]
    meta = json.loads(journal_paths[1].read_text(encoding="utf-8"))
    assert meta["trade_history"][0]["net_pnl_brl"] == 70.0


def test_agent_journal_append_loss_then_win_keeps_both(journal_paths, monkeypatch):
    from api.agent_journal import get_agent_journal

    _mock_row(monkeypatch, symbol="VALE3", net=-40.0, win=False, entry_reason="falso rompimento")
    j1 = get_agent_journal()
    assert j1["close_count"] == 1
    assert j1["loss_count"] == 1
    assert j1["win_count"] == 0
    assert j1["saved_since_first_win"] is False
    assert "aguardando primeiro acerto" in j1["markdown"].lower()
    assert "Erro #1" in j1["markdown"]
    assert "VALE3" in j1["markdown"]
    assert "Rascunho (pré-primeiro acerto)" in j1["markdown"]

    _mock_row(monkeypatch, symbol="PETR4", net=55.0, win=True, entry_reason="squeeze M1")
    j2 = get_agent_journal()
    assert j2["win_count"] == 1
    assert j2["loss_count"] == 1
    assert j2["close_count"] == 2
    assert "Acerto #1" in j2["markdown"]
    assert "Erro #1" in j2["markdown"]
    assert "VALE3" in j2["markdown"]
    assert j2["markdown"].count("| erro |") >= 1
    assert j2["markdown"].count("| acerto |") >= 1
    assert "Salvo desde o primeiro acerto" in j2["markdown"]

    meta = json.loads(journal_paths[1].read_text(encoding="utf-8"))
    assert len(meta["trade_history"]) == 2
