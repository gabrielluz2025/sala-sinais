# Deploy em financasmais.com (acesso web)

> **Sem VPS?** Se você quer usar só o plano **Website** da Hostinger (File Manager / WordPress) e **não** contratar VPS, leia **[DEPLOY_HOSTINGER_SITE.md](DEPLOY_HOSTINGER_SITE.md)** — PC Windows + Cloudflare Tunnel (MT5), landing + link, ou PaaS em simulação.

> **Importante:** enviar o código para o **GitHub** ou ler este guia **não** publica o site sozinho. O domínio só mostra o Sala de Sinais depois de **API + engine rodando 24/7** em algum lugar (VPS, PC+túnel, PaaS) e o **DNS** apontando para esse destino — **não** para o parking `cdn.hstgr.net`. Este guia foca em **VPS**; ninguém da Hostinger instala o Python por você; é SSH + comandos abaixo (ou [`scripts/bootstrap-vps-ubuntu.sh`](../scripts/bootstrap-vps-ubuntu.sh)).

Este guia explica como publicar o **Sala de Sinais** na internet — por exemplo em `https://financasmais.com` ou `https://app.financasmais.com` — **sem depender do duplo clique em `Sala-Sinais.bat`**. O `.bat` continua útil no seu PC Windows; no servidor você usa **systemd** (Linux) ou **Agendador de Tarefas** (Windows).

---

## Como o sistema funciona (arquitetura honesta)

| Componente | O que faz | Onde roda |
|------------|-----------|-----------|
| **`api/` (FastAPI)** | REST, SQLite, serve o **cockpit** (`cockpit/dist`) na porta configurada (padrão **8000**) | Qualquer OS com Python 3.11+ |
| **`engine/`** | Estratégia, sinais, opcionalmente **ordens no MetaTrader 5** | Processo **separado** da API |
| **MetaTrader 5** | Cotação e execução na corretora | **Somente Windows** (PC ou VPS Windows) |

Fluxo local (hoje):

1. `python -m api.main` → uvicorn em `API_HOST:API_PORT` (`.env`: `127.0.0.1:8000`).
2. `python -m engine.main` → lê `.env`, fala com a API via `API_BASE_URL` e, se `paper_mt5` / `live_mt5`, com o MT5 instalado na **mesma máquina Windows**.

O painel web usa a **mesma origem** do navegador (`window.location.host`), então atrás de um reverse proxy (nginx/Caddy) não precisa recompilar o cockpit — desde que `/` e `/api/*` (rotas FastAPI) estejam no mesmo domínio.

### Limite importante: MT5

- **Ordens reais ou demo via MT5** exigem **Windows + terminal MT5 logado** na mesma rede que o engine (idealmente mesma VM).
- Um **VPS Linux** na Hostinger roda **cockpit + API + engine em `ENGINE_MODE=simulation`** perfeitamente — **não** roda MT5 nativamente.
- Para MT5 “na nuvem”: **VPS Windows** (Hostinger ou outro) **ou** engine/MT5 no seu PC em casa e API na VPS via **VPN/tunnel** (WireGuard, Tailscale, etc.) — mais complexo, mas possível.

**MVP recomendado:** site abre o painel + API no VPS em **modo simulação**; MT5 fica para uma fase 2 (VPS Windows ou PC + túnel).

---

## O que comprar na Hostinger

| Objetivo | Produto Hostinger | Observação |
|----------|-------------------|------------|
| **Só site + simulação (MVP)** | **VPS Linux** (Ubuntu 22.04/24.04) | 2 vCPU / 4 GB RAM costuma bastar para API + engine sim + SQLite |
| **MT5 + ordens na mesma máquina** | **VPS Windows** (ou KVM Windows) | Licença Windows + MT5 da corretora; engine `paper_mt5` / `live_mt5` |
| **Só e-mail / landing estática** | Hospedagem “Website” | **Não** substitui VPS para este projeto (Python long-running + engine) |

O domínio **financasmais.com** pode ficar na Hostinger; o **servidor** que responde HTTP precisa ser o IP do VPS (não o parking `cdn.hstgr.net`).

---

## Caminhos recomendados

### A) VPS Windows — tudo junto (trading completo)

1. VPS Windows na Hostinger (ou equivalente).
2. Clone o repositório, Python 3.11+, `pip install -r requirements.txt`, `.env` com `API_HOST=0.0.0.0`, `ENGINE_MODE=paper_mt5` (demo primeiro).
3. Instale **MetaTrader 5** da corretora, logado na demo.
4. **IIS + ARR**, **Caddy** ou **nginx for Windows** na frente do uvicorn `:8000`, certificado SSL (Let’s Encrypt ou Hostinger SSL).
5. DNS: registro **A** `@` e **A** (ou **CNAME** `www`) apontando para o **IP público do VPS**.
6. Substitua o `.bat` por serviços Windows ou Agendador de Tarefas (ver [Substituir o Sala-Sinais.bat](#substituir-o-sala-sinaisbat-no-servidor)).

### B) VPS Linux — cockpit + API + simulação (MVP web)

1. VPS Linux Ubuntu.
2. Deploy do código (git clone), venv, `cockpit/dist` já no repo **ou** `npm run build` no servidor.
3. `.env` de produção (exemplo mínimo):

   ```env
   API_HOST=0.0.0.0
   API_PORT=8000
   WEBHOOK_SECRET=<string-longa-aleatoria>
   CORS_ORIGINS=https://financasmais.com,https://www.financasmais.com
   ENGINE_MODE=simulation
   API_BASE_URL=http://127.0.0.1:8000
   SIGNAL_MODE=paper
   LIVE_TRADING=false
   AUTO_EXECUTE_ORDERS=false
   ```

4. **nginx** (ou Caddy) → proxy para `127.0.0.1:8000` — ver [`deploy/nginx-sala-sinais.conf.example`](../deploy/nginx-sala-sinais.conf.example).
5. **systemd**: API + engine — ver [`deploy/systemd/`](../deploy/systemd/).
6. DNS **A** para `@` e `www` → IP do VPS.
7. (Opcional) MT5 em casa: PC Windows com engine + MT5; `API_BASE_URL=https://financasmais.com` **só se** o webhook/engine conseguir alcançar a API (VPN/tunnel; ajuste firewall).

### C) Subdomínio `app.financasmais.com`

Útil se o site principal (`@`) for WordPress ou landing na Hostinger:

1. No painel DNS, crie **A** `app` → IP do VPS (não use parking CDN).
2. No nginx, `server_name app.financasmais.com;` e certificado SSL só para esse host.
3. `CORS_ORIGINS=https://app.financasmais.com`.

---

## DNS na Hostinger — checklist (você clica, nós não configuramos)

**Situação típica hoje (parking):** nameservers tipo `dns-parking`, **ALIAS** `@` → `cdn.hstgr.net`, **CNAME** `www` → CDN. Isso **não** aponta para o seu Sala de Sinais.

**Para apontar ao VPS:**

1. Hostinger → **Domínios** → **financasmais.com** → **DNS / Zona DNS** (ou “Gerenciar DNS”).
2. **Remova ou edite** registros que apontam `@` / `www` para `cdn.hstgr.net` / parking (ALIAS/CNAME de estacionamento).
3. Adicione:
   - **Tipo A** | **Nome** `@` | **Aponta para** `<IP_PUBLICO_DO_VPS>` | TTL automático.
   - **Tipo A** | **Nome** `www` | **Aponta para** `<IP_PUBLICO_DO_VPS>`  
     *ou* **CNAME** `www` → `@` (se a Hostinger permitir CNAME para apex via alias, siga o que o painel sugerir).
4. (Opcional) **A** `app` → mesmo IP para subdomínio.
5. Aguarde propagação (minutos a algumas horas). Teste: `ping financasmais.com` deve mostrar o IP do VPS (não o CDN de parking).
6. **Firewall do VPS:** liberar **80** e **443** (HTTP/HTTPS); **não** exponha a porta 8000 na internet — só nginx local → uvicorn.

**Hostinger “Website” / construtor:** serve sites estáticos ou stacks gerenciadas limitadas. Este projeto precisa de **processo Python contínuo** + **segundo processo (engine)** → use **VPS**, não só o plano de site, salvo se a Hostinger oferecer VPS/container com SSH e você instalar manualmente (mesmo fluxo do caminho B).

---

## Deploy passo a passo (Linux MVP)

### 1. Servidor

```bash
sudo apt update && sudo apt install -y python3-venv python3-pip nginx certbot python3-certbot-nginx git
```

### 2. Código

```bash
sudo useradd -m -s /bin/bash sinais || true
sudo -u sinais git clone https://github.com/gabrielluz2025/sala-sinais.git /home/sinais/sala-sinais
cd /home/sinais/sala-sinais
sudo -u sinais python3 -m venv .venv
sudo -u sinais .venv/bin/pip install -r requirements.txt
sudo -u sinais cp .env.example .env
# Edite .env (nano) conforme seção B acima
```

Garanta `cockpit/dist/index.html` (build no repo ou `cd cockpit && npm ci && npm run build`).

### 3. systemd

```bash
sudo cp deploy/systemd/sala-sinais-api.service.example /etc/systemd/system/sala-sinais-api.service
sudo cp deploy/systemd/sala-sinais-engine.service.example /etc/systemd/system/sala-sinais-engine.service
# Ajuste User, WorkingDirectory e paths se necessário
sudo systemctl daemon-reload
sudo systemctl enable --now sala-sinais-api sala-sinais-engine
curl -s http://127.0.0.1:8000/health
```

### 4. nginx + SSL

```bash
sudo cp deploy/nginx-sala-sinais.conf.example /etc/nginx/sites-available/sala-sinais
sudo ln -sf /etc/nginx/sites-available/sala-sinais /etc/nginx/sites-enabled/
# Edite server_name e paths
sudo nginx -t && sudo systemctl reload nginx
sudo certbot --nginx -d financasmais.com -d www.financasmais.com
```

Abra `https://financasmais.com/` — deve carregar o Pulse Deck; engine em simulação deve aparecer online no painel após alguns segundos.

### 5. Docker (opcional)

Se preferir containers, veja [`docker-compose.prod.yml`](../docker-compose.prod.yml). **MT5 não roda dentro do container Linux**; use compose só para API + engine sim.

---

## Substituir o `Sala-Sinais.bat` no servidor

| Ambiente | API | Engine |
|----------|-----|--------|
| **Linux** | `sala-sinais-api.service` (systemd) | `sala-sinais-engine.service` |
| **Windows Server** | Agendador de Tarefas na inicialização: `cmd /c set PYTHONPATH=C:\...\sala-sinais&& C:\...\sala-sinais\.venv\Scripts\python.exe -m api.main` | Tarefa separada: `python -m engine.main` (MT5 aberto antes, se `paper_mt5`) |
| **Windows** | NSSM ou serviço WinSW envolvendo os mesmos comandos | Idem |

Equivalente à opção **1** do `.bat` (API + engine sim): duas unidades systemd habilitadas no boot.

---

## Segurança mínima em produção

- Troque `WEBHOOK_SECRET` por valor longo e aleatório; engine e API usam o mesmo segredo.
- Mantenha `LIVE_TRADING=false` até passar por [MODO_REAL.md](MODO_REAL.md) e demo.
- Restrinja SSH (chave, não senha); considere **fail2ban**.
- Backup de `data/sala_sinais.db` e `.env`.
- Disclaimers educacionais se o site for público ([README](../README.md)).

---

## Resumo rápido

| Pergunta | Resposta |
|----------|----------|
| O que comprar? | **VPS Linux** (MVP web + sim) ou **VPS Windows** (MT5 + ordens). |
| DNS? | Tirar parking CDN; **A** `@` e `www` → IP do VPS; opcional **A** `app`. |
| Primeiro MVP? | Cockpit + API + engine **simulation** no VPS; HTTPS via nginx + Certbot. |
| MT5 na Hostinger Linux? | **Não** nativo; use Windows VPS ou MT5 em outro lugar + túnel. |
| Quem configura o painel Hostinger? | **Você**, seguindo o checklist acima — este repositório não tem acesso à sua conta. |

Arquivos de apoio no repo:

- [DEPLOY_HOSTINGER_SITE.md](DEPLOY_HOSTINGER_SITE.md) — deploy **sem VPS** (Website Hostinger + túnel / PaaS)
- [`scripts/cloudflare-tunnel.example.yml`](../scripts/cloudflare-tunnel.example.yml) — exemplo Cloudflare Tunnel no PC Windows
- [`deploy/nginx-sala-sinais.conf.example`](../deploy/nginx-sala-sinais.conf.example)
- [`deploy/systemd/sala-sinais-api.service.example`](../deploy/systemd/sala-sinais-api.service.example)
- [`deploy/systemd/sala-sinais-engine.service.example`](../deploy/systemd/sala-sinais-engine.service.example)
- [`docker-compose.prod.yml`](../docker-compose.prod.yml)
