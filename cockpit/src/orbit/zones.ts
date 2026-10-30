export type ZoneId =
  | "zone-status"
  | "zone-signals"
  | "zone-trades"
  | "zone-agent"
  | "zone-library"
  | "zone-news";

export type ZoneDef = {
  id: ZoneId;
  label: string;
  angle: number;
  radius: string;
};

export const ZONES: ZoneDef[] = [
  { id: "zone-status", label: "Status", angle: -90, radius: "min(38vw, 220px)" },
  { id: "zone-signals", label: "Sinais", angle: -30, radius: "min(42vw, 260px)" },
  { id: "zone-trades", label: "Trades", angle: 30, radius: "min(42vw, 260px)" },
  { id: "zone-agent", label: "Agente", angle: 90, radius: "min(38vw, 220px)" },
  { id: "zone-library", label: "Biblioteca", angle: 150, radius: "min(42vw, 260px)" },
  { id: "zone-news", label: "News", angle: 210, radius: "min(38vw, 220px)" },
];

export function mountOrbitNav(onSelect: (zone: ZoneId) => void): void {
  const nav = document.getElementById("zone-nav");
  if (!nav) return;
  nav.innerHTML = ZONES
    .map(
      (z) => `
    <div class="orbit-node" style="--angle:${z.angle}deg;--radius:${z.radius}" data-zone="${z.id}">
      <button type="button" class="orbit-node-btn zone-nav-link" data-zone="${z.id}" aria-label="${z.label}">
        ${z.label}
      </button>
    </div>`,
    )
    .join("");

  nav.querySelectorAll(".orbit-node-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      const id = btn.getAttribute("data-zone") as ZoneId;
      nav.querySelectorAll(".orbit-node-btn").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      onSelect(id);
    });
  });
}
