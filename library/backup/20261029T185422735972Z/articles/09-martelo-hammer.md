# Martelo e martelo invertido

No **day trade B3** (ações líquidas ou mini-índice WIN em M5/M1), o **martelo** aparece quando o preço testa uma região e **devolve** grande parte do movimento intrabar.

## Forma

- Corpo pequeno no **topo** da faixa do candle.
- **Sombra inferior** longa (compradores absorveram venda).
- Sombra superior curta.

O **martelo invertido** inverte a lógica: sombra superior longa, corpo no fundo — sinal de possível repique após queda, mas exige confirmação.

## Psicologia

Mostra **rejeição de preços mais baixos**: vendedores perderam controle antes do fechamento. Sozinho não garante reversão — o mercado pode continuar lateral.

## Uso no Sala de Sinais

A **camada matemática** (`GET /agent/candle-patterns`) marca martéis nas últimas barras M5. A **biblioteca** (este artigo) explica *quando* filtrar por tendência, volume do pregão (10h–17h55) e alinhamento com stop/alvo do engine.

## Checklist prático

1. Preferir martelo após sequência de candles de baixa ou teste de suporte visível no gráfico rio.
2. Aguardar confirmação (rompimento da máxima do martelo ou close acima da média).
3. Respeitar gestão de risco do painel — padrão visual não substitui stop.
