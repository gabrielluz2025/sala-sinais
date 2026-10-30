import { api, type AgentConfig, type AgentStudyResponse } from "../api/client";

function sessionFallback(): AgentStudyResponse["session"] {
  const now = new Date();
  return {
    now_brt: now.toLocaleTimeString("pt-BR"),
    date_brt: now.toISOString().slice(0, 10),
    phase: "unknown",
    phase_label: "Estudo parcial — reinicie a API se persistir",
    in_session_window: true,
    engine_may_trade: true,
    engine_block_reason: null,
    trade_hours: "10:00–17:00",
  };
}

function buildPartialStudy(symbol: string, cfg: AgentConfig, series: Awaited<ReturnType<typeof api.strategySeries>>): AgentStudyResponse {
  const st = (cfg.strategy_type || "volatility") as "breakout" | "volatility";
  const contracts = cfg.shares_per_order ?? 100;
  const reason =
    `Regime ${series.regime} · ATR ${series.atr_pct_last}%. ` +
    `Atualize a API (feche e abra "Sala de Sinais - API") para estudo completo com horário B3 e proposta de ordem.`;
  const emptyStrat = {
    strategy_type: st,
    signal_ready: false,
    side: null,
    entry: null,
    stop: null,
    target: null,
    contracts,
    entry_reason: reason,
    levels: {},
  };
  return {
    symbol: symbol.toUpperCase(),
    market: { bid: 0, ask: 0, mid: 0 },
    session: sessionFallback(),
    indicators: {
      atr_pct: series.atr_pct_last,
      bb_width_pct: 0,
      regime: series.regime,
      regime_score: series.regime_score,
    },
    active_strategy: st,
    sizing: {
      contracts,
      label: `${contracts} ações/lote`,
      risk_per_trade_pct: cfg.risk_per_trade_pct,
      capital_brl: cfg.capital_brl,
      stop_loss_pct: cfg.stop_loss_pct,
      take_profit_pct: cfg.take_profit_pct,
    },
    strategies: { breakout: { ...emptyStrat, strategy_type: "breakout" }, volatility: { ...emptyStrat, strategy_type: "volatility" } },
    recommendation: {
      action: "wait",
      action_label: "Aguardando estudo completo da API",
      strategy_type: st,
      side: null,
      entry: null,
      stop: null,
      target: null,
      contracts,
      entry_reason: reason,
      alternative_note: null,
    },
    last_order: null,
    candle_patterns: {
      timeframe: "M5",
      engine: "partial",
      bars_analyzed: 0,
      hits: [],
      last_bar: null,
      summary_pt: "Padrões de candle disponíveis após reiniciar a API.",
    },
  };
}

export async function loadAgentStudy(
  symbol: string,
): Promise<{ study: AgentStudyResponse | null; notice: string | null }> {
  try {
    const study = await api.agentStudy(symbol);
    return { study, notice: null };
  } catch (err) {
    const detail = err instanceof Error ? err.message : String(err);
    try {
      const [cfg, series] = await Promise.all([api.agentConfig(), api.strategySeries(symbol, "M5", 100)]);
      return {
        study: buildPartialStudy(symbol, cfg, series),
        notice: `Estudo completo indisponível (${detail}). Reinicie a janela «Sala de Sinais - API» (Sala-Sinais.bat opção 1 ou 2).`,
      };
    } catch {
      return { study: null, notice: `Estudo indisponível: ${detail}` };
    }
  }
}

export function applyStrategyBadge(cfg: AgentConfig | null, study: AgentStudyResponse | null): void {
  const badge = document.getElementById("deck-strategy-badge");
  if (!badge) return;
  const st = study?.active_strategy || cfg?.strategy_type || "volatility";
  badge.textContent = st === "breakout" ? "Breakout" : "Volatilidade";
  badge.classList.toggle("deck-badge-breakout", st === "breakout");
}
