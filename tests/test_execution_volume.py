"""Volume mapping for equity symbols."""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from engine.execution import _volume_from_signal
from shared.schemas import SignalCreate, SignalMode, SignalSide


def test_equity_volume_uses_contract_size():
    info = SimpleNamespace(trade_contract_size=100.0)
    sig = SignalCreate(
        symbol="PETR4",
        side=SignalSide.BUY,
        entry=50.0,
        stop=49.0,
        target=55.0,
        contracts=100,
        strategy_id="t",
        mode=SignalMode.LIVE,
    )
    assert _volume_from_signal(sig, info=info) == 1.0
