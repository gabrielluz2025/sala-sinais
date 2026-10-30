"""Biblioteca de aprendizado — artigos curados em Markdown."""

from __future__ import annotations

import io
import json
import shutil
import zipfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

from fastapi import HTTPException

from api.library_catalog import catalog_counts, load_merged_catalog
from shared.schemas import (
    LibraryArticleIndex,
    LibraryArticleResponse,
    LibraryCategory,
    LibraryCategoryCount,
    LibraryIndexResponse,
    LibraryStatsResponse,
    LibraryStoragePaths,
)

_ROOT = Path(__file__).resolve().parents[1]
_LIBRARY_DIR = _ROOT / "library"
_INDEX_FILE = _LIBRARY_DIR / "index.json"
_ARTICLES_DIR = _LIBRARY_DIR / "articles"
_BACKUP_DIR = _LIBRARY_DIR / "backup"
_READ_PROGRESS_FILE = _ROOT / "data" / "library_read_progress.json"

LIBRARY_EXPORT_FORMAT = "sala_sinais_library_v1"
_MANIFEST_NAME = "manifest.json"


def _validate_archive_member(name: str) -> str:
    """Normaliza caminho do ZIP e rejeita zip slip."""
    pure = PurePosixPath(name.replace("\\", "/"))
    if pure.is_absolute() or ".." in pure.parts:
        raise HTTPException(400, f"Caminho inválido no arquivo: {name}")
    normalized = pure.as_posix().lstrip("./")
    if not normalized:
        raise HTTPException(400, f"Entrada vazia no arquivo: {name}")
    if normalized == _MANIFEST_NAME:
        return normalized
    if normalized == "index.json":
        return normalized
    if normalized.startswith("articles/") and normalized.endswith(".md"):
        rest = normalized[len("articles/") :]
        if "/" in rest or rest.startswith("."):
            raise HTTPException(400, f"Caminho de artigo inválido: {name}")
        return normalized
    raise HTTPException(400, f"Arquivo não permitido no pacote: {name}")


def _load_index_raw() -> dict:
    if not _INDEX_FILE.is_file():
        raise HTTPException(503, "Biblioteca indisponível — index.json ausente")
    try:
        return json.loads(_INDEX_FILE.read_text(encoding="utf-8"))
    except Exception as exc:
        raise HTTPException(500, f"Erro ao ler biblioteca: {exc}") from exc


def get_library_index() -> LibraryIndexResponse:
    raw = load_merged_catalog()
    categories = [LibraryCategory(**c) for c in raw.get("categories", [])]
    articles = [LibraryArticleIndex(**a) for a in raw.get("articles", [])]
    return LibraryIndexResponse(categories=categories, articles=articles)


def _scan_catalog_markdown() -> tuple[int, int]:
    """Retorna (total_words, total_bytes) de todos os .md do catálogo."""
    total_words = 0
    total_bytes = 0
    raw = load_merged_catalog()
    seen: set[str] = set()
    for article in raw.get("articles") or []:
        rel = article.get("path") or ""
        if not rel or rel in seen:
            continue
        seen.add(rel)
        path = _LIBRARY_DIR / rel
        if not path.is_file():
            continue
        raw_bytes = path.read_bytes()
        total_bytes += len(raw_bytes)
        text = raw_bytes.decode("utf-8", errors="replace")
        total_words += len(text.split())
    return total_words, total_bytes


def _article_markdown_path(match: dict) -> Path:
    rel = match.get("path") or f"articles/{match.get('id', '')}.md"
    return _LIBRARY_DIR / rel


def _word_count_file(path: Path) -> int:
    if not path.is_file():
        return 0
    text = path.read_text(encoding="utf-8", errors="replace")
    return len(text.split())


def get_knowledge_counts_for_read_ids(read_ids: list[str]) -> tuple[int, int]:
    """Itens lidos válidos no catálogo e soma de palavras dos .md correspondentes."""
    raw = load_merged_catalog()
    by_id = {a.get("id"): a for a in raw.get("articles") or [] if a.get("id")}
    seen: set[str] = set()
    article_count = 0
    total_words = 0
    for rid in read_ids:
        if rid in seen or rid not in by_id:
            continue
        seen.add(rid)
        article_count += 1
        total_words += _word_count_file(_article_markdown_path(by_id[rid]))
    return article_count, total_words


def load_library_read_progress() -> list[str]:
    if not _READ_PROGRESS_FILE.is_file():
        return []
    try:
        data = json.loads(_READ_PROGRESS_FILE.read_text(encoding="utf-8"))
        ids = data.get("read_article_ids") or []
        return [str(x) for x in ids if x]
    except Exception:
        return []


def save_library_read_progress(read_ids: list[str]) -> list[str]:
    _READ_PROGRESS_FILE.parent.mkdir(parents=True, exist_ok=True)
    raw = load_merged_catalog()
    valid = {a.get("id") for a in raw.get("articles") or [] if a.get("id")}
    merged: list[str] = []
    seen: set[str] = set()
    for rid in read_ids:
        if rid not in valid or rid in seen:
            continue
        seen.add(rid)
        merged.append(rid)
    payload = {"read_article_ids": merged, "updated_at": datetime.now(timezone.utc).isoformat()}
    _READ_PROGRESS_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return merged


def merge_library_read_progress(new_ids: list[str]) -> list[str]:
    existing = load_library_read_progress()
    return save_library_read_progress(existing + new_ids)


def get_library_stats() -> LibraryStatsResponse:
    raw = load_merged_catalog()
    articles = list(raw.get("articles") or [])
    index_categories = list(raw.get("categories") or [])
    counts_cat: dict[str, int] = {}
    for article in articles:
        cat = article.get("category") or ""
        counts_cat[cat] = counts_cat.get(cat, 0) + 1

    categories_out: list[LibraryCategoryCount] = []
    seen_cat_ids: set[str] = set()
    for cat in index_categories:
        cid = cat.get("id") or ""
        seen_cat_ids.add(cid)
        categories_out.append(
            LibraryCategoryCount(
                id=cid,
                label=cat.get("label") or cid,
                count=counts_cat.get(cid, 0),
            )
        )
    for cid, n in counts_cat.items():
        if cid and cid not in seen_cat_ids:
            categories_out.append(LibraryCategoryCount(id=cid, label=cid, count=n))

    last_updated = ""
    for article in articles:
        updated = article.get("updated") or ""
        if updated and (not last_updated or updated > last_updated):
            last_updated = updated

    total_words, total_bytes = _scan_catalog_markdown()
    layer = catalog_counts()
    return LibraryStatsResponse(
        article_count=layer["article_count"],
        curated_count=layer["curated_count"],
        imported_count=layer["imported_count"],
        news_count=layer["news_count"],
        catalog_total=layer["catalog_total"],
        categories=categories_out,
        total_words=total_words,
        total_bytes=total_bytes,
        last_updated=last_updated,
        storage_paths=LibraryStoragePaths(
            articles="library/articles/ (+ imported/, news/)",
            index="library/index.json + catálogo dinâmico",
            signals_db="data/sala_sinais.db",
            note="Camadas curada, importada e notícias; ingestão contínua configurável",
        ),
    )


def _backup_library_snapshot() -> Path:
    """Copia index.json e articles/ para library/backup/<timestamp>/."""
    _BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    for _ in range(20):
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        dest = _BACKUP_DIR / ts
        try:
            dest.mkdir(parents=False, exist_ok=False)
            break
        except FileExistsError:
            continue
    else:
        raise HTTPException(500, "Não foi possível criar pasta de backup")
    if _INDEX_FILE.is_file():
        shutil.copy2(_INDEX_FILE, dest / "index.json")
    articles_dest = dest / "articles"
    if _ARTICLES_DIR.is_dir():
        shutil.copytree(_ARTICLES_DIR, articles_dest)
    else:
        articles_dest.mkdir(parents=True, exist_ok=True)
    return dest


def _merge_index(existing: dict, incoming: dict) -> dict:
    cat_by_id = {c.get("id"): c for c in existing.get("categories") or [] if c.get("id")}
    for c in incoming.get("categories") or []:
        cid = c.get("id")
        if cid:
            cat_by_id[cid] = c
    art_by_id = {a.get("id"): a for a in existing.get("articles") or [] if a.get("id")}
    for a in incoming.get("articles") or []:
        aid = a.get("id")
        if aid:
            art_by_id[aid] = a
    return {
        "categories": list(cat_by_id.values()),
        "articles": list(art_by_id.values()),
    }


def build_library_export_zip() -> bytes:
    if not _INDEX_FILE.is_file():
        raise HTTPException(503, "Biblioteca indisponível — index.json ausente")
    buf = io.BytesIO()
    exported_at = datetime.now(timezone.utc).isoformat()
    manifest = {
        "format": LIBRARY_EXPORT_FORMAT,
        "exported_at": exported_at,
        "note": "Conhecimento curado (index.json + articles/*.md). Não inclui sala_sinais.db.",
    }
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(_MANIFEST_NAME, json.dumps(manifest, ensure_ascii=False, indent=2))
        zf.write(_INDEX_FILE, arcname="index.json")
        if _ARTICLES_DIR.is_dir():
            for path in sorted(_ARTICLES_DIR.glob("*.md")):
                zf.write(path, arcname=f"articles/{path.name}")
    return buf.getvalue()


def import_library_archive(data: bytes, mode: str = "merge") -> dict:
    """
    Importa ZIP no formato sala_sinais_library_v1.

    mode:
      - merge (padrão): mescla index por id de artigo/categoria; grava .md do pacote.
      - replace: backup completo, depois substitui index e artigos pelos do pacote.
    """
    mode_norm = (mode or "merge").strip().lower()
    if mode_norm not in ("merge", "replace"):
        raise HTTPException(400, "mode deve ser 'merge' ou 'replace'")

    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as exc:
        raise HTTPException(400, "Arquivo ZIP inválido") from exc

    entries: dict[str, bytes] = {}
    for info in zf.infolist():
        if info.is_dir():
            continue
        key = _validate_archive_member(info.filename)
        entries[key] = zf.read(info)

    if _MANIFEST_NAME not in entries:
        raise HTTPException(400, "Pacote sem manifest.json")
    try:
        manifest = json.loads(entries[_MANIFEST_NAME].decode("utf-8"))
    except Exception as exc:
        raise HTTPException(400, f"manifest.json inválido: {exc}") from exc
    if manifest.get("format") != LIBRARY_EXPORT_FORMAT:
        raise HTTPException(
            400,
            f"Formato incompatível: esperado {LIBRARY_EXPORT_FORMAT}, "
            f"recebido {manifest.get('format')}",
        )
    if "index.json" not in entries:
        raise HTTPException(400, "Pacote sem index.json")

    try:
        incoming_index = json.loads(entries["index.json"].decode("utf-8"))
    except Exception as exc:
        raise HTTPException(400, f"index.json inválido: {exc}") from exc

    article_files = {
        k: v for k, v in entries.items() if k.startswith("articles/") and k.endswith(".md")
    }

    backup_dir: Path | None = None
    if mode_norm == "replace" or _INDEX_FILE.is_file() or _ARTICLES_DIR.is_dir():
        backup_dir = _backup_library_snapshot()

    _ARTICLES_DIR.mkdir(parents=True, exist_ok=True)

    if mode_norm == "replace":
        for path in _ARTICLES_DIR.glob("*.md"):
            path.unlink()
        final_index = incoming_index
    else:
        if _INDEX_FILE.is_file():
            try:
                existing_index = json.loads(_INDEX_FILE.read_text(encoding="utf-8"))
            except Exception:
                existing_index = {"categories": [], "articles": []}
        else:
            existing_index = {"categories": [], "articles": []}
        final_index = _merge_index(existing_index, incoming_index)

    for rel, raw in article_files.items():
        name = rel.split("/", 1)[1]
        dest = _ARTICLES_DIR / name
        dest.write_bytes(raw)

    _INDEX_FILE.parent.mkdir(parents=True, exist_ok=True)
    _INDEX_FILE.write_text(
        json.dumps(final_index, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    rel_backup = ""
    if backup_dir is not None:
        try:
            rel_backup = str(backup_dir.relative_to(_ROOT)).replace("\\", "/")
        except ValueError:
            rel_backup = str(backup_dir)

    articles_in_index = len(final_index.get("articles") or [])
    return {
        "format": LIBRARY_EXPORT_FORMAT,
        "mode": mode_norm,
        "articles_written": len(article_files),
        "articles_in_index": articles_in_index,
        "backup_dir": rel_backup or None,
        "message": (
            "Importação concluída. Backup anterior em "
            f"{rel_backup}."
            if rel_backup
            else "Importação concluída."
        ),
    }


def get_library_article(article_id: str) -> LibraryArticleResponse:
    match = next(
        (a for a in load_merged_catalog().get("articles", []) if a.get("id") == article_id),
        None,
    )
    if not match:
        raise HTTPException(404, "Artigo não encontrado")
    rel = match.get("path") or f"articles/{article_id}.md"
    path = _LIBRARY_DIR / rel
    if not path.is_file():
        raise HTTPException(404, "Conteúdo do artigo ausente")
    markdown = path.read_text(encoding="utf-8")
    return LibraryArticleResponse(
        id=match["id"],
        title=match.get("title", article_id),
        category=match.get("category", ""),
        tags=list(match.get("tags") or []),
        markdown=markdown,
        updated=match.get("updated", ""),
    )
