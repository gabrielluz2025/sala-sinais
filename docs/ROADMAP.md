# Roadmap e respostas honestas — Sala de Sinais

Documento em português sobre o que o sistema **faz hoje**, o que **não faz**, e próximos passos.

## Entradas, saídas e parar

| Capacidade | Status |
|------------|--------|
| Gerar sinais (estratégia breakout no engine) | Funciona com MT5 conectado |
| Registrar sinais na API / painel | Funciona |
| Enviar ordem mercado com SL/TP no MT5 | Só com `SIGNAL_MODE=live` **e** `LIVE_TRADING=true` |
| Pausar / retomar estratégia | **Painel → API** (`engine_paused`); engine continua heartbeat |
| Zerar posição (emergência) | Flag `emergency_flatten`; engine tenta fechar posições no MT5 se LIVE |
| ML autônomo “aprendendo sozinho” | **Não existe** nesta versão |

Não há robô que aprende padrões em tempo real. A lógica é a estratégia fixa em `engine/strategy.py`.

## Modo real — checklist passo a passo

1. Validar na **conta demo** por vários dias (paper e depois live sem dinheiro real).
2. Confirmar símbolo WIN no MT5 (`MT5_SYMBOL` no `.env`).
3. Ativar **RLP** na corretora (corretagem zero em minis — ajuste `BROKER_FEE_PER_CONTRACT` se não usar RLP).
4. No `.env`: `SIGNAL_MODE=live` e só então `LIVE_TRADING=true` quando aceitar o risco.
5. MT5 terminal **real** logado na mesma máquina do engine.
6. Capital adequado, limites de risco (`MAX_CONTRACTS`, horário de trade).
7. **Impostos**: operações na B3 podem gerar obrigações (IR, DARF etc.) — consulte contador; este projeto não calcula imposto.

O painel web mostra um checklist estático; a responsabilidade operacional é sua.

## “Aprender estratégias” — expectativa realista

**Hoje (MVP):** uma estratégia parametrizada via `.env` (stop/alvo em pontos, cooldown, horário). Ajustar comportamento = alterar código ou parâmetros e testar de novo.

**Fase 2 (futuro, não implementado):**

- Backtest com histórico MT5 ou arquivo CSV
- Grade de parâmetros / otimização com validação out-of-sample
- Pipeline opcional de ML (features, treino offline, deploy de modelo) — **sempre** com validação rigorosa; nunca “caixa preta que opera sozinha” sem supervisão

## Taxas e métricas implementadas

### Fórmula PnL bruto (WIN)

Para cada contrato, **R$ 0,20 por ponto** de variação do índice:

- **Compra:** `(preço_saída - preço_entrada) × 0,20 × contratos`
- **Venda:** `(preço_entrada - preço_saída) × 0,20 × contratos`

### PnL líquido estimado

```
líquido = bruto - (B3_FEE_PER_CONTRACT_ROUND + BROKER_FEE_PER_CONTRACT) × contratos
```

Defaults no `.env.example`:

- `B3_FEE_PER_CONTRACT_ROUND=0.28` (ida e volta, valor educacional)
- `BROKER_FEE_PER_CONTRACT=0` (RLP)

Registre `exit_price` ao fechar o sinal (`PATCH /signals/{id}`) para popular PnL no painel e em `GET /metrics/pnl`.

## Notícias

- **Agora:** feed RSS público (Google News Brasil — economia/mercado), cache server-side (`NEWS_CACHE_SEC`, padrão 600 s).
- **Depois:** APIs pagas (Bloomberg, Refinitiv, etc.) ou fontes com autenticação.

## Controle do sistema (API)

| Endpoint | Uso |
|----------|-----|
| `GET /system/state` | Pausa, emergência, último heartbeat |
| `PATCH /system/state` | Painel: pausar, retomar, zerar posição |
| `POST /system/heartbeat` | Engine (com webhook secret) |
| `GET /metrics/pnl` | KPIs diário / mensal / total |
| `GET /market/quote` | Última cotação em `data/last_quote.json` |
| `GET /news/headlines` | Manchetes RSS |

## Outras ideias (backlog)

- VPS dedicada com MT5 + watchdog
- Kill switch: perda máxima diária em R$
- Diário de trades exportável (CSV)
- Backtest integrado ao MT5
- Múltiplas estratégias e alocação de risco
- Autenticação no painel (token) para uso fora de localhost

## Limitações conhecidas

- Painel sem login — use apenas em rede local confiável.
- Fechamento automático de PnL depende de informar `exit_price` (não lê deal history do MT5 ainda).
- Zerar posição no MT5 exige engine rodando e `LIVE_TRADING=true`.
