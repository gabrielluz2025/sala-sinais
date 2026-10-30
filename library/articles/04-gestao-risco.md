# Gestão de risco no intraday

Parâmetros do agente no painel:

- **Capital** e **% risco por trade** — dimensionam exposição.
- **Stop loss %** (ações) ou **pontos** (WIN) — limite de perda por operação.
- **Take profit %** — objetivo de ganho.

Na simulação, fechamentos automáticos em stop/alvo gravam `exit_reason` para você auditar o comportamento.
