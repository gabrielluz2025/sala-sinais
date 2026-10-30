# Biblioteca de aprendizado

## Propósito

A **Biblioteca de aprendizado** é uma base de conhecimento **curada** (Markdown em `library/`), exibida no painel e via API. Ela complementa a transparência das estratégias do engine — cada sinal registra `strategy_type`, motivos de entrada/saída e regime de volatilidade quando aplicável.

**Catálogo v2:** o API mescla `index.json` + `library/imported/` + `library/news/` (`api/library_catalog.py`). Roadmap e ingestão contínua: **`docs/BIBLIOTECA_ESCALA.md`**.

**Não é** um modelo de machine learning que reescreve regras automaticamente. RSS e APIs externas são **opcionais** (ver script `scripts/ingest_library_news.py`).

## Ligação com o engine

- Artigo **07-estrategias-sistema** descreve as duas estratégias ativas:
  - `volatility` — `engine/strategy_volatility.py`
  - `breakout` — `engine/strategy.py` (`BreakoutStrategy`)
- No painel, colunas **Estratégia**, **Motivo entrada** e **Motivo saída** refletem os campos gravados na tabela `signals`.

## Onde os arquivos ficam no disco

No repositório local (exemplo Windows):

| Conteúdo | Caminho relativo | Exemplo absoluto |
|----------|------------------|------------------|
| Catálogo da biblioteca | `library/index.json` | `C:\Users\xgame\sala-sinais\library\index.json` |
| Artigos (Markdown) | `library/articles/*.md` | `C:\Users\xgame\sala-sinais\library\articles\` |
| Sinais, operações e PnL | `data/sala_sinais.db` | `C:\Users\xgame\sala-sinais\data\sala_sinais.db` |
| Cotações / barras simuladas | `data/*.json` | `C:\Users\xgame\sala-sinais\data\last_quote.json` |

O painel em **Biblioteca de aprendizado** mostra contagem de artigos, categorias e palavras (`GET /library/stats`) e um resumo “Onde os dados ficam”.

## API

| Endpoint | Descrição |
|----------|-----------|
| `GET /library` | Catálogo (`index.json`) + categorias |
| `GET /library/stats` | Tamanho da base (artigos, categorias com contagem, palavras/bytes, `last_updated`, caminhos de armazenamento) |
| `GET /library/knowledge-level` | Faixa de conhecimento. `?read_ids=` = **seu** progresso no cockpit; `?agent=true` = artigos estudados pelo agente; sem query = tamanho da biblioteca (legado). |
| `GET /library/agent-study-status` | Progresso autônomo do agente (X/Y artigos, nível, fila, ocioso se `AGENT_AUTO_STUDY_LIBRARY=false`) |
| `GET /library/agent-journal` | Diário markdown (`data/agent_journal/agente-aprendizado.md`) — criado no **primeiro fechamento**; selo «salvo desde primeiro acerto» após vitória; **histórico cumulativo** (últimos 30, erros visíveis) + seção operacional |
| `POST /library/agent-study/tick` | Dispara um artigo na fila (`?force=true` ignora flag para testes) |
| `GET /library/read-progress` | IDs lidos persistidos no servidor (`data/library_read_progress.json`) |
| `PUT /library/read-progress` | Corpo `{ "read_article_ids": [...], "merge": true }` — backup opcional do progresso |

## Níveis de conhecimento (Pulse Deck)

Dois progressos distintos:

| Trilha | Onde grava | UI |
|--------|------------|-----|
| **Seu progresso** | localStorage + opcional `data/library_read_progress.json` | Cartão «Seu progresso», barra no balão Conhecimento |
| **Conhecimento do agente** | `data/agent_library_progress.json` | Linha «Agente estudando…» no Raio-X; badge nos cards |
| **Diário do agente** | `data/agent_journal/agente-aprendizado.md` + `journal_meta.json` | Aba Biblioteca · cartão «Diário do agente»; atualizado a **cada fechamento** (acerto ou erro); barra «Experiência prática» em `agent_library_progress.json` |

Mesma fórmula de faixas para ambos:

| Faixa | Mín. artigos | Mín. palavras |
|-------|--------------|---------------|
| Iniciante | 0 | 0 |
| Aprendiz | 3 | 2.000 |
| Intermediário | 6 | 5.000 |
| Avançado | 10 | 10.000 |

O nível atual é a **maior faixa** em que **ambos** os critérios são atingidos. A **barra principal** mede o progresso até a **próxima faixa**, usando o **critério mais fraco** (artigos ou palavras) — nunca 100% enquanto ainda faltar um dos dois para promover.

**Escada na UI:** Iniciante → Aprendiz → Intermediário → Avançado (marca «você está aqui») + **Especialista** (roadmap, ainda sem faixa numérica).

**Duas barras no agente:** (1) progresso de **nível** até a próxima faixa; (2) **catálogo** `X/Y` artigos estudados — cobertura da biblioteca, independente do nível.

**Rótulo no cabeçalho:** `Nível: Aprendiz · 17% até Intermediário` (exemplo) — o percentual **não** é «100% Aprendiz»; significa quanto falta para **Intermediário**, não conclusão da faixa atual.

## Estudo autônomo do agente

O agente **não usa LLM** nesta fase: cada tick abre o `.md`, soma palavras para o nível e registra um digest curto (primeiro título `#`).

| Variável | Padrão | Efeito |
|----------|--------|--------|
| `AGENT_AUTO_STUDY_LIBRARY` | `true` | `true` = ticks automáticos na API (24h; desligue com `false`) |
| `AGENT_STUDY_INTERVAL_SEC` | `300` | Intervalo entre artigos |
| `OVERNIGHT_LEARNING` | `false` | Sinais sim + estudo ao vivo noturno no **engine**; **não** controla ticks da biblioteca |

**Ativar:** padrão recomendado no `.env` (`AGENT_AUTO_STUDY_LIBRARY=true`). **Sala-Sinais.bat → opção 1 ou 2** também liga o estudo salvo `AGENT_AUTO_STUDY_LIBRARY=false` no `.env`. Opção **7** continua sendo modo aprendizado completo (sim + overnight).

**Segurança em LIVE:** o estudo autônomo só lê Markdown em `library/articles/` e grava `data/agent_library_progress.json` — **não envia ordens** nem altera risco/execução.

Arquivo de progresso: `data/agent_library_progress.json`. Livros em `library/books/` ficam para uma fase futura.

| `GET /library/articles/{id}` | Corpo Markdown do artigo |
| `GET /library/export` | Arquivo ZIP para backup (`sala_sinais_conhecimento.zip`) |
| `POST /library/import` | Restaura o ZIP (multipart `file`; query `mode=merge` ou `replace`) |

## Backup e restauração do conhecimento

O pacote usa o formato **`sala_sinais_library_v1`**: `manifest.json`, `index.json` e `articles/*.md`. **Não inclui** o banco `data/sala_sinais.db` — apenas a base educacional curada.

### No painel (Biblioteca)

1. Role até **Conhecimento adquirido**.
2. **Baixar conhecimento** — salva um `.zip` no seu PC (ex.: `Downloads\sala_sinais_conhecimento.zip`).
3. Após reset ou em outra máquina, **Importar conhecimento** e escolha o mesmo arquivo.
   - **Mesclar (padrão):** artigos e categorias com o mesmo `id` são atualizados; os demais permanecem.
   - **Substituir tudo:** apaga os `.md` atuais e troca o catálogo pelo do ZIP.
4. Antes de gravar, a API copia o estado anterior para `library/backup/<timestamp>/` (UTC).

### Via API (Windows)

```powershell
# Download (API em http://127.0.0.1:8000)
curl -o C:\Users\SEU_USUARIO\Downloads\sala_sinais_conhecimento.zip http://127.0.0.1:8000/library/export

# Importar (mesclar)
curl -X POST "http://127.0.0.1:8000/library/import?mode=merge" -F "file=@C:\Users\SEU_USUARIO\Downloads\sala_sinais_conhecimento.zip"
```

Caminhos típicos no disco após import:

| Conteúdo | Caminho |
|----------|---------|
| Biblioteca ativa | `C:\Users\xgame\sala-sinais\library\` |
| Backup automático | `C:\Users\xgame\sala-sinais\library\backup\20261027T120000Z\` |

## Expansão (curadoria primeiro)

1. Novos artigos manuais em `library/articles/`.
2. Revisão pedagógica e links para fontes oficiais (B3 Educação, CVM).
3. Fase 2 (futuro): pipelines de ingestão com revisão humana antes de publicar.
