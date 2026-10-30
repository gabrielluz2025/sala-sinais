# Execução de ordens no MT5 (demo / paper)

Este guia descreve como fazer a **Sala de Sinais** enviar ordens reais ao **MetaTrader 5** na conta **demo** (ex.: Clear), não apenas registrar sinais no SQLite.

## Pré-requisitos

1. **MetaTrader 5** instalado (terminal da corretora, ex. Clear).
2. Login na **conta demo** no MT5 e **Negociação algorítmica** ligada: na barra de ferramentas do MT5, o botão **AlgoTrading** / **Negociação algorítmica** deve ficar **verde (ON)**. Com ele desligado, `order_send` via API Python falha com **retcode 10027** (*AutoTrading disabled by client*).
3. Ativo no **Market Watch** (ex.: `PETR4` — o sistema tenta variantes como `PETR4F`).
4. **API** FastAPI rodando (`Iniciar-API.bat` ou equivalente).
5. **Engine** rodando com MT5 (`Sala-Sinais.bat` opção **3** ou `engine`) para cotação, heartbeat e execução automática de sinais da estratégia.

## .env recomendado (demo Clear, paper_mt5)

```env
ENGINE_MODE=paper_mt5
SIGNAL_MODE=live
LIVE_TRADING=false
AUTO_EXECUTE_ORDERS=true
EXECUTE_ON_DEMO=true
API_BASE_URL=http://127.0.0.1:8000
```

Opcional (recomendado com várias instalações ou Clear): aponte para o executável da corretora:

```env
MT5_PATH=C:\Program Files\Clear Investimentos MT5 Terminal\terminal64.exe
```

Engine e API leem o mesmo `.env`. Se `MT5_PATH` não coincidir com o terminal que a API Python anexou, `/system/execution-status` reporta `mt5_path_mismatch`.

## Reiniciar após mudar o .env

1. Pare o engine (Ctrl+C na janela do engine).
2. Reinicie a API se ela estiver rodando.
3. Abra o MT5 e confirme login demo.
4. Execute `Sala-Sinais.bat engine` de novo (ou opção **3** no menu).
5. Atualize o Pulse Deck / painel web.

## Como verificar no painel

1. Aba **Sistema** → seção **Execução MT5**: checklist verde e “Pode executar (MT5): Sim”.
2. `GET /system/execution-status` → `can_execute: true`, `blockers: []`.
3. Aba **Negociação** do MT5: posições/deals após ordem.
4. Boleta **Comprar/Vender** em `PETR4`: mensagem “Ordem enviada ao MT5” ou log **ORDEM** no console da engine/painel.

## Fluxos de execução

| Origem | Comportamento |
|--------|----------------|
| Sinal da estratégia (engine) | Após `POST /signals`, engine chama `place_market_order` se a política permitir. |
| Boleta / `POST /orders/execute` | Registra sinal e, se `should_send_manual_order_to_mt5`, envia ordem imediata via MT5 (processo da **API** inicializa MT5). |
| `ENGINE_MODE=simulation` | Apenas SQLite — sem MT5. |

## Segurança

- **`LIVE_TRADING=true`** envia ordens em conta **real** (com checklist em `docs/MODO_REAL.md`).
- **`EXECUTE_ON_DEMO=true`** só faz sentido com **`ENGINE_MODE=paper_mt5`** e conta demo.
- Use **flatten / pausar engine** antes de testes arriscados.
- Demo ainda simula slippage e rejeições — trate como ambiente de teste, não garantia de lucro.

## ZERAR TUDO vs REALIZADO no painel

**ZERAR TUDO** (`POST /system/flatten`) fecha **posições abertas** na base, cancela sinais pendentes e **pausa o motor** (`engine_paused=true`) para evitar novas entradas acidentais. O MT5 fica sem posição aberta; o **MTM ABERTO** zera.

O KPI **REALIZADO** (e o número de trades fechados no dia) **não** é apagado pelo **ZERAR TUDO**: soma o P&amp;L dos trades **já fechados** no histórico. Zerar posição ≠ apagar histórico contábil. Para **zerar KPIs sem apagar o banco**, use **Limpar histórico de sessão** (ou `POST /system/reset-session`). Para voltar a operar após ZERAR, clique **Retomar** no Pulse Deck (ou `PATCH /system/state` com `engine_paused: false`).

## Problemas comuns

| Sintoma | Ação |
|---------|------|
| Sinal fica `sent` sem deal no MT5 | Confira `SIGNAL_MODE=live`, `EXECUTE_ON_DEMO=true`, engine online, aba Sistema sem bloqueios. |
| “Símbolo PETR4 não encontrado” | Adicione PETR4 no Market Watch; veja nome exato no MT5. |
| MT5 desconectado no painel | MT5 aberto + engine rodando (heartbeat). |
| Boleta só SQLite | Política bloqueou — leia `blockers` em `/system/execution-status`. Reinicie a **API** após mudar `.env` (`SIGNAL_MODE=live`). |
| Volume inválido (ações) | Use múltiplos de **100 ações** (ex.: qty 100). `contracts=1` tende a ser rejeitado no MT5. |
| retcode stops | SL/TP inválidos — o backend tenta reenviar sem stops; veja `execution_message` do sinal. |
| Barra AlgoTrading vermelho/cinza (OFF) | Após `prepare_mt5_trading.bat`, clique o botão **Negociação algorítmica** na barra até ficar **verde**. Com OFF, `trade_allowed=False` mesmo com `Enabled=1` no ini. |

## Clear / MT5 não grava «Permitir algotrading»

Em contas **demo Clear** (e alguns builds do terminal), o checkbox **Permitir algotrading** em *Ferramentas → Opções → Expert Advisors* **não persiste**: você marca, clica OK, reabre Opções e a caixa volta desmarcada. Enquanto isso, `terminal_info().trade_allowed` fica `False` e toda ordem via API Python retorna **retcode 10027** (*AutoTrading disabled by client*).

### Passo a passo (ordem importa)

1. **Feche** ordens pendentes e confirme login na **conta demo** correta no MT5 Clear.
2. Abra **Ferramentas → Opções → Expert Advisors** (aba *Expert Advisors* / *Consultores*).
3. Marque **Permitir algotrading** (*Allow algorithmic trading*).
4. **Desmarque** **Desativar API Python externa** (*Disable Python API*) — sub-opção na mesma tela. Se ficar marcada, a API lê `tradeapi_disabled=True` mesmo com a barra verde.
5. Clique **OK** (não Cancelar) **antes** de tocar no botão da barra.
6. Na **barra de ferramentas**, clique **Negociação algorítmica** / **AlgoTrading** até ficar **verde (ON)**.
7. No Pulse Deck, aba **Sistema** → seção **Diagnóstico MT5 (API Python)**: linhas `trade_allowed` e checklist devem ficar verdes. Ou `GET /system/execution-status` → `mt5_terminal.checklist`.
8. Se a caixa **Permitir algotrading** continuar desmarcada ao reabrir Opções:
   - Feche o MT5 por completo (File → Exit / Arquivo → Sair).
   - Rode **manualmente** (com MT5 fechado): `python scripts/fix_mt5_experts_ini.py` — faz backup de `config/common.ini` e ajusta a seção `[Experts]` (não é executado automaticamente pelo sistema).
   - **Execute o terminal como administrador** só se ainda falhar permissão de escrita na pasta `%APPDATA%\MetaQuotes\Terminal\<id>\`.
   - Confira que só há **uma** instância do MT5 (Gerenciador de Tarefas → `terminal64.exe`); `check_mt5_trading.py` avisa se houver mais de um processo.
9. **Perfil / pasta de dados** (se ainda não grava):
   - Em Opções → aba *Servidor* ou *Community*, anote o caminho em *Dados* / *Data folder* (ex.: `%APPDATA%\MetaQuotes\Terminal\<hash>` — na Clear demo verificado: `...\698B86206820B42976F30D28CAC50412`).
   - Verifique permissão de escrita nessa pasta (antivírus, OneDrive sync na pasta MetaQuotes).
10. **Chaves ini verificadas (Clear build 6286, `config/common.ini`, seção `[Experts]`)** — documentação MetaQuotes + arquivo local:

| Chave ini | Valor para operar via Python | UI equivalente |
|-----------|------------------------------|----------------|
| `AllowLiveTrading` | `1` | **Permitir algotrading** / Allow Auto Trading |
| `Enabled` | `1` | Uso de Expert Advisors ligado (sem isso a Clear ficou com `Enabled=0` e `trade_allowed=False`) |
| `Api` | `0` | **Desativar API Python externa** desmarcado (`tradeapi_disabled=False`) |

Se após o passo a passo o botão verde estiver ON mas a API ainda mostrar `trade_allowed=False`, abra `config/common.ini` (UTF-16): é comum ficar **`AllowLiveTrading=1` com `Enabled=0`** — o terminal grava isso ao sair quando o checkbox da UI não persiste. Só o script `fix_mt5_experts_ini.py` (com MT5 **fechado**) corrige `Enabled`; marcar Opções de novo sem fechar o terminal costuma regravar `Enabled=0`.

Outras chaves MetaQuotes na mesma seção (referência): `AllowDllImport`, `Account`, `Profile`, `Chart` (proteções ao trocar conta/perfil/gráfico — `0` = não desliga algotrading nesses eventos).

O script `fix_mt5_experts_ini.py` define `AllowLiveTrading=1`, `Enabled=1`, `Api=0`. Depois de abrir o MT5, ligue o botão **verde** AlgoTrading na barra (estado da barra não fica só no ini).

**Nota Windows:** o MT5 grava `common.ini` em **UTF-16**; o script preserva a codificação ao editar.

### Como validar sem o painel

```bat
python scripts\\check_mt5_trading.py
```

Deve mostrar `trade_allowed=True`, `tradeapi_disabled=False` e `connected=True`.

### Um clique (Windows): preparar Clear antes de operar

Se o checkbox **Permitir algotrading** não grava ou `Enabled` volta a `0` ao sair do MT5:

```bat
scripts\\prepare_mt5_trading.bat
```

O script fecha `terminal64.exe` (gracioso, depois força se necessário), roda `fix_mt5_experts_ini.py`, imprime `[Experts]` e abre o terminal da Clear (`MT5_PATH` no `.env`).

O **`Sala-Sinais.bat`** (opção 1 / `all`) **sempre** roda `prepare_mt5_trading.bat` **antes** de subir a API quando `ENGINE_MODE=paper_mt5` (evita `Enabled=0` ao reiniciar só a API). Depois de abrir o MT5, se o botão **AlgoTrading** na barra ainda estiver **vermelho/cinza (OFF)**, clique até ficar **verde (ON)** — o ini sozinho não liga a barra; sem verde, `trade_allowed` fica `False` e boletas retornam **10027**.

### Descrição visual (telas)

| Tela | O que procurar |
|------|----------------|
| Opções → Expert Advisors | Checkbox **Permitir algotrading** marcado; **Desativar API Python externa** desmarcado; botões **OK** / **Cancelar** na base — use **OK**. |
| Barra principal | Botão com ícone de “play”/robô; estado **verde** = algotrading ligado; cinza/vermelho = 10027 na boleta. |
| Aba Sistema (cockpit) | Bloco vermelho **Diagnóstico MT5** com linhas bloqueadas e texto em português até corrigir. |

## Limpar histórico de sessão (KPIs)

Botão **Limpar histórico de sessão** (aba Sistema) ou `POST /system/reset-session` grava `data/sala_sinais_session_epoch.json`. KPIs (**REALIZADO**, fechados, equity) passam a considerar só sinais com `created_at` ≥ epoch. SQLite e MT5 **não** são apagados.

Documentação relacionada: [EXECUCAO_AUTOMATICA.md](EXECUCAO_AUTOMATICA.md), [SIMULACAO.md](SIMULACAO.md).
