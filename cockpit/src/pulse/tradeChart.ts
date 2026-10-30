import {
  createChart,
  type IChartApi,
  type ISeriesApi,
  type CandlestickData,
  type LineData,
  type HistogramData,
  type Time,
  type IPriceLine,
  type SeriesMarker,
} from "lightweight-charts";
import type { OhlcBar } from "./riverChart";
import type { ChartLevelLine, ChartMarker } from "./riverChart";
import type { MarketStructureResponse } from "../api/client";
import {
  bindStructureZoneOverlay,
  detachStructureZoneOverlay,
  structureMarkers,
  structureLevelLines,
  updateStructureZoneOverlay,
} from "./structureChart";

export type StrategySeries = {
  times: Array<number | null | undefined>;
  bb_upper: Array<number | null>;
  bb_mid: Array<number | null>;
  bb_lower: Array<number | null>;
};

export type ChartRangeMode = "session" | "recent" | "all";

let chart: IChartApi | null = null;
let candleSeries: ISeriesApi<"Candlestick"> | null = null;
let bbUpper: ISeriesApi<"Line"> | null = null;
let bbMid: ISeriesApi<"Line"> | null = null;
let bbLower: ISeriesApi<"Line"> | null = null;
let volumeSeries: ISeriesApi<"Histogram"> | null = null;
let boundHost: HTMLElement | null = null;
let levelLines: IPriceLine[] = [];
let lastCandles: CandlestickData[] = [];
let userAdjustedRange = false;
let suppressRangeEvents = false;
let chartSymbolKey = "";
let structureEnabled = true;
let structureCache: MarketStructureResponse | null = null;
let zoneOverlayBound = false;

function barTimeSec(b: OhlcBar, index: number): number {
  if (b.time != null) {
    const t = Number(b.time);
    if (Number.isFinite(t)) return t > 1e12 ? Math.floor(t / 1000) : Math.floor(t);
  }
  return Math.floor(Date.now() / 1000) - (500 - index) * 300;
}

function toCandles(bars: OhlcBar[]): CandlestickData[] {
  const mapped = bars.map((b, i) => ({
    time: barTimeSec(b, i),
    open: Number(b.open),
    high: Number(b.high),
    low: Number(b.low),
    close: Number(b.close),
  }));
  mapped.sort((a, b) => a.time - b.time);
  const out: CandlestickData[] = [];
  let lastT = -1;
  for (const c of mapped) {
    if (!Number.isFinite(c.open) || !Number.isFinite(c.high) || !Number.isFinite(c.low) || !Number.isFinite(c.close)) {
      continue;
    }
    let t = c.time;
    if (t <= lastT) t = lastT + 1;
    lastT = t;
    out.push({ time: t as Time, open: c.open, high: c.high, low: c.low, close: c.close });
  }
  return out;
}

function volumeFromBars(bars: OhlcBar[], candles: CandlestickData[]): HistogramData[] | null {
  let hasVol = false;
  const data: HistogramData[] = [];
  const n = Math.min(bars.length, candles.length);
  for (let i = 0; i < n; i++) {
    const raw = (bars[i] as OhlcBar & { volume?: number }).volume;
    const vol = raw != null ? Number(raw) : 0;
    if (vol > 0) hasVol = true;
    const up = candles[i].close >= candles[i].open;
    data.push({
      time: candles[i].time,
      value: vol,
      color: up ? "rgba(52, 211, 153, 0.45)" : "rgba(248, 113, 113, 0.45)",
    });
  }
  return hasVol ? data : null;
}

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

function brtDateKey(sec: number): string {
  return new Date(sec * 1000).toLocaleDateString("en-CA", { timeZone: "America/Sao_Paulo" });
}

function brtHourMinute(sec: number): { h: number; m: number } {
  const parts = new Intl.DateTimeFormat("en-GB", {
    timeZone: "America/Sao_Paulo",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).formatToParts(new Date(sec * 1000));
  const h = Number(parts.find((p) => p.type === "hour")?.value ?? 0);
  const m = Number(parts.find((p) => p.type === "minute")?.value ?? 0);
  return { h, m };
}

function sessionOpenIndex(candles: CandlestickData[]): number {
  if (!candles.length) return 0;
  const today = brtDateKey(candleSec(candles[candles.length - 1].time));
  for (let i = 0; i < candles.length; i++) {
    const sec = candleSec(candles[i].time);
    if (brtDateKey(sec) !== today) continue;
    const { h, m } = brtHourMinute(sec);
    if (h > 10 || (h === 10 && m >= 0)) return i;
  }
  for (let i = 0; i < candles.length; i++) {
    if (brtDateKey(candleSec(candles[i].time)) === today) return i;
  }
  return 0;
}

function applyVisibleRange(mode: ChartRangeMode): void {
  if (!chart || lastCandles.length === 0) return;
  const n = lastCandles.length;
  let from = 0;
  let to = n + 1;
  if (mode === "all") {
    from = 0;
    to = n + 1;
  } else if (mode === "session") {
    from = sessionOpenIndex(lastCandles);
    to = n + 1;
    if (to - from < 12 && n > 24) {
      from = Math.max(0, n - 96);
    }
  } else {
    from = Math.max(0, n - 72);
    to = n + 1;
  }
  suppressRangeEvents = true;
  chart.timeScale().setVisibleLogicalRange({ from, to });
  window.setTimeout(() => {
    suppressRangeEvents = false;
  }, 50);
}

export function setStructureLayerEnabled(on: boolean): void {
  structureEnabled = on;
}

export function getStructureLayerEnabled(): boolean {
  return structureEnabled;
}

export function resetChartViewForSymbol(symbol: string): void {
  const key = symbol.toUpperCase();
  if (key !== chartSymbolKey) {
    chartSymbolKey = key;
    userAdjustedRange = false;
  }
}

export function setChartTimeRange(mode: ChartRangeMode): void {
  userAdjustedRange = true;
  applyVisibleRange(mode);
}

function measureChartBox(): { w: number; h: number } {
  if (!boundHost) return { w: 320, h: 240 };
  const frame = boundHost.closest(".deck-chart-frame") as HTMLElement | null;
  const box = (frame && frame.clientHeight > 8 ? frame : boundHost).getBoundingClientRect();
  return {
    w: Math.max(Math.floor(box.width), 280),
    h: Math.max(Math.floor(box.height), 200),
  };
}

function applyChartSize(): void {
  if (!chart || !boundHost) return;
  const { w, h } = measureChartBox();
  chart.applyOptions({ width: w, height: h });
}

export function resizeTradeChart(): void {
  applyChartSize();
}

function markerToSeries(m: ChartMarker, candles: CandlestickData[]): SeriesMarker<Time> | null {
  if (!Number.isFinite(m.price)) return null;
  const time = snapTimeToCandles(m.time, candles);
  const sell = m.side === "SELL";
  const win = m.outcome === "win";
  const loss = m.outcome === "loss";

  if (m.kind === "exit") {
    if (win) {
      return {
        time,
        position: "aboveBar",
        shape: "circle",
        color: "#34d399",
        text: "Acerto",
      };
    }
    if (loss) {
      return {
        time,
        position: "aboveBar",
        shape: "circle",
        color: "#f87171",
        text: "Erro",
      };
    }
    return {
      time,
      position: "aboveBar",
      shape: "square",
      color: "#c084fc",
      text: "Saida",
    };
  }

  if (win) {
    return {
      time,
      position: sell ? "aboveBar" : "belowBar",
      shape: "circle",
      color: "#34d399",
      text: "✓",
    };
  }
  if (loss) {
    return {
      time,
      position: sell ? "aboveBar" : "belowBar",
      shape: "circle",
      color: "#f87171",
      text: "✗",
    };
  }

  return {
    time,
    position: sell ? "aboveBar" : "belowBar",
    shape: sell ? "arrowDown" : "arrowUp",
    color: sell ? "#f87171" : "#38bdf8",
    text: sell ? "V" : "C",
  };
}

export function bindTradeChart(host: HTMLElement): () => void {
  boundHost = host;
  host.innerHTML = "";
  const { w: initialW, h: initialH } = measureChartBox();
  chart = createChart(host, {
    layout: {
      background: { color: "#0c0e14" },
      textColor: "#94a3b8",
    },
    grid: {
      vertLines: { color: "rgba(255,255,255,0.05)" },
      horzLines: { color: "rgba(255,255,255,0.05)" },
    },
    rightPriceScale: { borderColor: "rgba(148,163,184,0.2)" },
    timeScale: {
      borderColor: "rgba(148,163,184,0.2)",
      timeVisible: true,
      secondsVisible: false,
      barSpacing: 9,
      minBarSpacing: 2,
      fixLeftEdge: false,
      fixRightEdge: false,
      rightOffset: 4,
    },
    handleScroll: { mouseWheel: true, pressedMouseMove: true, horzTouchDrag: true, vertTouchDrag: false },
    handleScale: { axisPressedMouseMove: true, mouseWheel: true, pinch: true },
    width: initialW,
    height: initialH,
  });
  candleSeries = chart.addCandlestickSeries({
    upColor: "#34d399",
    downColor: "#f87171",
    borderVisible: false,
    wickUpColor: "#34d399",
    wickDownColor: "#f87171",
  });
  bbUpper = chart.addLineSeries({
    color: "rgba(251, 113, 133, 0.78)",
    lineWidth: 2,
    priceLineVisible: false,
    lastValueVisible: false,
  });
  bbMid = chart.addLineSeries({
    color: "rgba(56, 189, 248, 0.5)",
    lineWidth: 1,
    lineStyle: 2,
    priceLineVisible: false,
    lastValueVisible: false,
  });
  bbLower = chart.addLineSeries({
    color: "rgba(52, 211, 153, 0.78)",
    lineWidth: 2,
    priceLineVisible: false,
    lastValueVisible: false,
  });
  volumeSeries = chart.addHistogramSeries({
    priceFormat: { type: "volume" },
    priceScaleId: "vol",
  });
  chart.priceScale("vol").applyOptions({
    scaleMargins: { top: 0.82, bottom: 0 },
  });
  candleSeries.priceScale().applyOptions({
    scaleMargins: { top: 0.05, bottom: 0.22 },
  });

  const frame = host.closest(".deck-chart-frame") as HTMLElement | null;
  if (frame && candleSeries && !zoneOverlayBound) {
    bindStructureZoneOverlay(frame, chart, candleSeries);
    zoneOverlayBound = true;
  }

  chart.timeScale().subscribeVisibleLogicalRangeChange(() => {
    if (suppressRangeEvents) return;
    userAdjustedRange = true;
  });

  const ro = new ResizeObserver(() => {
    applyChartSize();
  });
  const frameForRo = host.closest(".deck-chart-frame") as HTMLElement | null;
  if (frameForRo) ro.observe(frameForRo);
  else ro.observe(host);

  requestAnimationFrame(() => {
    requestAnimationFrame(() => applyChartSize());
  });

  return () => {
    ro.disconnect();
    detachStructureZoneOverlay();
    zoneOverlayBound = false;
    chart?.remove();
    chart = null;
    candleSeries = null;
    bbUpper = bbMid = bbLower = null;
    volumeSeries = null;
    boundHost = null;
    lastCandles = [];
    structureCache = null;
  };
}

export function updateTradeChart(
  bars: OhlcBar[],
  markers: ChartMarker[],
  levels: ChartLevelLine[],
  strategy?: StrategySeries | null,
  symbol?: string,
  structure?: MarketStructureResponse | null,
): void {
  if (!candleSeries || !chart) return;
  if (symbol) resetChartViewForSymbol(symbol);
  if (structure !== undefined) structureCache = structure;

  levelLines.forEach((line) => candleSeries?.removePriceLine(line));
  levelLines = [];

  const candles = toCandles(bars);
  lastCandles = candles;
  candleSeries.setData(candles);

  const volData = volumeFromBars(bars, candles);
  if (volumeSeries) {
    if (volData) volumeSeries.setData(volData);
    else volumeSeries.setData([]);
  }

  if (strategy && bbUpper && bbMid && bbLower && candles.length > 0) {
    const upperData: LineData[] = [];
    const midData: LineData[] = [];
    const lowerData: LineData[] = [];
    const n = Math.min(candles.length, strategy.bb_upper.length);
    for (let i = 0; i < n; i++) {
      const t = candles[i].time;
      const u = strategy.bb_upper[i];
      const m = strategy.bb_mid[i];
      const l = strategy.bb_lower[i];
      if (u != null) upperData.push({ time: t, value: u });
      if (m != null) midData.push({ time: t, value: m });
      if (l != null) lowerData.push({ time: t, value: l });
    }
    bbUpper.setData(upperData);
    bbMid.setData(midData);
    bbLower.setData(lowerData);
  } else if (bbUpper && bbMid && bbLower) {
    bbUpper.setData([]);
    bbMid.setData([]);
    bbLower.setData([]);
  }

  const markersOnSeries = markers
    .map((m) => markerToSeries(m, candles))
    .filter((m): m is SeriesMarker<Time> => m != null);

  const structOn = structureEnabled && structureCache;
  const structMarkers = structOn ? structureMarkers(structureCache, candles) : [];
  const mergedMarkers = [...markersOnSeries, ...structMarkers]
    .sort((a, b) => candleSec(a.time) - candleSec(b.time))
    .slice(-32);

  candleSeries.setMarkers(mergedMarkers);

  const allLevels = structOn ? [...levels, ...structureLevelLines(structureCache)] : levels;
  allLevels.forEach((lv) => {
    const pl = candleSeries!.createPriceLine({
      price: lv.price,
      color: lv.color,
      lineWidth: lv.width ?? 2,
      lineStyle: lv.style === "dashed" ? 2 : 0,
      axisLabelVisible: true,
      title: lv.label,
    });
    levelLines.push(pl);
  });

  updateStructureZoneOverlay(
    structureCache,
    candles,
    Boolean(structOn),
    chart,
    candleSeries,
  );

  if (candles.length === 0) {
    chart.timeScale().fitContent();
  } else if (!userAdjustedRange) {
    applyVisibleRange("session");
  }
  requestAnimationFrame(() => {
    applyChartSize();
    if (candles.length > 0 && !userAdjustedRange) applyVisibleRange("session");
  });
}
