import { api, type PnlMetricsResponse, type Signal, type TradeMetricsItem } from "../api/client";
import { resolveOpenMtmBrl, resolveTodayClosedNet } from "./pnlDisplay";
import {
  buildDayReading,
  buildEquityCurve,
  buildHeroContext,
  directionBadge,
  formatEquityCaption,
  type EquityCurvePoint,
} from "./lucrosInsights";
import {
  formatResultadoCellHtml,
  resolveRowPnl,
  type LiveOpsQuote,
} from "./signalRowPnl";

function esc(s: string): string {
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

function fmtBrl(n: number | null | undefined): string {
  if (n == null || Number.isNaN(n)) return "—";
  return n.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}

function fmtPct(n: number | null | undefined): string {
  if (n == null || Number.isNaN(n)) return "—";
  return `${n.toFixed(1)}%`;
}

function sidePt(side: string): string {
  return side === "BUY" ? "Compra" : side === "SELL" ? "Venda" : side;
}

function strategyLabel(t: string | null | undefined): string {
  if (t === "breakout") return "Breakout";
  if (t === "volatility") return "Volatilidade";
  return t || "—";
}

function kpiCard(label: string, id: string, hint: string): string {
  return `<div class="pnl-card">
    <span class="pnl-card-label">${esc(label)}</span>
    <strong id="${esc(id)}">—</strong>
    <span class="pnl-card-hint">${esc(hint)}</span>
  </div>`;
}

function thTip(label: string, tip: string): string {
  return `<th class="lucros-th-tip" title="${esc(tip)}">${esc(label)}</th>`;
}

let mounted = false;
let equityHoverBound = false;
let lastEquityPoints: EquityCurvePoint[] = [];

export function mountLucrosPanel(host: HTMLElement): void {
  if (mounted && host.querySelector("#lucros-kpi-grid")) return;
  host.innerHTML = `
    <section class="zone-section lucros-live deck-lucros-panel" id="lucros-panel">
      <div class="pnl-hero-row">
        <div class="pnl-card pnl-card--hero">
          <span class="pnl-card-label">Hoje (líquido)</span>
          <div class="pnl-hero-value-row">
            <strong id="lucros-today-net" class="pnl-hero-value">—</strong>
            <span id="lucros-today-badge" class="pnl-dir-badge" hidden aria-hidden="true"></span>
          </div>
          <p id="lucros-hero-context" class="pnl-card-hint pnl-hero-context">—</p>
          <span class="pnl-card-hint">Lucro/prejuízo líquido dos trades já fechados hoje (taxas estimadas já descontadas).</span>
        </div>
        <div class="pnl-hero-secondary">
          <div class="pnl-card">
            <span class="pnl-card-label">MTM aberto</span>
            <div class="pnl-metric-row">
              <strong id="lucros-mtm">—</strong>
              <span id="lucros-mtm-badge" class="pnl-dir-badge pnl-dir-badge--sm" hidden aria-hidden="true"></span>
            </div>
            <span class="pnl-card-hint">Marcação a mercado das posições ainda abertas (estimativa).</span>
          </div>
          <div class="pnl-card">
            <span class="pnl-card-label">Win rate hoje</span>
            <strong id="lucros-win-rate">—</strong>
            <span class="pnl-card-hint">% de trades fechados hoje com resultado líquido positivo.</span>
          </div>
        </div>
      </div>
      <div class="pnl-grid" id="lucros-kpi-grid">
        ${kpiCard("Fechados hoje", "lucros-closed", "Operações encerradas na sessão (contagem).")}
        ${kpiCard("Compras / vendas", "lucros-buys-sells", "Ordens de compra vs venda executadas hoje.")}
        ${kpiCard("Taxas (est.)", "lucros-fees", "Emolumentos B3 + corretagem estimados nos fechados.")}
        ${kpiCard("IR est. (sessão)", "lucros-ir", "Imposto day trade estimado sobre lucro (não retido auto.).")}
        ${kpiCard("Mês (líquido)", "lucros-month-net", "Acumulado líquido do mês calendário.")}
        ${kpiCard("All-time (líquido)", "lucros-alltime-net", "Histórico líquido desde o início do registro.")}
      </div>
      <div class="lucros-insights-block">
        <h3 class="lucros-section-title">Leitura do dia</h3>
        <p id="lucros-day-reading" class="lucros-day-reading">—</p>
        <p class="lucros-disclaimer">
          <span class="lucros-disclaimer-mark" title="Valores modelados com parâmetros configuráveis; não substituem DARF, nota de corretagem ou contador.">ℹ</span>
          Taxas e IR são estimativas educacionais — confira extrato e regras fiscais aplicáveis.
        </p>
      </div>
      <div class="lucros-equity-wrap">
        <h3 class="lucros-section-title">Equity intraday</h3>
        <p class="lucros-section-hint">Fechados hoje — curva acumulada (eixo X: ordem de fechamento)</p>
        <div class="lucros-equity-chart-host">
          <canvas id="lucros-equity-spark" class="lucros-equity-spark" width="640" height="160" role="img" aria-label="Curva de equity intraday"></canvas>
          <div id="lucros-equity-tooltip" class="lucros-equity-tooltip" hidden></div>
        </div>
        <p id="lucros-equity-caption" class="lucros-equity-caption">—</p>
      </div>
      <h3 class="lucros-section-title">Por ativo (hoje)</h3>
      <div class="lucros-table-wrap">
        <table class="data-table sticky-head lucros-table lucros-zebra"><thead><tr>
          ${thTip("Ativo", "Símbolo negociado")}
          ${thTip("Trades", "Fechamentos no dia")}
          ${thTip("Win rate", "% de trades lucrativos no ativo")}
          ${thTip("Líquido", "Soma líquida (R$) no ativo hoje")}
        </tr></thead>
        <tbody id="lucros-by-symbol"></tbody></table>
      </div>
      <h3 class="lucros-section-title">Operações recentes</h3>
      <div class="live-ops-table-wrap">
        <table class="data-table sticky-head lucros-zebra"><thead><tr>
          ${thTip("Hora", "Horário local do sinal")}
          ${thTip("Ativo", "Contrato ou ação")}
          ${thTip("Lado", "Compra ou venda")}
          ${thTip("Estratégia", "Preset / tipo de setup")}
          ${thTip("Entrada", "Preço de entrada")}
          ${thTip("Status", "Estado da ordem / trade")}
          ${thTip("Resultado", "PnL realizado ou MTM estimado")}
        </tr></thead><tbody id="lucros-ops-body"></tbody></table>
      </div>
    </section>`;
  mounted = true;
  bindEquityHover(host);
}

function bindEquityHover(root: ParentNode): void {
  if (equityHoverBound) return;
  const canvas = root.querySelector("#lucros-equity-spark") as HTMLCanvasElement | null;
  const tip = root.querySelector("#lucros-equity-tooltip") as HTMLElement | null;
  if (!canvas || !tip) return;
  equityHoverBound = true;

  const hide = () => {
    tip.hidden = true;
  };

  canvas.addEventListener("mouseleave", hide);
  canvas.addEventListener("mousemove", (ev) => {
    const pts = lastEquityPoints;
    if (pts.length < 2) {
      hide();
      return;
    }
    const rect = canvas.getBoundingClientRect();
    const x = ev.clientX - rect.left;
    const padL = 52;
    const padR = 10;
    const innerW = rect.width - padL - padR;
    if (innerW <= 0) {
      hide();
      return;
    }
    const ratio = (x - padL) / innerW;
    const idx = Math.round(Math.max(0, Math.min(1, ratio)) * (pts.length - 1));
    const p = pts[idx];
    if (!p) {
      hide();
      return;
    }
    const time = new Date(p.closedAt).toLocaleTimeString("pt-BR", {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    });
    tip.textContent = `#${p.index} · ${fmtBrl(p.cum)} · ${time}`;
    tip.hidden = false;
    tip.style.left = `${Math.min(rect.width - 8, Math.max(8, x))}px`;
    tip.style.top = "8px";
  });
}

function pnlTone(n: number | null | undefined): "pos" | "neg" | undefined {
  if (n == null || Number.isNaN(n)) return undefined;
  if (n > 0) return "pos";
  if (n < 0) return "neg";
  return undefined;
}

function setText(id: string, text: string, tone?: "pos" | "neg", root?: ParentNode | Document): void {
  const el =
    root && "getElementById" in root
      ? root.getElementById(id)
      : document.getElementById(id);
  if (!el) return;
  el.textContent = text;
  el.classList.remove("positive", "negative");
  if (tone === "pos") el.classList.add("positive");
  if (tone === "neg") el.classList.add("negative");
}

function setDirBadge(id: string, net: number | null | undefined, root?: ParentNode | Document): void {
  const el =
    root && "getElementById" in root
      ? root.getElementById(id)
      : document.getElementById(id);
  if (!el) return;
  const dir = directionBadge(net);
  if (!dir) {
    el.hidden = true;
    el.textContent = "";
    el.classList.remove("pnl-dir-badge--up", "pnl-dir-badge--down");
    return;
  }
  el.hidden = false;
  el.textContent = dir.glyph;
  el.setAttribute("title", dir.label);
  el.setAttribute("aria-label", dir.label);
  el.classList.toggle("pnl-dir-badge--up", net! > 0);
  el.classList.toggle("pnl-dir-badge--down", net! < 0);
}

function niceYTicks(min: number, max: number, count: number): number[] {
  const span = max - min || 1;
  const raw = span / Math.max(1, count - 1);
  const mag = 10 ** Math.floor(Math.log10(Math.abs(raw) || 1));
  const step = Math.ceil(raw / mag) * mag;
  const ticks: number[] = [];
  let v = Math.floor(min / step) * step;
  while (v <= max + step * 0.01) {
    if (v >= min - step * 0.01 && v <= max + step * 0.01) ticks.push(v);
    v += step;
  }
  if (!ticks.length) ticks.push(min, max);
  return ticks;
}

function paintEquitySpark(trades: TradeMetricsItem[], root?: ParentNode | Document): void {
  const canvas = (
    root && "getElementById" in root
      ? root.getElementById("lucros-equity-spark")
      : document.getElementById("lucros-equity-spark")
  ) as HTMLCanvasElement | null;
  const captionEl =
    root && "getElementById" in root
      ? root.getElementById("lucros-equity-caption")
      : document.getElementById("lucros-equity-caption");

  const stats = buildEquityCurve(trades);
  lastEquityPoints = stats.points;
  if (captionEl) captionEl.textContent = formatEquityCaption(stats);

  if (!canvas) return;
  const ctx = canvas.getContext("2d");
  if (!ctx) return;
  const dpr = devicePixelRatio;
  const w = canvas.clientWidth || 640;
  const h = canvas.clientHeight || 160;
  canvas.width = Math.floor(w * dpr);
  canvas.height = Math.floor(h * dpr);
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, w, h);

  const padL = 52;
  const padR = 10;
  const padT = 10;
  const padB = 26;
  const chartW = w - padL - padR;
  const chartH = h - padT - padB;

  if (stats.points.length < 2) {
    ctx.fillStyle = "#64748b";
    ctx.font = "11px IBM Plex Sans, sans-serif";
    ctx.fillText("Sem trades fechados hoje para curva", padL, h / 2);
    return;
  }

  const values = stats.points.map((p) => p.cum);
  const min = Math.min(0, ...values);
  const max = Math.max(0, ...values);
  const span = max - min || 1;

  const yOf = (v: number) => padT + chartH * (1 - (v - min) / span);
  const xOf = (i: number) => padL + (chartW * i) / (values.length - 1);

  ctx.strokeStyle = "rgba(148, 163, 184, 0.12)";
  ctx.lineWidth = 1;
  for (const tick of niceYTicks(min, max, 5)) {
    const y = yOf(tick);
    ctx.beginPath();
    ctx.moveTo(padL, y);
    ctx.lineTo(w - padR, y);
    ctx.stroke();
  }

  if (min < 0 && max > 0) {
    const zy = yOf(0);
    ctx.strokeStyle = "rgba(248, 113, 113, 0.45)";
    ctx.lineWidth = 1;
    ctx.setLineDash([4, 4]);
    ctx.beginPath();
    ctx.moveTo(padL, zy);
    ctx.lineTo(w - padR, zy);
    ctx.stroke();
    ctx.setLineDash([]);
  }

  ctx.fillStyle = "#64748b";
  ctx.font = "10px IBM Plex Mono, monospace";
  ctx.textAlign = "right";
  ctx.textBaseline = "middle";
  for (const tick of niceYTicks(min, max, 4)) {
    const y = yOf(tick);
    const label =
      Math.abs(tick) >= 1000
        ? `${(tick / 1000).toFixed(1)}k`
        : tick.toLocaleString("pt-BR", { maximumFractionDigits: 0 });
    ctx.fillText(label, padL - 6, y);
  }

  ctx.textAlign = "center";
  ctx.textBaseline = "top";
  ctx.font = "10px IBM Plex Sans, sans-serif";
  const firstT = new Date(stats.points[0].closedAt).toLocaleTimeString("pt-BR", {
    hour: "2-digit",
    minute: "2-digit",
  });
  const lastT = new Date(stats.points[stats.points.length - 1].closedAt).toLocaleTimeString("pt-BR", {
    hour: "2-digit",
    minute: "2-digit",
  });
  ctx.fillText(firstT, padL, h - padB + 4);
  ctx.fillText(`#${stats.points.length}`, padL + chartW / 2, h - padB + 4);
  ctx.fillText(lastT, padL + chartW, h - padB + 4);

  const final = values[values.length - 1] ?? 0;
  ctx.strokeStyle = final >= 0 ? "#34d399" : "#f87171";
  ctx.lineWidth = 2;
  ctx.lineJoin = "round";
  ctx.beginPath();
  values.forEach((v, i) => {
    const x = xOf(i);
    const y = yOf(v);
    if (i === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  });
  ctx.stroke();

  ctx.fillStyle = final >= 0 ? "rgba(52, 211, 153, 0.85)" : "rgba(248, 113, 113, 0.85)";
  ctx.beginPath();
  ctx.arc(xOf(values.length - 1), yOf(final), 3.5, 0, Math.PI * 2);
  ctx.fill();
}

export type LucrosLiveCache = {
  trades: TradeMetricsItem[];
  signals: Signal[];
  mids?: Record<string, number>;
  quote?: LiveOpsQuote;
};

export function syncLucrosLive(pnl: PnlMetricsResponse | null, cache: LucrosLiveCache): void {
  const host = document.getElementById("tab-lucros-body");
  if (!host) return;
  if (!host.querySelector("#lucros-kpi-grid")) mountLucrosPanel(host);

  const today = resolveTodayClosedNet(pnl);
  const mtm = resolveOpenMtmBrl(pnl);
  setText("lucros-today-net", fmtBrl(today), today > 0 ? "pos" : today < 0 ? "neg" : undefined, host);
  setDirBadge("lucros-today-badge", today, host);
  setText("lucros-hero-context", buildHeroContext(pnl), undefined, host);
  setText("lucros-mtm", fmtBrl(mtm), mtm > 0 ? "pos" : mtm < 0 ? "neg" : undefined, host);
  setDirBadge("lucros-mtm-badge", mtm, host);
  setText("lucros-win-rate", fmtPct(pnl?.daily?.win_rate_pct), undefined, host);
  setText("lucros-closed", String(pnl?.daily?.closed_trades ?? "—"), undefined, host);
  const sess = pnl?.session_today;
  setText(
    "lucros-buys-sells",
    sess ? `${sess.buys} / ${sess.sells}` : "—",
    undefined,
    host,
  );
  setText("lucros-fees", fmtBrl(pnl?.fees_paid_brl ?? sess?.fees_open_est_brl), undefined, host);
  setText("lucros-ir", fmtBrl(sess?.estimated_ir_brl ?? pnl?.estimated_ir_brl), undefined, host);
  const monthNet = pnl?.monthly?.net_pnl_brl;
  const allNet = pnl?.all_time?.net_pnl_brl;
  setText("lucros-month-net", fmtBrl(monthNet), pnlTone(monthNet), host);
  setText("lucros-alltime-net", fmtBrl(allNet), pnlTone(allNet), host);

  const readingEl = host.querySelector("#lucros-day-reading");
  if (readingEl) readingEl.textContent = buildDayReading(pnl, cache.trades, today);

  const bySym = host.querySelector("#lucros-by-symbol");
  if (bySym) {
    const rows = cache.trades.length
      ? aggregateBySymbol(cache.trades)
      : (pnl?.recent_closed || []).map((r) => ({
          symbol: r.symbol,
          trades: 1,
          win_rate: null as number | null,
          net: r.net_pnl_brl,
        }));
    bySym.innerHTML =
      rows
        .map(
          (r) =>
            `<tr><td>${esc(r.symbol)}</td><td>${r.trades}</td><td>${r.win_rate != null ? fmtPct(r.win_rate) : "—"}</td><td class="mono-num ${pnlTone(r.net) === "pos" ? "positive" : pnlTone(r.net) === "neg" ? "negative" : ""}">${fmtBrl(r.net)}</td></tr>`,
        )
        .join("") || `<tr><td colspan="4">—</td></tr>`;
  }

  const opsBody = host.querySelector("#lucros-ops-body");
  if (opsBody) {
    const tradeById = new Map(cache.trades.map((t) => [t.id, t]));
    const mids = cache.mids ?? {};
    const quote = cache.quote ?? null;
    opsBody.innerHTML = cache.signals
      .slice(0, 40)
      .map((r) => {
        const p = resolveRowPnl(r, tradeById, mids, quote);
        return `<tr>
          <td>${esc(new Date(r.created_at).toLocaleTimeString("pt-BR"))}</td>
          <td>${esc(r.symbol)}</td>
          <td>${sidePt(r.side)}</td>
          <td>${esc(strategyLabel(r.strategy_type))}</td>
          <td class="mono-num">${r.entry}</td>
          <td>${esc(r.status)}</td>
          <td>${formatResultadoCellHtml(r, p)}</td>
        </tr>`;
      })
      .join("");
  }

  paintEquitySpark(cache.trades, host);
}

function aggregateBySymbol(trades: TradeMetricsItem[]): Array<{
  symbol: string;
  trades: number;
  win_rate: number | null;
  net: number;
}> {
  const map = new Map<string, { n: number; wins: number; net: number }>();
  for (const t of trades) {
    const cur = map.get(t.symbol) || { n: 0, wins: 0, net: 0 };
    cur.n += 1;
    if (t.win) cur.wins += 1;
    cur.net += t.net_pnl;
    map.set(t.symbol, cur);
  }
  return [...map.entries()]
    .map(([symbol, v]) => ({
      symbol,
      trades: v.n,
      win_rate: v.n ? (100 * v.wins) / v.n : null,
      net: v.net,
    }))
    .sort((a, b) => b.net - a.net);
}

export async function fetchLucrosLiveData(todayOnly = true): Promise<LucrosLiveCache> {
  try {
    const [tradesRes, signals] = await Promise.all([
      api.trades(todayOnly, 200),
      api.signals(todayOnly ? 80 : 120),
    ]);
    return { trades: tradesRes.trades || [], signals };
  } catch {
    return { trades: [], signals: [] };
  }
}
