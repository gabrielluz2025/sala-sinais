"""Playbooks operacionais de day trade — três pilares alinhados ao engine."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

from engine.agent_runtime import is_win_symbol

StrategyType = Literal["breakout", "volatility"]

PILLAR_CONTEXT = "context_filter"
PILLAR_ENTRY = "entry_trigger"
PILLAR_EXIT = "exit_management"


@dataclass
class PlaybookPillar:
    """Um pilar do setup (contexto, gatilho ou saída)."""

    stage: str
    label_pt: str
    rule_pt: str
    detail_pt: str = ""


@dataclass
class DayTradePlaybook:
    strategy_type: StrategyType
    title_pt: str
    pillars: list[PlaybookPillar]
    library_article_ids: list[str] = field(default_factory=list)
    config_fields: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "strategy_type": self.strategy_type,
            "title_pt": self.title_pt,
            "pillars": [asdict(p) for p in self.pillars],
            "library_article_ids": self.library_article_ids,
            "config_fields": self.config_fields,
        }


def _fmt_win_stops(cfg: dict) -> tuple[str, str]:
    sp = int(cfg.get("stop_points") or 150)
    tp = int(cfg.get("target_points") or 300)
    return (
        f"Stop {sp} pts abaixo/acima da entrada; alvo {tp} pts (WIN/WDO).",
        f"stop_points={sp}, target_points={tp}",
    )


def _fmt_pct_stops(cfg: dict, stop_mult: float = 1.0, target_mult: float = 1.0) -> tuple[str, str]:
    sl = float(cfg.get("stop_loss_pct") or 2.0) * stop_mult
    tp = float(cfg.get("take_profit_pct") or 3.0) * target_mult
    rr = (tp / sl) if sl > 0 else 0.0
    return (
        f"Stop {sl:.2f}% e alvo {tp:.2f}% em relação à entrada "
        f"(R:R configurado ≈ {rr:.2f}:1).",
        f"stop_loss_pct={sl:.2f}, take_profit_pct={tp:.2f}",
    )


def playbook_breakout(cfg: dict, symbol: str) -> DayTradePlaybook:
    lookback = 12
    exit_rule, exit_params = (
        _fmt_win_stops(cfg) if is_win_symbol(symbol) else _fmt_pct_stops(cfg)
    )
    return DayTradePlaybook(
        strategy_type="breakout",
        title_pt="Rompimento de range (Breakout M1)",
        library_article_ids=[
            "14-tres-pilares-setup",
            "15-breakout-range-stop",
            "17-rr-e-posicao",
            "18-fechar-antes-leilao",
            "05-horarios-pregao-b3",
        ],
        config_fields=[
            "strategy_type",
            "stop_loss_pct",
            "take_profit_pct",
            "stop_points",
            "target_points",
            "risk_per_trade_pct",
            "capital_brl",
            "shares_per_order",
        ],
        pillars=[
            PlaybookPillar(
                stage=PILLAR_CONTEXT,
                label_pt="Filtro de contexto",
                rule_pt="Pregão B3 operável (10h–17h55 BRT), sem leilão; engine respeita cooldown e horário.",
                detail_pt=(
                    f"Range de referência: máxima/mínima dos últimos {lookback} candles M1 "
                    f"(exclui barra em formação)."
                ),
            ),
            PlaybookPillar(
                stage=PILLAR_ENTRY,
                label_pt="Gatilho de entrada",
                rule_pt=(
                    "Compra se o close da penúltima barra M1 romper a máxima do range; "
                    "venda se romper a mínima. Entrada no ask (compra) ou bid (venda)."
                ),
                detail_pt=f"lookback={lookback} · tipo=breakout v1",
            ),
            PlaybookPillar(
                stage=PILLAR_EXIT,
                label_pt="Stop e alvo",
                rule_pt=exit_rule,
                detail_pt=exit_params,
            ),
        ],
    )


def playbook_volatility(cfg: dict, symbol: str, regime: str, atr_pct: float, bb_width: float) -> DayTradePlaybook:
    lookback_base = 12
    stop_mult = target_mult = 1.0
    effective_lb = lookback_base
    if regime == "vol alta":
        effective_lb = lookback_base + 4
        stop_mult, target_mult = 1.45, 1.35
    elif regime == "vol baixa":
        effective_lb = max(6, lookback_base - 2)
        stop_mult, target_mult = 0.75, 0.85

    exit_rule, exit_params = (
        _fmt_win_stops(cfg)
        if is_win_symbol(symbol)
        else _fmt_pct_stops(cfg, stop_mult, target_mult)
    )
    if not is_win_symbol(symbol):
        exit_rule = (
            f"Regime «{regime}»: multiplicadores stop×{stop_mult:.2f}, alvo×{target_mult:.2f}. "
            + exit_rule
        )

    return DayTradePlaybook(
        strategy_type="volatility",
        title_pt="Rompimento adaptativo à volatilidade",
        library_article_ids=[
            "14-tres-pilares-setup",
            "16-volatilidade-atr-stop",
            "03-volatilidade-atr",
            "17-rr-e-posicao",
            "18-fechar-antes-leilao",
            "07-estrategias-sistema",
        ],
        config_fields=[
            "strategy_type",
            "stop_loss_pct",
            "take_profit_pct",
            "stop_points",
            "target_points",
            "risk_per_trade_pct",
            "capital_brl",
        ],
        pillars=[
            PlaybookPillar(
                stage=PILLAR_CONTEXT,
                label_pt="Filtro de contexto",
                rule_pt=(
                    f"Mesmo horário B3 do módulo de risco; regime atual «{regime}» "
                    f"(ATR% {atr_pct:.2f}, BB width {bb_width:.2f}%)."
                ),
                detail_pt="Alta vol exige rompimento mais limpo (buffer + lookback maior).",
            ),
            PlaybookPillar(
                stage=PILLAR_ENTRY,
                label_pt="Gatilho de entrada",
                rule_pt=(
                    "Rompimento da máxima/mínima do range com lookback efetivo ajustado pelo regime; "
                    "buffer extra em vol alta."
                ),
                detail_pt=f"lookback_efetivo={effective_lb} · ATR período 14 · BB período 20",
            ),
            PlaybookPillar(
                stage=PILLAR_EXIT,
                label_pt="Stop e alvo",
                rule_pt=exit_rule,
                detail_pt=exit_params,
            ),
        ],
    )


def get_playbook(
    strategy_type: str,
    cfg: dict,
    symbol: str,
    *,
    regime: str = "vol moderada",
    atr_pct: float = 0.0,
    bb_width_pct: float = 0.0,
) -> DayTradePlaybook:
    st = (strategy_type or "volatility").strip().lower()
    if st == "breakout":
        return playbook_breakout(cfg, symbol)
    return playbook_volatility(cfg, symbol, regime, atr_pct, bb_width_pct)


def _risk_reward(entry: float, stop: float, target: float) -> float | None:
    risk = abs(entry - stop)
    reward = abs(target - entry)
    if risk <= 1e-9:
        return None
    return round(reward / risk, 2)


def _levels_from_config(
    symbol: str,
    cfg: dict,
    side: str,
    entry: float,
    stop_mult: float = 1.0,
    target_mult: float = 1.0,
) -> tuple[float, float]:
    if is_win_symbol(symbol):
        stop_pts = int((cfg.get("stop_points") or 150) * stop_mult)
        target_pts = int((cfg.get("target_points") or 300) * target_mult)
        if side == "BUY":
            return entry - stop_pts, entry + target_pts
        return entry + stop_pts, entry - target_pts
    sl_pct = float(cfg.get("stop_loss_pct") or 2.0) * stop_mult
    tp_pct = float(cfg.get("take_profit_pct") or 3.0) * target_mult
    if side == "BUY":
        return entry * (1 - sl_pct / 100), entry * (1 + tp_pct / 100)
    return entry * (1 + sl_pct / 100), entry * (1 - tp_pct / 100)


def build_example_levels(
    symbol: str,
    cfg: dict,
    bid: float,
    ask: float,
    recommendation: dict,
    active_pack: dict,
    *,
    regime: str = "vol moderada",
) -> dict[str, Any]:
    """Níveis numéricos alinhados ao que o engine calcularia."""
    stop_mult = target_mult = 1.0
    if (cfg.get("strategy_type") or "volatility") == "volatility":
        if regime == "vol alta":
            stop_mult, target_mult = 1.45, 1.35
        elif regime == "vol baixa":
            stop_mult, target_mult = 0.75, 0.85

    levels = active_pack.get("levels") or {}
    range_high = levels.get("range_high")
    range_low = levels.get("range_low")

    if recommendation.get("side") and recommendation.get("entry") is not None:
        entry = float(recommendation["entry"])
        stop = float(recommendation["stop"])
        target = float(recommendation["target"])
        side = recommendation["side"]
        scenario = "sinal_ativo"
        entry_zone = f"{entry:.4f} (mercado)"
    else:
        side = "BUY"
        if range_high is not None:
            entry = float(ask if ask else range_high)
            ref = float(range_high)
            entry_zone = f"Romper máx {ref:.4f} → entrada ~ask {entry:.4f}"
        else:
            entry = float(ask or bid or 0)
            ref = entry
            entry_zone = "Aguardar range M1"
        stop, target = _levels_from_config(symbol, cfg, side, ref if range_high else entry, stop_mult, target_mult)
        if range_high is not None:
            entry = ref
        scenario = "exemplo_compra_pendente"

    rr = _risk_reward(entry, stop, target)
    dist_stop = abs(entry - stop)
    dist_target = abs(target - entry)

    return {
        "scenario": scenario,
        "side": side,
        "entry_zone_pt": entry_zone,
        "entry": round(entry, 4),
        "stop": round(stop, 4),
        "target": round(target, 4),
        "risk_distance": round(dist_stop, 4),
        "reward_distance": round(dist_target, 4),
        "risk_reward_ratio": rr,
        "range_high": range_high,
        "range_low": range_low,
        "aligned_with_engine": bool(recommendation.get("side")),
    }


def build_trade_playbook_section(
    symbol: str,
    cfg: dict,
    bid: float,
    ask: float,
    study: dict,
) -> dict[str, Any]:
    """Monta seção `trade_playbook` para GET /agent/study."""
    active = study.get("active_strategy") or "volatility"
    ind = study.get("indicators") or {}
    rec = study.get("recommendation") or {}
    strategies = study.get("strategies") or {}
    active_pack = strategies.get(active) or {}

    playbook = get_playbook(
        active,
        cfg,
        symbol,
        regime=str(ind.get("regime") or "—"),
        atr_pct=float(ind.get("atr_pct") or 0),
        bb_width_pct=float(ind.get("bb_width_pct") or 0),
    )
    example = build_example_levels(
        symbol,
        cfg,
        bid,
        ask,
        rec,
        active_pack,
        regime=str(ind.get("regime") or "vol moderada"),
    )

    chips = [
        {"key": "filtro", "label": "Filtro", "text": playbook.pillars[0].rule_pt},
        {"key": "entrada", "label": "Entrada", "text": playbook.pillars[1].rule_pt},
        {"key": "stop", "label": "Stop", "text": f"{example['stop']}"},
        {"key": "alvo", "label": "Alvo", "text": f"{example['target']}"},
        {
            "key": "rr",
            "label": "R:R",
            "text": f"{example['risk_reward_ratio']}:1" if example["risk_reward_ratio"] else "—",
        },
    ]

    return {
        "playbook": playbook.to_dict(),
        "example_levels": example,
        "summary_chips": chips,
        "forced_flat_note_pt": (
            "Regra operacional B3: encerrar posições de day trade antes do leilão "
            "(≈17h55 BRT) — ver biblioteca «18-fechar-antes-leilao»."
        ),
    }
