# Dados B3: o que é tempo real e o que é simulado

## Resposta direta

**Não.** O Sala de Sinais **não carrega automaticamente todas as ações da B3** com cotação oficial em tempo real.

| Modo | Cotação | Universo de ativos |
|------|---------|-------------------|
| **Simulação** (`ENGINE_MODE=simulation`) | Preços **sintéticos** (random walk + histórico de exemplo) | Tickers que você configura no painel — não é feed da B3 |
| **Paper MT5** / **Live MT5** | **Tempo real via MetaTrader 5** + corretora | Só símbolos que existem na sua corretora **e** que você adicionou ao **Market Watch** do MT5 |

## O que é “tempo real” hoje

- **Simulação:** educacional. O engine gera ticks e candles localmente. O painel mostra o badge **Dados: SIMULADO**.
- **MT5:** quando o engine está em `paper_mt5` ou `live_mt5`, conectado ao terminal, o heartbeat envia `data_source=mt5` e o painel mostra **Dados: MT5 AO VIVO** (cotação vem do broker/MT5, não de um agregador B3 genérico).

## Como ver PETR4 (ou outro ticker) ao vivo

1. Instale o **MetaTrader 5** da sua corretora brasileira.
2. Adicione **PETR4** (ou o símbolo exato que a corretora usa) ao **Market Watch**.
3. Configure `.env` com `ENGINE_MODE=paper_mt5` (demo) ou `live_mt5` (real, com checklist em `MODO_REAL.md`).
4. No painel, inclua o ticker em **Configurar → Ações** e defina como **Ativo foco**.
5. Inicie `Sala-Sinais.bat engine` com MT5 aberto e logado.

## Limitações importantes

- **Nem todo ticker B3** está disponível em todo broker MT5; nomes podem diferir (sufixos, mercado fracionário, etc.).
- **Não há lista automática** com centenas de papéis — você escolhe e mantém no Market Watch.
- **Gráficos multi-timeframe (M1/M5/H1)** no painel usam barras gravadas pelo engine (`data/bars_SYMBOL.json`) ou agregação de `quote_history.json` — em simulação isso reflete o mercado **simulado**, não o book oficial da B3.
- **Sinais e alertas** seguem a estratégia configurada; não são recomendação de investimento.

## Onde ler mais

- `SIMULACAO.md` — subir API + engine em modo treino
- `MODO_REAL.md` — checklist antes de dinheiro real
- `APRENDIZADO.md` — como o agente usa volatilidade (e plano de ML)
