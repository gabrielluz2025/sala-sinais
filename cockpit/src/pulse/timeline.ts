import type { ZoneId } from "../orbit/zones";

export type TimelinePhase = {
  id: string;
  label: string;
  range: string;
  startMin: number;
  endMin: number;
  zone?: ZoneId;
  zoneLabel?: string;
};

/** Minutos desde meia-noite em America/Sao_Paulo (aprox. BRT). */
function nowMinutesBrt(): number {
  const parts = new Intl.DateTimeFormat("en-GB", {
    timeZone: "America/Sao_Paulo",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).formatToParts(new Date());
  const h = Number(parts.find((p) => p.type === "hour")?.value ?? 0);
  const m = Number(parts.find((p) => p.type === "minute")?.value ?? 0);
  return h * 60 + m;
}

export const PHASES: TimelinePhase[] = [
  { id: "pre", label: "Pré-mercado", range: "09:00 – 10:00", startMin: 9 * 60, endMin: 10 * 60, zone: "zone-status", zoneLabel: "Status" },
  {
    id: "session",
    label: "Pregão",
    range: "10:00 – 17:55",
    startMin: 10 * 60,
    endMin: 17 * 60 + 55,
    zone: "zone-signals",
    zoneLabel: "Sinais",
  },
  {
    id: "after",
    label: "Pós-fechamento",
    range: "Após 18:00",
    startMin: 18 * 60,
    endMin: 24 * 60,
    zone: "zone-trades",
    zoneLabel: "Trades",
  },
];

export function mountDayTimeline(onZone: (zone: ZoneId) => void): void {
  const nav = document.getElementById("zone-nav");
  if (!nav) return;

  const now = nowMinutesBrt();
  const sessionStart = 10 * 60;
  const sessionEnd = 17 * 60 + 55;
  const daySpan = sessionEnd - sessionStart;
  const nowPct =
    now < sessionStart ? 0 : now > sessionEnd ? 100 : ((now - sessionStart) / daySpan) * 100;

  nav.innerHTML = PHASES
    .map((p) => {
      const active = now >= p.startMin && now < p.endMin;
      const zoneBtn = p.zone
        ? `<button type="button" class="timeline-zone-btn zone-nav-link" data-zone="${p.zone}">${p.zoneLabel}</button>`
        : "";
      return `
        <div class="timeline-segment${active ? " active" : ""}" data-phase="${p.id}">
          <h3>${p.label}</h3>
          <p class="seg-time">${p.range}</p>
          ${zoneBtn}
        </div>`;
    })
    .join("");

  const sessionEl = nav.querySelector('[data-phase="session"]');
  if (sessionEl && now >= sessionStart && now <= sessionEnd) {
    const marker = document.createElement("div");
    marker.className = "timeline-now";
    marker.style.left = `${Math.min(98, Math.max(2, nowPct))}%`;
    marker.setAttribute("aria-hidden", "true");
    sessionEl.appendChild(marker);
  }

  nav.querySelectorAll(".timeline-zone-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      const id = btn.getAttribute("data-zone") as ZoneId;
      onZone(id);
    });
  });

  const activeIdx = PHASES.findIndex((p) => now >= p.startMin && now < p.endMin);
  const scrollTarget = nav.children[Math.max(0, activeIdx)] as HTMLElement | undefined;
  scrollTarget?.scrollIntoView({ inline: "center", behavior: "smooth" });
}
