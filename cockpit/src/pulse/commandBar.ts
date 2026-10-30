import { exportLibrary } from "../api/client";
import type { ZoneId } from "../orbit/zones";
import type { PulseTabId } from "./tabs";

export type CommandAction = {
  id: string;
  label: string;
  hint?: string;
  run: () => void | Promise<void>;
};

export function initCommandBar(actions: {
  onZone: (z: ZoneId) => void;
  onTab?: (tab: PulseTabId) => void;
  onTicker: (symbol: string) => void;
  symbols: string[];
}): void {
  const dialogEl = document.getElementById("command-dialog") as HTMLDialogElement | null;
  const inputEl = document.getElementById("command-input") as HTMLInputElement | null;
  const resultsEl = document.getElementById("command-results");
  const openBtn = document.getElementById("cmd-open");
  if (!dialogEl || !inputEl || !resultsEl) return;
  const dialog = dialogEl;
  const input = inputEl;
  const results = resultsEl;

  const zones: Array<{ id: ZoneId; label: string }> = [
    { id: "zone-status", label: "Status do sistema" },
    { id: "zone-signals", label: "Sinais recentes" },
    { id: "zone-trades", label: "Métricas de trades" },
    { id: "zone-agent", label: "Configuração do agente" },
    { id: "zone-library", label: "Biblioteca" },
    { id: "zone-news", label: "Headlines" },
  ];

  const tabs: Array<{ id: PulseTabId; label: string }> = [
    { id: "painel", label: "Aba Painel" },
    { id: "ops", label: "Aba Operações" },
    { id: "lucros", label: "Aba Lucros" },
    { id: "agente", label: "Aba Agente" },
    { id: "biblioteca", label: "Aba Biblioteca" },
    { id: "sistema", label: "Aba Sistema" },
  ];

  function buildActions(query: string): CommandAction[] {
    const q = query.trim().toLowerCase();
    const list: CommandAction[] = [];

    tabs.forEach((t) => {
      if (!actions.onTab) return;
      if (!q || t.label.toLowerCase().includes(q) || t.id.includes(q)) {
        list.push({
          id: `tab-${t.id}`,
          label: t.label,
          hint: "Abrir aba",
          run: () => actions.onTab!(t.id),
        });
      }
    });

    zones.forEach((z) => {
      if (!q || z.label.toLowerCase().includes(q) || z.id.includes(q)) {
        list.push({ id: z.id, label: z.label, hint: "Abrir zona", run: () => actions.onZone(z.id) });
      }
    });

    actions.symbols.forEach((sym) => {
      if (!q || sym.toLowerCase().includes(q)) {
        list.push({
          id: `ticker-${sym}`,
          label: `Ativo ${sym}`,
          hint: "Trocar gráfico",
          run: () => actions.onTicker(sym),
        });
      }
    });

    if (!q || "opera".includes(q) || "live".includes(q) || "trades".includes(q)) {
      list.push({
        id: "scroll-live-ops",
        label: "Operações ao vivo",
        hint: "Abrir aba",
        run: () =>
          actions.onTab
            ? actions.onTab("ops")
            : document.getElementById("live-ops")?.scrollIntoView({ behavior: "smooth" }),
      });
    }

    if (!q || "export".includes(q) || "biblioteca".includes(q)) {
      list.push({
        id: "export-lib",
        label: "Exportar biblioteca (ZIP)",
        hint: "Download",
        run: async () => {
          const blob = await exportLibrary();
          const a = document.createElement("a");
          a.href = URL.createObjectURL(blob);
          a.download = "sala_sinais_conhecimento.zip";
          a.click();
          URL.revokeObjectURL(a.href);
        },
      });
    }

    return list.slice(0, 12);
  }

  function render(query: string): void {
    const items = buildActions(query);
    results.innerHTML = items
      .map(
        (a, i) =>
          `<li><button type="button" data-cmd-idx="${i}"><strong>${a.label}</strong>${a.hint ? `<span class="muted"> — ${a.hint}</span>` : ""}</button></li>`,
      )
      .join("");
    results.querySelectorAll("button").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const idx = Number(btn.getAttribute("data-cmd-idx"));
        const act = items[idx];
        if (!act) return;
        dialog.close();
        await act.run();
      });
    });
  }

  function openPalette(): void {
    input.value = "";
    render("");
    dialog.showModal();
    window.setTimeout(() => input.focus(), 0);
  }

  openBtn?.addEventListener("click", () => openPalette());

  document.addEventListener("keydown", (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
      e.preventDefault();
      openPalette();
    }
  });

  input.addEventListener("input", () => render(input.value));
  dialog.addEventListener("close", () => {
    input.value = "";
  });
}
