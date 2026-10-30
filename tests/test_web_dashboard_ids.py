"""IDs críticos do painel: cockpit (padrão) e classic (legado)."""

from __future__ import annotations

import re
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
APP_JS = _ROOT / "web" / "app.js"
INDEX_HTML = _ROOT / "web" / "index.html"
COCKPIT_HTML = _ROOT / "cockpit" / "index.html"

COCKPIT_CRITICAL_IDS = frozenset(
    {
        "engine-status",
        "engine-dot",
        "engine-label",
        "zone-nav",
        "chip-api",
        "chip-engine",
        "chip-modo",
        "btn-pause",
        "btn-resume",
        "btn-flatten",
        "api-url",
        "last-update-label",
        "live-sync-dot",
        "live-ops",
        "live-ops-today-net",
        "live-ops-body",
        "live-ops-totals",
        "pulse-tab-nav",
        "today-mtm-amount",
        "watchlist-bar",
        "ticker-search",
        "decision-panel",
        "trade-chart-host",
        "ticker-grid",
        "chart-regime-label",
        "zone-status",
        "zone-signals",
        "zone-trades",
        "zone-agent",
        "zone-library",
    }
)


def _ids_from_app_js() -> set[str]:
    text = APP_JS.read_text(encoding="utf-8")
    found = set(re.findall(r'\$\("([^"]+)"\)', text))
    found.update(re.findall(r'setText\("([^"]+)"', text))
    found.update(re.findall(r'setStatText\("([^"]+)"', text))
    found.update(re.findall(r'setPnlEl\("([^"]+)"', text))
    found.update(re.findall(r'setLiveChip\("([^"]+)"', text))
    found.update(re.findall(r'setStatusTile\("([^"]+)"', text))
    for m in re.finditer(r'^\s+set\("([^"]+)"', text, re.M):
        found.add(m.group(1))
    return found


def _ids_from_html(path: Path) -> set[str]:
    text = path.read_text(encoding="utf-8")
    return set(re.findall(r'\bid="([^"]+)"', text))


def test_app_js_element_ids_exist_in_classic_index_html():
    """Painel em /classic — app.js continua alinhado ao index legado."""
    app_ids = _ids_from_app_js()
    html_ids = _ids_from_html(INDEX_HTML)
    missing = sorted(app_ids - html_ids)
    assert not missing, f"IDs em app.js ausentes no index.html (classic): {missing}"


def test_cockpit_critical_ids_in_cockpit_html():
    """Pulse Deck — IDs usados por testes e integração."""
    assert COCKPIT_HTML.is_file(), "cockpit/index.html ausente — rode npm run build no cockpit/"
    html_ids = _ids_from_html(COCKPIT_HTML)
    # zone-* panels são criados dinamicamente no painel; exigimos ids fixos no shell
    shell_required = COCKPIT_CRITICAL_IDS - {
        "zone-status",
        "zone-signals",
        "zone-trades",
        "zone-agent",
        "zone-library",
    }
    missing = sorted(shell_required - html_ids)
    assert not missing, f"IDs críticos ausentes no cockpit/index.html: {missing}"
