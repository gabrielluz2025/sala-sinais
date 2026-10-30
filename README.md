# Sala de Sinais (WIN) — MVP

Painel v2 dinâmico — onboarding, zonas claras e gráficos ao vivo para treinar em simulação antes do modo real.

Sistema educacional de sinais com **MetaTrader 5 + Python**: engine lê o mini-índice, gera alertas, grava na API, opcionalmente envia ordens na **sua** conta (demo primeiro) e exibe um painel web.

## Pré-requisitos

- Windows com **MetaTrader 5** instalado e **conta demonstração** logada
- Python 3.11+
- Símbolo do WIN no Market Watch (copie o nome exato para `MT5_SYMBOL`)

## Instalação rápida

```powershell
cd C:\Users\xgame\sala-sinais
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
```

Edite `.env`: `MT5_SYMBOL` (nome exato do WIN no MT5).

## Acesso web (financasmais.com / VPS)

Para abrir o painel **pelo site** (sem depender do `.bat` no PC), publique a API atrás de nginx/Caddy num VPS e aponte o DNS do domínio para o servidor. **Modo simulação** funciona em VPS Linux; **ordens MT5** exigem Windows + MetaTrader na mesma máquina (ou túnel).

Guia completo: **[docs/DEPLOY_FINANCASMAIS.md](docs/DEPLOY_FINANCASMAIS.md)** — DNS Hostinger, systemd, SSL e limites do MT5. **Sem VPS (só plano Website):** **[docs/DEPLOY_HOSTINGER_SITE.md](docs/DEPLOY_HOSTINGER_SITE.md)** — PC + Cloudflare Tunnel ou PaaS.

## Abrir o sistema (mais fácil)

**Duplo clique** em [`Sala-Sinais.bat`](Sala-Sinais.bat) — menu interativo (opção **1** = API + engine + painel, recomendado).

Atalhos na linha de comando: `Sala-Sinais.bat all` | `sistema` | `engine` | `simulacao` | `mt5` | `corretora` | `real`.

- Instala dependências na primeira vez
- Sobe a API e abre o painel no navegador
- **Hoje (sem MT5):** opção **4** ou `simulacao` com `ENGINE_MODE=simulation` no `.env`
- **Depois (cotação real):** opção **3** ou `engine` com MT5 aberto (`paper_mt5` ou `live_mt5`)

Guia completo da simulação: **[docs/SIMULACAO.md](docs/SIMULACAO.md)**.

**Compra/venda automática na corretora (MT5, demo primeiro):** **[docs/EXECUCAO_AUTOMATICA.md](docs/EXECUCAO_AUTOMATICA.md)** — ou `Sala-Sinais.bat` opção **6 → a** / `corretora`.

O painel inclui gráfico de equity, PnL líquido (taxas B3/corretagem), pausar/retomar engine, zerar posição (com engine + LIVE), notícias RSS e checklist de modo real.

- **Ações B3:** na seção *Configurar*, busque o ticker — perfil Moderado e parâmetros já vêm prontos; veja [docs/ACOES_BR.md](docs/ACOES_BR.md).

Você pode criar um atalho do **`Sala-Sinais.bat`** na Área de Trabalho (botão direito → Enviar para → Área de trabalho). Resumo: [`LEIA-ME-ATALHOS.txt`](LEIA-ME-ATALHOS.txt).

## Validar MT5

Com o terminal aberto e logado:

```powershell
$env:PYTHONPATH = "."
python -m engine.scripts.check_mt5
```

## Modo real (conta com dinheiro)

**Não** ative `LIVE_TRADING=true` sem ler o guia e rodar o preflight:

```powershell
python -m engine.scripts.preflight_live
```

Ou `Sala-Sinais.bat` opção **6 → b** / `real`. Passo a passo completo: **[docs/MODO_REAL.md](docs/MODO_REAL.md)**.

## Manual (alternativa aos .bat)

```powershell
.\run_api.ps1          # API + painel em http://127.0.0.1:8000/
.\run_engine.ps1       # engine MT5
```

- `SIGNAL_MODE=paper` — só registra sinais (sem ordens)
- `SIGNAL_MODE=live` + `LIVE_TRADING=true` — envia ordens no MT5 (use **demo** primeiro)

## Checklist antes de conta real

- [ ] Backtest / simulação na demo por vários dias
- [ ] RLP ativo na corretora (corretagem zero em minis)
- [ ] `LIVE_TRADING` só quando você entender o risco
- [ ] Disclaimers educacionais em qualquer canal público
- [ ] Consultoria jurídica se for cobrar assinatura

## Estrutura

| Pasta    | Função                          |
|----------|---------------------------------|
| `engine/` | Estratégia, risco, MT5, execução |
| `api/`    | FastAPI, SQLite, painel         |
| `web/`    | Painel de sinais                |
| `shared/` | Contrato JSON (Pydantic)        |

## Documentação

- [docs/DEPLOY_FINANCASMAIS.md](docs/DEPLOY_FINANCASMAIS.md) — deploy web (financasmais.com), DNS, nginx, systemd
- [docs/DEPLOY_HOSTINGER_SITE.md](docs/DEPLOY_HOSTINGER_SITE.md) — financasmais.com no plano Website Hostinger, sem VPS
- [docs/EXECUCAO_AUTOMATICA.md](docs/EXECUCAO_AUTOMATICA.md) — MT5 da corretora, `paper_mt5`, ordens em demo
- [docs/MODO_REAL.md](docs/MODO_REAL.md) — preflight, `.env` live, emergência e IR
- [docs/ROADMAP.md](docs/ROADMAP.md) — modo real, taxas/PnL, pausar engine, limitações e fase 2

## Aviso legal

Este projeto é infraestrutura técnica. Não garante lucro. Operações na B3 envolvem risco de perda total do capital alocado.
