# Pulse Deck

Uma única superfície de produto na raiz `/` — **Pulse Deck**: abas persistentes, linha do tempo do pregão B3, gráfico “rio” em candlestick (OHLC da API), cartões de insight e comando **⌘K** (ticker, abas, zonas legado, export da biblioteca).

## Visual (v2 — Terminal B3)

- **Rail esquerda:** navegação vertical (Painel, Ops, Lucros, Agente, Biblioteca, Sistema) + controles do engine.
- **Topo:** pregão B3 compacto, PnL do dia, chips de status, cotação, **Raio-X no cabeçalho** (Conhecimento · Acertos · Risco · Modo) com balões/popover organizados.
- **Centro:** gráfico principal + faixa de decisão em chips; multi-ativo em `<details>`.
- **Cortina direita:** conteúdo da aba ativa ocupa toda a altura (sem vazio inferior).
- Tipografia: DM Sans + JetBrains Mono; paleta escura com acento âmbar.

## Watchlist e layout split

- **Watchlist** no topo: busca B3 (`GET /agent/tickers`), chips para ver gráfico (clique) ou definir ativo operado (Shift+clique). Barra com scroll próprio se houver muitos ativos.
- **Desktop (≥1100px):** gráfico à esquerda; **cortina direita** redimensionável (padrão ~440px, até ~560px) com scroll vertical suave no Painel. Outras abas usam o palco full (`deck-stage--full`).
- **Painel (insight deck):** fluxo em **coluna única** na cortina; grade 2×2 nos cartões rápidos só em viewport ≥1280px e cortina larga. P&L hero com stats inline (realizado, MTM, fechados/abertas) e chip de horário B3; **Raio-X** em blocos compactos (dl + números grandes) e atalhos Agente / Simulação / Biblioteca.
- **Estratégia por ativo:** bloco recolhível em telas estreitas; expandido automaticamente em ≥1280px.
- **Mobile:** no **Painel**, gráfico + cortina empilhados; nas demais abas, só o conteúdo em tela cheia (sem stack duplo gráfico + tabela).
- **Layout 100% zoom:** shell em coluna (`deck-body` → `deck-main` / `#deck-full-stage`) com `min-height: 0` e **uma** rolagem vertical por aba (`.deck-tab-scroll` no corpo visível; pais com `overflow: hidden`). Tabelas largas só com scroll horizontal no wrapper. Abas inativas ficam com `hidden` + `.deck-tab-active` (sem empilhar títulos no mesmo pixel). Cabeçalho KPI quebra em até 3 linhas em viewports ≤1720px (ex.: 1920×1080 com rail). Biblioteca no palco full: diário + cards + FAQ em **coluna única**. Testar zoom do navegador **100%** em 1366×768 e 1920×1080.
- **Gráfico:** lightweight-charts com Bollinger (`GET /market/strategy-series`), linhas stop/alvo do sinal aberto.
- **Lucros:** KPIs atualizados no poll rápido (~4s) com curva equity intraday.

## Abas

**Navegação v3:** **Painel** é a tela inicial — gráfico + boleta/livro à direita e **cortina estreita** só com o resumo do dia (KPIs). **Operações, Lucros, Agente, Biblioteca e Sistema** abrem o **palco principal em largura total** (sem gráfico espremido ao lado); o item ativo fica destacado no rail e o cabeçalho mostra **← Voltar ao painel**. Links `#ops`, `#lucros`, etc. continuam válidos.

| Aba | Conteúdo |
|-----|----------|
| **Painel** | KPIs + gráfico river (fechado hoje vs MTM aberto) |
| **Operações** | Tabela completa (entrada, saída, taxas, resultado, acumulado), filtros Hoje/Todos, totais do pregão |
| **Lucros** | KPIs de PnL, win rate, fechados recentes, resumo por ativo |
| **Agente** | Configuração, presets, risco |
| **Biblioteca** | Nível de conhecimento, artigos, export/import ZIP |
| **Sistema** | Engine, execução, modo, link legado |

Deep link opcional: `#ops`, `#lucros`, `#agente`, `#biblioteca`, `#sistema`.

## Dados de PnL

- **Fechado hoje** vem de `/metrics/pnl` (`today_net` / trades encerrados no dia).
- **MTM aberto** usa mids de `/market/mids` + mesma lógica da API (`open_positions_estimated_pnl`).
- Operações fechadas na tabela usam `/metrics/trades` quando há `exit_price`; sinais ainda abertos mostram saída estimada (`*`) e PnL MTM por linha.
- Totais na aba Operações: compras/vendas, volume em ações, taxas estimadas em abertas, IR estimado (`session_today` no PnL).

## Primeira tela (aba Painel)

1. **Header** — chips API / engine / modo, botão ⌘K e sincronização; **balões Raio-X** (clique ou hover em desktop) com os mesmos blocos do painel: biblioteca/nível, acertos/WR, projeção de risco e modo/motor.
2. **Timeline** — pré-mercado → pregão (marcador “agora”) → pós; atalhos para bottom sheet legado.
3. **Insight deck** — PnL fechado + MTM, risco aberto, último sinal, **snapshot do agente** (capital, risco, lote, rotação), **Raio-X** (chips motor/AUTO/guardas/heartbeat, conhecimento com atalho à biblioteca, acertos/erros com contexto quando zero fechados, projeção “se fosse real” sempre que houver config), estratégia por ativo com dica se histórico vazio.
4. **River chart** — candlestick full-width do ativo ativo.

### Raio-X no cabeçalho

Quatro chips abaixo dos KPIs de PnL abrem popovers (posição fixa, scroll interno, fecha com Esc ou clique fora):

| Chip | Conteúdo do balão |
|------|-------------------|
| **Conhecimento** | Nível day trade, barra de progresso, artigos lidos/palavras, atalho Biblioteca |
| **Acertos** | WR janela ou pregão, W/L, PnL da janela, insight se vazio |
| **Risco** | Equity educativa, capital + fechados + MTM, risco/trade, dia (est.) |
| **Modo** | Modo honesto (live/demo/sim), chips motor/AUTO/guardas/HB, snapshot operação/risco |

Dados compartilhados com o card Raio-X (`buildAgentXraySections`); poll rápido atualiza Modo/Risco; leitura na Biblioteca refresca Conhecimento.

### FAQ no painel (Biblioteca / Sistema / balão Modo)

Caixa **Perguntas frequentes** no topo da aba Biblioteca e na aba Sistema resume:

- Conhecimento (seu progresso, agente, diário, experiência prática) **não zera** na abertura do pregão — só o PnL **do dia** reinicia na virada (BRT).
- **Simulador:** projeção «se fosse real» usa `capital_brl` / risco do agente — educativo, não saldo MT5.
- **Modo real:** preflight `READY`, `.env` (`ENGINE_MODE=live_mt5`, `LIVE_TRADING=true`), checklist MT5 — ver `docs/MODO_REAL.md`. No balão **Modo** do cabeçalho, link **Checklist modo real** leva à aba Sistema.

O botão **Limpar histórico de sessão** (Sistema) zera KPIs de trades a partir de um epoch — **não** apaga biblioteca nem diário.

`session_hours` bloqueia novas ordens/sinais MT5 fora da janela B3; **estudo 24h da biblioteca** e leitura de artigos seguem independentes.

## URLs

| Caminho | Conteúdo |
|---------|----------|
| `/` | **Pulse Deck** (`cockpit/dist/`) |
| `/dashboard` | Alias |
| `/classic` | Painel legado |
| `/static/*` | Assets do classic |

## Build

```bash
cd cockpit
npm install
npm run build
```

## Desenvolvimento

```bash
cd cockpit
npm run dev
```

## IDs críticos (testes)

`engine-status`, `engine-dot`, `engine-label`, `zone-nav`, `pulse-tab-nav`, chips, botões de engine, `api-url`, `live-ops`, `live-ops-body`, `live-ops-totals`, `today-result-amount`, `today-mtm-amount`, `last-update-label`, `live-sync-dot`.

Conteúdo `zone-*` permanece no bottom sheet (timeline / ⌘K legado).
