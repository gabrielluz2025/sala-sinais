# Relação risco:retorno (R:R) e tamanho de posição

## R:R

**R:R** = distância até o alvo ÷ distância até o stop (mesma unidade: R$, pontos ou %).

Exemplo: stop 2% abaixo da entrada e alvo 4% acima → R:R **2:1**.

No painel do agente, `take_profit_pct` / `stop_loss_pct` (ações) ou `target_points` / `stop_points` (WIN) definem essa proporção. O estudo ao vivo calcula o R:R dos níveis propostos.

## Tamanho da posição

Campos **capital_brl** e **risk_per_trade_pct** orientam quantos contratos/ações o runtime sugere (`contracts_for_config`). Regra prática:

> Risco em R$ por trade ≈ capital × (risk_per_trade_pct / 100)

Ajuste o lote para que, se o stop for atingido, a perda fique dentro desse teto — especialmente em ações fracionadas ou WIN com margem reduzida.

## Objetivo vs realidade

R:R 2:1 **não garante** lucro; exige taxa de acerto compatível com custos (corretagem, RLP). Use a simulação e `exit_reason` nos sinais para validar antes de operar conta real.
