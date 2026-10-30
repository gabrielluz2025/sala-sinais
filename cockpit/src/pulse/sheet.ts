import { panelTitle, renderPanel, wirePanelInteractions, type PanelContext } from "../orbit/panels";
import type { ZoneId } from "../orbit/zones";

export function openSheet(zone: ZoneId, ctx: PanelContext): void {
  const sheet = document.getElementById("pulse-sheet");
  const title = document.getElementById("pulse-sheet-title");
  const body = document.getElementById("pulse-sheet-body");
  if (!sheet || !body || !title) return;

  sheet.hidden = false;
  requestAnimationFrame(() => sheet.classList.add("open"));
  title.textContent = panelTitle(zone);
  body.innerHTML = `<p class="muted">Carregando…</p>`;

  void renderPanel(zone, ctx).then((html) => {
    body.innerHTML = html;
    wirePanelInteractions(body);
  });
}

export function closeSheet(): void {
  const sheet = document.getElementById("pulse-sheet");
  if (!sheet) return;
  sheet.classList.remove("open");
  window.setTimeout(() => {
    if (!sheet.classList.contains("open")) sheet.hidden = true;
  }, 320);
}

export async function refreshSheetBody(zone: ZoneId, ctx: PanelContext): Promise<void> {
  const body = document.getElementById("pulse-sheet-body");
  if (!body || document.getElementById("pulse-sheet")?.hidden) return;
  body.innerHTML = await renderPanel(zone, ctx);
  wirePanelInteractions(body);
}

export function initSheetChrome(): void {
  document.getElementById("pulse-sheet-close")?.addEventListener("click", () => closeSheet());
}
