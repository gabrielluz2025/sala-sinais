# Agente, biblioteca e notícias

## Biblioteca (`/library`)

A **biblioteca** é a base de conhecimento curada do Sala de Sinais: artigos em português sobre day trade, risco, taxas B3, horários e como as estratégias do engine funcionam. O painel lê esses textos via API; não substituem aconselhamento financeiro.

Use a biblioteca para entender **por que** o agente usa certos stops, lotes de 100 ações ou filtros de volatilidade antes de mudar parâmetros em **Configurar**.

## Notícias (filtro heurístico)

O módulo `engine/news_context.py` lê manchetes em cache (`GET /news/headlines`) e aplica **regras simples de palavras-chave** em português — por exemplo termos ligados a Copom, Selic ou “crise” marcam viés de **cautela** e podem **bloquear novas entradas** na simulação.

Isso **não é NLP**, não lê o corpo da notícia e não prevê o mercado. É um filtro educacional para mostrar como contexto macro pode entrar num robô no futuro.

- `agent_config.use_news_filter` (padrão `true` na simulação) liga ou desliga o filtro.
- Quando uma regra dispara, o `entry_reason` do sinal pode citar a manchete e artigos da biblioteca (ex.: gestão de risco **04**, estratégias **07**).

## Evolução (roadmap)

- Hoje: regras fixas + biblioteca estática.
- Futuro possível: embeddings/ML sobre histórico e notícias — sempre com revisão humana e compliance.
