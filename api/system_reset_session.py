"""POST /system/reset-session — zera KPIs do painel sem apagar MT5."""

from __future__ import annotations

from sqlalchemy.orm import Session

from api.session_epoch import load_session_epoch_at, set_session_epoch
from shared.schemas import SystemResetSessionResponse


def reset_metrics_session(db: Session) -> SystemResetSessionResponse:
    _ = db  # reservado para arquivar sinais no futuro
    previous_epoch_at = load_session_epoch_at()
    epoch_at = set_session_epoch(reason="pulse_deck_reset")
    return SystemResetSessionResponse(
        ok=True,
        message=(
            "Histórico de sessão limpo para KPIs — REALIZADO e fechados passam a contar "
            "somente sinais a partir de agora. Posições no MT5 não foram alteradas. "
            "Biblioteca, diário do agente, progresso de leitura e experiência prática "
            "não foram apagados."
        ),
        epoch_at=epoch_at,
        previous_epoch_at=previous_epoch_at,
    )
