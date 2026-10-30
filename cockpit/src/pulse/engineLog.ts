type LogKind = "info" | "smc" | "order" | "heartbeat" | "latency" | "signal";

const MAX_LINES = 64;
const lines: { ts: string; kind: LogKind; text: string }[] = [];
const STORAGE_COLLAPSED = "sala_engine_log_collapsed";

function nowTs(): string {
  return new Date().toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

function tagFor(kind: LogKind): string {
  switch (kind) {
    case "heartbeat":
      return "HB";
    case "latency":
      return "LAT";
    case "signal":
    case "smc":
      return "SMC";
    case "order":
      return "ORDEM";
    default:
      return "INFO";
  }
}

function paint(): void {
  const root = document.getElementById("engine-log-body");
  if (!root) return;
  if (!lines.length) {
    root.innerHTML = `<div class="engine-log-line kind-info"><span class="engine-log-ts">${nowTs()}</span><span class="engine-log-tag">INFO</span><span class="engine-log-msg muted">Aguardando eventos da engine…</span></div>`;
    return;
  }
  root.innerHTML = lines
    .map(
      (l) =>
        `<div class="engine-log-line kind-${l.kind}"><span class="engine-log-ts">${l.ts}</span><span class="engine-log-tag">${tagFor(l.kind)}</span><span class="engine-log-msg">${l.text}</span></div>`,
    )
    .join("");
  root.scrollTop = root.scrollHeight;
}

export function appendEngineLog(kind: LogKind, text: string): void {
  const last = lines[lines.length - 1];
  if (last && last.kind === kind && last.text === text) return;
  lines.push({ ts: nowTs(), kind, text });
  while (lines.length > MAX_LINES) lines.shift();
  paint();
}

export function appendEngineLogOnce(kind: LogKind, text: string, key: string): void {
  const attr = `data-once-${key}`;
  const root = document.getElementById("engine-log-panel");
  if (root?.dataset[attr] === "1") return;
  if (root) root.dataset[attr] = "1";
  appendEngineLog(kind, text);
}

let lastLatencyLog = "";

export function logLatency(ms: number | null): void {
  if (ms == null) return;
  const rounded = Math.round(ms);
  const text = `Round-trip API ${rounded}ms`;
  if (text === lastLatencyLog) return;
  lastLatencyLog = text;
  appendEngineLog("latency", text);
}

let lastHeartbeatKey = "";

export function logHeartbeat(online: boolean, lastIso: string | null | undefined): void {
  const key = `${online}:${lastIso ?? ""}`;
  if (key === lastHeartbeatKey) return;
  lastHeartbeatKey = key;
  if (!online) {
    appendEngineLog("heartbeat", "Engine offline · sem heartbeat recente");
    return;
  }
  const tail = lastIso ? ` · ${lastIso.slice(11, 19)}` : "";
  appendEngineLog("heartbeat", `Engine online${tail}`);
}

function setDrawerCollapsed(collapsed: boolean): void {
  const panel = document.getElementById("engine-log-panel");
  const toggle = document.getElementById("engine-log-toggle");
  panel?.classList.toggle("is-collapsed", collapsed);
  if (toggle) {
    toggle.setAttribute("aria-expanded", collapsed ? "false" : "true");
    toggle.textContent = collapsed ? "Expandir ▾" : "Recolher ▴";
  }
  const chevron = document.querySelector(".deck-log-chevron");
  if (chevron) chevron.textContent = collapsed ? "›" : "⌄";
  try {
    localStorage.setItem(STORAGE_COLLAPSED, collapsed ? "1" : "0");
  } catch {
    /* ignore */
  }
}

export function initEngineLog(): void {
  /** Default collapsed (~28px rail); expand only if user opted in. */
  let collapsed = true;
  try {
    const stored = localStorage.getItem(STORAGE_COLLAPSED);
    if (stored === "0") collapsed = false;
    else if (stored === "1") collapsed = true;
  } catch {
    /* ignore */
  }
  setDrawerCollapsed(collapsed);
  const toggle = document.getElementById("engine-log-toggle");
  const head = document.querySelector(".deck-engine-log-head");
  toggle?.addEventListener("click", (ev) => {
    ev.stopPropagation();
    const panel = document.getElementById("engine-log-panel");
    setDrawerCollapsed(!panel?.classList.contains("is-collapsed"));
  });
  head?.addEventListener("click", () => {
    const panel = document.getElementById("engine-log-panel");
    if (panel?.classList.contains("is-collapsed")) {
      setDrawerCollapsed(false);
    }
  });
  paint();
}
