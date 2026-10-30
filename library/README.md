# Biblioteca de aprendizado

Base de artigos em Markdown consumida pela API (`GET /library`) e pelo painel.

## Adicionar um artigo

1. Crie `articles/NN-titulo-curto.md` em português, com título `#` na primeira linha.
2. Registre em `index.json`: `id`, `title`, `category`, `tags`, `path`, `updated`.
3. Categorias válidas: `fundamentos`, `risco`, `estrategias`, `fontes`.
4. Reinicie a API (ou aguarde reload) — não há ingestão automática nesta fase.

## Fase 2 (não implementada)

- RSS, arXiv ou scraping de fontes abertas.
- Sincronização com embeddings / busca semântica.

Esta pasta é **curadoria manual**; o sistema não “aprende sozinho” alterando o engine.
