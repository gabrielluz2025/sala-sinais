# Estratégias do Sala de Sinais

Versão atual do engine: **v1**. Duas estratégias selecionáveis em **Configurar agente**:

## Volatilidade adaptativa (`volatility`)

- Arquivo: `engine/strategy_volatility.py`
- Rompimento de range com filtros por ATR% e Bollinger
- Regime gravado em `regime` (vol alta / moderada / baixa)
- Saída simulada: motivos como *stop vol adaptativo* ou *alvo atingido*

## Rompimento (`breakout`)

- Arquivo: `engine/strategy.py` (`BreakoutStrategy`)
- Rompimento clássico da máxima/mínima dos últimos N candles M1
- Stops/alvos em % (ações) ou pontos (WIN)

Cada sinal na API inclui `entry_reason` em português. Ao fechar, `exit_reason` explica stop ou alvo.

## Filtro de notícias (simulação)

Com `use_news_filter` ativo na config do agente, o engine consulta manchetes RSS (palavras-chave em PT) antes de confirmar entrada. Viés de **cautela** pode impedir o sinal; viés levemente otimista só anota o motivo — ver `docs/AGENTE_CONHECIMENTO.md`. Não é análise de sentimento profunda.
