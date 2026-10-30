# Harami — pausa dentro da tendência

O **harami** (corpo menor dentro do corpo anterior) sinaliza **desaceleração**, não reversão garantida. No day trade B3, aparece com frequência após sequências direcionais em PETR4, VALE3 ou WIN M5.

## Forma

Candle grande (mãe) seguido de corpo **contido** dentro da faixa da mãe. Harami de alta: mãe de baixa e filho pequeno; harami de baixa: mãe de alta.

## Contexto

Funciona melhor **após tendência clara** e próximo a suporte/resistência do dia. Em meio de range, gera muitos falsos positivos.

## Confirmação

Espere rompimento da máxima/mínima do par ou alinhamento com volume crescente no pregão (10h–17h55). O engine pode sinalizar breakout; o harami ajuda a **filtrar** entradas contra momentum.

## Risco

Stop além da mãe ou além do extremo do harami. Tamanho de posição conforme artigo de R:R — padrão visual não substitui gestão.

## Sala de Sinais

Use `GET /agent/candle-patterns` como radar; a biblioteca explica quando **ignorar** harami em leilão de abertura ou nos últimos minutos antes do fechamento.
