# Cloudflare Tunnel — financasmais.com no seu PC (sem VPS)

Guia passo a passo em português para publicar o **Sala de Sinais** em `https://financasmais.com` e `https://www.financasmais.com` usando **Cloudflare Tunnel** (`cloudflared`). A **API** e o **engine** rodam no **Windows** em casa; o domínio aponta para o túnel — **sem** abrir porta no roteador e **sem** VPS na Hostinger.

> Contexto **Supabase / site antigo** no mesmo domínio: [DEPLOY_SUPABASE_E_DOMINIO.md](DEPLOY_SUPABASE_E_DOMINIO.md).

> Visão geral dos caminhos (landing Hostinger, PaaS, etc.): [DEPLOY_HOSTINGER_SITE.md](DEPLOY_HOSTINGER_SITE.md).

---

## O que você vai ter no final

```
Navegador → https://financasmais.com
         → Cloudflare (DNS + TLS)
         → cloudflared no seu PC
         → http://127.0.0.1:8000 (FastAPI + Pulse Deck)
Engine (+ MT5 opcional) no mesmo PC → API em localhost
```

---

## Pré-requisitos no PC

- [ ] Windows 10/11, Python 3.11+, repositório clonado, `.venv` criado (`Sala-Sinais.bat` opção 1 uma vez).
- [ ] Domínio **financasmais.com** registrado (Hostinger ou outro).
- [ ] PC ligado durante o pregão (ou 24h se quiser painel sempre online).
- [ ] MetaTrader 5 no mesmo PC se usar `ENGINE_MODE=paper_mt5` ou `live_mt5`.

---

## Parte 1 — Conta Cloudflare e domínio

### Opção A — DNS na Cloudflare (recomendado para túnel)

1. Crie conta grátis em [https://dash.cloudflare.com/sign-up](https://dash.cloudflare.com/sign-up).
2. **Add a site** → digite `financasmais.com` → plano **Free**.
3. Cloudflare mostra **dois nameservers** (ex.: `ada.ns.cloudflare.com` e `bob.ns.cloudflare.com`).
4. Na **Hostinger**: **hPanel** → **Domínios** → **financasmais.com** → **DNS / Nameservers** → **Alterar nameservers** → cole os da Cloudflare → salve.
5. Aguarde propagação (minutos a 48h). No Cloudflare, o site deve ficar **Active**.

### Opção B — DNS continua na Hostinger (só CNAME)

1. Crie conta Cloudflare e o túnel (Parte 3); anote o host `<TUNNEL_ID>.cfargotunnel.com`.
2. **hPanel** → **DNS** do domínio:
   - Remova registros de **parking** (`cdn.hstgr.net`) em `@` e `www` quando for publicar o app.
   - **CNAME** `www` → `<TUNNEL_ID>.cfargotunnel.com`.
   - Apex `@`: muitos painéis **não** permitem CNAME em `@` — use redirecionamento `@` → `www` ou migre para Opção A.

---

## Parte 2 — Instalar `cloudflared` no Windows

1. Baixe o instalador oficial: [Cloudflare Tunnel downloads](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/).
2. Escolha **Windows** (64-bit), instale ou extraia `cloudflared.exe`.
3. Coloque `cloudflared` no **PATH** (instalador MSI costuma fazer isso) ou use caminho completo.
4. Abra **PowerShell** e confira:

```powershell
cloudflared --version
```

---

## Parte 3 — Login, criar túnel e DNS

Execute no PowerShell (**você** precisa fazer login no navegador — o agente não pode fazer isso por você):

```powershell
cloudflared tunnel login
```

- Abre o browser → escolha a zona **financasmais.com** → autorize.

```powershell
cloudflared tunnel create sala-sinais
```

- Anote o **UUID** do túnel (aparece na saída e em `%USERPROFILE%\.cloudflared\<UUID>.json`).

Rotas DNS (se DNS estiver na Cloudflare — Opção A):

```powershell
cloudflared tunnel route dns sala-sinais financasmais.com
cloudflared tunnel route dns sala-sinais www.financasmais.com
```

Se usar só Hostinger (Opção B), crie os CNAME manualmente (Parte 1B) em vez desses comandos.

---

## Parte 4 — Arquivo de configuração (`config.yml`)

1. Copie o exemplo do repositório:

```powershell
Copy-Item "C:\caminho\sala-sinais\scripts\cloudflare-tunnel.yml.example" "$env:USERPROFILE\.cloudflared\config.yml"
```

   Ou copie para o projeto:

```powershell
Copy-Item "C:\caminho\sala-sinais\scripts\cloudflare-tunnel.yml.example" "C:\caminho\sala-sinais\scripts\cloudflare-tunnel.yml"
```

2. Edite o arquivo copiado:
   - `tunnel:` → substitua `TUNNEL_ID` pelo **UUID** real.
   - `credentials-file:` → caminho do JSON, ex.: `C:\Users\SEU_USUARIO\.cloudflared\<UUID>.json`.

O **ingress** já aponta para a API local:

```yaml
ingress:
  - hostname: financasmais.com
    service: http://127.0.0.1:8000
  - hostname: www.financasmais.com
    service: http://127.0.0.1:8000
  - service: http_status:404
```

3. Teste o túnel (API ainda pode estar parada — só valida o conector):

```powershell
cloudflared tunnel --config "$env:USERPROFILE\.cloudflared\config.yml" run sala-sinais
```

Status **Healthy** no painel: **Zero Trust** → **Networks** → **Tunnels** → `sala-sinais`.

### (Opcional) Serviço Windows — túnel sobe com o PC

Depois que o config estiver correto:

```powershell
cloudflared service install
```

Use a documentação da sua versão se precisar passar `--config` no serviço. Muitos usuários preferem `scripts\start-cloudflare-tunnel.ps1` ou opção **8** do `Sala-Sinais.bat` em vez do serviço.

---

## Parte 5 — `.env` para produção via túnel

Edite `.env` na raiz do projeto (veja também `.env.example`):

```env
API_HOST=0.0.0.0
API_PORT=8000
API_BASE_URL=http://127.0.0.1:8000
CORS_ORIGINS=https://financasmais.com,https://www.financasmais.com
WEBHOOK_SECRET=<string-longa-aleatoria>
LIVE_TRADING=false
```

- `API_HOST=0.0.0.0` ou `127.0.0.1`: o túnel fala com `127.0.0.1:8000`; **não** exponha a porta 8000 no roteador.
- `CORS_ORIGINS` deve incluir o **https** do domínio público.

Teste **antes** do túnel:

```powershell
# Com API rodando (opção 1 ou 8 do .bat)
Invoke-WebRequest -Uri http://127.0.0.1:8000/health -UseBasicParsing
```

---

## Parte 6 — Subir tudo (API + engine + túnel)

### Pelo menu

```bat
Sala-Sinais.bat
```

Escolha **8 — Modo web (domínio)**.

### Pelo PowerShell

```powershell
cd C:\caminho\sala-sinais
powershell -ExecutionPolicy Bypass -File .\scripts\start-sala-sinais-web.ps1
```

Só o túnel (API/engine já rodando):

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\start-cloudflare-tunnel.ps1
```

---

## Checklist final

- [ ] `http://127.0.0.1:8000/health` responde com API + engine no ar.
- [ ] `cloudflared` com config ajustado; túnel **Healthy** no painel Cloudflare.
- [ ] DNS: nameservers Cloudflare **ou** CNAME `www` → `.cfargotunnel.com`; parking Hostinger removido.
- [ ] `https://financasmais.com` abre o Pulse Deck (pode levar alguns minutos após DNS).
- [ ] MT5 aberto e logado se usar `paper_mt5` / `live_mt5`.
- [ ] PC não entra em suspensão durante o pregão; considere UPS.

---

## Segurança

- Não faça port forward da porta **8000** no roteador.
- `WEBHOOK_SECRET` forte; leia [MODO_REAL.md](MODO_REAL.md) antes de trading real.
- PC em casa = ponto único de falha (luz, update do Windows).

---

## Arquivos no repositório

| Arquivo | Uso |
|---------|-----|
| [scripts/cloudflare-tunnel.yml.example](../scripts/cloudflare-tunnel.yml.example) | Modelo de `config.yml` |
| [scripts/cloudflare-tunnel.example.yml](../scripts/cloudflare-tunnel.example.yml) | Mesmo conteúdo (nome alternativo) |
| [scripts/start-sala-sinais-web.ps1](../scripts/start-sala-sinais-web.ps1) | API + engine + túnel opcional |
| [scripts/start-cloudflare-tunnel.ps1](../scripts/start-cloudflare-tunnel.ps1) | Só `cloudflared` |
| [DEPLOY_HOSTINGER_SITE.md](DEPLOY_HOSTINGER_SITE.md) | Contexto Hostinger sem VPS |

---

## Solução de problemas

| Sintoma | O que verificar |
|---------|------------------|
| 502 / erro Cloudflare | API parada; `/health` local falha |
| Túnel unhealthy | UUID/credentials-file errados no yml |
| CORS no browser | `CORS_ORIGINS` com `https://financasmais.com` |
| Só `www` funciona | Apex `@` na Hostinger sem CNAME — use Opção A ou redirect |
| `cloudflared` não encontrado | PATH ou reinstale o binário |
