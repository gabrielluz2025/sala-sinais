# Biblioteca em escala — arquitetura v2

A base **não é infinita por magia**: é **expansível de forma contínua** quando você configura ingestão (RSS, importação manual, ZIP, futuras APIs). O agente e o cockpit leem um **catálogo unificado** que mescla todas as camadas.

## Camadas

| Camada | Pasta | Origem | Catálogo |
|--------|--------|--------|----------|
| **Núcleo curado** | `library/articles/` | `library/index.json` | Entradas explícitas + export ZIP v1 |
| **Importados** | `library/imported/` | Markdown solto (frontmatter opcional) | Glob automático |
| **Digest de notícias** | `library/news/` | RSS (`LIBRARY_NEWS_RSS_URLS`) ou manual | Glob automático |
| **Diário do agente** | `data/agent_journal/` | Escrito após acertos + ticks de estudo | Fora do catálogo (meta-aprendizado) |

Implementação: `api/library_catalog.py` → `load_merged_catalog()` usado por `GET /library`, estatísticas, estudo autônomo e leitura de artigos.

## Ingestão

### Manual (sempre disponível)

1. Novos artigos curados: `.md` em `library/articles/` + entrada em `index.json`.
2. Lote externo: copie `.md` para `library/imported/` (veja `library/imported/README.md`).
3. Notícia pontual: copie `library/news/_TEMPLATE.md` → `library/news/YYYY-MM-DD-slug.md`.

### ZIP (camada curada)

`GET /library/export` e `POST /library/import` continuam no formato **sala_sinais_library_v1** (`index.json` + `articles/`). Não inclui `imported/` nem `news/` — faça backup dessas pastas no SO ou git privado.

### RSS v1 (opcional)

Variável de ambiente:

```env
LIBRARY_NEWS_RSS_URLS=https://exemplo.com/feed.xml,https://outro.com/rss
```

Comando:

```powershell
cd C:\Users\xgame\sala-sinais
python scripts\ingest_library_news.py
```

Opções: `--dry-run`, `--url https://...`, `--template` (cria `_TEMPLATE.md`). Rate limit ~2 s entre feeds. Cada item vira um `.md` em `library/news/` com **disclaimer** no frontmatter.

Se RSS falhar (bloqueio, HTML inválido), use ingestão manual — o script documenta isso ao rodar sem URLs.

### Roadmap (não implementado)

- APIs pagas (Bloomberg, Refinitiv) com política de uso.
- Pipelines Hugging Face / papers — **referências abaixo**, sem bulk no repo.
- Agendador (Task Scheduler / cron) chamando `ingest_library_news.py` 1–2× ao dia.

## Categorias

Além das do `index.json`: `acoes-b3`, `noticias`, `psicologia`, `macro`, `imported`. Filtro no cockpit usa `category` de cada item.

## Estudo autônomo do agente

`api/agent_library_study.py` percorre **todos** os itens do catálogo mesclado (curado + importado + news). Contagem exibida: `studied_count / catalog_total`.

Segurança: só lê Markdown local; não envia ordens.

## Datasets e fontes abertas (sem download em massa no repo)

Consulte também `library/articles/08-fontes-abertas.md`. Referências úteis para **expandir conhecimento fora do repo**:

- [Hugging Face Datasets](https://huggingface.co/datasets) — busque finance, news, portuguese; revise licença antes de ingestão automatizada.
- [B3 Educação / market data](https://www.b3.com.br) — material oficial.
- [CVM — educação](https://www.gov.br/cvm/pt-br) — investidor.
- Papers de microestrutura/volatilidade intraday — curadoria humana recomendada antes de importar para `library/imported/`.

## Cockpit

`GET /library/stats` retorna:

- `article_count` — curado + importado (sem notícias)
- `news_count` — digest RSS/manual
- `catalog_total` — tudo o que o agente pode estudar

Painel Biblioteca: **Base: N artigos + M notícias** e filtro por categoria.

## Honestidade sobre “infinito”

**Infinito** aqui significa: arquitetura preparada para **crescimento contínuo** (RSS, pastas, ZIP, futuras APIs), com catálogo dinâmico e agente iterando a fila completa — não um LLM com memória ilimitada nem scraping irrestrito.

Veja também `docs/BIBLIOTECA.md` (API e painel v1).
