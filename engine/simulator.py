"""Mercado WIN simulado — ticks/candles sem MT5."""

from __future__ import annotations

import csv
import random
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np

from engine.config import settings

TZ_BR = ZoneInfo("America/Sao_Paulo")
_ROOT = Path(__file__).resolve().parents[1]
SAMPLE_CSV = _ROOT / "data" / "sample_win_m1.csv"

MT5_RATES_DTYPE = np.dtype(
    [
        ("time", "i8"),
        ("open", "f8"),
        ("high", "f8"),
        ("low", "f8"),
        ("close", "f8"),
        ("tick_volume", "i8"),
        ("spread", "i4"),
        ("real_volume", "i8"),
    ]
)


def ensure_sample_csv(path: Path | None = None, bars: int = 500) -> Path:
    """Gera CSV M1 de exemplo (~500 barras) se não existir."""
    path = path or SAMPLE_CSV
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_file():
        return path

    base = float(settings.sim_base_price)
    price = base
    start = datetime.now(TZ_BR).replace(hour=10, minute=0, second=0, microsecond=0)
    rows: list[dict[str, float | str]] = []
    for i in range(bars):
        ts = start + timedelta(minutes=i)
        move = random.gauss(0, 25)
        open_p = price
        close_p = max(1000.0, open_p + move)
        high_p = max(open_p, close_p) + abs(random.gauss(0, 15))
        low_p = min(open_p, close_p) - abs(random.gauss(0, 15))
        price = close_p
        rows.append(
            {
                "time": ts.isoformat(),
                "open": round(open_p, 2),
                "high": round(high_p, 2),
                "low": round(low_p, 2),
                "close": round(close_p, 2),
                "volume": random.randint(80, 800),
            }
        )

    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["time", "open", "high", "low", "close", "volume"])
        writer.writeheader()
        writer.writerows(rows)
    return path


def _load_bars_from_csv(path: Path) -> list[dict[str, float]]:
    bars: list[dict[str, float]] = []
    with path.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            bars.append(
                {
                    "open": float(row["open"]),
                    "high": float(row["high"]),
                    "low": float(row["low"]),
                    "close": float(row["close"]),
                    "volume": float(row.get("volume") or 100),
                }
            )
    return bars


def bars_to_rates(bars: list[dict[str, float]], count: int | None = None) -> np.ndarray:
    slice_bars = bars[-count:] if count else bars
    n = len(slice_bars)
    arr = np.zeros(n, dtype=MT5_RATES_DTYPE)
    now = int(datetime.now(TZ_BR).timestamp())
    for i, b in enumerate(slice_bars):
        arr[i]["time"] = now - (n - i) * 60
        arr[i]["open"] = b["open"]
        arr[i]["high"] = b["high"]
        arr[i]["low"] = b["low"]
        arr[i]["close"] = b["close"]
        arr[i]["tick_volume"] = int(b.get("volume", 100))
        arr[i]["spread"] = 5
        arr[i]["real_volume"] = 0
    return arr


EQUITY_BASE_PRICES: dict[str, float] = {
    "PETR4": 38.5,
    "VALE3": 62.0,
    "ITUB4": 32.0,
    "BBDC4": 14.5,
    "ABEV3": 12.8,
    "MGLU3": 3.2,
    "WEGE3": 42.0,
    "RENT3": 48.0,
    "BBAS3": 28.0,
    "SUZB3": 58.0,
}


def _equity_seed_bars(base: float, bars: int = 200) -> list[dict[str, float]]:
    price = base
    out: list[dict[str, float]] = []
    for _ in range(bars):
        move = random.gauss(0, 0.08)
        open_p = price
        close_p = max(0.5, open_p + move)
        high_p = max(open_p, close_p) + abs(random.gauss(0, 0.04))
        low_p = min(open_p, close_p) - abs(random.gauss(0, 0.04))
        price = close_p
        out.append(
            {
                "open": round(open_p, 2),
                "high": round(high_p, 2),
                "low": round(low_p, 2),
                "close": round(close_p, 2),
                "volume": random.randint(50, 400),
            }
        )
    return out


class WinMarketSimulator:
    """Random walk com histórico M1 para a estratégia."""

    def __init__(self, symbol: str, base_price: float | None = None) -> None:
        self.symbol = symbol
        sym = symbol.upper().replace("$", "")
        is_equity = sym in EQUITY_BASE_PRICES or (
            not sym.startswith("WIN") and not sym.startswith("WDO")
        )
        if is_equity and sym not in ("WIN", "WIN$"):
            base = base_price or EQUITY_BASE_PRICES.get(sym, 25.0)
            self._bars = _equity_seed_bars(base)
            self._mid = float(self._bars[-1]["close"])
            self._spread_pts = 0.04
            self._tick_sigma = 0.05
            self._min_price = 0.5
        else:
            ensure_sample_csv()
            seed_bars = _load_bars_from_csv(SAMPLE_CSV)
            self._bars: list[dict[str, float]] = list(seed_bars[-120:])
            self._mid = base_price or float(settings.sim_base_price)
            if self._bars:
                self._mid = float(self._bars[-1]["close"])
            self._spread_pts = 5.0
            self._tick_sigma = 8.0
            self._min_price = 1000.0

    @property
    def mid(self) -> float:
        return self._mid

    def step_tick(self) -> dict[str, float]:
        """Avança um passo de preço (WIN ou ação B3 simulada)."""
        self._mid = max(self._min_price, self._mid + random.gauss(0, self._tick_sigma))
        half = self._spread_pts / 2
        bid = round(self._mid - half, 2)
        ask = round(self._mid + half, 2)
        last_bar = self._bars[-1]
        last_bar["close"] = self._mid
        last_bar["high"] = max(last_bar["high"], self._mid)
        last_bar["low"] = min(last_bar["low"], self._mid)
        return {"bid": bid, "ask": ask, "last": self._mid}

    def maybe_roll_m1(self) -> None:
        """A cada chamada, chance de fechar candle M1 e abrir outro."""
        if random.random() > 0.35:
            return
        prev = self._bars[-1]
        new_open = prev["close"]
        self._bars.append(
            {
                "open": new_open,
                "high": new_open,
                "low": new_open,
                "close": new_open,
                "volume": random.randint(50, 400),
            }
        )
        if len(self._bars) > 200:
            self._bars = self._bars[-150:]

    def copy_rates(self, count: int = 100) -> np.ndarray:
        return bars_to_rates(self._bars, count)

    def demo_signal_payload(
        self,
        side: str,
        stop_loss_pct: float | None = None,
        take_profit_pct: float | None = None,
    ) -> tuple[float, float, float]:
        """Entrada/stop/alvo para sinal demo periódico."""
        tick = self.step_tick()
        entry = tick["ask"] if side == "BUY" else tick["bid"]
        sym = self.symbol.upper().replace("$", "")
        use_pct = sym in EQUITY_BASE_PRICES or (
            not sym.startswith("WIN") and not sym.startswith("WDO")
        )
        if use_pct:
            sl = stop_loss_pct if stop_loss_pct is not None else 2.0
            tp = take_profit_pct if take_profit_pct is not None else 3.0
            if side == "BUY":
                return entry, entry * (1 - sl / 100), entry * (1 + tp / 100)
            return entry, entry * (1 + sl / 100), entry * (1 - tp / 100)
        stop_pts = settings.stop_points
        target_pts = settings.target_points
        if side == "BUY":
            return entry, entry - stop_pts, entry + target_pts
        return entry, entry + stop_pts, entry - target_pts
