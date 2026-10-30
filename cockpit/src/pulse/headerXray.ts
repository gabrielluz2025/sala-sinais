import {
  buildAgentXraySections,
  type AgentXrayInput,
} from "./agentXray";
import { navigateToTab } from "./tabs";

type PopoverKey = "conhecimento" | "acertos" | "risco" | "modo";

const POPOVERS: PopoverKey[] = ["conhecimento", "acertos", "risco", "modo"];

let lastInput: AgentXrayInput | null = null;
let openKey: PopoverKey | null = null;
let clickPinned = false;
let hoverFine = false;
let bound = false;

function $(id: string): HTMLElement | null {
  return document.getElementById(id);
}

function popoverId(key: PopoverKey): string {
  return `header-popover-${key}`;
}

function btnId(key: PopoverKey): string {
  return `header-xray-btn-${key}`;
}

function chipValId(key: PopoverKey): string {
  return `header-xray-val-${key}`;
}

function positionPopover(btn: HTMLElement, pop: HTMLElement): void {
  const gap = 6;
  const pad = 8;
  pop.style.position = "fixed";
  pop.style.visibility = "hidden";
  pop.style.display = "block";
  const w = pop.offsetWidth;
  const h = pop.offsetHeight;
  const r = btn.getBoundingClientRect();
  let left = r.left;
  if (left + w > window.innerWidth - pad) {
    left = Math.max(pad, window.innerWidth - w - pad);
  }
  let top = r.bottom + gap;
  if (top + h > window.innerHeight - pad) {
    top = Math.max(pad, r.top - h - gap);
  }
  pop.style.left = `${left}px`;
  pop.style.top = `${top}px`;
  pop.style.visibility = "";
}

function setOpen(key: PopoverKey | null, pin = false): void {
  openKey = key;
  clickPinned = pin && key != null;

  POPOVERS.forEach((k) => {
    const btn = $(btnId(k));
    const pop = $(popoverId(k));
    const open = k === key;
    if (btn) {
      btn.setAttribute("aria-expanded", open ? "true" : "false");
      btn.classList.toggle("is-open", open);
    }
    if (pop) {
      pop.hidden = !open;
      pop.classList.toggle("is-open", open);
      if (open && btn) {
        positionPopover(btn, pop);
      }
    }
  });
}

function closeAll(): void {
  setOpen(null, false);
}

function bindPopoverActions(root: HTMLElement, onOpenLibrary: () => void): void {
  root.querySelectorAll("[data-open-library]").forEach((btn) => {
    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      onOpenLibrary();
      closeAll();
    });
  });
  root.querySelectorAll("[data-open-agent]").forEach((btn) => {
    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      navigateToTab("agente");
      closeAll();
    });
  });
  root.querySelectorAll("[data-open-sistema]").forEach((btn) => {
    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      navigateToTab("sistema");
      closeAll();
      const scrollChecklist = btn.hasAttribute("data-scroll-exec-checklist");
      if (scrollChecklist) {
        requestAnimationFrame(() => {
          document.getElementById("exec-mt5-checklist")?.scrollIntoView({ behavior: "smooth", block: "start" });
        });
      }
    });
  });
}

function renderPopoverBodies(input: AgentXrayInput, onOpenLibrary: () => void): void {
  const sections = buildAgentXraySections(input);

  const titles: Record<PopoverKey, string> = {
    conhecimento: "Conhecimento",
    acertos: "Acertos e erros",
    risco: "Risco · projeção educativa",
    modo: "Modo e motor",
  };

  const bodies: Record<PopoverKey, string> = {
    conhecimento: sections.knowledge,
    acertos: sections.hits,
    risco: sections.risk,
    modo: sections.mode,
  };

  POPOVERS.forEach((key) => {
    const pop = $(popoverId(key));
    if (!pop) return;
    pop.innerHTML = `<div class="header-popover-inner">
      <header class="header-popover-head">
        <h3 class="header-popover-title">${titles[key]}</h3>
        <button type="button" class="header-popover-close" data-header-popover-close aria-label="Fechar">×</button>
      </header>
      <div class="header-popover-body agent-xray-col">${bodies[key]}</div>
    </div>`;
    pop.querySelector("[data-header-popover-close]")?.addEventListener("click", () => closeAll());
    bindPopoverActions(pop, onOpenLibrary);
  });

  (["conhecimento", "acertos", "risco", "modo"] as const).forEach((key) => {
    const el = $(chipValId(key));
    if (el) el.textContent = sections.chips[key];
  });
}

export function syncHeaderXrayPopovers(
  input: AgentXrayInput,
  onOpenLibrary: () => void,
): void {
  lastInput = input;
  renderPopoverBodies(input, onOpenLibrary);
  if (openKey) {
    const btn = $(btnId(openKey));
    const pop = $(popoverId(openKey));
    if (btn && pop && !pop.hidden) {
      positionPopover(btn, pop);
    }
  }
}

export function syncHeaderXrayLiveContext(
  patch: Partial<AgentXrayInput>,
  onOpenLibrary: () => void,
): void {
  if (!lastInput) return;
  lastInput = { ...lastInput, ...patch };
  renderPopoverBodies(lastInput, onOpenLibrary);
  if (openKey) {
    const btn = $(btnId(openKey));
    const pop = $(popoverId(openKey));
    if (btn && pop && !pop.hidden) {
      positionPopover(btn, pop);
    }
  }
}

export function initHeaderXrayPopovers(onOpenLibrary: () => void): void {
  if (bound) return;
  bound = true;
  hoverFine = window.matchMedia("(hover: hover) and (pointer: fine)").matches;

  POPOVERS.forEach((key) => {
    const btn = $(btnId(key));
    const item = btn?.closest(".header-xray-item");
    if (!btn || !item) return;

    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      if (openKey === key && clickPinned) {
        closeAll();
      } else {
        setOpen(key, true);
      }
    });

    if (hoverFine) {
      item.addEventListener("mouseenter", () => {
        if (!clickPinned) setOpen(key, false);
      });
      item.addEventListener("mouseleave", () => {
        if (!clickPinned && openKey === key) closeAll();
      });
    }
  });

  document.addEventListener("click", (e) => {
    const t = e.target as Node | null;
    if (!t) return;
    if (document.getElementById("header-xray-nav")?.contains(t)) return;
    closeAll();
  });

  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") closeAll();
  });

  window.addEventListener(
    "resize",
    () => {
      if (!openKey) return;
      const btn = $(btnId(openKey));
      const pop = $(popoverId(openKey));
      if (btn && pop && !pop.hidden) positionPopover(btn, pop);
    },
    { passive: true },
  );

  window.addEventListener(
    "scroll",
    () => {
      if (!openKey) return;
      const btn = $(btnId(openKey));
      const pop = $(popoverId(openKey));
      if (btn && pop && !pop.hidden) positionPopover(btn, pop);
    },
    true,
  );

  if (lastInput) {
    renderPopoverBodies(lastInput, onOpenLibrary);
  }
}
