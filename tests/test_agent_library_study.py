"""Estudo autônomo da biblioteca pelo agente — progresso e tick."""

from __future__ import annotations

import json
from pathlib import Path

import pytest


@pytest.fixture
def agent_progress_file(tmp_path, monkeypatch):
    path = tmp_path / "agent_library_progress.json"
    monkeypatch.setattr("api.agent_library_study._PROGRESS_FILE", path)
    return path


def test_agent_study_tick_marks_article(agent_progress_file, monkeypatch):
    monkeypatch.setattr("api.agent_library_study.settings.agent_auto_study_library", True)
    from api.agent_library_study import agent_study_tick, load_agent_library_progress

    result = agent_study_tick(force=True)
    assert result["ticked"] is True
    assert result["article_id"]
    assert result["studied_count"] == 1
    assert result["digest"]
    progress = load_agent_library_progress()
    assert result["article_id"] in progress["read_article_ids"]
    assert progress["study_log"]


def test_agent_study_tick_disabled_without_force(monkeypatch, agent_progress_file):
    monkeypatch.setattr("api.agent_library_study.settings.agent_auto_study_library", False)
    from api.agent_library_study import agent_study_tick

    result = agent_study_tick(force=False)
    assert result["ticked"] is False
    assert "desligado" in result["message"].lower()


def test_agent_knowledge_level_after_reads(agent_progress_file, monkeypatch):
    monkeypatch.setattr("api.agent_library_study.settings.agent_auto_study_library", True)
    from api.agent_library_study import agent_knowledge_level, agent_study_tick

    for _ in range(3):
        agent_study_tick(force=True)
    level = agent_knowledge_level()
    assert level.article_count >= 3
    assert level.level_id in ("iniciante", "aprendiz", "intermediario", "avancado")


def test_agent_study_status_endpoint(agent_progress_file, monkeypatch):
    monkeypatch.setattr("api.agent_library_study.settings.agent_auto_study_library", False)
    from fastapi.testclient import TestClient

    import api.main as main_mod

    client = TestClient(main_mod.app)
    res = client.get("/library/agent-study-status")
    assert res.status_code == 200
    data = res.json()
    assert data["state"] == "idle"
    assert data["auto_study_enabled"] is False
    assert data["total_articles"] >= 1


def test_knowledge_level_agent_query(agent_progress_file, monkeypatch):
    monkeypatch.setattr("api.agent_library_study.settings.agent_auto_study_library", True)
    from fastapi.testclient import TestClient

    import api.main as main_mod
    from api.agent_library_study import agent_study_tick

    agent_study_tick(force=True)
    client = TestClient(main_mod.app)
    res = client.get("/library/knowledge-level?agent=true")
    assert res.status_code == 200
    data = res.json()
    assert data["progress_scope"] == "agent_study"
    assert data["article_count"] == 1


def test_manual_tick_endpoint(agent_progress_file):
    from fastapi.testclient import TestClient

    import api.main as main_mod

    client = TestClient(main_mod.app)
    res = client.post("/library/agent-study/tick?force=true")
    assert res.status_code == 200
    assert res.json()["ticked"] is True


def test_agent_study_background_enabled_with_overnight(monkeypatch):
    from api.config import settings

    monkeypatch.setattr(settings, "agent_auto_study_library", True)
    monkeypatch.setattr(settings, "overnight_learning", True)
    assert settings.agent_study_background_enabled is True
