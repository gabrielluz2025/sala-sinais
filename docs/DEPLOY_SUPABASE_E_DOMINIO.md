# Supabase, financasmais.com e o Sala de Sinais (este repositório)

Este documento explica **como o projeto `sala-sinais` se relaciona** com um sistema anterior em **financasmais.com** que costumava usar **Supabase**, e o que muda (ou não) no **DNS** e no **deploy** quando você passa para a arquitetura **FastAPI + engine** deste repositório.

> **Resumo em uma frase:** o **Supabase** pode ser o **Postgres** da API via `DATABASE_URL` / `SUPABASE_DB_URL` (ver **[SUPABASE_INTEGRACAO.md](SUPABASE_INTEGRACAO.md)**), mas **não substitui** a API Python, o **engine** nem o **MetaTrader 5**.

---

## Dois “mundos” que as pessoas confundem

| Aspecto | Sistema típico com **Supabase** (legado / outro app) | **Sala de Sinais** (`sala-sinais`, este repo) |
|--------|------------------------------------------------------|-----------------------------------------------|
| Backend HTTP | Edge Functions, ou frontend falando direto com Supabase | **`api/` — FastAPI (uvicorn)** na porta `8000` |
| Dados | Postgres + Auth + Realtime no Supabase | **`SQLite`** local por padrão; **Postgres Supabase** opcional (`DATABASE_URL`, ver [SUPABASE_INTEGRACAO.md](SUPABASE_INTEGRACAO.md)) |
| Lógica de mercado / sinais | Regras em JS/SQL ou funções serverless | **`engine/` — processo Python separado** (estratégia, webhook na API, MT5) |
| Painel web | App hospedado (Vercel, Lovable, etc.) + Supabase | **Cockpit** servido pela própria API (`cockpit/dist` em `/`) |
| Trading B3 | **Não** roda MT5 dentro do Supabase | **MT5 só no Windows**, na mesma máquina que o engine (idealmente) |
| Publicar em **financasmais.com** | DNS apontando para hosting estático / Supabase / outro SaaS | DNS apontando para **VPS**, **PaaS** ou **Cloudflare Tunnel → PC** (ver guias abaixo) |

**Conclusão:** migrar o domínio **financasmais.com** para este projeto **não** é “trocar a URL no Supabase”. É passar a servir **FastAPI + engine** (e, se quiser MT5, manter um **Windows** ligado).

---

## O que este repositório **não** contém

- Nenhum SDK Supabase client (Auth/Realtime/Storage) no cockpit — só conexão **Postgres** opcional na API.
- Nenhum deploy automático para Supabase Hosting ou Edge Functions.

Se você ainda tem usuários, tabelas ou um front antigo no Supabase, trate isso como **sistema legado** até migrar dados e desligar o app antigo de forma consciente (backup, export CSV, etc.).

---

## Supabase vs FastAPI + engine (por que não dá para “só usar Supabase”)

### O que o Supabase faz bem

- **Postgres** gerenciado, backups, SQL.
- **Auth** (e-mail, OAuth), **Storage**, **Realtime** para apps web clássicos.
- Hospedagem de **sites estáticos** ou integração com frontends JAMstack.

### O que o Sala de Sinais **precisa** além disso

1. **Processo long-running (`engine`)** — lê mercado (simulação ou MT5), calcula sinais, chama a API (`API_BASE_URL`), opcionalmente envia ordens.
2. **MetaTrader 5** — terminal Windows + conta demo/real; **impossível** instalar ou executar MT5 “dentro” do Supabase (não é VPS Windows sua).
3. **Um servidor HTTP contínuo** — uvicorn com REST, webhook, SQLite (hoje) e arquivos estáticos do cockpit.

Supabase **não** executa `python -m engine.main` 24/7 nem o terminal MT5. No máximo, no futuro, o Supabase **Postgres** poderia ser o banco **remoto** da API — ainda assim API + engine + (opcional) MT5 precisam rodar **fora** do Supabase.

Diagrama do stack **atual** (recomendado para entender o deploy):

```
[Navegador] → https://financasmais.com
                    ↓
         (DNS: VPS / PaaS / Cloudflare Tunnel)
                    ↓
         FastAPI :8000  ← SQLite, cockpit, /api/*
                    ↑
         engine (Python) ←→ MT5 (Windows, opcional)
```

Diagrama **com Postgres no Supabase** (opcional — ver [SUPABASE_INTEGRACAO.md](SUPABASE_INTEGRACAO.md)):

```
FastAPI + engine (+ MT5 no PC/VPS Windows)
        ↓ DATABASE_URL ou SUPABASE_DB_URL (postgresql+psycopg://...)
   Supabase Postgres (só banco)
```

---

## financasmais.com: mudança de DNS em relação ao host antigo

O domínio **financasmais.com** pode continuar registrado na **Hostinger** (ou outro registrador). O que muda é **para onde o DNS aponta**.

### Situações comuns

| Antes (host antigo) | O que o visitante via | Depois (Sala de Sinais) |
|---------------------|------------------------|-------------------------|
| **Parking Hostinger** (`cdn.hstgr.net`) | Página “domínio registrado” | Remover parking; apontar para **IP do VPS** ou **CNAME do túnel** |
| **Site estático / WordPress** no plano Website | Landing PHP/HTML | Mesmo plano pode ficar só **marketing**; o **app** fica em VPS/túnel/PaaS (ver [DEPLOY_HOSTINGER_SITE.md](DEPLOY_HOSTINGER_SITE.md)) |
| **Front + Supabase** (URL de outro deploy) | App antigo | Desligar ou manter em subdomínio; **apex/www** passam a apontar para **este** backend (FastAPI) |
| **Subdomínio `app.`** | Painel antigo | Pode reutilizar `app.financasmais.com` no túnel ou nginx — ver exemplos em `scripts/cloudflare-tunnel.yml.example` |

### Registros típicos **depois** da migração

- **VPS Linux/Windows:** registros **A** `@` e `www` → **IP público do VPS**; nginx/Caddy → `127.0.0.1:8000`.
- **PC em casa + túnel (MT5):** **CNAME** `www` (e/ou apex via Cloudflare) → `<tunnel-id>.cfargotunnel.com`, ou nameservers na **Cloudflare** + `cloudflared tunnel route dns` — guia completo: [CLOUDFLARE_TUNNEL_PASSO_A_PASSO.md](CLOUDFLARE_TUNNEL_PASSO_A_PASSO.md).

**Importante:** propagar DNS pode levar minutos a 48 h. Enquanto o DNS antigo ainda resolver, visitantes podem ver o **site legado** (Supabase/outro) — planeje janela de corte e TTL baixo se possível.

### Variáveis ao publicar no domínio

No `.env` de produção:

```env
API_HOST=0.0.0.0
CORS_ORIGINS=https://financasmais.com,https://www.financasmais.com
```

Com túnel, a API continua escutando em `127.0.0.1:8000` localmente; o `cloudflared` faz o bridge — **não** é necessário abrir porta 8000 no roteador.

---

## Cloudflare Tunnel continua válido

Nada na arquitetura FastAPI + engine **invalida** o túnel. É o caminho recomendado se você **não** quer VPS na Hostinger mas **quer MT5 no PC Windows**:

- [DEPLOY_HOSTINGER_SITE.md](DEPLOY_HOSTINGER_SITE.md) — caminho A (PC 24h + túnel)
- [CLOUDFLARE_TUNNEL_PASSO_A_PASSO.md](CLOUDFLARE_TUNNEL_PASSO_A_PASSO.md) — login, `sala-sinais`, DNS, serviço Windows
- `Sala-Sinais.bat` opção **8** ou `scripts/start-sala-sinais-web.ps1`

O túnel termina em **HTTP local na FastAPI**, independentemente de você usar SQLite hoje ou Postgres amanhã.

---

## Postgres / Supabase como banco (opcional, futuro)

Por padrão a API usa **SQLite** (`DATABASE_URL=sqlite+aiosqlite:///./data/sala_sinais.db` no `.env.example`).

Para o **Postgres do Supabase**, configure a URI em **`DATABASE_URL`** ou **`SUPABASE_DB_URL`** — passo a passo em **[SUPABASE_INTEGRACAO.md](SUPABASE_INTEGRACAO.md)**. Isso **não** migra sozinho dados do SQLite nem reativa Auth/Realtime do app antigo.

Benefícios se fizer isso depois:

- Backups gerenciados, acesso SQL remoto, réplica para BI.
- API + engine em VPS; banco na nuvem (Supabase ou outro Postgres).

Limitações que **permanecem**:

- Engine e MT5 **continuam** fora do Supabase.
- Latência rede API ↔ Postgres — aceitável para este MVP se a API e o DB estiverem na mesma região.

---

## MT5: o que **não** roda no Supabase

| Componente | Roda no Supabase? | Onde roda no Sala de Sinais |
|------------|-------------------|-----------------------------|
| MetaTrader 5 | **Não** | Windows (PC ou VPS Windows) |
| `engine` com `paper_mt5` / `live_mt5` | **Não** | Mesma máquina Windows que o MT5 (ideal) |
| `engine` em `simulation` | **Não** (precisa processo Python) | VPS Linux, PaaS, Docker, PC |
| FastAPI + cockpit | **Não** (não é produto Supabase) | VPS, PaaS, PC + túnel |

Para ordens reais ou demo via corretora, leia [MT5_EXECUCAO.md](MT5_EXECUCAO.md), [EXECUCAO_AUTOMATICA.md](EXECUCAO_AUTOMATICA.md) e [DEPLOY_FINANCASMAIS.md](DEPLOY_FINANCASMAIS.md) (VPS Windows vs Linux).

---

## Checklist de transição (Supabase/legado → sala-sinais)

1. [ ] Decidir onde rodam **API + engine** (VPS sim, PC+túnel com MT5, etc.).
2. [ ] Subir stack localmente; validar `http://127.0.0.1:8000/health` (ou rota equivalente).
3. [ ] Exportar dados do sistema antigo (Supabase) se ainda forem necessários — **não** há import automático no repo.
4. [ ] Ajustar **DNS** de financasmais.com: remover parking/host antigo; apontar para VPS ou túnel.
5. [ ] Configurar `CORS_ORIGINS` e `WEBHOOK_SECRET` em produção.
6. [ ] Se usar túnel: `cloudflared` **Healthy** + teste `https://financasmais.com`.
7. [ ] Comunicar usuários se Auth/contas mudaram (este projeto não usa Supabase Auth por padrão).

---

## Documentos relacionados

| Documento | Quando usar |
|-----------|-------------|
| [DEPLOY_FINANCASMAIS.md](DEPLOY_FINANCASMAIS.md) | VPS, nginx, systemd, DNS A record |
| [DEPLOY_HOSTINGER_SITE.md](DEPLOY_HOSTINGER_SITE.md) | Plano Website Hostinger, sem VPS, túnel ou PaaS |
| [CLOUDFLARE_TUNNEL_PASSO_A_PASSO.md](CLOUDFLARE_TUNNEL_PASSO_A_PASSO.md) | Publicar no PC com financasmais.com |
| [README.md](../README.md) | Visão geral e links |

---

## Perguntas frequentes

**Posso hospedar só o front no Supabase e a API na Hostinger?**  
Você *poderia* manter um front separado, mas o **cockpit oficial** já vem embutido na FastAPI. Dois fronts exigem CORS, rotas e deploy duplicados — fora do desenho padrão deste repo.

**O domínio continua na Hostinger?**  
Sim, o registrador pode ser Hostinger; só mudam **nameservers** (Cloudflare) ou **registros A/CNAME**.

**Substituir Supabase elimina custo?**  
Você troca custo Supabase por **VPS**, **eletricidade do PC 24h**, ou plano PaaS. SQLite local no VPS/PC não cobra banco gerenciado até você optar por Postgres.

**Git push publica financasmais.com?**  
Não. Só código no GitHub; o site muda quando **processos + DNS** estiverem corretos (igual aos outros guias de deploy).
