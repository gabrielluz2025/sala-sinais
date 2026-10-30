"""Estudo ao vivo: estratégia, horário B3, tamanho e setup de entrada/saída."""

from __future__ import annotations

from datetime import datetime, time
from zoneinfo import ZoneInfo

import numpy as np

from api.agent_config import config_to_dict, get_or_create_config
from api.database import SessionLocal, SignalRow
from api.candle_patterns import get_candle_patterns
from api.market_structure import get_market_structure
from api.market_ohlc import load_m1_bars
from api.strategy_series import BB_PERIOD, _atr_percent_last, _bb_series, _vol_regime
from engine.agent_runtime import contracts_for_config, is_win_symbol
from engine.config import settings
from engine.risk import RiskManager
from engine.strategy import BreakoutStrategy
from engine.strategy_volatility import VolatilityAdaptiveStrategy
from shared.daytrade_rules import build_trade_playbook_section
from shared.schemas import SignalMode

TZ_BR = ZoneInfo("America/Sao_Paulo")

# Dados estáticos (listagem B3) — o estudo numérico usa todo o histórico em disco.
SYMBOL_FUNDAMENTALS: dict[str, dict] = {
    "PETR4": {
        "name": "Petrobras PN",
        "listed_b3": "1997-08-05",
        "sector": "Petróleo e gás",
        "note": "PN negociada na B3; histórico longo e alta liquidez no índice.",
    },
    "WEGE3": {
        "name": "WEG ON",
        "listed_b3": "1993-06-29",
        "sector": "Bens industriais",
        "note": "Ação de crescimento; volatilidade moderada vs commodities.",
    },
    "VALE3": {
        "name": "Vale ON",
        "listed_b3": "2000-06-29",
        "sector": "Mineração",
        "note": "Correlacionada a commodities; pregões com gaps em notícias globais.",
    },
    "ITUB4": {
        "name": "Itaú PN",
        "listed_b3": "1995-11-22",
        "sector": "Financeiro",
        "note": "Liquidez elevada; range intraday costuma ser mais estreito que small caps.",
    },
}


def _bar_dt_utc(ts: int) -> datetime:
    return datetime.fromtimestamp(ts, tz=ZoneInfo("UTC"))


def _bar_dt_brt(ts: int) -> datetime:
    return datetime.fromtimestamp(ts, tz=TZ_BR)


def _history_profile(symbol: str, m1_bars: list[dict]) -> dict:
    sym = symbol.upper()
    meta = SYMBOL_FUNDAMENTALS.get(sym, {})
    if not m1_bars:
        return {
            "has_data": False,
            "message": "Sem barras M1 salvas — engine/API precisam acumular cotações.",
            "fundamentals": meta or None,
        }

    first_ts = int(m1_bars[0]["time"])
    last_ts = int(m1_bars[-1]["time"])
    first_brt = _bar_dt_brt(first_ts)
    last_brt = _bar_dt_brt(last_ts)
    span_days = max(1, (last_brt.date() - first_brt.date()).days + 1)

    closes = np.array([float(b["close"]) for b in m1_bars], dtype=float)
    lows = np.array([float(b["low"]) for b in m1_bars], dtype=float)
    highs = np.array([float(b["high"]) for b in m1_bars], dtype=float)
    first_close = float(closes[0])
    last_close = float(closes[-1])
    ret_pct = ((last_close - first_close) / first_close * 100.0) if first_close > 0 else 0.0

    today = _now_brt().date()
    today_bars = [b for b in m1_bars if _bar_dt_brt(int(b["time"])).date() == today]
    session_open = None
    session_high = None
    session_low = None
    session_close = None
    session_bars = 0
    if today_bars:
        pregão = [b for b in today_bars if _bar_dt_brt(int(b["time"])).time() >= time(10, 0)]
        use = pregão if pregão else today_bars
        session_bars = len(use)
        session_open = float(use[0]["open"])
        session_high = float(max(float(b["high"]) for b in use))
        session_low = float(min(float(b["low"]) for b in use))
        session_close = float(use[-1]["close"])

    daily_rets: list[float] = []
    by_day: dict = {}
    for b in m1_bars:
        d = _bar_dt_brt(int(b["time"])).date()
        by_day[d] = float(b["close"])
    days_sorted = sorted(by_day.keys())
    for i in range(1, len(days_sorted)):
        p0, p1 = by_day[days_sorted[i - 1]], by_day[days_sorted[i]]
        if p0 > 0:
            daily_rets.append((p1 - p0) / p0 * 100.0)
    vol_daily_pct = float(np.std(daily_rets)) if len(daily_rets) >= 2 else 0.0

    narrative_parts = [
        f"Histórico em disco: {len(m1_bars)} barras M1 "
        f"({first_brt.strftime('%d/%m/%Y %H:%M')} → {last_brt.strftime('%d/%m/%Y %H:%M')}, ~{span_days} dias).",
        f"No período: mín {float(np.min(lows)):.2f}, máx {float(np.max(highs)):.2f}, "
        f"variação {ret_pct:+.2f}% (primeiro → último close).",
    ]
    if meta.get("listed_b3"):
        narrative_parts.insert(
            0,
            f"{meta.get('name', sym)} listada na B3 desde {meta['listed_b3']} "
            f"({meta.get('sector', '—')}). Análise técnica abaixo usa só o histórico disponível no sistema.",
        )
    if session_open is not None:
        narrative_parts.append(
            f"Hoje ({today.strftime('%d/%m/%Y')}): abertura pregão ~{session_open:.2f}, "
            f"faixa {session_low:.2f}–{session_high:.2f}, último {session_close:.2f} ({session_bars} barras M1).",
        )

    return {
        "has_data": True,
        "m1_bars_count": len(m1_bars),
        "first_brt": first_brt.isoformat(),
        "last_brt": last_brt.isoformat(),
        "span_days": span_days,
        "period_low": round(float(np.min(lows)), 4),
        "period_high": round(float(np.max(highs)), 4),
        "period_return_pct": round(ret_pct, 3),
        "vol_daily_pct": round(vol_daily_pct, 3),
        "today_session": {
            "open": round(session_open, 4) if session_open is not None else None,
            "high": round(session_high, 4) if session_high is not None else None,
            "low": round(session_low, 4) if session_low is not None else None,
            "close": round(session_close, 4) if session_close is not None else None,
            "m1_bars": session_bars,
        },
        "fundamentals": meta or None,
        "narrative": " ".join(narrative_parts),
    }


def _now_brt() -> datetime:
    return datetime.now(TZ_BR)


def _session_info(now: datetime | None = None) -> dict:
    now = now or _now_brt()
    t = now.time()
    wd = now.weekday()
    if wd >= 5:
        phase = "fim_de_semana"
        label = "Mercado fechado (fim de semana)"
        can = False
    elif t < time(9, 0):
        phase = "antes_pre"
        label = "Antes do pré-mercado"
        can = False
    elif time(9, 0) <= t < time(10, 0):
        phase = "pre"
        label = "Pré-mercado (sem day trade pleno)"
        can = False
    elif time(10, 0) <= t < time(17, 55):
        phase = "pregao"
        label = "Pregão — janela operacional"
        can = True
    elif time(17, 55) <= t < time(18, 0):
        phase = "leilao_fechamento"
        label = "Leilão de fechamento"
        can = False
    else:
        phase = "pos"
        label = "Pós-fechamento"
        can = False

    rm = RiskManager()
    risk_ok, risk_msg = rm.can_trade(now)
    return {
        "now_brt": now.strftime("%H:%M:%S"),
        "date_brt": now.strftime("%Y-%m-%d"),
        "phase": phase,
        "phase_label": label,
        "in_session_window": can,
        "engine_may_trade": risk_ok,
        "engine_block_reason": risk_msg if not risk_ok else None,
        "trade_hours": f"{settings.trade_start_hour}:00–{settings.trade_end_hour}:00",
    }


def _rates_from_bars(bars: list[dict]) -> dict:
    if not bars:
        return {"high": np.array([]), "low": np.array([]), "close": np.array([])}
    return {
        "high": np.array([float(b["high"]) for b in bars], dtype=float),
        "low": np.array([float(b["low"]) for b in bars], dtype=float),
        "close": np.array([float(b["close"]) for b in bars], dtype=float),
    }


def _breakout_levels(rates: dict, lookback: int) -> dict:
    closes = rates["close"]
    if len(closes) < lookback + 2:
        return {"ready": False, "message": "Poucas barras M1 para calcular range"}
    highs = rates["high"][-(lookback + 1) : -1]
    lows = rates["low"][-(lookback + 1) : -1]
    range_high = float(np.max(highs))
    range_low = float(np.min(lows))
    last_close = float(closes[-2])
    return {
        "lookback": lookback,
        "range_high": round(range_high, 4),
        "range_low": round(range_low, 4),
        "last_close": round(last_close, 4),
        "dist_to_buy_pct": round(((range_high - last_close) / last_close) * 100, 3) if last_close else None,
        "dist_to_sell_pct": round(((last_close - range_low) / last_close) * 100, 3) if last_close else None,
    }


def _sizing_label(symbol: str, contracts: int) -> str:
    if is_win_symbol(symbol):
        return f"{contracts} contrato(s) WIN/WDO"
    return f"{contracts} ações (lote {contracts})"


def _evaluate_study(symbol: str, cfg: dict, bid: float, ask: float) -> dict:
    bars = load_m1_bars(symbol)
    rates = _rates_from_bars(bars)
    mid = (bid + ask) / 2.0 if bid and ask else float(bars[-1]["close"]) if bars else 0.0

    closes = rates["close"]
    atr_pct = _atr_percent_last(bars) if bars else 0.0
    bb_width = 0.0
    regime = "—"
    regime_score = 0.0
    if len(closes) >= BB_PERIOD:
        upper, mid_bb, lower = _bb_series(closes)
        if mid_bb[-1] is not None and upper[-1] is not None and lower[-1] is not None:
            m = mid_bb[-1]
            bb_width = ((upper[-1] - lower[-1]) / m) * 100.0 if m > 0 else 0.0
        regime, regime_score = _vol_regime(atr_pct, bb_width)

    active = (cfg.get("strategy_type") or "volatility").strip().lower()
    if active not in ("breakout", "volatility"):
        active = "volatility"

    breakout = BreakoutStrategy()
    vol_strat = VolatilityAdaptiveStrategy()
    br_result = breakout.evaluate(symbol, rates, bid, ask, SignalMode.PAPER, cfg)
    vol_result = vol_strat.evaluate(symbol, rates, bid, ask, SignalMode.PAPER, cfg)

    br_levels = _breakout_levels(rates, breakout.LOOKBACK)
    vol_levels = _breakout_levels(rates, vol_strat.LOOKBACK)

    contracts = contracts_for_config(cfg, symbol)
    sizing = {
        "contracts": contracts,
        "label": _sizing_label(symbol, contracts),
        "risk_per_trade_pct": cfg.get("risk_per_trade_pct"),
        "capital_brl": cfg.get("capital_brl"),
        "stop_loss_pct": cfg.get("stop_loss_pct"),
        "take_profit_pct": cfg.get("take_profit_pct"),
        "stop_points": cfg.get("stop_points"),
        "target_points": cfg.get("target_points"),
    }

    def pack_result(name: str, result, levels: dict) -> dict:
        if result is not None:
            p = result.payload
            side = p.side.value if hasattr(p.side, "value") else str(p.side)
            return {
                "strategy_type": name,
                "signal_ready": True,
                "side": side,
                "entry": p.entry,
                "stop": p.stop,
                "target": p.target,
                "contracts": p.contracts,
                "entry_reason": result.entry_reason,
                "regime": result.regime,
                "levels": levels,
            }
        msg = (
            f"Sem rompimento — close {levels.get('last_close', '—')} entre "
            f"mín {levels.get('range_low', '—')} e máx {levels.get('range_high', '—')}"
        )
        if levels.get("dist_to_buy_pct") is not None:
            msg += (
                f". Compra se romper máx (+{levels['dist_to_buy_pct']:.2f}%); "
                f"venda se romper mín (-{levels['dist_to_sell_pct']:.2f}%)"
            )
        return {
            "strategy_type": name,
            "signal_ready": False,
            "side": None,
            "entry": None,
            "stop": None,
            "target": None,
            "contracts": contracts,
            "entry_reason": msg,
            "regime": regime if name == "volatility" else None,
            "levels": levels,
        }

    strategies = {
        "breakout": pack_result("breakout", br_result, br_levels),
        "volatility": pack_result("volatility", vol_result, vol_levels),
    }

    rec = strategies.get(active) or strategies["volatility"]
    if rec["signal_ready"]:
        action = "enter_buy" if rec["side"] == "BUY" else "enter_sell"
        action_label = "Entrada recomendada (compra)" if rec["side"] == "BUY" else "Entrada recomendada (venda)"
    else:
        action = "wait"
        action_label = "Aguardar setup — sem rompimento"

    alt = strategies["volatility" if active == "breakout" else "breakout"]
    alt_note = None
    if alt["signal_ready"] and not rec["signal_ready"]:
        alt_note = f"A estratégia alternativa ({alt['strategy_type']}) teria sinal {alt['side']}."

    return {
        "symbol": symbol.upper(),
        "market": {"bid": bid, "ask": ask, "mid": round(mid, 4)},
        "indicators": {
            "atr_pct": round(atr_pct, 4),
            "bb_width_pct": round(bb_width, 3),
            "regime": regime,
            "regime_score": round(regime_score, 3),
        },
        "active_strategy": active,
        "sizing": sizing,
        "strategies": strategies,
        "recommendation": {
            "action": action,
            "action_label": action_label,
            "strategy_type": active,
            "side": rec.get("side"),
            "entry": rec.get("entry"),
            "stop": rec.get("stop"),
            "target": rec.get("target"),
            "contracts": rec.get("contracts"),
            "entry_reason": rec.get("entry_reason"),
            "alternative_note": alt_note,
        },
    }


def _last_signal_row(symbol: str) -> dict | None:
    db = SessionLocal()
    try:
        row = (
            db.query(SignalRow)
            .filter(SignalRow.symbol == symbol.upper())
            .order_by(SignalRow.id.desc())
            .first()
        )
        if not row:
            return None
        demo = "demo" in (row.entry_reason or "").lower() or "demo" in (row.note or "").lower()
        return {
            "id": row.id,
            "side": row.side,
            "entry": row.entry,
            "stop": row.stop,
            "target": row.target,
            "contracts": row.contracts,
            "status": row.status,
            "strategy_type": row.strategy_type,
            "regime": row.regime,
            "entry_reason": row.entry_reason or row.note,
            "created_at": row.created_at,
            "is_demo": demo,
        }
    finally:
        db.close()


def get_agent_study(symbol: str, bid: float | None, ask: float | None) -> dict:
    sym = symbol.upper()
    db = SessionLocal()
    try:
        cfg = config_to_dict(get_or_create_config(db))
    finally:
        db.close()
    if bid is None or ask is None or (bid == 0 and ask == 0):
        bid = ask = 0.0
    bars = load_m1_bars(sym)
    if bars and (bid == 0 or ask == 0):
        c = float(bars[-1]["close"])
        spread = max(0.01, c * 0.0002)
        bid = c - spread / 2
        ask = c + spread / 2
    study = _evaluate_study(sym, cfg, float(bid), float(ask))
    study["trade_playbook"] = build_trade_playbook_section(
        sym, cfg, float(bid), float(ask), study
    )
    study["session"] = _session_info()
    study["history"] = _history_profile(sym, bars)
    study["last_order"] = _last_signal_row(sym)
    try:
        study["candle_patterns"] = get_candle_patterns(sym, tf="M5", limit=80, lookback=24)
    except Exception:
        study["candle_patterns"] = {
            "timeframe": "M5",
            "engine": "unavailable",
            "bars_analyzed": 0,
            "hits": [],
            "last_bar": None,
            "summary_pt": "Análise de candles indisponível no momento.",
        }
    try:
        ms = get_market_structure(sym, tf="M5", limit=200)
        study["market_structure"] = {
            "narrative_pt": ms.get("narrative_pt"),
            "trend_bias": ms.get("trend_bias"),
            "choch": ms.get("choch"),
        }
    except Exception:
        study["market_structure"] = None
    _attach_performance_learning(study, cfg)
    return study


def _attach_performance_learning(study: dict, cfg: dict) -> None:
    db = SessionLocal()
    try:
        from api.trade_learning import build_performance_learning
        from shared.trade_learning import generate_insights_pt

        perf = build_performance_learning(db)
        insights = generate_insights_pt(perf)
        study["performance_learning"] = {
            "trade_count": perf.get("trade_count"),
            "rolling": perf.get("rolling"),
            "best_strategy": perf.get("best_strategy"),
            "worst_strategy": perf.get("worst_strategy"),
            "soft_guards": perf.get("soft_guards"),
            "last_insight": insights[0] if insights else None,
            "insights_pt": insights[:4],
        }
        guards = perf.get("soft_guards") or {}
        factor = float(guards.get("qty_factor") or 1.0)
        if factor < 1.0 and study.get("sizing"):
            c0 = int(study["sizing"].get("contracts") or 1)
            c1 = max(1, int(c0 * factor))
            study["sizing"]["contracts"] = c1
            study["sizing"]["learning_qty_note"] = (
                "Tamanho sugerido reduzido pelo aprendizado com trades (não altera boleta manual)."
            )
            rec = study.get("recommendation")
            if isinstance(rec, dict) and rec.get("contracts"):
                rec["contracts"] = c1
    except Exception:
        study["performance_learning"] = None
    finally:
        db.close()
