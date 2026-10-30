export type PulseTabId = "painel" | "ops" | "lucros" | "agente" | "biblioteca" | "sistema";

const TAB_HASH: Record<PulseTabId, string> = {
  painel: "",
  ops: "ops",
  lucros: "lucros",
  agente: "agente",
  biblioteca: "biblioteca",
  sistema: "sistema",
};

const HASH_TO_TAB: Record<string, PulseTabId> = {
  "": "painel",
  ops: "ops",
  lucros: "lucros",
  agente: "agente",
  biblioteca: "biblioteca",
  sistema: "sistema",
};

let activeTab: PulseTabId = "painel";
let onTabChange: ((tab: PulseTabId) => void) | null = null;

export function getActiveTab(): PulseTabId {
  return activeTab;
}

function setPanelVisible(panel: HTMLElement, show: boolean): void {
  panel.classList.toggle("hidden", !show);
  panel.classList.toggle("deck-tab-active", show);
  panel.hidden = !show;
  panel.setAttribute("aria-hidden", show ? "false" : "true");
  if (show) {
    panel.removeAttribute("inert");
  } else {
    panel.setAttribute("inert", "");
  }
}

function setSplitChromeVisible(show: boolean): void {
  const ids = ["pulse-chart-dock", "deck-split-handle"] as const;
  for (const id of ids) {
    const el = document.getElementById(id);
    if (!el) continue;
    el.hidden = !show;
    el.setAttribute("aria-hidden", show ? "false" : "true");
  }
  const rightCol = document.querySelector<HTMLElement>(".deck-right-column");
  if (rightCol) {
    rightCol.hidden = !show;
    rightCol.setAttribute("aria-hidden", show ? "false" : "true");
  }
}

/** Painel = gráfico + cortina; demais abas = palco principal em largura total. */
export function applyDeckStageLayout(tab: PulseTabId): void {
  const main = document.querySelector<HTMLElement>(".deck-main");
  const fullStage = document.getElementById("deck-full-stage");
  const backBtn = document.getElementById("deck-back-painel");
  const isPainel = tab === "painel";

  main?.classList.toggle("deck-stage--split", isPainel);
  main?.classList.toggle("deck-stage--full", !isPainel);

  setSplitChromeVisible(isPainel);

  if (fullStage) {
    fullStage.hidden = isPainel;
    fullStage.setAttribute("aria-hidden", isPainel ? "true" : "false");
  }

  if (backBtn) {
    backBtn.classList.toggle("hidden", isPainel);
    backBtn.hidden = isPainel;
  }
}

export function setActiveTab(tab: PulseTabId, pushHash = true): void {
  activeTab = tab;
  document.querySelectorAll<HTMLElement>(".pulse-tab-panel").forEach((panel) => {
    const id = panel.getAttribute("data-tab") as PulseTabId | null;
    if (!id) return;
    setPanelVisible(panel, id === tab);
  });
  document
    .querySelectorAll<HTMLButtonElement>("#pulse-tab-nav .pulse-tab-btn")
    .forEach((btn) => {
      const id = btn.getAttribute("data-tab") as PulseTabId | null;
      const on = id === tab;
      btn.classList.toggle("active", on);
      btn.setAttribute("aria-selected", on ? "true" : "false");
    });
  applyDeckStageLayout(tab);
  if (pushHash) {
    const h = TAB_HASH[tab];
    const url = h ? `#${h}` : `${window.location.pathname}${window.location.search}`;
    window.history.replaceState(null, "", h ? `#${h}` : url);
  }
  onTabChange?.(tab);
}

export function initPulseTabs(handler?: (tab: PulseTabId) => void): void {
  onTabChange = handler ?? null;
  const nav = document.getElementById("pulse-tab-nav");
  nav?.querySelectorAll<HTMLButtonElement>(".pulse-tab-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      const id = btn.getAttribute("data-tab") as PulseTabId | null;
      if (id) setActiveTab(id);
    });
  });
  document.getElementById("deck-back-painel")?.addEventListener("click", () => {
    setActiveTab("painel");
  });
  const fromHash = (window.location.hash || "").replace(/^#/, "");
  const initial = HASH_TO_TAB[fromHash] ?? "painel";
  setActiveTab(initial, false);
  window.addEventListener("hashchange", () => {
    const h = (window.location.hash || "").replace(/^#/, "");
    const tab = HASH_TO_TAB[h] ?? "painel";
    setActiveTab(tab, false);
  });
}

function activeTabScrollEl(tab: PulseTabId): HTMLElement | null {
  if (tab === "painel") {
    return document.getElementById("deck-main-scroll");
  }
  const panel = document.querySelector<HTMLElement>(
    `.deck-full-stage .deck-full-panel.deck-tab-active[data-tab="${tab}"]`,
  );
  return panel?.querySelector<HTMLElement>(".deck-tab-scroll") ?? null;
}

export function navigateToTab(tab: PulseTabId): void {
  setActiveTab(tab);
  const scrollEl = activeTabScrollEl(tab);
  scrollEl?.scrollTo({ top: 0, behavior: "smooth" });
}
