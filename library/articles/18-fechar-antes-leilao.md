# Fechamento forçado antes do leilão (17h55 B3)

Day trade na B3 implica **zerar posição intraday**. O pregão de ações, em regra, opera até o **leilão de fechamento** (horário de referência **17h55**, horário de Brasília).

## Por que importa

- Spreads e volatilidade mudam no leilão.
- Risco de não conseguir sair no preço esperado.
- O engine **não emite novos sinais** a partir de 17h55 (`engine/risk.py`).

## Regra operacional sugerida

| Horário | Ação |
|---------|------|
| Até ~17h50 | Gestão normal de stop/alvo |
| 17h50–17h55 | Reduzir exposição; evitar novas entradas |
| ≥ 17h55 | Posição zerada (day trade) |

No simulador, respeite `SIM_RESPECT_RISK_HOURS` para alinhar fechamentos automáticos ao horário comercial.

Artigo relacionado: **05-horarios-pregao-b3**.
