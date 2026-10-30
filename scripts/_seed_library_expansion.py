"""Gera artigos 19–38 e atualiza library/index.json (uso único de seed)."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "library" / "articles"
INDEX = ROOT / "library" / "index.json"

NEW_CATEGORIES = [
    {"id": "acoes-b3", "label": "Ações B3"},
    {"id": "noticias", "label": "Notícias"},
    {"id": "psicologia", "label": "Psicologia"},
    {"id": "macro", "label": "Macro"},
]

ARTICLES = [
    (
        "19-harami",
        "Harami — pausa dentro da tendência",
        "candles",
        ["harami", "reversão", "M5"],
        """# Harami — pausa dentro da tendência

O **harami** (corpo menor dentro do corpo anterior) sinaliza **desaceleração**, não reversão garantida. No day trade B3, aparece com frequência após sequências direcionais em PETR4, VALE3 ou WIN M5.

## Forma

Candle grande (mãe) seguido de corpo **contido** dentro da faixa da mãe. Harami de alta: mãe de baixa e filho pequeno; harami de baixa: mãe de alta.

## Contexto

Funciona melhor **após tendência clara** e próximo a suporte/resistência do dia. Em meio de range, gera muitos falsos positivos.

## Confirmação

Espere rompimento da máxima/mínima do par ou alinhamento com volume crescente no pregão (10h–17h55). O engine pode sinalizar breakout; o harami ajuda a **filtrar** entradas contra momentum.

## Risco

Stop além da mãe ou além do extremo do harami. Tamanho de posição conforme artigo de R:R — padrão visual não substitui gestão.

## Sala de Sinais

Use `GET /agent/candle-patterns` como radar; a biblioteca explica quando **ignorar** harami em leilão de abertura ou nos últimos minutos antes do fechamento.
""",
    ),
    (
        "20-tres-soldados-corvos",
        "Três soldados e três corvos",
        "candles",
        ["sequência", "tendência", "M5"],
        """# Três soldados e três corvos

Sequências de **três candles** na mesma direção comunicam **pressão sustentada** — útil no intraday quando cada candle fecha perto do extremo e corpos são proporcionais.

## Três soldados (alta)

Três candles de alta consecutivos, cada um fechando acima do anterior, preferencialmente com aberturas dentro do corpo anterior. Indica compradores dominando a sessão.

## Três corvos (baixa)

Espelho para vendedores. Em ações B3, cuidado com **notícia corporativa** no meio da sequência — o terceiro candle pode ser armadilha.

## Filtros B3

- Evitar operar só no padrão após 17h30 (spread e leilão).
- Cruzar com **ATR**: sequência em volatilidade baixa pode ser ruído.
- WIN: sequências em M1 exigem stop mais curto; M5 alinha melhor ao engine.

## Estratégia

Entrada no **pullback** após o terceiro candle (reteste) costuma ter melhor R:R que perseguir o topo. Combine com artigo de breakout de range.

## Psicologia

Traders tardios entram no terceiro candle; profissionais esperam consolidação. Disciplina > padrão perfeito.
""",
    ),
    (
        "21-inside-bar",
        "Inside bar — compressão antes do movimento",
        "candles",
        ["inside bar", "compressão", "breakout"],
        """# Inside bar — compressão antes do movimento

**Inside bar**: máxima e mínima **dentro** do candle anterior. Representa **equilíbrio** e often precede expansão de volatilidade.

## Leitura

O candle “mãe” define o range; o inside bar mostra indecisão. Rompimento da mãe (com volume relativo maior) é o gatilho clássico.

## Day trade B3

Em ações líquidas, inside bars no **primeiro hour** (10h–11h) frequentemente antecedem direção do dia. Após almoço, falsos rompimentos aumentam.

## Stop e alvo

Stop no extremo oposto da mãe ou do inside (conforme volatilidade). Alvo mínimo: altura da mãe projetada — alinhe com R:R 2:1 do painel.

## Relação com engine

Estratégia **breakout** do Sala de Sinais pode coincidir com rompimento de inside bar em range identificado. Use biblioteca para entender *por que* o sinal apareceu.

## Erros comuns

Operar rompimento **dentro** do inside sem fechamento; ignorar notícias agendadas (calendário macro).
""",
    ),
    (
        "22-rejeicao-pavio",
        "Rejeição por pavio (pin bar)",
        "candles",
        ["pin bar", "rejeição", "liquidez"],
        """# Rejeição por pavio (pin bar)

**Pin bar**: corpo pequeno no extremo oposto à sombra longa. A sombra marca **rejeição de preço** — similar ao martelo, mas o termo pin bar enfatiza o teste de liquidez.

## Onde funciona

- Limites de range intraday.
- Reteste de rompimento (breakout retest).
- Próximo a VWAP ou abertura do dia.

## WIN vs ações

No mini-índice, pins em M1 são ruidosos; prefira M5 com contexto de índice e dólar. Em ações, pins em papéis ilíquidos são enganosos — filtre por volume financeiro.

## Confirmação

Entrada após fechamento do pin **ou** no rompimento da máxima/mínima do pin com stop técnico claro.

## Notícias

Pin antes de dado macro (IPCA, Copom) pode ser stop hunt. Consulte calendário e artigo de notícias macro.

## Integração

Camada de candle patterns do agente destaca rejeições; você decide se o contexto de risco do dia permite operar.
""",
    ),
    (
        "23-volume-liquidez-b3",
        "Volume e liquidez no pregão B3",
        "acoes-b3",
        ["volume", "liquidez", "pregão"],
        """# Volume e liquidez no pregão B3

**Volume financeiro** e **quantidade de negócios** indicam se um movimento tem participação institucional ou é thin market.

## Horários

- **10h–11h30**: formação de tendência; volume tende a ser maior.
- **Almoço**: queda de liquidez; spreads piores.
- **15h–17h55**: recomposição; cuidado com volatilidade de fechamento.

## Leitura prática

Rompimento de resistência com **volume abaixo da média** da sessão merece ceticismo. Pullbacks em tendência com volume decrescente podem ser saudáveis.

## Ações vs WIN

Ações: compare volume do candle com média dos últimos 20 candles M5. WIN: use proxy via amplitude e book quando disponível no MT5.

## RLP e custos

Volume alto com RLP pode reduzir custo efetivo — veja artigo de taxas. Não confunda volume com edge: edge vem de setup + risco.

## Ferramentas

Painel e histórico OHLC do cockpit; estudo noturno simula fluxo sem volume real — valide no pregão.
""",
    ),
    (
        "24-tape-reading-basico",
        "Tape reading — leitura de fluxo básica",
        "estrategias",
        ["tape", "fluxo", "times trades"],
        """# Tape reading — leitura de fluxo básica

**Tape reading** observa sequência de negócios (times & trades) para inferir agressão compradora ou vendedora.

## Conceitos

- **Agressor comprador**: negócio no ask ou acima.
- **Agressor vendedor**: no bid ou abaixo.
- **Absorção**: muito volume sem deslocar preço.

## B3 day trade

Plataformas mostram lotes e horários. Foque em **papéis líquidos** (PETR4, ITUB4, BBDC4) onde o tape reflete fluxo real.

## Limitações

Tape parcial vs book completo; spoofing e ordens iceberg distorcem leitura. Use tape como **filtro**, não gatilho único.

## Combinação

Candle de rejeição + absorção no nível = setup mais forte. Engine matemático não substitui olho no fluxo — complementa.

## Disciplina

Evitar overtrade ao “ver cada lote”. Defina gatilho objetivo antes de abrir o DOM.
""",
    ),
    (
        "25-calendario-economico-day-trade",
        "Calendário econômico e day trade",
        "noticias",
        ["calendário", "macro", "agenda"],
        """# Calendário econômico e day trade

Operar sem olhar a **agenda** é operar cego. Dados macro movem WIN, dólar e juros — e arrastam blue chips.

## Eventos críticos Brasil

- **Copom** e comunicado.
- **IPCA**, PIB, emprego.
- **Fiscal** e ruído político (impacto via curva).

## Janelas

Evite abrir posição **2–5 minutos** antes de release de alto impacto, salvo estratégia específica. Após o dado, espere volatilidade estabilizar (primeiro range pós-notícia).

## Correlacionados

EUA: payroll, CPI, FOMC — afetam EWZ e WIN overnight/indireto intraday.

## Ferramentas

Sites públicos de calendário (Investing, B3, institucionais). RSS de notícias na biblioteca (`library/news/`) complementa — não substitui calendário.

## Sala de Sinais

Filtro de notícias do agente (quando ativo) reduz sinais em janelas sensíveis; você mantém responsabilidade final.
""",
    ),
    (
        "26-noticias-corporativas-intraday",
        "Notícias corporativas no intraday",
        "noticias",
        ["resultados", "fatos relevantes", "ações"],
        """# Notícias corporativas no intraday

**Fato relevante**, guidance, M&A e resultados trimestrais reprice ações em minutos.

## Tipos

- Resultados **fora do horário** → gap na abertura.
- Divulgação **intraday** → halt ou leilão em casos extremos.
- Rumor em rede social → spike reversível.

## Day trade

Após notícia, spreads alargam. Prefira esperar **primeiro range de 5–15 min** pós-release antes de directional trade.

## WIN hedge

Notícia em petróleo/governança em PETR4 move índice; WIN pode reagir antes da ação estabilizar.

## Fontes

CVM, RI das companhias, agências. Snippets RSS salvos em `library/news/` trazem contexto — sempre verifique fonte primária.

## Risco

Stop mais largo ou size menor pós-notícia. Revenge após stop por notícia é armadilha clássica — veja psicologia.
""",
    ),
    (
        "27-rotacao-setores-b3",
        "Rotação setorial na B3",
        "acoes-b3",
        ["setores", "rotation", "índice"],
        """# Rotação setorial na B3

**Rotação**: capital migra entre setores (bancos, commodities, varejo) dentro da mesma sessão ou semana.

## Sinais intraday

- Índice sobe mas seu setor cai → stock picking difícil.
- Líder setorial rompe enquanto pares lateralizam → força relativa.

## Day trade

Operar **líder de setor** em tendência reduz frustração vs laggards ilíquidos.

## Macro

Selic, China (minério), petróleo puxam setores específicos — artigo macro complementa.

## WIN

Quando rotação é confusa, WIN segue fluxo agregado; ações exigem mapa setorial.

## Prática

Monte watchlist por setor no cockpit; Shift+clique define ativo operado pelo agente.
""",
    ),
    (
        "28-acoes-liquidas-day-trade",
        "Ações líquidas para day trade",
        "acoes-b3",
        ["PETR4", "liquidez", "watchlist"],
        """# Ações líquidas para day trade

Liquidez = sair quando precisar, com slippage controlado.

## Critérios

- Volume financeiro diário elevado.
- Spread bid-ask estreito no horário core.
- Presença em índices (IBOV, IBRX).

## Exemplos recorrentes

PETR4, VALE3, ITUB4, BBDC4, B3SA3 — **não é recomendação**; é observação de mercado. Revise diariamente.

## Lote padrão

Day trade em ações usa múltiplos de lote; ajuste `shares_per_order` no agente.

## Ilíquidas

Padrões de candle “perfeitos” em small caps falham na execução. Evite unless specialized.

## Dados

OHLC M5 no painel; bars persistidos em `data/bars_*.json` para estudo.
""",
    ),
    (
        "29-vwap-intraday",
        "VWAP no intraday",
        "estrategias",
        ["VWAP", "média", "institucional"],
        """# VWAP no intraday

**VWAP** (preço médio ponderado por volume) é referência institucional do “preço justo” do dia.

## Uso

- Acima VWAP → viés comprador intraday (contexto).
- Reteste de VWAP após rompimento → entrada trend-following.
- Abaixo VWAP → viés vendedor.

## Limitações

VWAP **reinicia** cada dia; não use fechamento anterior como VWAP. Indicador no MT5/cockpit se disponível.

## WIN

Proxy via índice; menos preciso que ação individual.

## Combinação

VWAP + candle de rejeição no nível = filtro forte. Engine volatility pode divergir — respeite stop do painel.

## Erro

Operar cruzamento VWAP sem volume confirmando.
""",
    ),
    (
        "30-suporte-resistencia-intraday",
        "Suporte e resistência intraday",
        "estrategias",
        ["S/R", "range", "níveis"],
        """# Suporte e resistência intraday

Níveis são **zonas** onde preço reagiu antes: máxima/mínima do dia, abertura, fechamento anterior, números redondos.

## Construção

Marque topos/fundos M5; quanto mais toques, mais relevante (até rompimento).

## Rompimento vs fake

Fechamento **fora** da zona + volume sustenta rompimento. Pavio isolado = possível fake — artigo dedicado.

## Stop

Além da zona; evite stop exatamente no número redondo visível a todos.

## Engine

Breakout strategy usa range_high/range_low — alinhe leitura visual com chips do insight deck.

## B3

Leilão de abertura forma primeiro S/R; 17h55 força flat no day trade sistemático.
""",
    ),
    (
        "31-gap-abertura-b3",
        "Gap de abertura na B3",
        "fundamentos",
        ["gap", "abertura", "overnight"],
        """# Gap de abertura na B3

**Gap** = abertura distante do fechamento anterior por fluxo overnight (ADR, futuros, notícias).

## Tipos

- Gap de continuação vs gap de exaustão.
- Gap parcialmente preenchido intraday.

## Estratégias

- Fade do gap em mercado lateral (arriscado).
- Seguir gap com pullbacks (trend day).

## WIN e dólar

Overnight em WIN reflete exterior; gap em ações reflete evento específico ou setor.

## Risco

Primeiros 15 minutos têm volatilidade alta; size reduzido.

## Regra operacional

Sala de Sinais: respeite janela 10h–17h55 e zeragem pré-leilão.
""",
    ),
    (
        "32-psicologia-fomo-revenge",
        "FOMO e revenge trading",
        "psicologia",
        ["disciplina", "FOMO", "revenge"],
        """# FOMO e revenge trading

**FOMO** (medo de perder movimento) e **revenge** (recuperar loss na marra) destroem edge matemático.

## FOMO

Entrar tarde no movimento, stop largo implícito, R:R ruim. Antídoto: lista de setups válidos **antes** do pregão.

## Revenge

Dobrar size após stop; operar fora do plano. Antídoto: limite diário de perda no painel; pausa física.

## Tilt

Três losses seguidos → reduzir ou parar. Agent journal registra acertos — não apaga losses emocionais.

## Processo

Biblioteca + estudo autônomo do agente reforçam **processo**, não euforia de um trade.

## LIVE

Em conta real, emoção amplifica erros. Paper_mt5 treina rotina sem adrenalina de capital crítico.
""",
    ),
    (
        "33-macro-selic-dolar-intraday",
        "Selic, dólar e intraday",
        "macro",
        ["Selic", "dólar", "juros"],
        """# Selic, dólar e intraday

**Macro** filtra viés direcional mesmo em setups técnicos curtos.

## Selic / juros futuros

Subida de DI → pressão em bancos e varejo; queda → risco-on. Copom intraday move curva em segundos.

## Dólar

USD/BRL forte → commodities exportadoras vs importadores divergem; WIN sensível.

## Correlation trade

Evite comprar índice contra dólar em rally forte do USD sem catalyst positivo local.

## Calendário

Cruze artigo de calendário econômico; macro sem horário surpreende via headline.

## Humildade

Prever número do IPCA no tick é loteria; gestão de risco sob incerteza é profissão.
""",
    ),
    (
        "34-falso-rompimento",
        "Falso rompimento (bull/bear trap)",
        "estrategias",
        ["fake breakout", "armadilha", "stop hunt"],
        """# Falso rompimento (bull/bear trap)

Preço **rompe** nível, atrai breakout traders, e **reverte** fechando dentro do range — clássico stop hunt.

## Identificação

- Rompimento com volume fraco.
- Pavio longo além do nível e close interno.
- Notícia falsa ou headline revertida.

## Resposta

Operar **reversão** só com confirmação (engolfo, pin). Ou aguardar segundo teste.

## Engine

Sinal breakout pode coincidir com fake; stop técnico limita dano.

## WIN M5

Frequente em números redondos de índice. Não mova stop para “dar espaço” emocionalmente.

## Journal

Anote fakes no diário de trades (`trade_learning`) — padrões repetem por ativo.
""",
    ),
    (
        "35-order-flow-book-b3",
        "Book de ofertas — conceitos básicos",
        "estrategias",
        ["book", "DOM", "microestrutura"],
        """# Book de ofertas — conceitos básicos

O **book** mostra bid/ask e profundidade; ajuda a ver **paredes** e desequilíbrio.

## Termos

- **Spread**: custo imediato.
- **Wall**: lote grande aparente (pode ser spoofing).
- **Iceberg**: liquidez oculta.

## Day trade B3

Útil em ações líquidas; WIN via MT5 depende do feed da corretora.

## Tape + book

Agressão consumindo nível sem replenishment → movimento continua. Replenishment forte → possível reversão.

## Limites

Book snapshot não garante execução na quantidade visível.

## Ética

Não manipule — foque em leitura defensiva e execução disciplinada.
""",
    ),
    (
        "36-sequencia-marubozu",
        "Sequências de Marubozu e momentum",
        "candles",
        ["marubozu", "momentum", "tendência"],
        """# Sequências de Marubozu e momentum

**Marubozu** (pouco ou nenhum pavio) indica controle de ponta a ponta do período.

## Momentum

Dois ou três marubozus na mesma direção sugerem **impulso** — comum após notícia ou rompimento.

## Cuidado

Perseguir marubozu tardio no dia = R:R pobre. Preferir pullback shallow.

## Tamanho

Marubozu grande vs ATR → exaustão possível no candle seguinte.

## Sistema

Volatility strategy do engine pode entrar em expansão; marubozu explica visualmente.

## Stop

Abaixo/ acima do corpo ou ATR fraction — artigo de stops adaptativos.
""",
    ),
    (
        "37-noticias-macro-copom",
        "Copom e pregão — o que esperar",
        "noticias",
        ["Copom", "BCB", "volatilidade"],
        """# Copom e pregão — o que esperar

Decisão **Selic** move juros futuros, bancos e WIN simultaneamente.

## Timeline

Comunicado ~18h30 em dias de Copom — **fora** do day trade cash padrão, mas afeta gap seguinte e WIN estendido se operar.

## Intraday em dias de semana Copom

Mercado posiciona antes; volatilidade em DI e USD pode anteceder ruído em ações.

## Estratégia conservadora

Reduzir size ou ficar flat em janelas de headline BCB.

## Biblioteca news

Ingestão RSS pode salvar resumos em `library/news/` — leia disclaimer; confirme na fonte.

## Educação

B3 e BCB publicam material oficial — artigo 08-fontes-abertas lista links.
""",
    ),
    (
        "38-fibonacci-intraday-pragmatico",
        "Fibonacci intraday (uso pragmático)",
        "estrategias",
        ["fibonacci", "retração", "pullback"],
        """# Fibonacci intraday (uso pragmático)

Retrações **38,2% / 50% / 61,8%** de um swing intraday são **mapas**, não oráculos.

## Como traçar

Swing claro M5/M15 do dia: fundo → topo (ou inverso). Zona 50–61,8% com confluência S/R vale mais.

## Confluência

Fib + VWAP + nível anterior = zona de decisão.

## Anti-padrão

Desenhar fib em todo micro-movimento — paralisia analítica.

## B3

Funciona melhor em trending days; em range, níveis se quebram repetidamente.

## Humildade

Sem prova estatística universal; use como filtro visual alinhado ao risk do painel.
""",
    ),
]


def main() -> None:
    ART.mkdir(parents=True, exist_ok=True)
    for aid, title, cat, tags, body in ARTICLES:
        path = ART / f"{aid}.md"
        path.write_text(body.strip() + "\n", encoding="utf-8")

    data = json.loads(INDEX.read_text(encoding="utf-8"))
    cats = {c["id"]: c for c in data.get("categories", [])}
    for c in NEW_CATEGORIES:
        cats[c["id"]] = c
    data["categories"] = sorted(cats.values(), key=lambda x: x["id"])

    by_id = {a["id"]: a for a in data.get("articles", []) if a.get("id")}
    for aid, title, cat, tags, _body in ARTICLES:
        by_id[aid] = {
            "id": aid,
            "title": title,
            "category": cat,
            "tags": tags,
            "path": f"articles/{aid}.md",
            "updated": "2026-10-29",
        }

    data["articles"] = sorted(by_id.values(), key=lambda x: x["id"])
    INDEX.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(ARTICLES)} articles; total index: {len(data['articles'])}")


if __name__ == "__main__":
    main()
