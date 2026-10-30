"""Envia um sinal de teste à API (sem MT5)."""

import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))

import httpx
from shared.schemas import SignalCreate, SignalMode, SignalSide

secret = os.environ.get("WEBHOOK_SECRET", "change-me-to-a-long-random-string")
base = os.environ.get("API_BASE_URL", "http://127.0.0.1:8000").rstrip("/")

payload = SignalCreate(
    symbol="WIN$DEMO",
    side=SignalSide.BUY,
    entry=125000,
    stop=124920,
    target=125120,
    contracts=1,
    strategy_id="demo",
    mode=SignalMode.PAPER,
    note="Sinal de teste manual",
)

resp = httpx.post(
    f"{base}/signals",
    json=payload.model_dump(mode="json"),
    headers={"X-Webhook-Secret": secret},
    timeout=10,
)
print(resp.status_code, resp.text)
raise SystemExit(0 if resp.is_success else 1)
