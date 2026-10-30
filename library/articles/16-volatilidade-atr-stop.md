# Volatilidade adaptativa: ATR, regime e stop

A estratégia `volatility` (`engine/strategy_volatility.py`) não troca o **tipo** de gatilho (continua rompimento de range), mas **adapta**:

- **Lookback** do range (maior em vol alta, menor em vol baixa).
- **Buffer** mínimo de rompimento quando a volatilidade está alta.
- **Multiplicadores** de stop e alvo sobre os parâmetros da config.

## Leitura do regime

O engine combina **ATR%** (14 períodos) e **largura das Bandas de Bollinger** (20, 2 desvios) em um score:

- **Vol alta** → exige rompimento mais “limpo”; stops/alvos mais largos.
- **Vol baixa** → range menor; stops/alvos mais apertados.

O campo `regime` no sinal e no estudo ao vivo reflete esse rótulo.

## Stop “por ATR” vs config

Este projeto **não** substitui automaticamente seu `stop_loss_pct` por múltiplos de ATR puro; ele **escala** seus percentuais/pontos conforme o regime. Para estudo teórico de stops só por ATR, veja também o artigo **03-volatilidade-atr**.
