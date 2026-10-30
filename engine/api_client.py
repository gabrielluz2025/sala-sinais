from __future__ import annotations

import httpx

from engine.config import settings
from datetime import datetime

from shared.schemas import SignalCreate, SignalOutcome, SignalRead, SignalStatus, SignalUpdate


class SignalApiClient:
    def __init__(self) -> None:
        self._base = settings.api_base_url.rstrip("/")
        self._secret = settings.webhook_secret

    def post_signal(self, signal: SignalCreate) -> SignalRead:
        headers = {"X-Webhook-Secret": self._secret}
        with httpx.Client(timeout=15.0) as client:
            resp = client.post(
                f"{self._base}/signals",
                json=signal.model_dump(mode="json"),
                headers=headers,
            )
            resp.raise_for_status()
            return SignalRead.model_validate(resp.json())

    def get_agent_config(self) -> dict:
        with httpx.Client(timeout=8.0) as client:
            resp = client.get(f"{self._base}/agent/config")
            resp.raise_for_status()
            return resp.json()

    def get_agent_study(self, symbol: str) -> dict:
        with httpx.Client(timeout=20.0) as client:
            resp = client.get(
                f"{self._base}/agent/study",
                params={"symbol": symbol},
            )
            resp.raise_for_status()
            return resp.json()

    def get_library_stats(self) -> dict:
        with httpx.Client(timeout=12.0) as client:
            resp = client.get(f"{self._base}/library/stats")
            resp.raise_for_status()
            return resp.json()

    def get_learning_stats(self) -> dict:
        with httpx.Client(timeout=12.0) as client:
            resp = client.get(f"{self._base}/agent/learning-stats")
            resp.raise_for_status()
            return resp.json()

    def post_agent_library_study_tick(self) -> dict:
        with httpx.Client(timeout=15.0) as client:
            resp = client.post(f"{self._base}/library/agent-study/tick")
            resp.raise_for_status()
            return resp.json()

    def update_status(self, signal_id: int, status: str, message: str | None = None) -> SignalRead:
        headers = {"X-Webhook-Secret": self._secret}
        params = {"status": status}
        if message:
            params["message"] = message
        with httpx.Client(timeout=15.0) as client:
            resp = client.patch(
                f"{self._base}/signals/{signal_id}/status",
                params=params,
                headers=headers,
            )
            resp.raise_for_status()
            return SignalRead.model_validate(resp.json())

    def close_signal(
        self,
        signal_id: int,
        *,
        exit_price: float,
        outcome: SignalOutcome,
        exit_reason: str,
        closed_at: datetime | None = None,
        message: str | None = None,
    ) -> SignalRead:
        body = SignalUpdate(
            status=SignalStatus.CLOSED,
            exit_price=exit_price,
            outcome=outcome,
            exit_reason=exit_reason,
            closed_at=closed_at,
            message=message or exit_reason,
        )
        headers = {"X-Webhook-Secret": self._secret}
        with httpx.Client(timeout=15.0) as client:
            resp = client.patch(
                f"{self._base}/signals/{signal_id}",
                json=body.model_dump(mode="json", exclude_none=True),
                headers=headers,
            )
            resp.raise_for_status()
            return SignalRead.model_validate(resp.json())
