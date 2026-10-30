"""Nível de conhecimento do agente a partir da biblioteca curada."""

from __future__ import annotations

from dataclasses import dataclass

from shared.schemas import LibraryKnowledgeLevelResponse, LibraryKnowledgeTierInfo


@dataclass(frozen=True)
class _TierDef:
    id: str
    label: str
    min_articles: int
    min_words: int


TIERS: tuple[_TierDef, ...] = (
    _TierDef("iniciante", "Iniciante", 0, 0),
    _TierDef("aprendiz", "Aprendiz", 3, 2_000),
    _TierDef("intermediario", "Intermediário", 6, 5_000),
    _TierDef("avancado", "Avançado", 10, 10_000),
)

FORMULA_NOTE = (
    "Nível = maior faixa em que artigos e palavras atingem o mínimo da faixa "
    "(Aprendiz: 3 artigos e 2.000 palavras; Intermediário: 6 e 5.000; "
    "Avançado: 10 e 10.000). Barra principal = menor avanço entre artigos e palavras "
    "até a próxima faixa (o critério que falta promover)."
)

READ_PROGRESS_FORMULA_NOTE = (
    "Nível pelos artigos que você abriu na biblioteca (lidos). "
    "Faixas: Aprendiz 3/2.000; Intermediário 6/5.000; Avançado 10/10.000. "
    "Barra = progresso até a próxima faixa (limitado pelo critério mais fraco)."
)

AGENT_STUDY_FORMULA_NOTE = (
    "Nível pelos artigos que o agente estudou autonomamente (data/agent_library_progress.json). "
    "Mesmas faixas: Aprendiz 3/2.000; Intermediário 6/5.000; Avançado 10/10.000. "
    "Catálogo X/Y é só cobertura — não confundir com a barra de nível."
)


def _tier_index(article_count: int, total_words: int) -> int:
    idx = 0
    for i, tier in enumerate(TIERS):
        if article_count >= tier.min_articles and total_words >= tier.min_words:
            idx = i
    return idx


def compute_knowledge_level(
    article_count: int,
    total_words: int,
    *,
    formula_note: str | None = None,
) -> LibraryKnowledgeLevelResponse:
    idx = _tier_index(article_count, total_words)
    current = TIERS[idx]
    next_tier = TIERS[idx + 1] if idx + 1 < len(TIERS) else None

    if next_tier is None:
        progress_pct = 100.0
        articles_progress_pct = 100.0
        words_progress_pct = 100.0
        articles_to_next = 0
        words_to_next = 0
    else:
        art_span = max(1, next_tier.min_articles - current.min_articles)
        word_span = max(1, next_tier.min_words - current.min_words)
        art_prog = (article_count - current.min_articles) / art_span
        word_prog = (total_words - current.min_words) / word_span
        articles_progress_pct = round(min(100.0, max(0.0, art_prog * 100)), 1)
        words_progress_pct = round(min(100.0, max(0.0, word_prog * 100)), 1)
        progress_pct = round(min(articles_progress_pct, words_progress_pct), 1)
        articles_to_next = max(0, next_tier.min_articles - article_count)
        words_to_next = max(0, next_tier.min_words - total_words)

    tiers_out = [
        LibraryKnowledgeTierInfo(
            id=t.id,
            label=t.label,
            min_articles=t.min_articles,
            min_words=t.min_words,
        )
        for t in TIERS
    ]

    return LibraryKnowledgeLevelResponse(
        level_id=current.id,
        level_label=current.label,
        article_count=article_count,
        total_words=total_words,
        progress_pct=progress_pct,
        articles_progress_pct=articles_progress_pct,
        words_progress_pct=words_progress_pct,
        next_level_id=next_tier.id if next_tier else None,
        next_level_label=next_tier.label if next_tier else None,
        articles_to_next=articles_to_next,
        words_to_next=words_to_next,
        tiers=tiers_out,
        formula_note=formula_note or FORMULA_NOTE,
    )
