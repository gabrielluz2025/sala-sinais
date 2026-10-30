# Ações brasileiras (B3) no Sala de Sinais

O agente pode operar **ações listadas na B3** (ex.: PETR4, VALE3, ITUB4) além do mini-índice WIN.

## Lote padrão

Na B3, o lote padrão de ações é **100 papéis**. No painel, o campo **Qtd. ações** deve ser múltiplo de 100 (100, 200, 500…).

- **Simulação:** o campo `contracts` do sinal guarda a quantidade de ações; PnL simulado usa essa quantidade.
- **MT5 (real/demo):** o engine converte `ações ÷ 100` em volume de lote quando o símbolo não é WIN/WDO.

## Configurar no painel

1. Abra o painel via `Sala-Sinais.bat` (opção **2** ou `sistema`).
2. Na seção **Configurar agente**, marque os tickers desejados e defina capital, risco, stop %, alvo % e quantidade.
3. Clique em **Salvar configuração** (grava em `/agent/config`).
4. Rode `Sala-Sinais.bat simulacao` ou `engine` conforme o modo.

Classe de ativo:

| Valor | Uso |
|-------|-----|
| `acoes` | Prioriza tickers de ações na lista |
| `win` | Prioriza WIN na lista |
| `mixed` | Alterna conforme seleção / rotação |

## “Treinar” o agente

**Treino em simulação** significa **ajustar parâmetros** (stop, alvo, tamanho, tickers) e observar sinais/PnL no painel — **não** há modelo de machine learning treinando sozinho nesta versão. Para ações, o PnL usa preço de saída × quantidade (lote em `shares_per_order`); a seção **Ganhos e perdas** do dashboard lê `/metrics/pnl` e só contabiliza resultado real após `exit_price` no fechamento do sinal.

## Operações por trade (compra e venda)

No painel, a seção **Operações (compra e venda)** lista cada trade **fechado** (entrada + saída) com resultado líquido, taxas e vitória/derrota. A API expõe:

- `GET /metrics/trades` — lista de trades (`symbol`, `today_only`, `limit`) com resumo global e **por ação** (`wins`, `losses`, `net_pnl_brl`, `win_rate`).
- `GET /metrics/trades/summary` — só os agregados.

O engine grava `exit_price` e `net_pnl_brl` ao fechar o sinal (simulação e, no MT5 com ordem executada, sincronização quando a posição zera).

Roadmap futuro: backtest histórico, otimização de parâmetros e eventual ML — veja [ROADMAP.md](ROADMAP.md).

## Capital reduzido e day trade

Na B3, a **menor quantidade padrão** que o Sala de Sinais usa para ações é **100 papéis** (`shares_per_order` ≥ 100, múltiplo de 100). O **notional** de uma ordem é aproximadamente `preço × quantidade` — por exemplo, a R$ 15/ação um lote de 100 exige ~R$ 1.500 de exposição (mais margem/taxas na corretora). O campo **Capital (R$)** e **Risco %** orientam curva de patrimônio e playbooks; o tamanho enviado pelo motor vem de **Qtd. ações**, não de um cálculo automático de risco ainda.

Para **pouco recurso**, comece em **simulação** ou **conta demo MT5** (`ENGINE_MODE=paper_mt5`, `EXECUTE_ON_DEMO=true`): ajuste `capital_brl` ao valor real da conta, use preset **Conservador** (0,5% de risco, 100 ações), escolha **blue chips líquidas** com preço baixo por papel se quiser minimizar o notional do lote, e opere só na janela **10h–17h BRT**. Day trade real com capital muito abaixo do notional de um lote inteiro fica inviável neste fluxo — o mercado fracionário não é o padrão do painel/MT5 aqui.

## Simulação vs real

| | Simulação | MT5 |
|---|-----------|-----|
| Preço | Random walk por ticker | Cotação do terminal |
| Ordens | Nunca envia | Com `LIVE_TRADING=true` |
| Símbolo | PETR4, VALE3, etc. | Nome exato no Market Watch |

Guia da simulação: [SIMULACAO.md](SIMULACAO.md). Modo real: [MODO_REAL.md](MODO_REAL.md).
