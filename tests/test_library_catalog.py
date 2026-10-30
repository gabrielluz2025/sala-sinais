"""Catálogo v2 — merge index + imported + news."""

from __future__ import annotations

from pathlib import Path

import pytest


def test_merged_catalog_includes_curated_articles():
    from api.library_catalog import load_merged_catalog

    cat = load_merged_catalog()
    ids = {a["id"] for a in cat["articles"]}
    assert "01-o-que-e-day-trade" in ids
    assert len(ids) >= 38


def test_catalog_counts_match_layers(tmp_path, monkeypatch):
    from api import library_catalog as lc

    lib = tmp_path / "library"
    (lib / "articles").mkdir(parents=True)
    (lib / "imported").mkdir()
    (lib / "news").mkdir()
    (lib / "articles" / "a.md").write_text("# A\n", encoding="utf-8")
    (lib / "imported" / "imp-one.md").write_text(
        "---\ntitle: Imp\n category: imported\n---\n# Imp\n",
        encoding="utf-8",
    )
    (lib / "news" / "2026-10-29-test.md").write_text(
        "---\ntitle: News\n category: noticias\n---\n# N\n",
        encoding="utf-8",
    )
    (lib / "index.json").write_text(
        """{"categories":[{"id":"fundamentos","label":"F"}],"articles":[{"id":"a","title":"A","category":"fundamentos","tags":[],"path":"articles/a.md","updated":"2026-10-29"}]}""",
        encoding="utf-8",
    )
    monkeypatch.setattr(lc, "_LIBRARY_DIR", lib)
    monkeypatch.setattr(lc, "_INDEX_FILE", lib / "index.json")
    monkeypatch.setattr(lc, "_IMPORTED_DIR", lib / "imported")
    monkeypatch.setattr(lc, "_NEWS_DIR", lib / "news")

    merged = lc.load_merged_catalog()
    assert len(merged["articles"]) == 3
    counts = lc.catalog_counts()
    assert counts["curated_count"] == 1
    assert counts["imported_count"] == 1
    assert counts["news_count"] == 1
    assert counts["catalog_total"] == 3
    assert counts["article_count"] == 2


def test_library_stats_endpoint_catalog_total():
    from fastapi.testclient import TestClient

    import api.main as main_mod

    client = TestClient(main_mod.app)
    res = client.get("/library/stats")
    assert res.status_code == 200
    data = res.json()
    assert data["catalog_total"] >= data["article_count"]
    assert data["curated_count"] >= 18
    assert "news_count" in data


def test_library_index_same_count_as_catalog():
    from fastapi.testclient import TestClient

    import api.main as main_mod
    from api.library_catalog import catalog_counts

    client = TestClient(main_mod.app)
    idx = client.get("/library").json()
    counts = catalog_counts()
    assert len(idx["articles"]) == counts["catalog_total"]


def test_agent_study_total_matches_catalog():
    from fastapi.testclient import TestClient

    import api.main as main_mod
    from api.library_catalog import catalog_counts

    client = TestClient(main_mod.app)
    st = client.get("/library/agent-study-status").json()
    assert st["total_articles"] == catalog_counts()["catalog_total"]
