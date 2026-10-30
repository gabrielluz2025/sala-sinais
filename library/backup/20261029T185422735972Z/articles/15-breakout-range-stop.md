# Breakout de range e stop além do extremo

## Ideia clássica

1. Marque a **máxima** e **mínima** dos últimos *N* candles (no sistema, N=12 no M1).
2. **Compra** quando o preço **fecha** acima da máxima; **venda** quando fecha abaixo da mínima.
3. Stop “técnico”: alguns traders colocam stop **abaixo da mínima do range** (compra) ou **acima da máxima** (venda).

## Como o engine faz hoje

A estratégia `breakout` (`engine/strategy.py`) usa o rompimento como **gatilho**, mas o **stop simulado** vem da sua config:

- **Ações:** `stop_loss_pct` e `take_profit_pct` sobre o preço de entrada.
- **WIN/WDO:** `stop_points` e `target_points` em pontos do índice/dólar.

Isso mantém gestão de risco **numérica e auditável** — o `entry_reason` descreve o rompimento; stop/alvo seguem o painel **Configurar agente**.

## Operacional B3

Evite entrar no leilão de abertura (≈9h–10h) e no de fechamento (≥17h55). O módulo `engine/risk.py` bloqueia novos sinais nessas janelas.
