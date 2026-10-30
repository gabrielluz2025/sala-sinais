from __future__ import annotations

import json
from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy.orm import Session

from api.database import AgentConfigRow

TZ_BR = ZoneInfo("America/Sao_Paulo")
_CONFIG_ID = 1

DEFAULT_SYMBOLS = ["PETR4", "VALE3"]

PRESET_NAMES = ("moderado", "conservador", "agressivo")

AGENT_PRESETS: dict[str, dict] = {
    "moderado": {
        "id": "moderado",
        "label": "Moderado (recomendado)",
        "description_pt": (
            "Equilíbrio para iniciantes: PETR4 e VALE3, 1% de risco por trade, "
            "stop 2% e alvo 3%, estratégia de volatilidade em ações BR."
        ),
        "symbols": ["PETR4", "VALE3"],
        "active_symbol": "PETR4",
        "rotate_symbols": False,
        "capital_brl": 10000.0,
        "risk_per_trade_pct": 1.0,
        "max_position_brl": 2000.0,
        "shares_per_order": 100,
        "stop_loss_pct": 2.0,
        "take_profit_pct": 3.0,
        "stop_points": 80,
        "target_points": 120,
        "asset_class": "acoes",
        "strategy_type": "volatility",
        "use_news_filter": True,
    },
    "conservador": {
        "id": "conservador",
        "label": "Conservador",
        "description_pt": (
            "Menos exposição: foco em PETR4, 0,5% de risco, stops um pouco mais largos "
            "e alvos menores — prioriza preservar capital na simulação."
        ),
        "symbols": ["PETR4"],
        "active_symbol": "PETR4",
        "rotate_symbols": False,
        "capital_brl": 10000.0,
        "risk_per_trade_pct": 0.5,
        "max_position_brl": 1500.0,
        "shares_per_order": 100,
        "stop_loss_pct": 2.5,
        "take_profit_pct": 2.0,
        "stop_points": 90,
        "target_points": 100,
        "asset_class": "acoes",
        "strategy_type": "volatility",
        "use_news_filter": True,
    },
    "agressivo": {
        "id": "agressivo",
        "label": "Agressivo",
        "description_pt": (
            "Mais trades e risco: três blue chips, 2% de risco, rotação de tickers, "
            "alvos maiores — só para quem já entende o painel e a simulação."
        ),
        "symbols": ["PETR4", "VALE3", "ITUB4"],
        "active_symbol": "PETR4",
        "rotate_symbols": True,
        "capital_brl": 10000.0,
        "risk_per_trade_pct": 2.0,
        "max_position_brl": 3000.0,
        "shares_per_order": 200,
        "stop_loss_pct": 1.5,
        "take_profit_pct": 4.0,
        "stop_points": 70,
        "target_points": 140,
        "asset_class": "acoes",
        "strategy_type": "volatility",
        "use_news_filter": True,
    },
}

BR_STOCK_PRESETS = [
    "PETR4",
    "VALE3",
    "ITUB4",
    "BBDC4",
    "ABEV3",
    "MGLU3",
    "WEGE3",
    "RENT3",
    "BBAS3",
    "SUZB3",
    "GGBR4",
    "RADL3",
    "B3SA3",
    "KLBN11",
    "PRIO3",
    "RAIL3",
    "CSAN3",
    "VIVT3",
    "LREN3",
    "HAPV3",
]


def _now_iso() -> str:
    return datetime.now(TZ_BR).isoformat()


def recommended_defaults() -> dict:
    return dict(AGENT_PRESETS["moderado"])


def _default_row() -> AgentConfigRow:
    d = recommended_defaults()
    return AgentConfigRow(
        id=_CONFIG_ID,
        symbols_json=json.dumps(d["symbols"], ensure_ascii=False),
        active_symbol=d["active_symbol"],
        rotate_symbols=d["rotate_symbols"],
        capital_brl=d["capital_brl"],
        risk_per_trade_pct=d["risk_per_trade_pct"],
        max_position_brl=d["max_position_brl"],
        shares_per_order=d["shares_per_order"],
        stop_loss_pct=d["stop_loss_pct"],
        take_profit_pct=d["take_profit_pct"],
        stop_points=d["stop_points"],
        target_points=d["target_points"],
        asset_class=d["asset_class"],
        strategy_type=d["strategy_type"],
        use_news_filter=d.get("use_news_filter", True),
        applied_preset="moderado",
        updated_at=_now_iso(),
    )


def merge_row_defaults(row: AgentConfigRow) -> bool:
    """Preenche campos ausentes com defaults recomendados; retorna True se alterou."""
    defaults = _default_row()
    changed = False

    def _set(attr: str, value) -> None:
        nonlocal changed
        current = getattr(row, attr, None)
        if current is None or (isinstance(current, str) and not str(current).strip()):
            setattr(row, attr, value)
            changed = True

    _set("symbols_json", defaults.symbols_json)
    _set("active_symbol", defaults.active_symbol)
    if row.capital_brl is None or row.capital_brl <= 0:
        row.capital_brl = defaults.capital_brl
        changed = True
    if row.risk_per_trade_pct is None or row.risk_per_trade_pct <= 0:
        row.risk_per_trade_pct = defaults.risk_per_trade_pct
        changed = True
    if row.max_position_brl is None or row.max_position_brl <= 0:
        row.max_position_brl = defaults.max_position_brl
        changed = True
    if not row.shares_per_order:
        row.shares_per_order = defaults.shares_per_order
        changed = True
    if row.stop_loss_pct is None or row.stop_loss_pct <= 0:
        row.stop_loss_pct = defaults.stop_loss_pct
        changed = True
    if row.take_profit_pct is None or row.take_profit_pct <= 0:
        row.take_profit_pct = defaults.take_profit_pct
        changed = True
    if not row.stop_points:
        row.stop_points = defaults.stop_points
        changed = True
    if not row.target_points:
        row.target_points = defaults.target_points
        changed = True
    _set("asset_class", defaults.asset_class)
    _set("strategy_type", defaults.strategy_type)
    if getattr(row, "use_news_filter", None) is None:
        row.use_news_filter = True
        changed = True
    return changed


def list_presets_public() -> list[dict]:
    return [
        {
            "id": p["id"],
            "label": p["label"],
            "description_pt": p["description_pt"],
        }
        for p in AGENT_PRESETS.values()
    ]


def apply_preset_to_row(row: AgentConfigRow, name: str) -> None:
    key = name.strip().lower()
    if key not in AGENT_PRESETS:
        raise HTTPException(422, f"Preset inválido — use: {', '.join(PRESET_NAMES)}")
    p = AGENT_PRESETS[key]
    row.symbols_json = json.dumps(p["symbols"], ensure_ascii=False)
    row.active_symbol = p["active_symbol"]
    row.rotate_symbols = p["rotate_symbols"]
    row.capital_brl = float(p["capital_brl"])
    row.risk_per_trade_pct = float(p["risk_per_trade_pct"])
    row.max_position_brl = float(p["max_position_brl"])
    row.shares_per_order = int(p["shares_per_order"])
    row.stop_loss_pct = float(p["stop_loss_pct"])
    row.take_profit_pct = float(p["take_profit_pct"])
    row.stop_points = int(p["stop_points"])
    row.target_points = int(p["target_points"])
    row.asset_class = p["asset_class"]
    row.strategy_type = p["strategy_type"]
    row.use_news_filter = bool(p.get("use_news_filter", True))
    row.applied_preset = key
    row.updated_at = _now_iso()


def get_or_create_config(db: Session) -> AgentConfigRow:
    row = db.get(AgentConfigRow, _CONFIG_ID)
    if row is None:
        row = _default_row()
        db.add(row)
        db.commit()
        db.refresh(row)
        return row
    if merge_row_defaults(row):
        row.updated_at = _now_iso()
        db.commit()
        db.refresh(row)
    return row


def _parse_symbols(raw: str) -> list[str]:
    try:
        data = json.loads(raw)
        if not isinstance(data, list):
            return list(DEFAULT_SYMBOLS)
        return [str(s).strip().upper() for s in data if str(s).strip()]
    except json.JSONDecodeError:
        return list(DEFAULT_SYMBOLS)


def config_to_dict(row: AgentConfigRow) -> dict:
    symbols = _parse_symbols(row.symbols_json)
    return {
        "symbols": symbols,
        "active_symbol": row.active_symbol,
        "rotate_symbols": row.rotate_symbols,
        "capital_brl": row.capital_brl,
        "risk_per_trade_pct": row.risk_per_trade_pct,
        "max_position_brl": row.max_position_brl,
        "shares_per_order": row.shares_per_order,
        "stop_loss_pct": row.stop_loss_pct,
        "take_profit_pct": row.take_profit_pct,
        "stop_points": row.stop_points,
        "target_points": row.target_points,
        "asset_class": row.asset_class,
        "strategy_type": getattr(row, "strategy_type", None) or "volatility",
        "use_news_filter": bool(getattr(row, "use_news_filter", True)),
        "applied_preset": getattr(row, "applied_preset", None),
        "recommended_defaults_active": (getattr(row, "applied_preset", None) or "moderado")
        == "moderado",
        "updated_at": row.updated_at,
        "presets": BR_STOCK_PRESETS,
    }


def _validate_patch(body: dict, asset_class: str) -> None:
    shares = body.get("shares_per_order")
    if shares is not None and asset_class in ("acoes", "mixed"):
        if int(shares) < 100 or int(shares) % 100 != 0:
            raise HTTPException(
                422,
                "shares_per_order deve ser múltiplo de 100 (lote B3) para ações",
            )
    symbols = body.get("symbols")
    if symbols is not None:
        if not symbols:
            raise HTTPException(422, "Informe ao menos um símbolo")
        for s in symbols:
            t = str(s).strip().upper()
            if len(t) < 4 or len(t) > 12:
                raise HTTPException(422, f"Símbolo inválido: {s}")


def apply_config_patch(row: AgentConfigRow, patch: dict) -> None:
    asset_class = patch.get("asset_class") or row.asset_class or "acoes"
    _validate_patch(patch, asset_class)

    if patch.get("symbols") is not None:
        syms = [str(s).strip().upper() for s in patch["symbols"]]
        row.symbols_json = json.dumps(syms, ensure_ascii=False)
        if row.active_symbol and row.active_symbol not in syms:
            row.active_symbol = syms[0]
    if patch.get("active_symbol") is not None:
        row.active_symbol = patch["active_symbol"].strip().upper() if patch["active_symbol"] else None
    if patch.get("rotate_symbols") is not None:
        row.rotate_symbols = bool(patch["rotate_symbols"])
    if patch.get("capital_brl") is not None:
        row.capital_brl = float(patch["capital_brl"])
    if patch.get("risk_per_trade_pct") is not None:
        row.risk_per_trade_pct = float(patch["risk_per_trade_pct"])
    if patch.get("max_position_brl") is not None:
        row.max_position_brl = float(patch["max_position_brl"])
    if patch.get("shares_per_order") is not None:
        row.shares_per_order = int(patch["shares_per_order"])
    if patch.get("stop_loss_pct") is not None:
        row.stop_loss_pct = float(patch["stop_loss_pct"])
    if patch.get("take_profit_pct") is not None:
        row.take_profit_pct = float(patch["take_profit_pct"])
    if patch.get("stop_points") is not None:
        row.stop_points = int(patch["stop_points"])
    if patch.get("target_points") is not None:
        row.target_points = int(patch["target_points"])
    if patch.get("asset_class") is not None:
        ac = patch["asset_class"].strip().lower()
        if ac not in ("acoes", "win", "mixed"):
            raise HTTPException(422, "asset_class deve ser acoes, win ou mixed")
        row.asset_class = ac
    if patch.get("strategy_type") is not None:
        st = patch["strategy_type"].strip().lower()
        if st not in ("breakout", "volatility"):
            raise HTTPException(422, "strategy_type deve ser breakout ou volatility")
        row.strategy_type = st
    if patch.get("use_news_filter") is not None:
        row.use_news_filter = bool(patch["use_news_filter"])

    row.updated_at = _now_iso()
