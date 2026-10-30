import type {
  IChartApi,
  ISeriesApi,
  CandlestickData,
  SeriesMarker,
  Time,
} from "lightweight-charts";
import type { MarketStructureResponse } from "../api/client";
import type { ChartLevelLine } from "./riverChart";

function candleSec(t: Time): number {
  return typeof t === "number" ? t : 0;
}

function snapTimeToCandles(targetSec: number, candles: CandlestickData[]): Time {
  if (!candles.length) return targetSec as Time;
  let best = candles[0];
  let bestDist = Math.abs(candleSec(best.time) - targetSec);
  for (const c of candles) {
    const d = Math.abs(candleSec(c.time) - targetSec);
    if (d < bestDist) {
      bestDist = d;
      best = c;
    }
  }
  return best.time;
}

export function structureLevelLines(data: MarketStructureResponse | null): ChartLevelLine[] {
  if (!data?.choch?.price) return [];
  const dir = data.choch.direction;
  const color =
    dir === "bearish" ? "rgba(244, 114, 182, 0.88)" : "rgba(52, 211, 153, 0.88)";
  return [
    {
      price: data.choch.price,
      label: "CHoCH",
      color,
      style: "dashed",
      width: 2,
    },
  ];
}

export function structureMarkers(
  data: MarketStructureResponse | null,
  candles: CandlestickData[],
): SeriesMarker<Time>[] {
  if (!data) return [];
  const out: SeriesMarker<Time>[] = [];

  for (const s of data.swings.slice(-10)) {
    const time = snapTimeToCandles(Number(s.time), candles);
    const isHigh = s.kind === "high";
    out.push({
      time,
      position: isHigh ? "aboveBar" : "belowBar",
      shape: "circle",
      color: "rgba(148, 163, 184, 0.85)",
      text: s.label,
    });
  }

  if (data.choch) {
    const time = snapTimeToCandles(Number(data.choch.time), candles);
    out.push({
      time,
      position: data.choch.direction === "bearish" ? "aboveBar" : "belowBar",
      shape: "square",
      color: data.choch.direction === "bearish" ? "#f472b6" : "#34d399",
      text: "CHoCH",
    });
  }

  for (const f of data.fvgs.slice(-3)) {
    const time = snapTimeToCandles(Number(f.time), candles);
    out.push({
      time,
      position: f.direction === "bullish" ? "belowBar" : "aboveBar",
      shape: "arrowUp",
      color: "rgba(251, 191, 36, 0.75)",
      text: "FVG",
    });
  }

  for (const z of data.zones.slice(-4)) {
    const time = snapTimeToCandles(Number(z.time_start), candles);
    const isSupply = z.type === "supply";
    out.push({
      time,
      position: isSupply ? "aboveBar" : "belowBar",
      shape: "square",
      color: isSupply ? "rgba(248, 113, 113, 0.82)" : "rgba(56, 189, 248, 0.82)",
      text: isSupply ? "OB−" : "OB+",
    });
  }

  return out.sort((a, b) => candleSec(a.time) - candleSec(b.time));
}

type ZoneOverlayState = {
  root: HTMLElement;
  chart: IChartApi;
  raf: number;
  pending: boolean;
  lastData: MarketStructureResponse | null;
  lastCandles: CandlestickData[] | null;
  onChange: () => void;
  ro: ResizeObserver;
};

let zoneOverlay: ZoneOverlayState | null = null;

function clearZoneChildren(root: HTMLElement): void {
  root.replaceChildren();
}

function renderZones(
  root: HTMLElement,
  chart: IChartApi,
  series: ISeriesApi<"Candlestick">,
  data: MarketStructureResponse,
  candles: CandlestickData[],
): void {
  clearZoneChildren(root);
  if (!candles.length) return;

  const ts = chart.timeScale();
  const w = root.clientWidth;
  const rightX = w > 0 ? w - 4 : 0;

  for (const z of data.zones) {
    const yTop = series.priceToCoordinate(z.price_top);
    const yBot = series.priceToCoordinate(z.price_bottom);
    if (yTop == null || yBot == null) continue;

    const tStart = snapTimeToCandles(Number(z.time_start), candles);
    const x0 = ts.timeToCoordinate(tStart);
    const top = Math.min(yTop, yBot);
    const height = Math.max(Math.abs(yBot - yTop), 6);

    const box = document.createElement("div");
    box.className = `deck-zone deck-zone-${z.type}`;
    const left = x0 != null ? Math.max(0, x0) : 0;
    box.style.left = `${left}px`;
    box.style.top = `${top}px`;
    box.style.width = `${Math.max(rightX - left, 40)}px`;
    box.style.height = `${height}px`;

    const label = document.createElement("span");
    label.className = "deck-zone-label";
    label.textContent = z.label_pt;
    box.appendChild(label);
    root.appendChild(box);
  }

  for (const f of data.fvgs) {
    const yTop = series.priceToCoordinate(f.top);
    const yBot = series.priceToCoordinate(f.bottom);
    if (yTop == null || yBot == null) continue;
    const t = snapTimeToCandles(Number(f.time), candles);
    const x = ts.timeToCoordinate(t);
    const top = Math.min(yTop, yBot);
    const height = Math.max(Math.abs(yBot - yTop), 4);
    const gap = document.createElement("div");
    gap.className = `deck-fvg deck-fvg-${f.direction}`;
    gap.style.left = x != null ? `${Math.max(0, x - 18)}px` : "0";
    gap.style.top = `${top}px`;
    gap.style.width = "36px";
    gap.style.height = `${height}px`;
    root.appendChild(gap);
  }
}

export function ensureStructureZoneLayer(frame: HTMLElement): HTMLElement {
  let layer = frame.querySelector<HTMLElement>(".deck-chart-zones");
  if (!layer) {
    layer = document.createElement("div");
    layer.className = "deck-chart-zones";
    layer.setAttribute("aria-hidden", "true");
    frame.appendChild(layer);
  }
  return layer;
}

export function bindStructureZoneOverlay(
  frame: HTMLElement,
  chart: IChartApi,
  series: ISeriesApi<"Candlestick">,
): void {
  detachStructureZoneOverlay();
  const root = ensureStructureZoneLayer(frame);
  const onChange = () => {
    if (!zoneOverlay) return;
    zoneOverlay.pending = true;
    cancelAnimationFrame(zoneOverlay.raf);
    zoneOverlay.raf = requestAnimationFrame(() => {
      if (!zoneOverlay?.lastData || !zoneOverlay.lastCandles) return;
      renderZones(root, chart, series, zoneOverlay.lastData, zoneOverlay.lastCandles);
      zoneOverlay.pending = false;
    });
  };
  chart.timeScale().subscribeVisibleLogicalRangeChange(onChange);
  const ro = new ResizeObserver(onChange);
  ro.observe(frame);
  zoneOverlay = {
    root,
    chart,
    raf: 0,
    pending: false,
    lastData: null,
    lastCandles: null,
    onChange,
    ro,
  };
}

export function updateStructureZoneOverlay(
  data: MarketStructureResponse | null,
  candles: CandlestickData[],
  enabled: boolean,
  chart: IChartApi | null,
  series: ISeriesApi<"Candlestick"> | null,
): void {
  if (!zoneOverlay || !chart || !series) return;
  zoneOverlay.lastData = enabled ? data : null;
  zoneOverlay.lastCandles = candles;
  if (!enabled || !data) {
    clearZoneChildren(zoneOverlay.root);
    return;
  }
  zoneOverlay.onChange();
}

export function detachStructureZoneOverlay(): void {
  if (zoneOverlay) {
    zoneOverlay.chart.timeScale().unsubscribeVisibleLogicalRangeChange(zoneOverlay.onChange);
    zoneOverlay.ro.disconnect();
    clearZoneChildren(zoneOverlay.root);
  }
  zoneOverlay = null;
}

export const STRUCTURE_STORAGE_KEY = "sala_pulse_structure_smc";

export function readStructureToggleDefault(): boolean {
  try {
    const v = localStorage.getItem(STRUCTURE_STORAGE_KEY);
    if (v === "0") return false;
    if (v === "1") return true;
  } catch {
    /* ignore */
  }
  return true;
}

export function persistStructureToggle(on: boolean): void {
  try {
    localStorage.setItem(STRUCTURE_STORAGE_KEY, on ? "1" : "0");
  } catch {
    /* ignore */
  }
}
