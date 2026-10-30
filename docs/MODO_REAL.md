# Modo real (conta MT5 com dinheiro)

Este guia descreve como conectar a **conta real** com segurança. O sistema **não** ativa ordens reais sozinho: você precisa passar no preflight e editar o `.env` manualmente.

## 1. Pré-requisitos na corretora

1. Conta de **day trade** habilitada para mini-índice (WIN).
2. **RLP** (retail liquidity provider) ativo, se sua corretora oferecer — costuma zerar corretagem em minis (confirme no site/contrato).
3. Margem e limite de contratos compatíveis com `MAX_CONTRACTS` no `.env` (padrão: 1).
4. MetaTrader 5 instalado e **login na conta REAL** (não demo).

## 2. Símbolo WIN no MT5

1. Abra o Market Watch no MT5.
2. Adicione o contrato WIN vigente.
3. Copie o nome **exato** (ex.: `WIN$`, `WINJ26`) para `MT5_SYMBOL` no `.env`.

## 3. Preflight (obrigatório)

Com API opcional (recomendado: `Sala-Sinais.bat sistema` já rodando) e MT5 aberto:

```powershell
cd C:\Users\xgame\sala-sinais
$env:PYTHONPATH = "."
python -m engine.scripts.preflight_live
```

Ou `Sala-Sinais.bat real` (opção **6 → b** no menu).

### Vereditos

| Veredito | Exit | Significado |
|----------|------|-------------|
| **SAFE for paper** | 0 | OK para paper/demo; `LIVE_TRADING` desligado ou sem intenção de ordens reais |
| **BLOCKED** | 1 | Não prossiga — corrija MT5, símbolo, API ou combinação demo + `LIVE_TRADING=true` |
| **READY for live** | 2 | Conta real detectada; pode copiar perfil de `.env.live.example` **se** você aceita o risco |

O engine **recusa iniciar** com `LIVE_TRADING=true` se o preflight estiver **BLOCKED**.

## 4. Configurar `.env`

Somente **depois** do preflight **READY for live**:

1. Abra `.env.live.example`.
2. Copie para seu `.env` (sem apagar `WEBHOOK_SECRET` e demais chaves):
   - `SIGNAL_MODE=live`
   - `LIVE_TRADING=true`
   - Taxas `B3_FEE_PER_CONTRACT_ROUND` e `BROKER_FEE_PER_CONTRACT` conforme sua corretora.
3. **Não** defina `ALLOW_DEMO_LIVE=true` em produção (só para testes extremos em demo).

## 5. Subir o sistema

1. `Sala-Sinais.bat sistema` — API + painel em http://127.0.0.1:8000/
2. `Sala-Sinais.bat engine` — engine conectado ao MT5

No painel, o badge mostra **paper/live** e, com engine online, **conta demo/real** (via heartbeat).

## 6. Emergência

Se algo sair do controle:

1. **Pausar engine** no painel (ou `engine_paused=true` na API).
2. **Zerar posição** no painel (exige engine rodando + `LIVE_TRADING=true`).
3. No `.env`, defina `LIVE_TRADING=false`, salve e **encerre** o engine (Ctrl+C na janela).
4. Feche posições manualmente no MT5 se o flatten falhar.

## 7. Imposto de renda (IR)

Operações na B3 podem gerar **ganhos tributáveis**. Day trade em mini-índice segue regras específicas (alíquota, DARF, compensação de prejuízos). **Este software não calcula IR.** Consulte um contador antes de operar com volume relevante.

## 8. Aviso

Não há garantia de lucro. Você pode perder todo o capital alocado. Use primeiro conta **demo** por vários dias.
