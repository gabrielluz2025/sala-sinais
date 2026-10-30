# Aprendizado com trades (Fase 1)

Camada **estatística** sobre trades **fechados** no SQLite — complementa a biblioteca manual e o estudo ao vivo (`GET /agent/study`).

## O que aprende

| Fonte | O quê |
|-------|--------|
| SQLite `signals` | PnL realizado, win/loss, `strategy_type`, `entry_reason`, duração, faixa horária BRT |
| Agregados | Win rate por estratégia, por ativo, janela rolling (20), expectativa (avg win / avg loss) |
| Insights PT | Frases curtas em `data/trade_learning.json` + `GET /library/learning-insights` |

**Não é** rede neural nem RAG automático — são contadores e regras conservadoras.

## Biblioteca vs trades

| | Biblioteca (`library/`) | Trade learning |
|--|-------------------------|----------------|
| Conteúdo | Artigos curados, pedagogy | Resultado das **suas** operações fechadas |
| Atualização | Manual / import ZIP | Automática ao fechar trade + passagem noturna |
| Efeito no motor | Nível de conhecimento (UI) | Cooldown, filtro de sinal fraco, qty sugerida no estudo |

## API

- `GET /agent/learning-stats` — agregados + `soft_guards` para o engine
- `GET /library/learning-insights` — insights persistidos
- `GET /agent/study` — bloco `performance_learning` (inclui última insight)

## Motor (soft guards)

Com `AUTO_LEARN_FROM_TRADES=true` (padrão):

- Após **3 perdas seguidas** ou WR &lt; 40% (rolling ou estratégia ativa, mín. 8 trades): cooldown **2×**, pode **ignorar sinais fracos** (volatilidade sem regime / heurística documentada em `engine/trade_feedback.py`), **metade** dos contratos nos sinais automáticos (mín. 1).
- **Boleta manual** (`POST /orders/execute`) **não** é bloqueada.

## Modo aprendizado 24h (opção 7)

A cada passagem de estudo, `run_trade_learning_pass` chama `GET /agent/learning-stats` (recalcula e grava JSON).

## Configuração

```env
AUTO_LEARN_FROM_TRADES=true
```

Desligue para desativar guardas e refresh automático do JSON (métricas brutas em `/metrics/trades` continuam).

## Código

- `shared/trade_learning.py` — matemática e insights
- `api/trade_learning.py` — leitura do DB
- `engine/trade_feedback.py` — loop do engine

**Cockpit:** card por ativo no Painel (KPI deck) e nas abas Agente/Sistema — `cockpit/src/pulse/symbolStrategyStats.ts` (`GET /metrics/trades?symbol=`).

## Testes

```bat
.venv\Scripts\python.exe -m pytest tests/test_trade_learning.py
```
