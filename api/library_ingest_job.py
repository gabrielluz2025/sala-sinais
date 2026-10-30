"""Job síncrono de ingestão de notícias (RSS + APIs) para a biblioteca."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from api.config import settings  # noqa: E402
from scripts.ingest_external_finance import run_all_ingest  # noqa: E402

log = logging.getLogger(__name__)


def library_ingest_tick() -> dict[str, list[str]]:
    """Executa ingestão conforme variáveis de ambiente / settings."""
    rss = [u.strip() for u in settings.library_news_rss_urls.split(",") if u.strip()]
    return run_all_ingest(
        rss_urls=rss,
        finnhub_key=settings.finnhub_api_key,
        newsapi_key=settings.newsapi_key,
        max_per_source=5,
        dry_run=False,
    )
