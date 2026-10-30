"""Export/import da biblioteca curada (library/)."""

from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path

from fastapi.testclient import TestClient

import api.main as main_mod
from api.library import LIBRARY_EXPORT_FORMAT, _LIBRARY_DIR, import_library_archive

_ROOT = Path(__file__).resolve().parents[1]


def test_library_export_zip_roundtrip_merge():
    client = TestClient(main_mod.app)
    res = client.get("/library/export")
    assert res.status_code == 200
    assert res.headers.get("content-type", "").startswith("application/zip")
    data = res.content
    assert len(data) > 100

    zf = zipfile.ZipFile(io.BytesIO(data))
    names = set(zf.namelist())
    assert "manifest.json" in names
    assert "index.json" in names
    manifest = json.loads(zf.read("manifest.json"))
    assert manifest["format"] == LIBRARY_EXPORT_FORMAT

    article_names = [n for n in names if n.startswith("articles/") and n.endswith(".md")]
    assert article_names

    result = import_library_archive(data, mode="merge")
    assert result["format"] == LIBRARY_EXPORT_FORMAT
    assert result["articles_written"] == len(article_names)
    assert result["articles_in_index"] >= 1
    assert result["backup_dir"]
    backup = _ROOT / result["backup_dir"]
    assert backup.is_dir()
    assert (backup / "index.json").is_file()


def test_library_import_rejects_zip_slip():
    buf = io.BytesIO()
    manifest = {"format": LIBRARY_EXPORT_FORMAT}
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("manifest.json", json.dumps(manifest))
        zf.writestr("index.json", json.dumps({"categories": [], "articles": []}))
        zf.writestr("../../evil.md", b"x")
    client = TestClient(main_mod.app)
    res = client.post(
        "/library/import",
        files={"file": ("bad.zip", buf.getvalue(), "application/zip")},
    )
    assert res.status_code == 400


def test_library_import_sample_extra_article_merge(tmp_path):
    """Importa pacote mínimo com artigo extra e verifica mesclagem."""
    extra_id = "99-test-export-import"
    md_name = f"articles/{extra_id}.md"
    index = {
        "categories": [{"id": "fundamentos", "label": "Fundamentos"}],
        "articles": [
            {
                "id": extra_id,
                "title": "Teste export/import",
                "category": "fundamentos",
                "tags": ["test"],
                "path": md_name,
                "updated": "2026-10-27",
            }
        ],
    }
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr(
            "manifest.json",
            json.dumps({"format": LIBRARY_EXPORT_FORMAT, "exported_at": "2026-10-27T00:00:00Z"}),
        )
        zf.writestr("index.json", json.dumps(index))
        zf.writestr(md_name, "# Teste\n\nConteúdo de teste.\n")
    payload = buf.getvalue()

    before = json.loads((_LIBRARY_DIR / "index.json").read_text(encoding="utf-8"))
    before_count = len(before.get("articles") or [])

    result = import_library_archive(payload, mode="merge")
    assert result["articles_written"] == 1

    after = json.loads((_LIBRARY_DIR / "index.json").read_text(encoding="utf-8"))
    ids = {a["id"] for a in after.get("articles") or []}
    assert extra_id in ids
    assert len(after.get("articles") or []) >= before_count

    art_path = _LIBRARY_DIR / "articles" / f"{extra_id}.md"
    assert art_path.is_file()
    art_path.unlink(missing_ok=True)

    after["articles"] = [a for a in after.get("articles") or [] if a.get("id") != extra_id]
    (_LIBRARY_DIR / "index.json").write_text(
        json.dumps(after, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
