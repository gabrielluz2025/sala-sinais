# Simulação (sem MetaTrader 5)

Use este modo para ver o painel, API e fluxo de sinais **sem** instalar ou abrir o MT5.

## Modos de operação

| `ENGINE_MODE` | O que faz |
|---------------|-----------|
| `simulation` | Preços e candles gerados em `engine/simulator.py`; sinais na API; **nunca** envia ordens |
| `paper_mt5` | MT5 conectado, cotação real; ordens na **demo** com `SIGNAL_MODE=live` + `EXECUTE_ON_DEMO=true` (ver [EXECUCAO_AUTOMATICA.md](EXECUCAO_AUTOMATICA.md)) |
| `live_mt5` | MT5 + ordens quando `LIVE_TRADING=true` e preflight OK |

Se `ENGINE_MODE` não estiver no `.env`, o sistema infere:

- `LIVE_TRADING=true` e `SIGNAL_MODE=live` → `live_mt5`
- Caso contrário → `paper_mt5` (ao usar `Sala-Sinais.bat engine`)

## Rodar só simulação

1. Duplo clique em **`Sala-Sinais.bat`** → opção **2** (API + painel).
2. **`Sala-Sinais.bat`** → opção **4** ou `simulacao` (engine simulado).

No `.env` (padrão do `.env.example`):

```env
ENGINE_MODE=simulation
SIGNAL_MODE=paper
LIVE_TRADING=false
```

Opcional:

- `SIM_SIGNAL_INTERVAL_SEC` — intervalo mínimo entre sinais demo automáticos
- `SIM_BASE_PRICE` — preço inicial (~WIN)
- `SIM_RESPECT_RISK_HOURS=true` — aplica horário de risco como no MT5
- `SIM_DEMO_SIGNALS=false` — desliga sinais demo periódicos (só estratégia)

Dados de exemplo: `data/sample_win_m1.csv` (criado automaticamente se não existir).

## Painel

O badge mostra **SIMULAÇÃO**. Na seção **Conexão** aparecem `data_source=simulation` e MT5 desconectado.

- Se a API não responder, o painel mostra **Offline — rode Sala-Sinais.bat (opção 2)** e verifica `/health` a cada 5 segundos.
- **Engine online** quando o heartbeat do engine chegou nos últimos 60 segundos (`engine_online` em `/system/state`).
- Use **Configurar agente** para escolher ações B3 (PETR4, VALE3, …), capital, stop/alvo % e quantidade antes de rodar a simulação. Detalhes: **[ACOES_BR.md](ACOES_BR.md)**.

**Treino em simulação** = ajustar parâmetros e rodar o engine simulado; não há aprendizado automático (ML) nesta versão.

## Ganhos e perdas no painel

A seção **Ganhos e perdas** consome `GET /metrics/pnl` (atualização automática a cada 20s). Trades **fechados** entram no resultado quando há `exit_price` (via engine ou `PATCH /signals/{id}`); lucro/prejuízo líquido desconta taxas configuradas em `.env` (`B3_FEE_*`, corretagem). Posições **abertas** mostram estimativa mark-to-market com a última cotação em `data/last_quote.json` / `quote_history.json` até você registrar a saída.

**Evolução do patrimônio** usa `GET /metrics/equity-curve` no mesmo ciclo de 20s: parte do **capital inicial** em *Configurar agente* (`capital_brl`) e soma o PnL líquido das operações fechadas por dia (ordenadas por `closed_at` ou `created_at`). O gráfico mostra patrimônio estimado, drawdown % e KPIs (atual, máximo, mínimo, variação %). O último ponto pode incluir mark-to-market de posições abertas; não há tabela `equity_snapshots` — a série é calculada na hora a partir dos sinais.

## Passar para tempo real

1. **Paper MT5** — MT5 demo aberto, no `.env`:
   - `ENGINE_MODE=paper_mt5`
   - `SIGNAL_MODE=paper`
   - `LIVE_TRADING=false`
   - Execute **`Sala-Sinais.bat`** opção **3** ou `engine`.

2. **Ao vivo** — leia **[MODO_REAL.md](MODO_REAL.md)**, rode preflight, depois:
   - `ENGINE_MODE=live_mt5` (ou omita e use `SIGNAL_MODE=live` + `LIVE_TRADING=true`)
   - **`Sala-Sinais.bat`** opção **6 → b** ou `real` antes de ligar ordens.

## Aprendizado 24h (overnight)

Para deixar o sistema **rodando à noite** ou no fim de semana — sinais simulados, passagens de `GET /agent/study` na watchlist e stats da biblioteca — **sem** exigir MetaTrader 5:

1. **`Sala-Sinais.bat`** → opção **7** (ou `Sala-Sinais.bat aprendizado`).
2. Ou no `.env`:

```env
OVERNIGHT_LEARNING=true
ENGINE_MODE=simulation
SIGNAL_MODE=paper
AUTO_EXECUTE_ORDERS=false
B3_IGNORE_SESSION_HOURS=true
SIM_RESPECT_RISK_HOURS=false
```

Com `OVERNIGHT_LEARNING=true`, o engine usa sempre o loop de **simulação** (ignora `ENGINE_MODE=paper_mt5` no arquivo). No painel, `GET /system/execution-status` traz `overnight_learning: true`.

| Roda 24h | Não roda neste modo |
|----------|---------------------|
| Heartbeat, estratégia sim, sinais `paper`, estudo por símbolo (`OVERNIGHT_STUDY_INTERVAL_SEC`, padrão 300s), PnL sim (`SimPositionTracker`) | Ordens demo/reais no MT5 |

Para **paper_mt5** com cotação real, desligue `OVERNIGHT_LEARNING` e use opção **1** ou **3** com [EXECUCAO_AUTOMATICA.md](EXECUCAO_AUTOMATICA.md).

A simulação **nunca** altera `LIVE_TRADING` nem envia ordens ao MT5.
