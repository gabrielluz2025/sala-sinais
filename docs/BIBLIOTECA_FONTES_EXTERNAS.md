# Fontes externas — Biblioteca (notícias para estudo do agente)

Este documento lista formas **legítimas** de alimentar `library/news/` com digest de mercado. O agente lê esses `.md` como catálogo `source: news` (sem LLM; só indexação + estudo autônomo).

**Não use scraping de sites sem permissão.** Prefira RSS oficial ou APIs documentadas.

---

## 1. RSS / Atom (recomendado, grátis)

| Fonte | URL / notas |
|--------|-------------|
| **InfoMoney** | `https://www.infomoney.com.br/feed/` — feed editorial; respeite robots/ToS |
| **Folha (Em cima da média)** | `https://feeds.folha.uol.com.br/emcimadamedia/rss091.xml` |
| **Reuters (mercados)** | Feeds públicos Reuters Markets (ver página de RSS atual); uso educativo local |
| **Investing.com** | Alguns feeds RSS existem por seção; **verifique ToS** — nem sempre permitido redistribuir |
| **B3** | Notícias institucionais em site/imprensa; quando houver feed oficial, inclua em `LIBRARY_NEWS_RSS_URLS` |

**Script:** `scripts/ingest_library_news.py` ou o agregador `scripts/ingest_external_finance.py`.

**Env:**

```env
LIBRARY_NEWS_RSS_URLS=https://www.infomoney.com.br/feed/
```

---

## 2. APIs gratuitas ou low-cost

### Finnhub (`FINNHUB_API_KEY`)

- Site: [finnhub.io](https://finnhub.io/)
- Endpoint usado: `GET /api/v1/news?category=general`
- **Limites:** plano free ~60 req/min (consulte dashboard); chave no header/query `token`
- **Foco B3:** notícias globais em inglês; útil para macro. Para ticker BR use `company-news` com símbolos US ADR ou combine com RSS locais
- **ToS:** uso não comercial/educativo local; não republicar feed bruto como produto

### NewsAPI.org (`NEWSAPI_KEY`)

- Site: [newsapi.org](https://newsapi.org/)
- Endpoint usado: `GET /v2/top-headlines?country=br&category=business`
- **Limites:** developer free ~100 req/dia; atraso de 24h em alguns planos
- **ToS:** exibir `source`/`url` no markdown; não remover atribuição

### Outras (roadmap, não implementadas v1)

| API | Notas |
|-----|--------|
| **Alpha Vantage** | NEWS_SENTIMENT — foco US; rate limit agressivo no free |
| **Polygon.io** | Notícias US; pago para volume |
| **Benzinga / Refinitiv** | Enterprise |

---

## 3. Como roda no projeto

### Manual (uma vez)

```powershell
cd c:\Users\xgame\sala-sinais
.\.venv\Scripts\python.exe scripts\ingest_external_finance.py --dry-run
.\.venv\Scripts\python.exe scripts\ingest_external_finance.py
```

Só RSS:

```powershell
.\.venv\Scripts\python.exe scripts\ingest_library_news.py --url https://www.infomoney.com.br/feed/
```

### Automático (API no ar)

```env
LIBRARY_AUTO_INGEST_HOURS=6
LIBRARY_NEWS_RSS_URLS=https://www.infomoney.com.br/feed/
FINNHUB_API_KEY=sua_chave
NEWSAPI_KEY=sua_chave
```

Enquanto a API estiver rodando, um job em background chama a mesma lógica de `ingest_external_finance.py` a cada N horas.

### Saída

Arquivos em `library/news/YYYY-MM-DD-slug.md` com frontmatter:

- `source: news`
- `source_url:` link original
- corpo = resumo curto para estudo

O catálogo mescla automaticamente (`api/library_catalog.py`).

---

## 4. Cockpit

Na aba **Biblioteca**: linha *Fontes externas: RSS + API (ver doc BIBLIOTECA_FONTES_EXTERNAS.md)*.

---

## 5. Checklist de conformidade

1. Guardar **URL da fonte** em todo digest gerado  
2. Respeitar **rate limits** (scripts dormem ~2s entre itens)  
3. Não contornar paywall  
4. Tratar conteúdo como **educativo**, não recomendação de investimento (disclaimer no template)
