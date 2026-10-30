import type { PanelContext } from "../orbit/panels";
import { renderPanel, showLibraryArticleInRoot, wirePanelInteractions } from "../orbit/panels";
import { fetchLucrosLiveData, mountLucrosPanel, syncLucrosLive } from "./pnlLive";

export async function refreshTabPanel(
  tab: "lucros" | "agente" | "biblioteca" | "sistema",
  ctx: PanelContext,
): Promise<void> {
  const map: Record<string, string> = {
    lucros: "zone-trades",
    agente: "zone-agent",
    biblioteca: "zone-library",
    sistema: "zone-status",
  };
  const zone = map[tab];
  const host = document.getElementById(`tab-${tab}-body`);
  if (!host || !zone) return;

  if (tab === "lucros") {
    mountLucrosPanel(host);
    const cache = await fetchLucrosLiveData(true);
    syncLucrosLive(ctx.pnl, cache);
    return;
  }

  host.innerHTML = `<p class="muted deck-tab-loading">Carregando…</p>`;
  const html = await renderPanel(zone as import("../orbit/zones").ZoneId, ctx);
  host.innerHTML = html;
  host.classList.add("deck-tab-embed");
  wirePanelInteractions(host);
  if (tab === "biblioteca") {
    const pending = sessionStorage.getItem("sala_pending_library_article");
    if (pending) {
      sessionStorage.removeItem("sala_pending_library_article");
      void showLibraryArticleInRoot(host, pending);
    }
  }
}
