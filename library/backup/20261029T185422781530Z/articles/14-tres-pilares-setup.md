# Três pilares de um setup de day trade

Todo plano operacional objetivo pode ser lido em **três estágios** (modelo usado no agente e no engine):

| Estágio | Pergunta | Exemplo |
|---------|----------|---------|
| **Contexto** | O mercado permite operar agora? | Pregão B3, liquidez, horário sem leilão |
| **Gatilho** | O que dispara a entrada? | Close M1 rompe máxima dos últimos 12 candles |
| **Saída** | Onde corto perda e realizo ganho? | Stop % ou pontos WIN; alvo com R:R definido |

No Sala de Sinais, a camada **matemática** (Python) calcula range, ATR e níveis; a **biblioteca** explica psicologia e regras B3. O painel **Estudo ao vivo** mostra o playbook da estratégia ativa com números do momento.

Padrões de candle (martelo, engolfo) podem enriquecer o **contexto** ou confirmar **suporte/resistência**, mas o engine atual usa rompimento de range — combine leitura visual com o gatilho configurado.
