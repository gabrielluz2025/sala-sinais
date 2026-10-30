# Integração Supabase (Postgres) — Sala de Sinais

Este guia explica como apontar a **API FastAPI** para o **Postgres** do seu projeto Supabase já existente (ex.: usado antes em **financasmais.com**), mantendo **SQLite** como padrão quando nada estiver configurado.

---

## O que muda (e o que não muda)

| Com Supabase | Sem Supabase (padrão) |
|--------------|------------------------|
| Sinais, config do agente e estado do sistema ficam no **Postgres remoto** | Arquivo `data/sala_sinais.db` local |
| Backup e acesso SQL pelo painel Supabase | Cópia manual do `.db` |

**Limites honestos:**

- O Supabase substitui **somente o banco de dados** da API. **API**, **engine** e **MetaTrader 5** continuam rodando no seu **PC ou VPS** (modo web/túnel).
- **Auth**, **Storage** e **Realtime** do app antigo no Supabase **não** são usados pelo cockpit atual — isso seria trabalho futuro opcional.
- Dados do **SQLite local não migram sozinhos**; exporte/importe se precisar (CSV, script, ou cópia manual).
- Arquivos em `data/*.json` (cotações, barras, epoch de sessão) **permanecem no disco** da máquina que roda a API — não vão para o Supabase.

O **engine** fala com a API via HTTP (`API_BASE_URL`); não abre o banco diretamente. Basta a **API** usar o mesmo `DATABASE_URL` / `SUPABASE_DB_URL`.

---

## Onde copiar a connection string no Supabase

1. Abra [supabase.com](https://supabase.com) → seu projeto.
2. **Project Settings** (engrenagem) → **Database**.
3. Em **Connection string**, escolha **URI**.
4. Copie a string **Session mode** ou **Transaction pooler** (recomendado para app server-side):
   - **Direct** (porta **5432**): conexão direta ao Postgres; ok para dev ou poucas conexões.
   - **Pooler** (porta **6543**): melhor para API sempre ligada; o código já ajusta `prepare_threshold` para o pooler.

Use usuário **`postgres`** ou o role de **service** que o painel mostrar na URI — **nunca** cole essa URI no frontend/cockpit.

> **Service role / senha do banco:** só no `.env` do servidor (PC/VPS). O cockpit no navegador **não** deve receber `SUPABASE_SERVICE_ROLE_KEY` nem a senha do Postgres.

Substitua `[YOUR-PASSWORD]` pela senha do banco (Settings → Database → **Database password** / reset se necessário).

Formatos aceitos no `.env` (normalizados automaticamente para `postgresql+psycopg://`):

- `postgresql://...`
- `postgres://...`
- `postgresql+asyncpg://...` (convertido para driver síncrono da API)

---

## Variáveis no `.env`

Escolha **uma** das formas:

```env
# Opção A — nome padrão
DATABASE_URL=postgresql://postgres.[ref]:[SENHA]@aws-0-[regiao].pooler.supabase.com:6543/postgres?sslmode=require

# Opção B — alias (útil se você já guardava SUPABASE_DB_URL no projeto antigo)
# SUPABASE_DB_URL=postgresql://postgres.[ref]:[SENHA]@aws-0-[regiao].pooler.supabase.com:6543/postgres?sslmode=require
```

Se **nenhuma** estiver definida, permanece:

```env
DATABASE_URL=sqlite+aiosqlite:///./data/sala_sinais.db
```

**Dependência Python** (Postgres):

```bash
pip install "psycopg[binary]>=3.1"
```

(já listado em `requirements.txt`.)

---

## Primeira subida com Postgres

1. Configure o `.env` com a URI do Supabase.
2. Instale dependências: `pip install -r requirements.txt`.
3. Suba a API (`uvicorn` / `Sala-Sinais.bat`). Na inicialização, `init_db()`:
   - cria as tabelas `signals`, `agent_config`, `system_state` se não existirem;
   - aplica migrações leves de colunas (mesmo fluxo do SQLite).

**Alternativa manual:** rode `scripts/supabase_schema.sql` no **SQL Editor** do Supabase antes de subir a API.

---

## Tabelas necessárias

| Tabela | Uso |
|--------|-----|
| `signals` | Sinais, PnL, histórico de trades |
| `agent_config` | Parâmetros do agente (linha `id=1`) |
| `system_state` | Pausa, heartbeat, modo, snapshot MT5 |

Se o projeto Supabase ainda tiver **tabelas do app legado** com os mesmos nomes, resolva conflito (outro schema, projeto novo, ou renomeação) antes de produção.

---

## Deploy web (financasmais.com + túnel)

Fluxo típico:

```
Navegador → Cloudflare Tunnel → FastAPI :8000 → Postgres (Supabase)
Engine + MT5 → API_BASE_URL (mesma máquina Windows)
```

- `API_HOST=0.0.0.0` e túnel para `http://127.0.0.1:8000` (ver `docs/DEPLOY_FINANCASMAIS.md`).
- **Mesmo `.env`** na máquina que roda a API, com `DATABASE_URL` ou `SUPABASE_DB_URL` apontando para o Supabase.

---

## Testes

Os testes em `tests/` usam **SQLite temporário** por padrão. Integração real com Supabase não roda no CI; valide manualmente após configurar o `.env`.

---

## Alembic (futuro)

Hoje o projeto usa `create_all` + `ALTER TABLE` pontual em `api/database.py`. Para evoluções grandes de schema em produção Postgres, considere adotar **Alembic** depois; o arquivo `scripts/supabase_schema.sql` reflete o estado atual dos models.

---

## Referências

- [DEPLOY_SUPABASE_E_DOMINIO.md](DEPLOY_SUPABASE_E_DOMINIO.md) — DNS, túnel e relação com o stack antigo
- `.env.example` — placeholders sem segredos
