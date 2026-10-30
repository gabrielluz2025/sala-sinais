# Deploy no financasmais.com **sem VPS** (plano Website Hostinger)

Você quer usar o **domínio na Hostinger** com o plano **Website / hospedagem compartilhada** (File Manager, WordPress, construtor, parking `cdn.hstgr.net`) — **sem** contratar um **VPS**. Este guia explica o que isso implica de forma direta e quais caminhos **funcionam** para o Sala de Sinais.

> **Relacionado:** se no futuro você aceitar um VPS, use [DEPLOY_FINANCASMAIS.md](DEPLOY_FINANCASMAIS.md). Este documento é só para **“meu site na Hostinger” + sem VPS clássico**.

---

## Por que o plano “Website” sozinho não basta

O Sala de Sinais **não** é um site estático (HTML no File Manager). Ele precisa de:

| Necessidade | O que o projeto usa |
|-------------|---------------------|
| Servidor HTTP contínuo | **FastAPI** (`python -m api.main` / uvicorn) |
| Processo em segundo plano | **Engine** (`python -m engine.main`) — estratégia, sinais, gravação na API |
| (Opcional) Trading | **MetaTrader 5** no **Windows**, na mesma máquina que o engine |

No seu PC, o [`Sala-Sinais.bat`](../Sala-Sinais.bat) sobe **dois processos Python** (API + engine) e mantém tudo rodando. Isso é o oposto do que a hospedagem **Website** oferece:

- **Parking / CDN** (`cdn.hstgr.net`): só mostra página de “domínio registrado” ou site estático — **não** executa uvicorn 24/7.
- **WordPress / construtor**: PHP + MySQL gerenciados — **não** há suporte oficial para você deixar `uvicorn` + `engine` rodando como no `.bat`.
- **File Manager**: ideal para `.html`, `.css`, imagens — **não** substitui um processo Python long-running com SQLite e webhook.

**Conclusão honesta:** colocar só arquivos do projeto no File Manager **não** publica o painel completo nem mantém o engine online. Para o app **inteiro** na internet, alguma máquina (ou PaaS) precisa rodar Python **sempre ligado** — ou você usa o PC em casa + túnel (caminho A).

---

## Visão dos caminhos viáveis (sem VPS Hostinger)

| Caminho | MT5 / ordens reais | Custo extra | Domínio financasmais.com |
|---------|-------------------|-------------|---------------------------|
| **A) PC Windows 24h + Cloudflare Tunnel** | **Sim** (MT5 no mesmo PC) | Grátis (tunnel) ou ngrok pago | CNAME → túnel |
| **B) Hostinger só landing + link** | Não (só marketing) | Só plano Website | Site estático; app em outro URL |
| **C) PaaS (Render, Railway, Fly.io)** | **Não** nativo (só **simulação**) | Plano free/low cloud | CNAME ou subdomínio |
| **D) SSH + Python no plano Website** | Improvável | — | Só se seu plano **realmente** permitir |

---

## A) PC Windows em casa (24h) + Cloudflare Tunnel — **recomendado se você recusa VPS e quer MT5**

Tudo roda **no seu computador**, como hoje com o `.bat`. A internet acessa via **túnel** — **sem** abrir porta no roteador e **sem** IP fixo obrigatório.

### Arquitetura

```
Navegador → https://financasmais.com
         → Cloudflare (DNS + túnel)
         → cloudflared no PC
         → http://127.0.0.1:8000 (FastAPI + cockpit)
Engine + MT5 no mesmo PC → API em localhost
```

### Pré-requisitos

- PC **Windows** ligado durante o pregão (ou 24h se quiser painel sempre online).
- Conta **Cloudflare** (grátis) com domínio **financasmais.com** usando nameservers da Cloudflare **ou** DNS na Hostinger com CNAME para o túnel (veja abaixo).
- Python 3.11+, repo clonado, `.env` configurado.
- [`cloudflared`](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/) instalado no Windows.

### 1. Subir API + engine no PC

Equivalente à opção **1** do menu:

```bat
Sala-Sinais.bat all
```

Ou manualmente (dois terminais ou tarefas agendadas na inicialização):

```bat
set PYTHONPATH=C:\caminho\sala-sinais
C:\caminho\sala-sinais\.venv\Scripts\python.exe -m api.main
```

```bat
set PYTHONPATH=C:\caminho\sala-sinais
C:\caminho\sala-sinais\.venv\Scripts\python.exe -m engine.main
```

No `.env` para uso com túnel (mesma origem no navegador):

```env
API_HOST=127.0.0.1
API_PORT=8000
API_BASE_URL=http://127.0.0.1:8000
CORS_ORIGINS=https://financasmais.com,https://www.financasmais.com
WEBHOOK_SECRET=<string-longa-aleatoria>
```

Para MT5: `ENGINE_MODE=paper_mt5` (demo primeiro), terminal MT5 aberto e logado **neste PC**.

Teste local: `http://127.0.0.1:8000/health` deve responder antes de configurar o túnel.

### 2. Criar túnel na Cloudflare

No painel Cloudflare → **Zero Trust** / **Networks** → **Tunnels** → **Create a tunnel** → conector **Windows**. Copie o comando de instalação ou use token.

Checklist detalhado: [**CLOUDFLARE_TUNNEL_PASSO_A_PASSO.md**](CLOUDFLARE_TUNNEL_PASSO_A_PASSO.md). Exemplo de config: [`scripts/cloudflare-tunnel.yml.example`](../scripts/cloudflare-tunnel.yml.example).

```powershell
cloudflared tunnel login
cloudflared tunnel create sala-sinais
cloudflared tunnel route dns sala-sinais financasmais.com
cloudflared tunnel route dns sala-sinais www.financasmais.com
cloudflared tunnel --config C:\caminho\sala-sinais\scripts\cloudflare-tunnel.example.yml run sala-sinais
```

Registre o `cloudflared` como **serviço Windows** para subir com o PC:

```powershell
cloudflared service install
```

(Use o config path correto conforme a documentação da versão instalada.)

### 3. DNS na Hostinger (sem mudar nameservers)

Se o DNS continuar na **Hostinger** (não na Cloudflare):

1. **hPanel** → **Domínios** → **financasmais.com** → **DNS**.
2. Remova **ALIAS/CNAME de parking** (`cdn.hstgr.net`) em `@` e `www` quando for publicar o app.
3. Cloudflare Tunnel fornece um host tipo `<tunnel-id>.cfargotunnel.com`.
4. Crie **CNAME** | **Nome** `@` ou `www` | **Destino** `<tunnel-id>.cfargotunnel.com`  
   - Alguns painéis **não** permitem CNAME no apex (`@`); nesse caso use **www** com CNAME e redirecione `@` → `www`, **ou** migre o DNS para Cloudflare (recomendado para túnel).

### 4. Segurança

- Não exponha a porta **8000** no roteador; só o túnel.
- `WEBHOOK_SECRET` forte; `LIVE_TRADING=false` até [MODO_REAL.md](MODO_REAL.md).
- PC em casa = single point of failure (queda de luz, Windows Update reiniciando). Considere UPS e tarefas agendadas para religar API/engine.

### Alternativa: ngrok

Mesma ideia: `ngrok http 8000` com domínio reservado no plano pago. DNS: CNAME para o hostname ngrok. Menos integrado que Cloudflare, mas válido se você já usa ngrok.

---

## B) Hostinger **só landing** + link para o app

Use o plano **Website** para o que ele faz bem:

- Página em **financasmais.com** (WordPress ou HTML): explicação educacional, disclaimer, botão **“Abrir painel”**.
- O painel real fica em **outro endereço**:
  - subdomínio via túnel: `https://app.financasmais.com` (PC + Cloudflare), ou
  - URL do PaaS: `https://sala-sinais.onrender.com` (caminho C).

**Limitação:** usuários não abrem o cockpit em `@` sem redirecionamento ou proxy — só a landing. O engine **não** roda na hospedagem compartilhada.

---

## C) PaaS (Render, Railway, Fly.io) — **sem VPS**, mas **nuvem**; **só simulação** (sem MT5)

Plataformas rodam containers/processos Python 24/7 **sem** você administrar um VPS. **Não** rodam MetaTrader 5.

Fluxo típico:

1. Conectar repositório GitHub ao serviço.
2. **Web service:** comando `python -m api.main`, porta `$PORT` (ajuste `API_HOST=0.0.0.0` e leia `PORT` se o PaaS exigir).
3. **Worker / segundo service:** `python -m engine.main` com `ENGINE_MODE=simulation`.
4. Volume persistente ou backup para `data/sala_sinais.db` (cada PaaS documenta volumes).
5. DNS: **CNAME** `app.financasmais.com` → hostname do PaaS; SSL no provedor.

`.env` mínimo (produção sim):

```env
ENGINE_MODE=simulation
SIGNAL_MODE=paper
LIVE_TRADING=false
AUTO_EXECUTE_ORDERS=false
CORS_ORIGINS=https://app.financasmais.com
```

Arquivos de referência no repo: [`deploy/systemd/`](../deploy/systemd/), [`docker-compose.prod.yml`](../docker-compose.prod.yml) (adaptar para o PaaS).

**Quando escolher:** você quer site público **sem** PC ligado e **aceita** operar só em simulação até ter VPS Windows ou PC+túnel para MT5.

---

## D) Meu plano Hostinger tem **SSH + Python**?

Em planos **Website** comuns (**Single**, **Premium**, **Business** web hosting), **não** há SSH com daemon Python 24/7 como em VPS. Em raros upgrades ou produtos híbridos, pode aparecer **SSH limitado** — ainda assim costuma **proibir** processos long-running e matar jobs idle.

### Como verificar no hPanel

1. Entre em **hostinger.com** → **hPanel**.
2. **Websites** → selecione o site ligado a **financasmais.com**.
3. Procure:
   - **SSH Access** / **Acesso SSH** — se **não existir**, não há caminho D.
   - **Advanced** → **PHP Configuration** — indica stack PHP, não FastAPI nativo.
4. Em **Plan details** / **Detalhes do plano**, confira se o produto é **Web hosting** ou **VPS**. Se for **VPS**, use [DEPLOY_FINANCASMAIS.md](DEPLOY_FINANCASMAIS.md) (não é “site sem VPS”).
5. Se SSH existir, teste: `python3 --version`. Mesmo com Python, pergunte ao suporte Hostinger se **processos em background permanentes** (uvicorn + worker) são permitidos — na prática, a resposta costuma ser **não** em shared hosting.

**Se a resposta for não:** use caminho **A** (PC + túnel) ou **C** (PaaS).

---

## O que **não** fazer (expectativa)

| Ação | Resultado |
|------|-----------|
| Upload da pasta `api/` no File Manager | Arquivos mortos; Python não executa |
| Só trocar DNS para parking CDN | Página Hostinger, **não** o painel |
| Esperar que WordPress plugin rode o engine | Fora do desenho do projeto |
| Git push sem PC/PaaS/VPS rodando | Código no GitHub; **financasmais.com** não muda sozinho |

---

## Recomendações práticas

| Seu objetivo | Caminho |
|--------------|---------|
| **financasmais.com** + **MT5** + **sem VPS** | **A** — PC Windows + Cloudflare Tunnel + `.bat`/tarefas agendadas |
| Domínio só marketing; app em subdomínio sim | **B** + **C** |
| App 24/7 na nuvem sem administrar servidor; sem MT5 | **C** — PaaS + `ENGINE_MODE=simulation` |
| Tudo na Hostinger com controle total | Contratar **VPS** (Linux sim ou Windows MT5) — [DEPLOY_FINANCASMAIS.md](DEPLOY_FINANCASMAIS.md) |

---

## Checklist rápido (caminho A)

- [ ] API + engine respondem em `http://127.0.0.1:8000`
- [ ] `cloudflared` instalado e túnel **Healthy**
- [ ] DNS: parking removido; CNAME ou Cloudflare DNS apontando ao túnel
- [ ] HTTPS abre o Pulse Deck em `https://financasmais.com`
- [ ] MT5 aberto no PC se usar `paper_mt5` / `live_mt5`
- [ ] PC configurado para não dormir durante pregão; serviços/tarefas na inicialização

---

## Arquivos de apoio

- [CLOUDFLARE_TUNNEL_PASSO_A_PASSO.md](CLOUDFLARE_TUNNEL_PASSO_A_PASSO.md) — passo a passo túnel + DNS
- [`scripts/cloudflare-tunnel.yml.example`](../scripts/cloudflare-tunnel.yml.example) — ingress para porta 8000
- [DEPLOY_FINANCASMAIS.md](DEPLOY_FINANCASMAIS.md) — VPS, nginx, systemd
- [MODO_REAL.md](MODO_REAL.md) — antes de trading real
