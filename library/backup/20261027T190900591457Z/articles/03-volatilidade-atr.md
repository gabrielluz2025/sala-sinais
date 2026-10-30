# Volatilidade e ATR

**ATR (Average True Range)** mede a amplitude média dos candles. Em % do preço, ajuda a comparar regimes entre ativos.

A estratégia **volatility** do sistema combina ATR% com largura das **Bandas de Bollinger** para classificar:

- vol alta
- vol moderada
- vol baixa

Com isso ajusta lookback, stop e alvo — veja os motivos de entrada no painel quando `strategy_type=volatility`.
