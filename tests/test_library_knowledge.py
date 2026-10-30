"""GET /library/knowledge-level — faixas de conhecimento da biblioteca."""

from __future__ import annotations

from api.library_knowledge import compute_knowledge_level


def test_compute_knowledge_level_iniciante():
    level = compute_knowledge_level(1, 500)
    assert level.level_id == "iniciante"
    assert level.next_level_id == "aprendiz"
    assert level.progress_pct >= 0
    assert level.articles_to_next == 2
    assert level.words_to_next == 1500
    assert level.articles_progress_pct <= 100.0
    assert level.words_progress_pct <= 100.0


def test_aprendiz_progress_not_100_when_words_lag():
    """Catálogo completo em artigos não implica 100% na faixa Aprendiz."""
    level = compute_knowledge_level(6, 2_500)
    assert level.level_id == "aprendiz"
    assert level.next_level_id == "intermediario"
    assert level.progress_pct < 100.0
    assert level.articles_progress_pct == 100.0
    assert level.words_progress_pct < 100.0
    assert level.progress_pct == level.words_progress_pct


def test_progress_uses_bottleneck_not_average():
    level = compute_knowledge_level(2, 1_500)
    assert level.level_id == "iniciante"
    assert level.articles_progress_pct < level.words_progress_pct
    assert level.progress_pct == min(level.articles_progress_pct, level.words_progress_pct)


def test_compute_knowledge_level_avancado():
    level = compute_knowledge_level(12, 15_000)
    assert level.level_id == "avancado"
    assert level.next_level_id is None
    assert level.progress_pct == 100.0


def test_knowledge_level_endpoint_library_size():
    from fastapi.testclient import TestClient

    import api.main as main_mod

    client = TestClient(main_mod.app)
    res = client.get("/library/knowledge-level")
    assert res.status_code == 200
    data = res.json()
    assert data["progress_scope"] == "library_size"
    assert data["level_id"] in ("iniciante", "aprendiz", "intermediario", "avancado")
    assert data["article_count"] >= 1
    assert len(data["tiers"]) == 4
    assert data["formula_note"]


def test_knowledge_level_endpoint_user_read_empty():
    from fastapi.testclient import TestClient

    import api.main as main_mod

    client = TestClient(main_mod.app)
    res = client.get("/library/knowledge-level?read_ids=")
    assert res.status_code == 200
    data = res.json()
    assert data["progress_scope"] == "user_read"
    assert data["article_count"] == 0
    assert data["level_id"] == "iniciante"


def test_knowledge_level_with_read_ids():
    from fastapi.testclient import TestClient

    import api.main as main_mod

    client = TestClient(main_mod.app)
    idx = client.get("/library").json()
    first_id = idx["articles"][0]["id"]
    res = client.get(f"/library/knowledge-level?read_ids={first_id}")
    assert res.status_code == 200
    data = res.json()
    assert data["progress_scope"] == "user_read"
    assert data["article_count"] == 1
    assert data["total_words"] > 0


def test_read_progress_put_merge():
    from fastapi.testclient import TestClient

    import api.main as main_mod

    client = TestClient(main_mod.app)
    idx = client.get("/library").json()
    ids = [a["id"] for a in idx["articles"][:2]]
    res = client.put("/library/read-progress", json={"read_article_ids": ids[:1], "merge": True})
    assert res.status_code == 200
    assert ids[0] in res.json()["read_article_ids"]
    res2 = client.put("/library/read-progress", json={"read_article_ids": ids, "merge": True})
    assert len(res2.json()["read_article_ids"]) >= 2
