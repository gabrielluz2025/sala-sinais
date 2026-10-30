# Aprendizado do agente (volatilidade e roadmap)

## O que “aprende” nesta versão (MVP)

Não usamos deep learning nem retreino automático de modelos. O modo padrão **`strategy_type=volatility`** implementa um **agente adaptativo à volatilidade**:

1. **ATR%** (Average True Range em percentual do preço) — mede amplitude típica dos candles.
2. **Largura de Bollinger** — mede expansão/contração do preço em torno da média.
3. **Regime** derivado desses indicadores:
   - **Vol alta** → stops e alvos mais largos, lookback maior, rompimento precisa ser mais forte → **menos sinais**.
   - **Vol baixa** → stops/alvos mais apertados, lookback menor → **mais sinais** (com filtro mais leve).
   - **Vol moderada** → parâmetros intermediários.

Cada sinal inclui uma `note` explicando o regime, por exemplo: `Vol adaptativo — vol alta (ATR%=..., BB%=...)`.

A alternativa **`strategy_type=breakout`** mantém a lógica clássica de rompimento em `engine/strategy.py` (sem adaptação por vol).

## Onde está no código

| Peça | Arquivo |
|------|---------|
| Estratégia volatilidade | `engine/strategy_volatility.py` |
| Seleção breakout vs vol | `engine/strategy_factory.py` + `agent_config.strategy_type` |
| Loop sim / MT5 | `engine/main.py` |
| Alertas entrada/saída | `GET /alerts/recent` (derivado dos sinais) |
| Gráficos M1/M5/H1 | `GET /market/ohlc` + candlestick no painel |

## Configuração no painel

Em **Configurar → Estratégia do agente**:

- **Volatilidade adaptativa** (padrão)
- **Rompimento (breakout)**

Salve com **Salvar configuração**; o engine lê a config a cada ciclo.

## Fase 2 — machine learning (planejado)

Ideias documentadas para evolução futura (não implementadas):

- **Features:** retornos log, vol realizada, skew de candles, horário B3, correlação com índice.
- **Labels:** resultado do trade (win/loss) ou hit de stop/alvo em janela fixa.
- **Modelos:** classificador leve (gradient boosting / rede pequena) ou RL com ambiente simulado.
- **Governança:** treino offline, validação walk-forward, limite de drift, nunca auto-ativar live sem revisão humana.

Até a Fase 2, trate o sistema como **laboratório educacional** com regras transparentes e auditáveis.

## Alertas entrada/saída

- **Entrada:** todo novo sinal registrado na API.
- **Saída:** sinal com `exit_price` e `closed_at` (trade fechado).

O painel lista os últimos 20 em **Alertas entrada/saída**; som opcional (desligado por padrão).
