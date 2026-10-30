# Execução automática (compra/venda no MT5)

Este guia conecta o **Sala de Sinais** à **sua corretora via MetaTrader 5** para que o engine **envie ordens** quando a estratégia gerar um sinal — não apenas registre alertas no painel.

> **Avenue e apps sem MT5:** para ações na B3 você precisa de uma **corretora que ofereça MetaTrader 5** (conta demo primeiro). O projeto **não** envia ordens pela Avenue nem por API proprietária da corretora.

## Sinal apenas vs execução automática

| Modo | O que acontece |
|------|----------------|
| `ENGINE_MODE=simulation` | Cotação fictícia; **nunca** há ordens no MT5 |
| `paper_mt5` + `SIGNAL_MODE=paper` | Cotação real do MT5; sinais só no painel |
| `paper_mt5` + `SIGNAL_MODE=live` + `EXECUTE_ON_DEMO=true` | Cotação real; **ordens na conta demo** do MT5 |
| `live_mt5` + `LIVE_TRADING=true` | Cotação real; **ordens na conta real** (após preflight) |

Com execução automática ligada, após cada sinal o engine chama `place_market_order` e atualiza o status do sinal (`filled` ou `rejected`) com `execution_message`.

## Passo a passo — demo (recomendado)

### 1. Instalar o MT5 da corretora

1. Abra o site da corretora e baixe o **MetaTrader 5** (instalador Windows).
2. Instale e abra o terminal.
3. Crie ou use uma **conta demonstração** e faça login.
4. No Market Watch, adicione o ativo (ex.: mini índice `WIN$` ou ação `PETR4`) e copie o **nome exato** do símbolo.

### 2. Configurar o `.env`

Na pasta `sala-sinais`, edite `.env` (copie de `.env.example` se ainda não existir):

```env
ENGINE_MODE=paper_mt5
SIGNAL_MODE=live
LIVE_TRADING=false
AUTO_EXECUTE_ORDERS=true
EXECUTE_ON_DEMO=true
MT5_SYMBOL=WIN$
```

Ajuste `MT5_SYMBOL` para o nome exato no seu MT5.

### 3. Preflight

Com o MT5 **aberto e logado**:

```powershell
cd C:\Users\xgame\sala-sinais
$env:PYTHONPATH = "."
python -m engine.scripts.preflight_live
```

Ou **`Sala-Sinais.bat`** opção **6 → a** ou `corretora` (roda o preflight e abre este guia).

Saída esperada para demo: **SAFE for paper** (exit 0).

### 4. Subir API e engine

1. **`Sala-Sinais.bat`** opção **2** ou `sistema` — API + painel em http://127.0.0.1:8000/
2. **`Sala-Sinais.bat`** opção **3** ou `engine` — engine conectado ao MT5 (deixe a janela aberta)

No painel, seção **Execução automática**: checklist com ✓ quando MT5, modo e flags estiverem corretos.

### 5. Confirmar no painel

- Barra superior do engine: indicador **verde** (“Engine ativo”).
- **Dados: MT5 AO VIVO** (heartbeat com `data_source=mt5`).
- Toggle **Execução automática**: ligado quando `AUTO_EXECUTE_ORDERS`, `SIGNAL_MODE=live`, demo + `EXECUTE_ON_DEMO` e engine não pausado.
- Na tabela de sinais, status pode mudar para **filled** após ordem na demo.

## Passo para conta real (somente depois da demo)

1. Leia [MODO_REAL.md](MODO_REAL.md).
2. No MT5, login na **conta real**.
3. No `.env`: `ENGINE_MODE=live_mt5`, `SIGNAL_MODE=live`, `LIVE_TRADING=true`.
4. Rode preflight até **READY for live** (exit 2).
5. Use **`Sala-Sinais.bat real`** como checklist adicional.
6. No painel, a caixa vermelha aparece quando `LIVE_TRADING=true` — confirme que é intencional.

## Variáveis importantes

| Variável | Função |
|----------|--------|
| `AUTO_EXECUTE_ORDERS` | `false` desliga envio de ordens (só registra sinal) |
| `EXECUTE_ON_DEMO` | Em `paper_mt5` + conta demo, permite ordens sem `LIVE_TRADING=true` |
| `LIVE_TRADING` | `true` habilita ordens em conta **real** (com preflight) |
| `ALLOW_DEMO_LIVE` | Só testes: `LIVE_TRADING=true` em conta demo |

## API

`GET /system/execution-status` — `can_send_orders`, `blockers[]` em português, checklist `steps`, snippet `.env` para demo.

## Problemas comuns

| Sintoma | Ação |
|---------|------|
| “MT5 desconectado” | Abra o MT5, login demo, rode `Sala-Sinais.bat engine` |
| Sinais sem `filled` | Confira `SIGNAL_MODE=live`, `EXECUTE_ON_DEMO=true`, engine não pausado |
| “SIGNAL_MODE≠live” | Altere `.env` e reinicie o engine |
| Avenue | Use corretora com MT5; este projeto não integra Avenue |

## Aviso

Operar na B3 envolve risco de perda. Use demo até entender latência, slippage e rejeição de ordens. Este material é educacional.
