export type OhlcBar = {
  time?: number;
  open: number;
  high: number;
  low: number;
  close: number;
};

export type ChartMarker = {
  time: number;
  price: number;
  kind: "entry" | "exit";
  side?: "BUY" | "SELL";
  outcome?: "win" | "loss";
  tooltip?: string;
};

export type ChartLevelLine = {
  price: number;
  label: string;
  color: string;
  style?: "solid" | "dashed";
  width?: 1 | 2;
};

let resizeObserver: ResizeObserver | null = null;
let cachedBars: OhlcBar[] = [];
let cachedMarkers: ChartMarker[] = [];
let cachedLevels: ChartLevelLine[] = [];
let boundCanvas: HTMLCanvasElement | null = null;

function ensureCanvasSize(canvas: HTMLCanvasElement): boolean {
  const w = canvas.clientWidth;
  const h = canvas.clientHeight;
  if (w < 8 || h < 8) return false;
  const dpr = devicePixelRatio;
  const nw = Math.floor(w * dpr);
  const nh = Math.floor(h * dpr);
  if (canvas.width !== nw || canvas.height !== nh) {
    canvas.width = nw;
    canvas.height = nh;
  }
  return true;
}

function paintEmptyState(ctx: CanvasRenderingContext2D, w: number, h: number): void {
  const dpr = devicePixelRatio;
  ctx.fillStyle = "#64748b";
  ctx.font = `600 ${14 * dpr}px "IBM Plex Sans", system-ui, sans-serif`;
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.fillText("Sem dados — inicie o engine", w / 2, h / 2 - 10 * dpr);
  ctx.font = `400 ${12 * dpr}px "IBM Plex Sans", system-ui, sans-serif`;
  ctx.fillStyle = "#475569";
  ctx.fillText("OHLC aparecerá quando a API enviar barras M5", w / 2, h / 2 + 14 * dpr);
  ctx.textAlign = "left";
  ctx.textBaseline = "alphabetic";
}

function paintChartOn(canvas: HTMLCanvasElement, bars: OhlcBar[], markers: ChartMarker[], levels: ChartLevelLine[]): void {
  const ctx = canvas.getContext("2d");
  if (!ctx) return;
  if (!ensureCanvasSize(canvas)) return;
  const w = canvas.width;
  const h = canvas.height;
  ctx.clearRect(0, 0, w, h);

  const pad = {
    t: 16 * devicePixelRatio,
    r: 16 * devicePixelRatio,
    b: 32 * devicePixelRatio,
    l: 52 * devicePixelRatio,
  };
  const plotW = w - pad.l - pad.r;
  const plotH = h - pad.t - pad.b;

  if (!bars.length) {
    paintEmptyState(ctx, w, h);
    return;
  }

  let lo = Infinity;
  let hi = -Infinity;
  for (const b of bars) {
    lo = Math.min(lo, b.low);
    hi = Math.max(hi, b.high);
  }
  for (const lv of levels) {
    lo = Math.min(lo, lv.price);
    hi = Math.max(hi, lv.price);
  }
  const margin = (hi - lo) * 0.06 || 1;
  lo -= margin;
  hi += margin;

  const y = (price: number) => pad.t + plotH * (1 - (price - lo) / (hi - lo));
  const n = bars.length;
  const slot = plotW / n;
  const bodyW = Math.max(2 * devicePixelRatio, slot * 0.55);

  ctx.strokeStyle = "rgba(148, 163, 184, 0.15)";
  ctx.lineWidth = devicePixelRatio;
  for (let i = 0; i <= 4; i++) {
    const gy = pad.t + (plotH * i) / 4;
    ctx.beginPath();
    ctx.moveTo(pad.l, gy);
    ctx.lineTo(pad.l + plotW, gy);
    ctx.stroke();
  }

  bars.forEach((b, i) => {
    const cx = pad.l + slot * i + slot / 2;
    const up = b.close >= b.open;
    ctx.strokeStyle = up ? "#34d399" : "#f87171";
    ctx.fillStyle = up ? "rgba(52, 211, 153, 0.28)" : "rgba(248, 113, 113, 0.28)";
    ctx.lineWidth = Math.max(1, devicePixelRatio);
    ctx.beginPath();
    ctx.moveTo(cx, y(b.high));
    ctx.lineTo(cx, y(b.low));
    ctx.stroke();
    const top = y(Math.max(b.open, b.close));
    const bot = y(Math.min(b.open, b.close));
    const bh = Math.max(devicePixelRatio * 2, bot - top);
    ctx.fillRect(cx - bodyW / 2, top, bodyW, bh);
    ctx.strokeRect(cx - bodyW / 2, top, bodyW, bh);
  });

  const tMin = (bars[0].time ?? 0) * 1000;
  const tMax = (bars[n - 1].time ?? 0) * 1000;
  const tSpan = tMax - tMin || 1;

  ctx.setLineDash([6 * devicePixelRatio, 4 * devicePixelRatio]);
  levels.forEach((lv) => {
    const gy = y(lv.price);
    ctx.strokeStyle = lv.color;
    ctx.lineWidth = Math.max(1.5, devicePixelRatio * 1.5);
    ctx.beginPath();
    ctx.moveTo(pad.l, gy);
    ctx.lineTo(pad.l + plotW, gy);
    ctx.stroke();
    ctx.fillStyle = lv.color;
    ctx.font = `${10 * devicePixelRatio}px "IBM Plex Mono", monospace`;
    ctx.fillText(lv.label, pad.l + 4 * devicePixelRatio, gy - 4 * devicePixelRatio);
  });
  ctx.setLineDash([]);

  markers.forEach((m) => {
    const tx = pad.l + plotW * ((m.time * 1000 - tMin) / tSpan);
    const py = y(m.price);
    const entryColor =
      m.side === "SELL" ? "#f87171" : m.side === "BUY" ? "#34d399" : m.kind === "entry" ? "#38bdf8" : "#f87171";
    ctx.fillStyle = m.kind === "entry" ? entryColor : "#c084fc";
    ctx.beginPath();
    if (m.kind === "entry") {
      ctx.moveTo(tx, py - 8 * devicePixelRatio);
      ctx.lineTo(tx - 6 * devicePixelRatio, py + 6 * devicePixelRatio);
      ctx.lineTo(tx + 6 * devicePixelRatio, py + 6 * devicePixelRatio);
    } else {
      ctx.moveTo(tx, py + 8 * devicePixelRatio);
      ctx.lineTo(tx - 6 * devicePixelRatio, py - 6 * devicePixelRatio);
      ctx.lineTo(tx + 6 * devicePixelRatio, py - 6 * devicePixelRatio);
    }
    ctx.closePath();
    ctx.fill();
  });

  ctx.fillStyle = "#94a3b8";
  ctx.font = `${11 * devicePixelRatio}px "IBM Plex Mono", monospace`;
  ctx.fillText(lo.toFixed(2), 6 * devicePixelRatio, pad.t + plotH);
  ctx.fillText(hi.toFixed(2), 6 * devicePixelRatio, pad.t + 12 * devicePixelRatio);
}

function paintChart(): void {
  if (!boundCanvas) return;
  paintChartOn(boundCanvas, cachedBars, cachedMarkers, cachedLevels);
}

export function renderRiverOnCanvas(
  canvas: HTMLCanvasElement,
  bars: OhlcBar[],
  markers: ChartMarker[],
  levels: ChartLevelLine[] = [],
): void {
  paintChartOn(canvas, bars, markers, levels);
}

export function bindRiverChart(canvas: HTMLCanvasElement): () => void {
  boundCanvas = canvas;
  const onResize = () => {
    requestAnimationFrame(() => paintChart());
  };
  resizeObserver = new ResizeObserver(onResize);
  resizeObserver.observe(canvas);
  const parent = canvas.closest(".river-chart-body");
  if (parent instanceof HTMLElement) resizeObserver.observe(parent);
  onResize();
  return () => {
    resizeObserver?.disconnect();
    resizeObserver = null;
    if (boundCanvas === canvas) boundCanvas = null;
  };
}

export function drawRiverChart(
  canvas: HTMLCanvasElement,
  bars: OhlcBar[],
  markers: ChartMarker[],
  levels: ChartLevelLine[] = [],
): void {
  cachedBars = bars;
  cachedMarkers = markers;
  cachedLevels = levels;
  if (boundCanvas === canvas) {
    requestAnimationFrame(() => paintChart());
  }
}
