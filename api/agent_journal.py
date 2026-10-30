"""Diário markdown do agente — fechamentos (acertos e erros) + ticks de estudo (sem LLM)."""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from api.agent_library_study import (
    agent_knowledge_level,
    get_agent_study_status,
    load_agent_library_progress,
    save_agent_library_progress,
)
from api.library import _load_index_raw
from api.pnl import resolved_pnl_for_row
from api.trades_metrics import trade_is_win
from shared.trade_learning import ROLLING_N, STRATEGY_LABEL_PT, load_learning_file

_ROOT = Path(__file__).resolve().parents[1]
_JOURNAL_DIR = _ROOT / "data" / "agent_journal"
_JOURNAL_FILE = _JOURNAL_DIR / "agente-aprendizado.md"
_META_FILE = _JOURNAL_DIR / "journal_meta.json"
_HISTORY_MAX = 30

_STRATEGY_PT = {
    "breakout": "breakout",
    "volatility": "volatilidade",
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _now_br_display() -> str:
    from zoneinfo import ZoneInfo

    return datetime.now(ZoneInfo("America/Sao_Paulo")).strftime("%d/%m/%Y %H:%M BRT")


def _format_pnl_br(net: float | None) -> str:
    if net is None:
        return "—"
    return f"R$ {float(net):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _closed_display_from_raw(closed_raw: Any) -> str:
    from zoneinfo import ZoneInfo

    if not closed_raw:
        return "—"
    try:
        dt = datetime.fromisoformat(str(closed_raw))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=ZoneInfo("America/Sao_Paulo"))
        return dt.astimezone(ZoneInfo("America/Sao_Paulo")).strftime("%d/%m/%Y %H:%M BRT")
    except Exception:
        return str(closed_raw)


def _default_meta() -> dict[str, Any]:
    return {
        "win_count": 0,
        "loss_count": 0,
        "close_count": 0,
        "updated_at": None,
        "last_win_at": None,
        "last_study_at": None,
        "first_win_at": None,
        "last_win_payload": None,
        "last_loss_payload": None,
        "trade_history": [],
    }


def _normalize_history_entry(entry: dict[str, Any]) -> dict[str, Any]:
    out = dict(entry)
    net = out.get("net_pnl")
    if net is None and out.get("net_pnl_brl") is not None:
        net = out["net_pnl_brl"]
    if net is not None:
        out["net_pnl"] = round(float(net), 2)
        out["net_pnl_brl"] = round(float(net), 2)
    return out


def _load_meta() -> dict[str, Any]:
    if not _META_FILE.is_file():
        return _default_meta()
    try:
        data = json.loads(_META_FILE.read_text(encoding="utf-8"))
    except Exception:
        return _default_meta()
    base = _default_meta()
    base.update({k: data.get(k, base[k]) for k in base})
    history = data.get("trade_history")
    if isinstance(history, list):
        base["trade_history"] = [
            _normalize_history_entry(h) for h in history if isinstance(h, dict)
        ]
    else:
        base["trade_history"] = []
    base["win_count"] = int(data.get("win_count") or 0)
    base["loss_count"] = int(data.get("loss_count") or 0)
    base["close_count"] = int(data.get("close_count") or 0)
    return base


def _save_meta(meta: dict[str, Any]) -> None:
    _JOURNAL_DIR.mkdir(parents=True, exist_ok=True)
    out = dict(meta)
    history = out.get("trade_history") or []
    if isinstance(history, list):
        out["trade_history"] = history[:_HISTORY_MAX]
    _META_FILE.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")


def compute_operational_maturity_pct(*, close_count: int, win_count: int) -> float:
    """Experiência prática (0–100) a partir de fechamentos reais — separado da biblioteca."""
    score = close_count * 3.0 + win_count * 4.0
    return min(100.0, round(score, 1))


def _sync_operational_maturity(meta: dict[str, Any]) -> None:
    close_count = int(meta.get("close_count") or 0)
    win_count = int(meta.get("win_count") or 0)
    pct = compute_operational_maturity_pct(close_count=close_count, win_count=win_count)
    progress = load_agent_library_progress()
    progress["closed_trades_count"] = close_count
    progress["journal_win_count"] = win_count
    progress["operational_maturity_pct"] = pct
    save_agent_library_progress(progress)


def _studied_titles(read_ids: list[str]) -> list[str]:
    articles = {a.get("id"): a for a in (_load_index_raw().get("articles") or []) if a.get("id")}
    out: list[str] = []
    for aid in read_ids:
        art = articles.get(aid) or {}
        title = str(art.get("title") or aid)
        out.append(f"- {title} (`{aid}`)")
    return out


def _lesson_from_win(trade: dict[str, Any]) -> str:
    symbol = trade.get("symbol") or "—"
    st = _STRATEGY_PT.get(str(trade.get("strategy_type") or "volatility"), "volatilidade")
    entry_reason = (trade.get("entry_reason") or "setup conforme regras do motor").strip()
    exit_reason = (trade.get("exit_reason") or "alvo ou gestão de risco").strip()
    net_s = _format_pnl_br(trade.get("net_pnl"))
    side = trade.get("side") or "—"
    return (
        f"Acerto em **{symbol}** ({side}) com estratégia **{st}**. "
        f"Entrada: {entry_reason}. Saída: {exit_reason}. "
        f"Resultado líquido {net_s}. "
        f"Reforço: repetir setups com motivo claro e respeitar o risco por trade."
    )


def _lesson_from_loss(trade: dict[str, Any]) -> str:
    symbol = trade.get("symbol") or "—"
    st = _STRATEGY_PT.get(str(trade.get("strategy_type") or "volatility"), "volatilidade")
    entry_reason = (trade.get("entry_reason") or "setup conforme regras do motor").strip()
    exit_reason = (trade.get("exit_reason") or "stop ou gestão").strip()
    net_s = _format_pnl_br(trade.get("net_pnl"))
    side = trade.get("side") or "—"
    return (
        f"Erro em **{symbol}** ({side}) com **{st}**. "
        f"Entrada: {entry_reason}. Saída: {exit_reason}. "
        f"Resultado {net_s}. "
        f"Ajuste: revisar contexto (horário, liquidez) antes de repetir o mesmo padrão."
    )


def _win_section(last_win: dict[str, Any] | None, win_count: int) -> str:
    if not last_win:
        return "Ainda sem acertos registrados neste diário."
    n = last_win.get("win_number") or win_count
    return f"""### Acerto #{n}

| Campo | Valor |
|-------|-------|
| Ativo | {last_win.get("symbol", "—")} |
| Lado | {last_win.get("side", "—")} |
| Estratégia | {_STRATEGY_PT.get(str(last_win.get("strategy_type") or ""), last_win.get("strategy_type") or "—")} |
| Motivo entrada | {last_win.get("entry_reason") or "—"} |
| PnL líquido | {_format_pnl_br(last_win.get("net_pnl"))} |
| Fechado em | {last_win.get("closed_at_display") or "—"} |

**Lição:** {_lesson_from_win(last_win)}
"""


def _loss_section(last_loss: dict[str, Any] | None, loss_count: int) -> str:
    if not last_loss:
        return "Nenhum erro registrado ainda."
    n = last_loss.get("loss_number") or loss_count
    return f"""### Erro #{n}

| Campo | Valor |
|-------|-------|
| Ativo | {last_loss.get("symbol", "—")} |
| Lado | {last_loss.get("side", "—")} |
| Estratégia | {_STRATEGY_PT.get(str(last_loss.get("strategy_type") or ""), last_loss.get("strategy_type") or "—")} |
| Motivo entrada | {last_loss.get("entry_reason") or "—"} |
| PnL líquido | {_format_pnl_br(last_loss.get("net_pnl"))} |
| Fechado em | {last_loss.get("closed_at_display") or "—"} |

**Lição:** {_lesson_from_loss(last_loss)}
"""


def _history_section(history: list[dict[str, Any]]) -> str:
    if not history:
        return "*(nenhum fechamento ainda)*"
    lines = [
        "| # | Resultado | Ativo | Estratégia | PnL | Motivo entrada | Fechado |",
        "|---|-----------|-------|------------|-----|----------------|---------|",
    ]
    for i, t in enumerate(history[:_HISTORY_MAX], start=1):
        res = "acerto" if t.get("win") else "erro"
        st = _STRATEGY_PT.get(str(t.get("strategy_type") or ""), t.get("strategy_type") or "—")
        motivo = (t.get("entry_reason") or "—").replace("|", "/")[:80]
        lines.append(
            f"| {i} | {res} | {t.get('symbol', '—')} | {st} | "
            f"{_format_pnl_br(t.get('net_pnl'))} | {motivo} | {t.get('closed_at_display') or '—'} |"
        )
    return "\n".join(lines)


def _practice_section(history: list[dict[str, Any]]) -> str:
    if not history:
        return "- *(aguardando fechamentos para correlacionar estratégia e resultado)*"
    bullets: list[str] = []
    for t in history[:8]:
        st = _STRATEGY_PT.get(str(t.get("strategy_type") or "volatility"), "volatilidade")
        sym = t.get("symbol") or "—"
        outcome = "acerto" if t.get("win") else "erro"
        pnl = _format_pnl_br(t.get("net_pnl"))
        motivo = (t.get("entry_reason") or "regras do motor").strip()[:100]
        bullets.append(f"- Aplicou **{st}** em **{sym}** → {outcome} ({pnl}) — {motivo}")
    return "\n".join(bullets)


def _operational_knowledge_section(meta: dict[str, Any]) -> str:
    cached = load_learning_file()
    perf = cached.get("performance_learning") or {}
    rolling = perf.get("rolling") or {}
    wr = rolling.get("win_rate_pct")
    r_trades = rolling.get("trades") or 0
    wr_line = "Win rate rolling: dados insuficientes (< 3 fechamentos na base)."
    if r_trades >= 3 and wr is not None:
        wr_line = (
            f"Win rate rolling (últimos {min(r_trades, ROLLING_N)} fechamentos): **{wr:.0f}%** · "
            f"PnL janela {rolling.get('net_pnl_brl', 0):+.2f} R$"
        )

    best = perf.get("best_strategy")
    best_line = "Melhor estratégia (stats): ainda sem amostra suficiente."
    if isinstance(best, dict) and best.get("id"):
        label = STRATEGY_LABEL_PT.get(str(best["id"]), str(best["id"]))
        bwr = best.get("win_rate_pct")
        if bwr is not None:
            exp = best.get("expectancy_brl")
            exp_s = f"{float(exp):+.2f}" if exp is not None else "—"
            best_line = (
                f"Melhor estratégia na base: **{label}** — {bwr:.0f}% acerto · "
                f"expectativa {exp_s} R$/trade"
            )

    history = meta.get("trade_history") or []
    counts = Counter(str(t.get("strategy_type") or "volatility") for t in history if isinstance(t, dict))
    apply_lines: list[str] = []
    for st_id, n in sorted(counts.items()):
        label = _STRATEGY_PT.get(st_id, st_id)
        apply_lines.append(f"- Aplicou **{label}** em **{n}** trade(s) no histórico do diário (últimos {_HISTORY_MAX}).")
    if not apply_lines:
        apply_lines.append("- *(contagem por estratégia aparece após fechamentos)*")

    maturity = compute_operational_maturity_pct(
        close_count=int(meta.get("close_count") or 0),
        win_count=int(meta.get("win_count") or 0),
    )
    return f"""{wr_line}

{best_line}

**Uso prático de estratégias (diário):**
{chr(10).join(apply_lines)}

- Experiência prática estimada: **{maturity:.0f}%** (fechamentos + acertos; barra separada da biblioteca no cockpit).
"""


def _header_banner(meta: dict[str, Any]) -> str:
    if meta.get("first_win_at"):
        return (
            "> **Salvo desde o primeiro acerto** — erros permanecem visíveis no histórico.\n"
            f"> Primeiro acerto registrado: {meta.get('first_win_at')}"
        )
    close_count = int(meta.get("close_count") or 0)
    if close_count > 0:
        return (
            "> Diário iniciado após fechamentos — **aguardando primeiro acerto**; "
            "perdas e histórico já ficam gravados."
        )
    return "> Documento gerado pelo motor — atualizado após fechamentos e estudo da biblioteca."


def _render_markdown(*, meta: dict[str, Any], study_status: dict, studied_lines: list[str]) -> str:
    level = agent_knowledge_level()
    status = study_status
    last_study_title = status.get("last_article_title") or "—"
    last_study_at = status.get("last_study_at") or "—"
    next_title = status.get("next_article_title") or "biblioteca completa"

    win_count = int(meta.get("win_count") or 0)
    loss_count = int(meta.get("loss_count") or 0)
    close_count = int(meta.get("close_count") or 0)
    history = [h for h in (meta.get("trade_history") or []) if isinstance(h, dict)]
    last_win = meta.get("last_win_payload") if isinstance(meta.get("last_win_payload"), dict) else None
    last_loss = meta.get("last_loss_payload") if isinstance(meta.get("last_loss_payload"), dict) else None

    studied_block = "\n".join(studied_lines) if studied_lines else "- *(nenhum artigo marcado ainda)*"

    draft_block = ""
    if close_count > 0 and win_count == 0:
        draft_block = """
## Rascunho (pré-primeiro acerto)

Perdas abaixo **não são apagadas** quando o primeiro acerto for registrado — o diário só ganha o selo «salvo desde primeiro acerto».
"""

    return f"""# Diário de aprendizado do agente

{_header_banner(meta)}
> Última revisão: {_now_br_display()}

## Nível atual (biblioteca)

- **Faixa:** {level.level_label} ({level.level_id})
- **Artigos estudados:** {status.get("studied_count", 0)}/{status.get("total_articles", 0)}
- **Palavras acumuladas:** {level.total_words:,}
- **Progresso na faixa:** {level.progress_pct:.0f}%

## Biblioteca estudada (cumulativo)

{studied_block}

## Estudo autônomo (24h)

- **Último artigo:** {last_study_title}
- **Horário:** {last_study_at}
- **Próximo na fila:** {next_title}
{draft_block}
## Último acerto

{_win_section(last_win, win_count)}

## Último erro

{_loss_section(last_loss, loss_count)}

## Histórico de operações

Últimos {min(len(history), _HISTORY_MAX)} fechamentos (acertos e erros — **nunca ocultados**):

{_history_section(history)}

## O que aplicou na prática

{_practice_section(history)}

## Conhecimento operacional

{_operational_knowledge_section(meta)}

---
*Fechamentos no diário: {close_count} · Acertos: {win_count} · Erros: {loss_count}*
"""


def rebuild_agent_journal(**_kwargs: Any) -> dict[str, Any]:
    """Reescreve o markdown a partir do meta + progresso (histórico preservado no JSON)."""
    meta = _load_meta()
    progress = load_agent_library_progress()
    studied_lines = _studied_titles(progress.get("read_article_ids") or [])
    study_status = get_agent_study_status()
    md = _render_markdown(meta=meta, study_status=study_status, studied_lines=studied_lines)
    _JOURNAL_DIR.mkdir(parents=True, exist_ok=True)
    _JOURNAL_FILE.write_text(md, encoding="utf-8")
    meta["updated_at"] = _now_iso()
    _save_meta(meta)
    return get_agent_journal()


def get_agent_journal() -> dict[str, Any]:
    meta = _load_meta()
    close_count = int(meta.get("close_count") or 0)
    if not _JOURNAL_FILE.is_file():
        rebuild_agent_journal()
    try:
        markdown = _JOURNAL_FILE.read_text(encoding="utf-8")
    except Exception:
        markdown = "# Diário indisponível\n"
    try:
        path = str(_JOURNAL_FILE.relative_to(_ROOT)).replace("\\", "/")
    except ValueError:
        path = str(_JOURNAL_FILE).replace("\\", "/")
    win_count = int(meta.get("win_count") or 0)
    return {
        "markdown": markdown,
        "win_count": win_count,
        "close_count": close_count,
        "loss_count": int(meta.get("loss_count") or 0),
        "saved_since_first_win": bool(meta.get("first_win_at")),
        "updated_at": meta.get("updated_at"),
        "last_win_at": meta.get("last_win_at"),
        "last_study_at": meta.get("last_study_at"),
        "path": path,
    }


def on_library_study_tick(*, article_id: str, title: str, studied_count: int, total_articles: int) -> None:
    del article_id, title, studied_count, total_articles
    meta = _load_meta()
    meta["last_study_at"] = _now_iso()
    _save_meta(meta)
    rebuild_agent_journal()


def on_trade_closed_row(row) -> None:
    """Chamado após fechamento persistido na API (acerto ou erro)."""
    from api.signal_close import persist_resolved_pnl

    _gross, net, _fees = persist_resolved_pnl(row)
    if net is None:
        return
    is_win = trade_is_win(row, float(net))
    closed_display = _closed_display_from_raw(row.closed_at or row.created_at)

    meta = _load_meta()
    close_count = int(meta.get("close_count") or 0) + 1
    entry: dict[str, Any] = {
        "symbol": row.symbol,
        "side": row.side,
        "strategy_type": row.strategy_type or "volatility",
        "entry_reason": row.entry_reason,
        "exit_reason": row.exit_reason,
        "net_pnl": round(float(net), 2),
        "net_pnl_brl": round(float(net), 2),
        "win": is_win,
        "closed_at_display": closed_display,
        "closed_at": str(row.closed_at or row.created_at or ""),
    }

    history = list(meta.get("trade_history") or [])
    history.insert(0, entry)
    meta["trade_history"] = history[:_HISTORY_MAX]
    meta["close_count"] = close_count

    if is_win:
        win_count = int(meta.get("win_count") or 0) + 1
        payload = {**entry, "win_number": win_count}
        meta["win_count"] = win_count
        meta["last_win_at"] = _now_iso()
        meta["last_win_payload"] = payload
        if not meta.get("first_win_at"):
            meta["first_win_at"] = _now_iso()
    else:
        loss_count = int(meta.get("loss_count") or 0) + 1
        payload = {**entry, "loss_number": loss_count}
        meta["loss_count"] = loss_count
        meta["last_loss_payload"] = payload

    meta["updated_at"] = _now_iso()
    _save_meta(meta)
    _sync_operational_maturity(meta)
    rebuild_agent_journal()


def trade_dict_from_row(row) -> dict[str, Any] | None:
    """Helper para testes."""
    _gross, net, _fees = resolved_pnl_for_row(row)
    if net is None or row.exit_price is None:
        return None
    return {
        "symbol": row.symbol,
        "side": row.side,
        "net_pnl": round(float(net), 2),
        "strategy_type": row.strategy_type,
        "entry_reason": row.entry_reason,
        "exit_reason": row.exit_reason,
        "win": trade_is_win(row, float(net)),
    }
