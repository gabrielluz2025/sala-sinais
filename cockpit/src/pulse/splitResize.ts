import { resizeTradeChart } from "./tradeChart";

const STORAGE_KEY = "pulse_deck_curtains_w";
const DEFAULT_WIDTH = 440;
const MIN_WIDTH = 280;
const MAX_WIDTH = 560;
const MAX_WIDTH_RATIO = 0.35;
const KEY_STEP = 12;
const KEY_STEP_LARGE = 32;

function parseStoredWidth(raw: string | null): number | null {
  if (raw == null || raw === "") return null;
  const n = Number.parseFloat(raw);
  if (!Number.isFinite(n)) return null;
  return n;
}

function maxAllowed(mainEl: HTMLElement): number {
  const byRatio = mainEl.clientWidth * MAX_WIDTH_RATIO;
  return Math.min(MAX_WIDTH, Math.max(MIN_WIDTH, byRatio));
}

function clampWidth(mainEl: HTMLElement, width: number): number {
  const max = maxAllowed(mainEl);
  return Math.min(max, Math.max(MIN_WIDTH, width));
}

function applyWidth(mainEl: HTMLElement, widthPx: number): void {
  const clamped = clampWidth(mainEl, widthPx);
  mainEl.style.setProperty("--deck-curtains-w", `${Math.round(clamped)}px`);
}

function readAppliedWidth(mainEl: HTMLElement): number {
  const raw = getComputedStyle(mainEl).getPropertyValue("--deck-curtains-w").trim();
  const n = Number.parseFloat(raw);
  return Number.isFinite(n) ? n : DEFAULT_WIDTH;
}

function persistWidth(width: number): void {
  try {
    localStorage.setItem(STORAGE_KEY, String(Math.round(width)));
  } catch {
    /* quota / private mode */
  }
}

function loadStoredWidth(): number | null {
  try {
    return parseStoredWidth(localStorage.getItem(STORAGE_KEY));
  } catch {
    return null;
  }
}

export function initDeckSplitResize(): void {
  const handle = document.getElementById("deck-split-handle");
  const mainEl = document.querySelector<HTMLElement>(".deck-main");
  if (!handle || !mainEl) return;

  const stored = loadStoredWidth();
  applyWidth(mainEl, stored ?? DEFAULT_WIDTH);

  let dragging = false;

  const endDrag = (): void => {
    if (!dragging) return;
    dragging = false;
    handle.classList.remove("is-dragging");
    document.body.classList.remove("deck-split-dragging");
    persistWidth(readAppliedWidth(mainEl));
    resizeTradeChart();
  };

  const onPointerMove = (e: PointerEvent): void => {
    if (!dragging) return;
    const rect = mainEl.getBoundingClientRect();
    const fromRight = rect.right - e.clientX;
    applyWidth(mainEl, fromRight);
    resizeTradeChart();
  };

  handle.addEventListener("pointerdown", (e) => {
    if (e.button !== 0) return;
    if (window.matchMedia("(max-width: 960px)").matches) return;
    e.preventDefault();
    dragging = true;
    handle.classList.add("is-dragging");
    document.body.classList.add("deck-split-dragging");
    handle.setPointerCapture(e.pointerId);
  });

  handle.addEventListener("pointermove", onPointerMove);

  handle.addEventListener("pointerup", (e) => {
    if (handle.hasPointerCapture(e.pointerId)) {
      handle.releasePointerCapture(e.pointerId);
    }
    endDrag();
  });

  handle.addEventListener("pointercancel", endDrag);

  handle.addEventListener("dblclick", () => {
    applyWidth(mainEl, DEFAULT_WIDTH);
    persistWidth(DEFAULT_WIDTH);
    resizeTradeChart();
  });

  handle.addEventListener("keydown", (e) => {
    if (window.matchMedia("(max-width: 960px)").matches) return;
    const step = e.shiftKey ? KEY_STEP_LARGE : KEY_STEP;
    let delta = 0;
    if (e.key === "ArrowLeft") delta = -step;
    else if (e.key === "ArrowRight") delta = step;
    if (delta === 0) return;
    e.preventDefault();
    const next = readAppliedWidth(mainEl) + delta;
    applyWidth(mainEl, next);
    persistWidth(readAppliedWidth(mainEl));
    resizeTradeChart();
  });

  window.addEventListener("resize", () => {
    if (window.matchMedia("(max-width: 960px)").matches) return;
    applyWidth(mainEl, readAppliedWidth(mainEl));
  });
}
