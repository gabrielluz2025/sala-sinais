"""Testes de ingestão externa (mock HTTP, dry-run)."""

from __future__ import annotations

import json
from unittest.mock import patch

RSS_XML = b"""<?xml version="1.0"?>
<rss><channel>
<item><title>Teste RSS B3</title><link>https://example.com/a</link>
<description>&lt;p&gt;Resumo RSS&lt;/p&gt;</description><pubDate>Wed, 29 Oct 2025 12:00:00 GMT</pubDate></item>
</channel></rss>"""

FINNHUB_JSON = json.dumps(
    [{"headline": "Mercado sobe", "url": "https://example.com/f", "summary": "Macro", "datetime": 1730203200}]
)

NEWSAPI_JSON = json.dumps(
    {
        "status": "ok",
        "articles": [
            {
                "title": "Ibovespa fecha em alta",
                "url": "https://example.com/n",
                "description": "Pregão positivo",
                "publishedAt": "2025-10-29T15:00:00Z",
            }
        ],
    }
)


def test_ingest_urls_dry_run_mock_feed():
    from scripts.ingest_library_news import ingest_urls

    with patch("scripts.ingest_library_news.fetch_feed", return_value=RSS_XML):
        ingest_urls(["https://feed.test/rss"], max_per_feed=3, dry_run=True)


def test_ingest_urls_writes_md(tmp_path, monkeypatch):
    from scripts import ingest_library_news as mod
    from scripts import library_news_io as io

    news = tmp_path / "library" / "news"
    news.mkdir(parents=True)
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    monkeypatch.setattr(mod, "NEWS_DIR", news)
    monkeypatch.setattr(io, "ROOT", tmp_path)
    monkeypatch.setattr(io, "NEWS_DIR", news)

    with patch.object(mod, "fetch_feed", return_value=RSS_XML):
        written = mod.ingest_urls(["https://feed.test/rss"], max_per_feed=1, dry_run=False)
    assert len(written) == 1
    fname = written[0].replace("\\", "/").split("/")[-1]
    path = news / fname
    assert path.is_file()
    text = path.read_text(encoding="utf-8")
    assert "source: news" in text
    assert "Teste RSS B3" in text


def test_run_all_ingest_dry_run_mock_apis(capsys):
    from scripts.ingest_external_finance import run_all_ingest

    def fake_json(url: str, timeout: int = 25):
        if "finnhub" in url:
            return json.loads(FINNHUB_JSON)
        if "newsapi" in url:
            return json.loads(NEWSAPI_JSON)
        return None

    with patch("scripts.ingest_external_finance._get_json", side_effect=fake_json):
        with patch("scripts.ingest_external_finance.ingest_urls", return_value=[]):
            out = run_all_ingest(
                rss_urls=[],
                finnhub_key="test-fh",
                newsapi_key="test-na",
                max_per_source=1,
                dry_run=True,
            )
    assert out["finnhub"] == []
    assert out["newsapi"] == []
    captured = capsys.readouterr()
    assert "Mercado sobe" in captured.out
    assert "Ibovespa" in captured.out


def test_library_ingest_tick_calls_runner(monkeypatch):
    from api import config as cfg

    monkeypatch.setattr(cfg.settings, "library_news_rss_urls", "")
    monkeypatch.setattr(cfg.settings, "finnhub_api_key", "")
    monkeypatch.setattr(cfg.settings, "newsapi_key", "")

    calls = []

    def fake_run(**kwargs):
        calls.append(kwargs)
        return {"rss": [], "finnhub": [], "newsapi": []}

    with patch("api.library_ingest_job.run_all_ingest", side_effect=fake_run):
        from api.library_ingest_job import library_ingest_tick

        library_ingest_tick()
    assert len(calls) == 1
