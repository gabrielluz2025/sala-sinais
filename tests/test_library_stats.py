"""GET /library/stats — tamanho e caminhos da biblioteca."""

from __future__ import annotations


def test_library_stats_endpoint():
    from fastapi.testclient import TestClient

    import api.main as main_mod

    client = TestClient(main_mod.app)
    res = client.get("/library/stats")
    assert res.status_code == 200
    data = res.json()
    assert data["article_count"] >= 1
    assert data["total_words"] > 0
    assert data["total_bytes"] > 0
    assert data["last_updated"]
    assert isinstance(data["categories"], list)
    assert any(c.get("count", 0) > 0 for c in data["categories"])
    paths = data["storage_paths"]
    assert paths["articles"] == "library/articles/"
    assert paths["index"] == "library/index.json"
    assert paths["signals_db"] == "data/sala_sinais.db"
    assert "Markdown" in paths["note"]


def test_get_library_stats_function():
    from api.library import get_library_stats

    stats = get_library_stats()
    assert stats.article_count == len(stats.categories) or stats.article_count >= 1
    assert stats.storage_paths.note
