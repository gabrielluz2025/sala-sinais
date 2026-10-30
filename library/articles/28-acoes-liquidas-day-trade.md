# Ações líquidas para day trade

Liquidez = sair quando precisar, com slippage controlado.

## Critérios

- Volume financeiro diário elevado.
- Spread bid-ask estreito no horário core.
- Presença em índices (IBOV, IBRX).

## Exemplos recorrentes

PETR4, VALE3, ITUB4, BBDC4, B3SA3 — **não é recomendação**; é observação de mercado. Revise diariamente.

## Lote padrão

Day trade em ações usa múltiplos de lote; ajuste `shares_per_order` no agente.

## Ilíquidas

Padrões de candle “perfeitos” em small caps falham na execução. Evite unless specialized.

## Dados

OHLC M5 no painel; bars persistidos em `data/bars_*.json` para estudo.
