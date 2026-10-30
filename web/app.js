const $ = (id) => document.getElementById(id);

let equityChart = null;
let priceChart = null;
let candleChart = null;
let pnlWlChart = null;
let activeTf = "M5";
let lastAlertMaxId = 0;
let apiOnline = false;
let configSavedSession = false;
let lastAgentConfigFingerprint = "";
const kpiPrev = {};
let pnlSparkChart = null;
let wealthEquityChart = null;
let wealthDrawdownChart = null;
let lastRenderedAlertKeys = new Set();
let dashboardFetchInFlight = 0;

const TF_HUMAN = {
  M1: "1 minuto",
  M5: "5 minutos",
  H1: "1 hora",
};

const LIBRARY_CAT_CLASS = {
  fundamentos: "cat-fundamentos",
  risco: "cat-risco",
  estrategia: "cat-estrategia",
  estratégias: "cat-estrategia",
  sistema: "cat-sistema",
  mercado: "cat-mercado",
};

const THEME_STORAGE_KEY = "sala_theme";
const COLOR_MODE_STORAGE_KEY = "sala_color_mode";
const SIDEBAR_STORAGE_KEY = "sala_sidebar_collapsed";

function normalizeDashboardTheme(theme) {
  const t = (theme || "").toLowerCase();
  if (t === "classic" || t === "legacy") return "classic";
  if (t === "pro" || t === "novo" || t === "v3" || t === "aurora") return "novo";
  return "novo";
}

function applyColorMode(mode) {
  const m = mode === "light" || mode === "dark" ? mode : "auto";
  const root = document.documentElement;
  if (m === "auto") root.removeAttribute("data-color-mode");
  else root.setAttribute("data-color-mode", m);
  document.querySelectorAll(".color-mode-btn").forEach((btn) => {
    btn.classList.toggle("active", btn.getAttribute("data-color-mode") === m);
  });
  try {
    localStorage.setItem(COLOR_MODE_STORAGE_KEY, m);
  } catch (_) {
    /* ignore */
  }
}

function initColorMode() {
  let stored = "auto";
  try {
    stored = localStorage.getItem(COLOR_MODE_STORAGE_KEY) || "auto";
  } catch (_) {
    /* ignore */
  }
  applyColorMode(stored);
}

function applyDashboardTheme(theme) {
  const normalized = normalizeDashboardTheme(theme);
  document.body.classList.toggle("theme-classic", normalized === "classic");
  document.body.classList.toggle("theme-novo", normalized !== "classic");
  document.documentElement.setAttribute("data-ui-theme", normalized === "classic" ? "legacy" : "aurora-v3");
  const classicLink = document.getElementById("theme-classic-css");
  if (classicLink) classicLink.disabled = normalized !== "classic";
  document.querySelectorAll(".theme-switch-btn").forEach((btn) => {
    const btnTheme = btn.getAttribute("data-theme");
    const match =
      normalized === "classic"
        ? btnTheme === "classic" || btnTheme === "legacy"
        : btnTheme === "novo" || btnTheme === "v3";
    btn.classList.toggle("active", match);
  });
  try {
    localStorage.setItem(THEME_STORAGE_KEY, normalized);
  } catch (_) {
    /* ignore */
  }
}

function initDashboardTheme() {
  let stored = "novo";
  try {
    stored = localStorage.getItem(THEME_STORAGE_KEY) || "novo";
  } catch (_) {
    /* ignore */
  }
  applyDashboardTheme(stored);
}

function applySidebarCollapsed(collapsed) {
  document.body.classList.toggle("sidebar-collapsed", collapsed);
  const btn = $("sidebar-toggle");
  const mobileBtn = $("mobile-nav-toggle");
  if (btn) {
    btn.setAttribute("aria-expanded", collapsed ? "false" : "true");
    btn.setAttribute("aria-label", collapsed ? "Expandir menu lateral" : "Recolher menu lateral");
  }
  if (mobileBtn) {
    mobileBtn.setAttribute("aria-expanded", collapsed ? "false" : "true");
    mobileBtn.setAttribute("aria-label", collapsed ? "Abrir menu de seções" : "Fechar menu de seções");
  }
  try {
    localStorage.setItem(SIDEBAR_STORAGE_KEY, collapsed ? "1" : "0");
  } catch (_) {
    /* ignore */
  }
}

function initSidebarToggle() {
  let collapsed = false;
  try {
    const stored = localStorage.getItem(SIDEBAR_STORAGE_KEY);
    if (stored === "1") collapsed = true;
    else if (stored === "0") collapsed = false;
    else if (window.matchMedia("(max-width: 960px)").matches) collapsed = true;
  } catch (_) {
    /* ignore */
  }
  applySidebarCollapsed(collapsed);
  const toggleSidebar = () => {
    applySidebarCollapsed(!document.body.classList.contains("sidebar-collapsed"));
  };
  $("sidebar-toggle")?.addEventListener("click", toggleSidebar);
  $("mobile-nav-toggle")?.addEventListener("click", toggleSidebar);
  document.querySelectorAll(".zone-nav-link").forEach((link) => {
    link.addEventListener("click", () => {
      if (window.matchMedia("(max-width: 960px)").matches) {
        applySidebarCollapsed(true);
      }
    });
  });
}

function initZoneNavActive() {
  const links = [...document.querySelectorAll(".zone-nav-link[data-zone]")];
  if (!links.length) return;
  const zones = links
    .map((a) => document.getElementById(a.getAttribute("data-zone")))
    .filter(Boolean);
  const setActive = () => {
    let current = links[0];
    const offset = 120;
    for (const link of links) {
      const id = link.getAttribute("data-zone");
      const el = document.getElementById(id);
      if (!el) continue;
      if (el.getBoundingClientRect().top - offset <= 0) current = link;
    }
    links.forEach((l) => l.classList.toggle("is-active", l === current));
  };
  window.addEventListener("scroll", setActive, { passive: true });
  setActive();
}

initDashboardTheme();
initColorMode();
initSidebarToggle();
initZoneNavActive();

// --- Live refresh indicator ---

function setRefreshing(busy) {
  $("refresh-spinner")?.classList.toggle("is-busy", busy);
  $("live-refresh")?.classList.toggle("is-fetching", busy);
}

function touchLastUpdate() {
  const el = $("last-update-label");
  if (!el) return;
  const t = new Date().toLocaleTimeString("pt-BR", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
  el.textContent = `Atualizado às ${t}`;
}

// --- Session summary strip ---

function strategyDisplayName(type) {
  const t = (type || "").toLowerCase();
  if (t === "volatility") return "Volatilidade adaptativa";
  if (t === "breakout") return "Rompimento (breakout)";
  return type || "—";
}

function updateSessionStrip(state, cfg) {
  const op = state ? inferOperatingMode(state) : null;
  const badge = operatingBadgeLabel(op);
  setText("session-modo", badge.text !== "—" ? badge.text : "Aguardando");
  const sym = cfg?.active_symbol || state?.active_symbol || "—";
  setText("session-ativo", sym);
  const strat = cfg?.strategy_type || state?.strategy_type || "volatility";
  setText("session-estrategia", strategyDisplayName(strat));
}

// --- Status connection dashboard ---

function setStatusTile(tileId, dashId, text, tone) {
  setText(dashId, text);
  const tile = $(tileId);
  if (!tile) return;
  tile.classList.remove("tile-ok", "tile-warn", "tile-bad");
  if (tone) tile.classList.add(`tile-${tone}`);
}

let lastExecutionStatus = null;

function updateAutoExecutionPanel(status) {
  lastExecutionStatus = status;
  const toggle = $("auto-exec-toggle");
  if (toggle && status) {
    const on = !!status.auto_execute_enabled;
    toggle.textContent = on ? "Ligada" : "Desligada";
    toggle.classList.toggle("on", on);
    toggle.classList.toggle("off", !on);
  }

  const warn = $("auto-exec-live-warning");
  if (warn) {
    warn.classList.toggle("hidden", !status?.live_trading_warning);
  }

  const stepsEl = $("auto-exec-steps");
  if (stepsEl) {
    const steps = status?.steps || [];
    if (!steps.length) {
      stepsEl.innerHTML = `<li class="muted">Carregando checklist…</li>`;
    } else {
      stepsEl.innerHTML = steps
        .map(
          (s) =>
            `<li class="${s.done ? "done" : ""}"><span class="step-mark" aria-hidden="true">${
              s.done ? "✓" : "○"
            }</span><span>${escHtml(s.label)}</span></li>`
        )
        .join("");
    }
  }

  const blockersEl = $("auto-exec-blockers");
  if (blockersEl) {
    const blockers = status?.blockers || [];
    blockersEl.innerHTML = blockers.map((b) => `<li>${escHtml(b)}</li>`).join("");
  }
}

function openAutoExecEnvModal() {
  const dialog = $("auto-exec-dialog");
  const ta = $("auto-exec-env-snippet");
  if (!dialog || !ta) return;
  ta.value = lastExecutionStatus?.env_snippet_paper_demo || "";
  dialog.showModal();
}

function updateStatusDashboard(state, signals) {
  const apiLabel = apiOnline ? "Online" : "Offline";
  setStatusTile("status-tile-api", "status-dash-api", apiLabel, apiOnline ? "ok" : "bad");

  let eng = "Parado";
  let engTone = "bad";
  if (state && engineIsOnline(state)) {
    if (state.engine_paused) {
      eng = "Pausado";
      engTone = "warn";
    } else {
      eng = "Ativo";
      engTone = "ok";
    }
  } else if (!apiOnline) {
    eng = "—";
    engTone = null;
  }
  setStatusTile("status-tile-engine", "status-dash-engine", eng, engTone);

  let dados = "Simulado";
  let dadosTone = "neutral";
  const src = (state?.data_source || "").toLowerCase();
  if (src === "mt5" && state?.mt5_connected) {
    dados = "MT5 ao vivo";
    dadosTone = "warn";
  } else if (src && src !== "simulation") {
    dados = src;
  }
  setStatusTile(
    "status-tile-dados",
    "status-dash-dados",
    dados,
    dadosTone === "warn" ? "warn" : dadosTone === "neutral" ? null : "ok"
  );

  const last = Array.isArray(signals) && signals.length ? signals[0] : null;
  const lastTxt = last
    ? `#${last.id} ${last.symbol || ""} ${(last.side || "").toLowerCase()}`
    : "Nenhum ainda";
  setStatusTile("status-tile-signal", "status-dash-last-signal", lastTxt.trim(), last ? "ok" : null);
}

function humanizeCandleTitle(symbol, tf) {
  const sym = symbol || "—";
  const human = TF_HUMAN[tf] || tf || "—";
  return `${sym} · ${human}`;
}

function setCandleChartLoading(loading) {
  $("candle-chart-skeleton")?.classList.toggle("hidden", !loading);
}

// --- Strategy visual picker ---

function syncStrategyPicker(value) {
  const v = (value || "volatility").toLowerCase();
  const sel = $("cfg-strategy-type");
  if (sel) sel.value = v;
  document.querySelectorAll(".strategy-card").forEach((btn) => {
    const s = btn.getAttribute("data-strategy");
    btn.classList.toggle("active", s === v);
    btn.setAttribute("aria-pressed", s === v ? "true" : "false");
  });
}

function initStrategyPicker() {
  document.querySelectorAll(".strategy-card").forEach((btn) => {
    btn.addEventListener("click", () => {
      const s = btn.getAttribute("data-strategy") || "volatility";
      syncStrategyPicker(s);
    });
  });
}

// --- CSV export ---

function signalsToCsv(rows) {
  const headers = [
    "id",
    "created_at",
    "mode",
    "side",
    "symbol",
    "entry",
    "stop",
    "target",
    "status",
    "net_pnl_brl",
    "strategy_type",
    "entry_reason",
    "exit_reason",
  ];
  const esc = (v) => {
    const s = v == null ? "" : String(v);
    if (/[",\n]/.test(s)) return `"${s.replace(/"/g, '""')}"`;
    return s;
  };
  const lines = [headers.join(",")];
  for (const s of rows) {
    lines.push(headers.map((h) => esc(s[h])).join(","));
  }
  return lines.join("\n");
}

async function exportSignalsCsv() {
  const base = apiBase();
  const btn = $("btn-export-signals");
  if (btn) btn.disabled = true;
  try {
    const res = await fetch(`${base}/signals?limit=500`, { cache: "no-store" });
    if (!res.ok) throw new Error("Falha ao buscar sinais");
    const data = await res.json();
    const rows = Array.isArray(data) ? data : [];
    const blob = new Blob([signalsToCsv(rows)], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `sinais-${new Date().toISOString().slice(0, 10)}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  } catch (e) {
    alert(e.message || "Exportação falhou");
  } finally {
    if (btn) btn.disabled = false;
  }
}

function configFingerprint(cfg) {
  if (!cfg) return "";
  return JSON.stringify({
    symbols: cfg.symbols,
    capital_brl: cfg.capital_brl,
    active_symbol: cfg.active_symbol,
  });
}

function isConfigComplete(cfg) {
  if (!cfg) return false;
  const cap = Number(cfg.capital_brl);
  const syms = cfg.symbols;
  return Array.isArray(syms) && syms.length > 0 && Number.isFinite(cap) && cap >= 100;
}

const CHART_DEFAULTS = {
  responsive: true,
  maintainAspectRatio: false,
  plugins: { legend: { display: false } },
  scales: {
    x: {
      ticks: { color: "#7d8fa8", maxTicksLimit: 8 },
      grid: { color: "rgba(36, 48, 64, 0.6)" },
    },
    y: {
      ticks: { color: "#7d8fa8" },
      grid: { color: "rgba(36, 48, 64, 0.6)" },
    },
  },
};

function chartsAvailable() {
  return typeof Chart !== "undefined";
}

function setText(id, text) {
  const el = $(id);
  if (el) el.textContent = text;
}

function signalTime(s) {
  return new Date(s.closed_at || s.created_at).getTime();
}

function sortSignalsChronological(signals) {
  if (!Array.isArray(signals)) return [];
  return [...signals].sort((a, b) => signalTime(a) - signalTime(b));
}

/** PnL estimado para sinais abertos (alvo como proxy educacional). */
function estimateSignalPnl(s) {
  if (s.net_pnl_brl != null && !Number.isNaN(Number(s.net_pnl_brl))) {
    return Number(s.net_pnl_brl);
  }
  const contracts = Number(s.contracts) || 1;
  const entry = Number(s.entry);
  const target = Number(s.target);
  const stop = Number(s.stop);
  if (!Number.isFinite(entry)) return 0;
  let exit = s.exit_price != null ? Number(s.exit_price) : null;
  if (exit == null || !Number.isFinite(exit)) {
    exit = Number.isFinite(target) ? target : Number.isFinite(stop) ? stop : entry;
  }
  if (s.side === "BUY") return (exit - entry) * contracts;
  return (entry - exit) * contracts;
}

function setEquityChartHint(text) {
  setText("equity-chart-hint", text);
}
let agentConfigCache = { symbols: [], presets: [] };
let selectedSymbols = new Set();
const CONFIG_SEEDED_KEY = "config_seeded_v1";
let tickerSearchDebounce = null;
let tickerSaveDebounce = null;
let tickerSuggestIdx = -1;

const PRESET_LABELS = {
  moderado: "Moderado",
  conservador: "Conservador",
  agressivo: "Agressivo",
};
let libraryIndexCache = null;
let libraryFilterCategory = "all";

function apiBase() {
  const p = window.location.pathname;
  if (p === "/" || p === "/dashboard" || p.startsWith("/dashboard/")) {
    return window.location.origin;
  }
  const el = $("api-url");
  return el ? el.value.replace(/\/$/, "") : window.location.origin;
}

function formatDate(iso) {
  try {
    const d = new Date(iso);
    return d.toLocaleString("pt-BR", { timeZone: "America/Sao_Paulo" });
  } catch {
    return iso;
  }
}

function formatBrl(n) {
  if (n == null || Number.isNaN(n)) return "—";
  const sign = n >= 0 ? "+" : "";
  return `${sign}R$ ${n.toFixed(2)}`;
}

function formatBrlPlain(n) {
  if (n == null || Number.isNaN(n)) return "—";
  return `R$ ${Number(n).toFixed(2)}`;
}

function formatPct(n) {
  if (n == null || Number.isNaN(n)) return "—";
  const sign = n > 0 ? "+" : "";
  return `${sign}${Number(n).toFixed(2)}%`;
}

function flashKpi(id) {
  const el = $(id);
  const wrap = el?.closest(".kpi");
  if (!wrap) return;
  wrap.classList.remove("kpi-flash");
  void wrap.offsetWidth;
  wrap.classList.add("kpi-flash");
}

function animateCounterEl(el, nextText, parseNum) {
  if (!el) return;
  const prevKey = el.id;
  const prevRaw = kpiPrev[prevKey];
  const nextNum = parseNum ? parseNum(nextText) : null;
  const prevNum = parseNum && prevRaw != null ? parseNum(prevRaw) : null;

  if (
    nextNum != null &&
    prevNum != null &&
    Number.isFinite(nextNum) &&
    Number.isFinite(prevNum) &&
    nextNum !== prevNum
  ) {
    const start = prevNum;
    const end = nextNum;
    const duration = 450;
    const t0 = performance.now();
    const step = (t) => {
      const p = Math.min(1, (t - t0) / duration);
      const eased = 1 - (1 - p) ** 3;
      const cur = start + (end - start) * eased;
      el.textContent = Number.isInteger(end) ? String(Math.round(cur)) : cur.toFixed(2);
      if (p < 1) requestAnimationFrame(step);
      else {
        el.textContent = nextText;
        flashKpi(prevKey);
      }
    };
    requestAnimationFrame(step);
  } else {
    el.textContent = nextText;
    if (prevRaw !== undefined && prevRaw !== nextText) flashKpi(prevKey);
  }
  kpiPrev[prevKey] = nextText;
}

function setPnlEl(id, value) {
  const el = $(id);
  if (!el) return;
  if (value == null || Number.isNaN(Number(value))) {
    el.textContent = "—";
    el.classList.remove("positive", "negative");
    return;
  }
  const num = Number(value);
  const text = formatBrl(num);
  el.classList.remove("positive", "negative");
  if (num > 0) el.classList.add("positive");
  if (num < 0) el.classList.add("negative");
  animateCounterEl(el, text);
}

function escHtml(s) {
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function cellTrunc(text, max = 42) {
  if (!text) return '<span class="muted">—</span>';
  const t = String(text);
  if (t.length <= max) return escHtml(t);
  return `<span class="trunc-tip" title="${escHtml(t)}">${escHtml(t.slice(0, max))}…</span>`;
}

function strategyLabel(s) {
  const t = (s.strategy_type || "").toLowerCase();
  const ver = s.strategy_version || "v1";
  if (t === "volatility") return `Volatilidade (${ver})`;
  if (t === "breakout") return `Rompimento (${ver})`;
  return s.strategy_id || "—";
}

function strategyBadgeHtml(s) {
  const t = (s.strategy_type || "").toLowerCase();
  const label = strategyLabel(s);
  if (t === "volatility" || t === "breakout") {
    return `<span class="strat-badge ${t}">${escHtml(label)}</span>`;
  }
  return escHtml(label);
}

function statusPillClass(status) {
  const st = (status || "").toLowerCase();
  if (st.includes("open") || st === "active" || st === "pending") return "open";
  if (st.includes("cancel")) return "cancelled";
  if (st.includes("close") || st === "filled") return "closed";
  return "";
}

function formatBrlAbs(n) {
  if (n == null || Number.isNaN(n)) return "—";
  return `R$ ${Math.abs(Number(n)).toFixed(2)}`;
}

function todayClosedNetBrl(pnl) {
  if (!pnl) return null;
  const d = pnl.daily;
  if (pnl.today_net != null && !Number.isNaN(Number(pnl.today_net))) return Number(pnl.today_net);
  if (d?.net_before_tax_brl != null && !Number.isNaN(Number(d.net_before_tax_brl))) {
    return Number(d.net_before_tax_brl);
  }
  if (d?.net_pnl_brl != null && !Number.isNaN(Number(d.net_pnl_brl))) return Number(d.net_pnl_brl);
  return null;
}

function renderTodayResultBanner(pnl) {
  const strip = $("today-result-strip");
  if (!strip) return;
  const amountEl = $("today-result-amount");
  const openEl = $("today-result-open");
  const net = todayClosedNetBrl(pnl);

  if (amountEl) {
    if (net == null || Number.isNaN(net)) {
      amountEl.textContent = "—";
      amountEl.classList.remove("positive", "negative");
      strip.classList.remove("today-result-up", "today-result-down");
    } else {
      amountEl.textContent = formatBrl(net);
      amountEl.classList.remove("positive", "negative");
      strip.classList.remove("today-result-up", "today-result-down");
      if (net > 0) {
        amountEl.classList.add("positive");
        strip.classList.add("today-result-up");
      } else if (net < 0) {
        amountEl.classList.add("negative");
        strip.classList.add("today-result-down");
      }
    }
  }

  if (openEl) {
    const openEst = pnl?.open_positions_estimated_pnl;
    if (openEst != null && openEst !== 0 && !Number.isNaN(Number(openEst))) {
      openEl.classList.remove("hidden");
      const est = Number(openEst);
      const cls = est >= 0 ? "pnl-pos" : "pnl-neg";
      openEl.innerHTML = `Em aberto (estimativa): <span class="${cls}">${formatBrlPlain(est)}</span>`;
    } else {
      openEl.classList.add("hidden");
      openEl.textContent = "";
    }
  }
}

function isSignalOpenForPnl(s) {
  if (s.net_pnl_brl != null && !Number.isNaN(Number(s.net_pnl_brl))) return false;
  const st = (s.status || "").toLowerCase();
  if (st === "cancelled" || st === "rejected" || st === "closed" || st === "filled") return false;
  return s.exit_price == null;
}

function formatSignalResultado(s) {
  if (s.net_pnl_brl != null && !Number.isNaN(Number(s.net_pnl_brl))) {
    const pnl = Number(s.net_pnl_brl);
    const cls = pnl >= 0 ? "pnl-pos" : "pnl-neg";
    return `<span class="${cls}">${formatBrl(pnl)}</span>`;
  }
  if (isSignalOpenForPnl(s)) {
    const est = estimateSignalPnl(s);
    const cls = est >= 0 ? "pnl-pos" : "pnl-neg";
    return `<span class="${cls} resultado-est" title="Estimativa educacional até registrar saída">${formatBrl(est)} <span class="muted">est.</span></span>`;
  }
  return "—";
}

function renderPnlAccountingTable(pnl) {
  const body = $("pnl-accounting-body");
  if (!body || !pnl) return;
  const rows = [
    { label: "Hoje", m: pnl.daily },
    { label: "Mês", m: pnl.monthly },
    { label: "Total", m: pnl.all_time },
  ];
  body.innerHTML = rows
    .map(({ label, m }) => {
      if (!m) {
        return `<tr><td>${label}</td><td colspan="5" class="muted">—</td></tr>`;
      }
      const after = m.net_after_tax_estimated_brl ?? m.net_pnl_brl;
      const ir = m.estimated_ir_brl ?? 0;
      const net = m.net_before_tax_brl ?? m.net_pnl_brl;
      return `<tr>
        <td>${label}</td>
        <td class="mono-num">${formatBrl(m.gross_pnl_brl)}</td>
        <td class="mono-num">${formatBrlAbs(m.fees_brl)}</td>
        <td class="mono-num">${formatBrl(net)}</td>
        <td class="mono-num">${formatBrlAbs(ir)}</td>
        <td class="mono-num"><strong>${formatBrl(after)}</strong></td>
      </tr>`;
    })
    .join("");
}

function renderPnlZone(pnl) {
  if (!pnl) return;

  renderTodayResultBanner(pnl);
  renderPnlAccountingTable(pnl);
  const afterAll = pnl.net_after_tax_estimated_brl ?? pnl.all_time_net ?? pnl.all_time?.net_pnl_brl;
  setPnlEl("pnl-today-net", pnl.today_net ?? pnl.daily?.net_after_tax_estimated_brl ?? pnl.daily?.net_pnl_brl);
  setPnlEl("pnl-month-net", pnl.monthly?.net_after_tax_estimated_brl ?? pnl.month_net ?? pnl.monthly?.net_pnl_brl);
  setPnlEl("pnl-all-net", afterAll);

  const feesEl = $("pnl-fees-total");
  if (feesEl) {
    feesEl.textContent = formatBrlAbs(pnl.fees_paid_brl ?? pnl.all_time?.fees_brl);
  }

  const gp = $("pnl-gross-profit");
  const gl = $("pnl-gross-loss");
  if (gp) gp.textContent = formatBrlAbs(pnl.gross_profit_brl ?? pnl.all_time?.gross_profit_brl);
  if (gl) {
    const loss = pnl.gross_loss_brl ?? pnl.all_time?.gross_loss_brl;
    gl.textContent = loss != null && loss < 0 ? `−${formatBrlAbs(loss)}` : formatBrlAbs(0);
  }

  const openLine = $("pnl-open-line");
  const openEst = pnl.open_positions_estimated_pnl;
  const openCount = pnl.open_positions_count ?? 0;
  if (openLine) {
    if (openCount > 0) {
      openLine.classList.remove("hidden");
      const cls = openEst >= 0 ? "pnl-pos" : "pnl-neg";
      const estText =
        openEst != null && openEst !== 0
          ? `<span class="${cls}">${formatBrl(openEst)}</span>`
          : "<span class=\"muted\">aguardando cotação</span>";
      openLine.innerHTML = `Em aberto (${openCount}): estimativa mark-to-market ${estText}`;
    } else {
      openLine.classList.add("hidden");
    }
  }

  const wins = pnl.wins ?? pnl.all_time?.wins ?? 0;
  const losses = pnl.losses ?? pnl.all_time?.losses ?? 0;
  const be = pnl.breakeven_count ?? pnl.all_time?.breakeven_count ?? 0;
  const cap = $("pnl-wl-caption");
  if (cap) {
    cap.textContent = `${wins} vitória(s) · ${losses} derrota(s)${be ? ` · ${be} empate(s)` : ""}`;
  }
  buildPnlWlChart(wins, losses, be);
  buildPnlSparkline(pnl);

  const body = $("pnl-closed-body");
  if (!body) return;
  const rows = Array.isArray(pnl.recent_closed) ? pnl.recent_closed : [];
  if (!rows.length) {
    body.innerHTML = `<tr><td colspan="6" class="muted">Nenhuma operação fechada ainda.</td></tr>`;
    return;
  }
  body.innerHTML = rows
    .map((t) => {
      const net = Number(t.net_pnl_brl);
      const cls = net >= 0 ? "pnl-pos" : "pnl-neg";
      const strat = strategyLabel(t);
      return `<tr>
        <td>${t.symbol || "—"} <span class="muted">${t.side || ""}</span></td>
        <td>${escHtml(strat)}</td>
        <td class="mono-num">${t.entry}</td>
        <td class="mono-num">${t.exit_price}</td>
        <td><span class="${cls}">${formatBrl(net)}</span></td>
        <td class="muted mono-num">${formatBrlAbs(t.fees_brl)}</td>
      </tr>`;
    })
    .join("");
}

function setWealthKpi(id, value, asPct = false) {
  const el = $(id);
  if (!el) return;
  if (value == null || Number.isNaN(Number(value))) {
    el.textContent = "—";
    el.classList.remove("positive", "negative");
    return;
  }
  const num = Number(value);
  const text = asPct ? formatPct(num) : formatBrlPlain(num);
  el.classList.remove("positive", "negative");
  if (!asPct) {
    if (num > 0) el.classList.add("positive");
    if (num < 0) el.classList.add("negative");
  } else {
    if (num > 0) el.classList.add("positive");
    if (num < 0) el.classList.add("negative");
  }
  el.textContent = text;
}

function renderWealthZone(curve) {
  if (!curve) return;
  const initial = curve.initial_capital_brl ?? curve.summary?.initial_capital_brl;
  setText("wealth-initial-capital", formatBrlPlain(initial));
  const s = curve.summary || {};
  setWealthKpi("wealth-kpi-current", s.current_equity_brl);
  setWealthKpi("wealth-kpi-max", s.peak_equity_brl);
  setWealthKpi("wealth-kpi-min", s.min_equity_brl);
  setWealthKpi("wealth-kpi-change", s.change_pct, true);

  const msgEl = $("wealth-curve-message");
  if (msgEl) {
    let msg = curve.message || "";
    if (s.includes_open_mtm) {
      msg = msg
        ? `${msg} Posições abertas incluídas no patrimônio atual (mark-to-market).`
        : "Patrimônio atual inclui estimativa mark-to-market de posições abertas.";
    }
    if (msg) {
      msgEl.textContent = msg;
      msgEl.classList.remove("hidden");
    } else {
      msgEl.textContent = "";
      msgEl.classList.add("hidden");
    }
  }

  buildWealthCharts(curve);
}

function buildWealthCharts(curve) {
  const equityCanvas = $("wealth-equity-chart");
  const ddCanvas = $("wealth-drawdown-chart");
  if (!equityCanvas || !chartsAvailable()) return;

  const points = Array.isArray(curve?.points) ? curve.points : [];
  const initial = Number(curve?.initial_capital_brl) || 0;
  const labels = points.map((p) => {
    try {
      const d = new Date(`${p.date}T12:00:00`);
      return d.toLocaleDateString("pt-BR", { day: "2-digit", month: "short" });
    } catch {
      return p.date;
    }
  });
  const equities = points.map((p) => Number(p.equity_brl));
  const drawdowns = points.map((p) => Number(p.drawdown_pct));

  const segmentColor = (ctx, above) => {
    const y0 = ctx.p0?.parsed?.y;
    const y1 = ctx.p1?.parsed?.y;
    const ref = initial;
    const below = y1 < ref || y0 < ref;
    return below ? "#ef4444" : "#22c55e";
  };

  const equityDataset = {
    label: "Patrimônio (R$)",
    data: equities,
    borderWidth: 2,
    fill: true,
    tension: 0.25,
    pointRadius: points.length > 1 ? 2 : 3,
    backgroundColor: "rgba(34, 197, 94, 0.08)",
    borderColor: "#22c55e",
    segment: {
      borderColor: (ctx) => segmentColor(ctx, true),
    },
  };

  const equityOpts = {
    ...CHART_DEFAULTS,
    plugins: {
      ...CHART_DEFAULTS.plugins,
      annotation: undefined,
    },
    scales: {
      ...CHART_DEFAULTS.scales,
      y: {
        ...CHART_DEFAULTS.scales.y,
        ticks: {
          ...CHART_DEFAULTS.scales.y.ticks,
          callback: (v) => `R$ ${v}`,
        },
      },
    },
  };

  try {
    if (wealthEquityChart) {
      wealthEquityChart.data.labels = labels;
      wealthEquityChart.data.datasets[0] = { ...wealthEquityChart.data.datasets[0], ...equityDataset };
      wealthEquityChart.update("none");
    } else {
      wealthEquityChart = new Chart(equityCanvas, {
        type: "line",
        data: { labels, datasets: [equityDataset] },
        options: equityOpts,
      });
    }
  } catch (err) {
    console.warn("wealth equity chart:", err);
  }

  if (!ddCanvas) return;
  const ddDataset = {
    label: "Drawdown %",
    data: drawdowns,
    borderColor: "#f97316",
    backgroundColor: "rgba(249, 115, 22, 0.2)",
    fill: true,
    tension: 0.2,
    pointRadius: 0,
    borderWidth: 1.5,
  };
  try {
    if (wealthDrawdownChart) {
      wealthDrawdownChart.data.labels = labels;
      wealthDrawdownChart.data.datasets[0] = { ...wealthDrawdownChart.data.datasets[0], ...ddDataset };
      wealthDrawdownChart.update("none");
    } else {
      wealthDrawdownChart = new Chart(ddCanvas, {
        type: "line",
        data: { labels, datasets: [ddDataset] },
        options: {
          ...CHART_DEFAULTS,
          scales: {
            ...CHART_DEFAULTS.scales,
            y: {
              ...CHART_DEFAULTS.scales.y,
              max: 0,
              ticks: { ...CHART_DEFAULTS.scales.y.ticks, callback: (v) => `${v}%` },
            },
          },
        },
      });
    }
  } catch (err) {
    console.warn("wealth drawdown chart:", err);
  }
}

function buildPnlSparkline(pnl) {
  const canvas = $("pnl-sparkline");
  const wrap = $("pnl-spark-wrap");
  if (!canvas || !chartsAvailable()) return;

  const rows = Array.isArray(pnl?.recent_closed) ? pnl.recent_closed : [];
  if (!rows.length) {
    wrap?.classList.add("is-empty");
    if (pnlSparkChart) {
      pnlSparkChart.destroy();
      pnlSparkChart = null;
    }
    return;
  }
  wrap?.classList.remove("is-empty");

  let cum = 0;
  const data = [];
  const labels = [];
  [...rows].reverse().forEach((t, i) => {
    cum += Number(t.net_pnl_brl) || 0;
    data.push(Math.round(cum * 100) / 100);
    labels.push(String(i + 1));
  });

  const last = data[data.length - 1] ?? 0;
  const borderColor = last >= 0 ? "#22c55e" : "#ef4444";
  const dataset = {
    data,
    borderColor,
    borderWidth: 2,
    pointRadius: 0,
    tension: 0.35,
    fill: true,
    backgroundColor: last >= 0 ? "rgba(34, 197, 94, 0.12)" : "rgba(239, 68, 68, 0.1)",
  };

  try {
    if (pnlSparkChart) {
      pnlSparkChart.data.labels = labels;
      pnlSparkChart.data.datasets[0] = { ...pnlSparkChart.data.datasets[0], ...dataset };
      pnlSparkChart.update("none");
      return;
    }
    pnlSparkChart = new Chart(canvas, {
      type: "line",
      data: { labels, datasets: [dataset] },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: false }, tooltip: { enabled: false } },
        scales: {
          x: { display: false },
          y: { display: false },
        },
      },
    });
  } catch (err) {
    console.warn("pnl sparkline:", err);
  }
}

function buildPnlWlChart(wins, losses, breakeven) {
  const canvas = $("pnl-wl-chart");
  if (!canvas || !chartsAvailable()) return;
  const labels = ["Vitórias", "Derrotas"];
  const data = [wins, losses];
  const colors = ["#22c55e", "#ef4444"];
  if (breakeven > 0) {
    labels.push("Empates");
    data.push(breakeven);
    colors.push("#94a3b8");
  }
  const total = data.reduce((a, b) => a + b, 0);
  if (!total) {
    if (pnlWlChart) {
      pnlWlChart.destroy();
      pnlWlChart = null;
    }
    return;
  }
  const dataset = {
    data,
    backgroundColor: colors,
    borderWidth: 0,
  };
  try {
    if (pnlWlChart) {
      pnlWlChart.data.labels = labels;
      pnlWlChart.data.datasets[0].data = data;
      pnlWlChart.data.datasets[0].backgroundColor = colors;
      pnlWlChart.update("none");
    } else {
      pnlWlChart = new Chart(canvas, {
        type: "doughnut",
        data: { labels, datasets: [dataset] },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          cutout: "62%",
          plugins: { legend: { position: "bottom", labels: { color: "#7d8fa8", boxWidth: 10 } } },
        },
      });
    }
  } catch (err) {
    console.warn("pnl wl chart:", err);
  }
}

function setStatText(id, text, parseNum) {
  const el = $(id);
  if (!el) return;
  animateCounterEl(el, text, parseNum);
}

function engineIsOnline(state) {
  if (state?.engine_online === true) return true;
  if (state?.engine_online === false) return false;
  const hb = state?.last_heartbeat ? new Date(state.last_heartbeat).getTime() : 0;
  return hb && Date.now() - hb < 60000;
}

function setOfflineBanner(show) {
  const banner = $("offline-banner");
  if (!banner) return;
  banner.classList.toggle("hidden", !show);
}

function setEngineOfflineBanner(show) {
  const banner = $("engine-offline-banner");
  if (!banner) return;
  banner.classList.toggle("hidden", !show);
}

function setLiveChip(id, label, tone) {
  const el = $(id);
  if (!el) return;
  el.textContent = label;
  el.className = `live-chip chip-${tone}`;
}

function updateOnboarding({ apiOk, engineOk, configOk }) {
  const steps = [
    { id: "step-api", ok: apiOk },
    { id: "step-engine", ok: engineOk },
    { id: "step-config", ok: configOk },
  ];
  steps.forEach(({ id, ok }) => {
    const li = $(id);
    if (!li) return;
    li.classList.toggle("done", ok);
    li.classList.toggle("pending", !ok);
  });
}

function updateDataSourceChip(state) {
  const el = $("chip-dados");
  if (!el) return;
  const src = (state?.data_source || "").toLowerCase();
  if (src === "mt5" && state?.mt5_connected) {
    el.textContent = "Dados: MT5 AO VIVO";
    el.className = "live-chip chip-warn";
  } else if (src === "simulation" || !src) {
    el.textContent = "Dados: SIMULADO";
    el.className = "live-chip chip-neutral";
  } else {
    el.textContent = `Dados: ${src}`;
    el.className = "live-chip chip-neutral";
  }
}

function updateLiveChips(state) {
  const apiTone = apiOnline ? "ok" : "bad";
  setLiveChip("chip-api", apiOnline ? "API online" : "API offline", apiTone);

  const online = state ? engineIsOnline(state) : false;
  let engLabel = "Engine offline";
  let engTone = "warn";
  if (online && state?.engine_paused) {
    engLabel = "Engine pausado";
    engTone = "warn";
  } else if (online) {
    engLabel = "Engine ativo";
    engTone = "ok";
  } else if (!apiOnline) {
    engTone = "neutral";
  }
  setLiveChip("chip-engine", engLabel, engTone);

  const op = state ? inferOperatingMode(state) : null;
  const badge = operatingBadgeLabel(op);
  const modoTone =
    badge.cls === "live" || badge.cls === "real" ? "warn" : badge.cls === "simulation" ? "ok" : "neutral";
  setLiveChip("chip-modo", badge.text !== "—" ? badge.text : "Modo —", modoTone);
  if (state) updateDataSourceChip(state);
  else updateDataSourceChip({ data_source: "simulation" });
}

async function pollHealth() {
  const base = apiBase();
  const stat = $("stat-api");
  try {
    const health = await fetch(`${base}/health`, { cache: "no-store" });
    apiOnline = health.ok;
    const apiText = health.ok ? "Online" : "Erro";
    if (stat) {
      setStatText("stat-api", apiText);
      stat.style.color = health.ok ? "var(--buy)" : "var(--sell)";
    }
    setOfflineBanner(!health.ok);
    if (!health.ok) setEngineOfflineBanner(false);
    updateOnboarding({
      apiOk: health.ok,
      engineOk: false,
      configOk: configSavedSession || !!lastAgentConfigFingerprint,
    });
    updateLiveChips(null);
  } catch {
    apiOnline = false;
    if (stat) {
      setStatText("stat-api", "Offline");
      stat.style.color = "var(--muted)";
    }
    setOfflineBanner(true);
    setEngineOfflineBanner(false);
    updateOnboarding({ apiOk: false, engineOk: false, configOk: configSavedSession });
    updateLiveChips(null);
  }
}

function rowHtml(s) {
  const modeClass = s.mode === "live" ? "live" : "paper";
  const sideClass = s.side === "BUY" ? "side-buy" : "side-sell";
  const pnlCell = formatSignalResultado(s);
  const stCls = statusPillClass(s.status);
  return `
    <tr>
      <td>${s.id}</td>
      <td>${formatDate(s.created_at)}</td>
      <td><span class="badge ${modeClass}">${s.mode}</span></td>
      <td class="${sideClass}">${s.side}</td>
      <td>${s.symbol || "—"}</td>
      <td class="mono-num">${s.contracts ?? "—"}</td>
      <td class="mono-num">${s.entry}</td>
      <td class="mono-num">${s.stop}</td>
      <td class="mono-num">${s.target}</td>
      <td><span class="status-pill ${stCls}">${escHtml(s.status || "—")}</span></td>
      <td>${pnlCell}</td>
      <td>${strategyBadgeHtml(s)}</td>
      <td>${cellTrunc(s.entry_reason || s.note)}</td>
      <td>${cellTrunc(s.exit_reason)}</td>
    </tr>
  `;
}

function operatingBadgeLabel(op) {
  const key = (op || "").toLowerCase();
  if (key === "live_mt5" || key === "live") return { text: "AO VIVO", cls: "live" };
  if (key === "paper_mt5") return { text: "PAPER MT5", cls: "paper-mt5" };
  if (key === "simulation" || key === "sim") return { text: "SIMULAÇÃO", cls: "simulation" };
  return { text: "—", cls: "muted" };
}

function inferOperatingMode(state) {
  if (state?.operating_mode) return state.operating_mode;
  if (state?.data_source === "simulation") return "simulation";
  if (state?.mt5_connected) {
    return (state?.mode || "").toLowerCase() === "live" ? "live_mt5" : "paper_mt5";
  }
  return null;
}

function updateConnectionPanel(state) {
  const op = inferOperatingMode(state);
  const badge = operatingBadgeLabel(op);
  const opEl = $("operating-badge");
  if (opEl) {
    opEl.textContent = badge.text;
    opEl.className = `mode-badge ${badge.cls}`;
  }
  const set = (id, text) => {
    const el = $(id);
    if (el) el.textContent = text;
  };
  set("conn-mode", badge.text);
  set("conn-source", state?.data_source || (op === "simulation" ? "simulation" : "—"));
  if (state?.mt5_connected === true) set("conn-mt5", "Conectado");
  else if (state?.mt5_connected === false) set("conn-mt5", "Desconectado");
  else set("conn-mt5", "—");
  set(
    "conn-heartbeat",
    state?.last_heartbeat ? formatDate(state.last_heartbeat) : "Sem heartbeat"
  );
}

function updateModeBadges(state) {
  const modeEl = $("mode-badge");
  const accEl = $("account-badge");
  updateConnectionPanel(state);

  const mode = (state?.mode || "paper").toLowerCase();
  if (modeEl) {
    modeEl.textContent = mode === "live" ? "SINAL LIVE" : "SINAL PAPER";
    modeEl.className = `mode-badge ${mode === "live" ? "live" : "paper"}`;
    const op = inferOperatingMode(state);
    if (op === "simulation") modeEl.classList.add("hidden");
    else modeEl.classList.remove("hidden");
  }

  if (!accEl) return;
  const online = engineIsOnline(state);
  const op = inferOperatingMode(state);
  if (!online || op === "simulation" || state.is_demo == null) {
    accEl.classList.add("hidden");
    accEl.textContent = "—";
    return;
  }
  accEl.classList.remove("hidden");
  if (state.is_demo) {
    accEl.textContent = "MT5 demo";
    accEl.className = "mode-badge demo";
  } else {
    const login = state.account_login ? `#${state.account_login}` : "MT5";
    accEl.textContent = `${login} real`;
    accEl.className = "mode-badge real";
  }
  if (state.account_server) {
    accEl.title = `Servidor: ${state.account_server}`;
  }
}

function updateEngineUi(state) {
  const dot = $("engine-dot");
  const label = $("engine-label");
  const statusWrap = $("engine-status");
  if (!dot || !label) return;

  updateModeBadges(state);
  updateLiveChips(state);

  const online = engineIsOnline(state);
  dot.className = "dot";
  statusWrap?.classList.remove("engine-live");
  if (!online) {
    dot.classList.add("offline");
    label.textContent =
      "Engine offline — use Sala-Sinais.bat (opções 1, 3 ou 4)";
  } else if (state.engine_paused) {
    dot.classList.add("paused");
    label.textContent = "Engine pausado (online)";
  } else {
    dot.classList.add("live");
    statusWrap?.classList.add("engine-live");
    label.textContent = `Engine ativo · ${state.mode}`;
  }

  const cfgOk =
    configSavedSession || (lastAgentConfigFingerprint && agentConfigCache && isConfigComplete(agentConfigCache));
  updateOnboarding({
    apiOk: apiOnline,
    engineOk: online,
    configOk: !!cfgOk,
  });
}

function buildEquityChart(signals) {
  const canvas = $("equity-chart");
  if (!canvas) return;
  if (!chartsAvailable()) {
    setEquityChartHint("Chart.js não carregou — verifique a rede (CDN).");
    return;
  }

  const list = Array.isArray(signals) ? signals : [];
  const closed = sortSignalsChronological(list.filter((s) => s.net_pnl_brl != null));
  const useSimulated = !closed.length && list.length > 0;
  const series = closed.length ? closed : sortSignalsChronological(list);

  let cum = 0;
  const labels = [];
  const data = [];
  series.forEach((s) => {
    const delta = closed.length ? Number(s.net_pnl_brl) : estimateSignalPnl(s);
    cum += delta;
    labels.push(`#${s.id}`);
    data.push(Math.round(cum * 100) / 100);
  });

  let hint = "Aguardando dados — inicie a simulação.";
  let title = "Curva PnL (fechados)";
  let borderColor = "#38bdf8";
  let fillColor = "rgba(56, 189, 248, 0.12)";

  if (closed.length) {
    hint = `${closed.length} trade(s) fechado(s)`;
  } else if (useSimulated) {
    title = "PnL simulado (sinais abertos)";
    hint = "Estimativa pelo alvo/stop — não é resultado real.";
    borderColor = "#a78bfa";
    fillColor = "rgba(167, 139, 250, 0.12)";
  } else if (!list.length) {
    labels.push("—");
    data.push(0);
    hint = "Sem sinais ainda.";
  }

  setText("equity-chart-title", title);
  setEquityChartHint(hint);

  const dataset = {
    label: closed.length ? "PnL acumulado (R$)" : "PnL simulado (R$)",
    data,
    borderColor,
    backgroundColor: fillColor,
    fill: true,
    tension: 0.25,
    pointRadius: series.length ? 3 : 0,
    pointBackgroundColor: "#22c55e",
  };

  try {
    if (equityChart) {
      equityChart.data.labels = labels;
      equityChart.data.datasets[0] = { ...equityChart.data.datasets[0], ...dataset };
      equityChart.update("none");
      return;
    }
    equityChart = new Chart(canvas, {
      type: "line",
      data: { labels, datasets: [dataset] },
      options: { ...CHART_DEFAULTS },
    });
  } catch (err) {
    console.error("equity chart:", err);
    setEquityChartHint("Erro ao desenhar gráfico PnL.");
  }
}

function buildPriceChart(signals, historyPoints) {
  const canvas = $("price-chart");
  if (!canvas || !chartsAvailable()) return;

  const history = Array.isArray(historyPoints) ? historyPoints : [];
  let labels = [];
  let data = [];
  let label = "Mid (bid+ask)/2";
  let borderColor = "#f59e0b";

  if (history.length) {
    history.forEach((p) => {
      const bid = Number(p.bid);
      const ask = Number(p.ask);
      const mid = Number.isFinite(bid) && Number.isFinite(ask) ? (bid + ask) / 2 : bid || ask;
      const t = p.timestamp ? new Date(p.timestamp) : null;
      labels.push(
        t && !Number.isNaN(t.getTime())
          ? t.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit", second: "2-digit" })
          : "—"
      );
      data.push(mid);
    });
  } else {
    const list = sortSignalsChronological(Array.isArray(signals) ? signals : []);
    list.forEach((s) => {
      labels.push(`#${s.id}`);
      data.push(Number(s.entry));
    });
    label = list.length ? "Preço de entrada (sinais)" : "Cotação";
    if (!list.length) {
      labels = ["—"];
      data = [0];
      borderColor = "#4b5563";
    }
  }

  const dataset = {
    label,
    data,
    borderColor,
    backgroundColor: "rgba(245, 158, 11, 0.08)",
    fill: true,
    tension: 0.2,
    pointRadius: data.length > 1 ? 0 : 2,
  };

  try {
    if (priceChart) {
      priceChart.data.labels = labels;
      priceChart.data.datasets[0] = { ...priceChart.data.datasets[0], ...dataset };
      priceChart.update("none");
      return;
    }
    priceChart = new Chart(canvas, {
      type: "line",
      data: { labels, datasets: [dataset] },
      options: { ...CHART_DEFAULTS },
    });
  } catch (err) {
    console.error("price chart:", err);
  }
}

const TF_EXPLAINERS = {
  M1: "M1 — timing fino: cada vela ≈ 1 minuto. Útil para ver ruído e volatilidade intraminuto.",
  M5: "M5 — visão intraday equilibrada: tendência curta e pullbacks sem excesso de ruído.",
  H1: "H1 — tendência mais ampla: contexto direcional antes de entrar no detalhe.",
};

function playAlertBeep() {
  if (!$("alert-sound")?.checked) return;
  try {
    const ctx = new (window.AudioContext || window.webkitAudioContext)();
    const o = ctx.createOscillator();
    const g = ctx.createGain();
    o.connect(g);
    g.connect(ctx.destination);
    o.frequency.value = 880;
    g.gain.value = 0.04;
    o.start();
    setTimeout(() => {
      o.stop();
      ctx.close();
    }, 120);
  } catch {
    /* optional */
  }
}

function renderAlerts(alerts) {
  const list = $("alerts-list");
  if (!list) return;
  const items = Array.isArray(alerts) ? alerts : [];
  if (!items.length) {
    list.innerHTML = `<li class="muted">Nenhum alerta recente — aguarde sinais do engine.</li>`;
    lastRenderedAlertKeys = new Set();
    return;
  }
  const topId = items[0]?.signal_id || items[0]?.id || 0;
  if (topId > lastAlertMaxId) {
    playAlertBeep();
    lastAlertMaxId = topId;
  }
  const nextKeys = new Set();
  list.innerHTML = items
    .map((a, idx) => {
      const cls = a.alert_type === "exit" ? "exit" : "entry";
      const label = a.alert_type === "exit" ? "Saída" : "Entrada";
      const icon = a.alert_type === "exit" ? "↘" : "↗";
      const side = a.side ? ` · ${a.side}` : "";
      const strat = a.strategy_type ? strategyLabel(a) : "";
      const reason =
        a.alert_type === "exit"
          ? a.exit_reason || a.note || ""
          : a.entry_reason || a.note || "";
      const key = `${a.signal_id || a.id || idx}-${a.created_at}-${a.alert_type}`;
      nextKeys.add(key);
      const isNew = !lastRenderedAlertKeys.has(key);
      return `<li class="alert-toast alert-timeline-item ${cls}${isNew ? " alert-new" : ""}">
        <span class="alert-timeline-icon" aria-hidden="true">${icon}</span>
        <div>
          <span class="alert-type">${label}</span>
          <strong>${escHtml(a.symbol || "—")}${escHtml(side)}</strong> @ ${Number(a.price).toFixed(2)}
          ${strat ? `<div class="muted" style="font-size:0.78rem">${escHtml(strat)}</div>` : ""}
          <div class="muted" style="font-size:0.82rem">${cellTrunc(reason, 120)}</div>
          <div class="muted" style="font-size:0.75rem">${formatDate(a.created_at)}</div>
        </div>
      </li>`;
    })
    .join("");
  lastRenderedAlertKeys = nextKeys;
}

async function fetchOhlc(symbol, tf) {
  const base = apiBase();
  const sym = symbol || agentConfigCache.active_symbol || "PETR4";
  setCandleChartLoading(true);
  try {
    const res = await fetch(
      `${base}/market/ohlc?symbol=${encodeURIComponent(sym)}&tf=${encodeURIComponent(tf)}&limit=80`,
      { cache: "no-store" }
    );
    if (!res.ok) return { bars: [], symbol: sym, timeframe: tf };
    return res.json();
  } finally {
    setCandleChartLoading(false);
  }
}

function buildCandlestickChart(ohlcPayload) {
  const canvas = $("candle-chart");
  if (!canvas || !chartsAvailable()) return;
  const bars = ohlcPayload?.bars || [];
  const tf = ohlcPayload?.timeframe || activeTf;
  setText("candle-chart-explainer", TF_EXPLAINERS[tf] || TF_EXPLAINERS.M5);
  setText("candle-chart-title", humanizeCandleTitle(ohlcPayload?.symbol, tf));

  const data = bars.map((b) => ({
    x: (b.time || 0) * 1000,
    o: b.open,
    h: b.high,
    l: b.low,
    c: b.close,
  }));

  const dataset = {
    label: "OHLC",
    data,
    color: {
      up: "#22c55e",
      down: "#ef4444",
      unchanged: "#94a3b8",
    },
  };

  const options = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: { legend: { display: false } },
    scales: {
      x: {
        type: "time",
        ticks: { color: "#7d8fa8", maxTicksLimit: 8 },
        grid: { color: "rgba(36, 48, 64, 0.6)" },
      },
      y: {
        ticks: { color: "#7d8fa8" },
        grid: { color: "rgba(36, 48, 64, 0.6)" },
      },
    },
  };

  try {
    if (candleChart) {
      candleChart.data.datasets[0].data = data;
      candleChart.update("none");
      return;
    }
    candleChart = new Chart(canvas, {
      type: "candlestick",
      data: { datasets: [dataset] },
      options,
    });
  } catch (err) {
    console.error("candle chart:", err);
    setText("candle-chart-title", "Candlestick indisponível (plugin Chart.js Financial)");
  }
}

function renderCharts(signals, historyPoints, ohlcPayload) {
  try {
    buildEquityChart(signals);
  } catch (err) {
    console.error("renderCharts equity:", err);
  }
  try {
    buildPriceChart(signals, historyPoints);
  } catch (err) {
    console.error("renderCharts price:", err);
  }
  try {
    if (ohlcPayload) buildCandlestickChart(ohlcPayload);
  } catch (err) {
    console.error("renderCharts candle:", err);
  }
}

function renderNewsSkeleton() {
  const list = $("news-list");
  if (!list) return;
  list.innerHTML = `<li class="news-skeleton" aria-hidden="true">
    <div class="news-skeleton-line"></div>
    <div class="news-skeleton-line"></div>
    <div class="news-skeleton-line"></div>
  </li>`;
}

function renderNews(items, error) {
  const list = $("news-list");
  if (!list) return;
  if (!items.length) {
    list.innerHTML = `<li class="muted">${error ? "Feed indisponível no momento." : "Sem notícias."}</li>`;
    return;
  }
  list.innerHTML = items
    .map(
      (n, i) =>
        `<li class="news-card news-card-stagger" style="animation-delay:${i * 55}ms">
          <a class="news-link" href="${escHtml(n.link)}" target="_blank" rel="noopener noreferrer">
            <span class="news-ext-icon" aria-hidden="true">↗</span>
            <span>${escHtml(n.title)}</span>
          </a>
        </li>`
    )
    .join("");
}

function formatBrlInt(n) {
  const v = Number(n);
  if (!Number.isFinite(v)) return "—";
  return new Intl.NumberFormat("pt-BR", {
    style: "currency",
    currency: "BRL",
    maximumFractionDigits: 0,
  }).format(v);
}

function strategyChipName(type) {
  const t = (type || "volatility").toLowerCase();
  if (t === "breakout") return "rompimento";
  return "volatilidade";
}

function updateConfigProfileLine(cfg) {
  const el = $("config-profile-name");
  if (!el) return;
  const id = (cfg?.applied_preset || "moderado").toLowerCase();
  el.textContent = PRESET_LABELS[id] || id;
}

function updateConfigSummaryChips(cfg) {
  const wrap = $("config-summary-chips");
  if (!wrap || !cfg) return;
  const news = cfg.use_news_filter !== false ? "ON" : "OFF";
  const parts = [
    `Capital ${formatBrlInt(cfg.capital_brl)}`,
    `Lote ${cfg.shares_per_order ?? 100}`,
    `Stop ${cfg.stop_loss_pct ?? "—"}%`,
    `Alvo ${cfg.take_profit_pct ?? "—"}%`,
    `Estratégia ${strategyChipName(cfg.strategy_type)}`,
    `Filtro notícias ${news}`,
  ];
  wrap.innerHTML = parts.map((p) => `<span class="config-summary-chip">${escHtml(p)}</span>`).join("");
}

function syncTickerSearchDisplay(cfg) {
  const sym = cfg?.active_symbol || (cfg?.symbols && cfg.symbols[0]) || "";
  const sel = $("ticker-selected");
  if (sel) sel.textContent = sym || "—";
  const inp = $("ticker-search");
  if (inp && document.activeElement !== inp) {
    inp.value = sym || "";
  }
}

function updateAssetClassBadge(assetClass) {
  const el = $("asset-class-badge");
  if (!el) return;
  const ac = (assetClass || "acoes").toLowerCase();
  if (ac === "win") {
    el.textContent = "WIN";
    el.className = "mode-badge win-badge";
  } else if (ac === "mixed") {
    el.textContent = "Misto";
    el.className = "mode-badge paper";
  } else {
    el.textContent = "Ações BR";
    el.className = "mode-badge acoes";
  }
}

function renderSymbolPresets() {
  const box = $("symbol-presets");
  if (!box) return;
  const presets = agentConfigCache.presets?.length
    ? agentConfigCache.presets
    : ["PETR4", "VALE3", "ITUB4", "BBDC4", "ABEV3", "MGLU3"];
  const all = [...new Set([...presets, ...selectedSymbols])];
  box.innerHTML = all
    .map((sym) => {
      const checked = selectedSymbols.has(sym) ? "checked" : "";
      return `<label><input type="checkbox" data-symbol="${sym}" ${checked} /> ${sym}</label>`;
    })
    .join("");
  box.querySelectorAll("input[data-symbol]").forEach((inp) => {
    inp.addEventListener("change", () => {
      const sym = inp.getAttribute("data-symbol");
      if (inp.checked) selectedSymbols.add(sym);
      else selectedSymbols.delete(sym);
      refreshActiveSymbolSelect();
    });
  });
}

function refreshActiveSymbolSelect() {
  const sel = $("cfg-active");
  if (!sel) return;
  const syms = [...selectedSymbols].sort();
  sel.innerHTML = syms.map((s) => `<option value="${s}">${s}</option>`).join("");
  if (agentConfigCache.active_symbol && syms.includes(agentConfigCache.active_symbol)) {
    sel.value = agentConfigCache.active_symbol;
  } else if (syms.length) {
    sel.value = syms[0];
  }
}

function fillAgentConfigForm(cfg) {
  agentConfigCache = cfg;
  lastAgentConfigFingerprint = configFingerprint(cfg);
  selectedSymbols = new Set(cfg.symbols || []);
  renderSymbolPresets();
  refreshActiveSymbolSelect();
  if ($("cfg-capital")) $("cfg-capital").value = cfg.capital_brl ?? "";
  if ($("cfg-risk")) $("cfg-risk").value = cfg.risk_per_trade_pct ?? "";
  if ($("cfg-max-pos")) $("cfg-max-pos").value = cfg.max_position_brl ?? "";
  if ($("cfg-shares")) $("cfg-shares").value = cfg.shares_per_order ?? 100;
  if ($("cfg-sl")) $("cfg-sl").value = cfg.stop_loss_pct ?? "";
  if ($("cfg-tp")) $("cfg-tp").value = cfg.take_profit_pct ?? "";
  if ($("cfg-rotate")) $("cfg-rotate").checked = !!cfg.rotate_symbols;
  if ($("cfg-use-news")) $("cfg-use-news").checked = cfg.use_news_filter !== false;
  if ($("cfg-asset-class")) $("cfg-asset-class").value = cfg.asset_class || "acoes";
  updateRecommendedBanner(cfg);
  highlightActivePreset(cfg.applied_preset);
  if ($("cfg-strategy-type")) $("cfg-strategy-type").value = cfg.strategy_type || "volatility";
  syncStrategyPicker(cfg.strategy_type || "volatility");
  updateAssetClassBadge(cfg.asset_class);
  updateConfigProfileLine(cfg);
  updateConfigSummaryChips(cfg);
  syncTickerSearchDisplay(cfg);
}

function collectAgentConfigPatch() {
  const syms = [...selectedSymbols];
  if (!syms.length) throw new Error("Selecione ao menos uma ação");
  return {
    symbols: syms,
    active_symbol: $("cfg-active")?.value || syms[0],
    rotate_symbols: !!$("cfg-rotate")?.checked,
    capital_brl: parseFloat($("cfg-capital")?.value || "0"),
    risk_per_trade_pct: parseFloat($("cfg-risk")?.value || "0"),
    max_position_brl: parseFloat($("cfg-max-pos")?.value || "0"),
    shares_per_order: parseInt($("cfg-shares")?.value || "100", 10),
    stop_loss_pct: parseFloat($("cfg-sl")?.value || "0"),
    take_profit_pct: parseFloat($("cfg-tp")?.value || "0"),
    asset_class: $("cfg-asset-class")?.value || "acoes",
    strategy_type: $("cfg-strategy-type")?.value || "volatility",
    use_news_filter: !!$("cfg-use-news")?.checked,
  };
}

const CONFIG_BANNER_KEY = "sala_config_banner_dismissed";

function updateRecommendedBanner(cfg) {
  const banner = $("config-recommended-banner");
  if (!banner) return;
  const dismissed = localStorage.getItem(CONFIG_BANNER_KEY) === "1";
  const show =
    !dismissed && (cfg?.recommended_defaults_active || cfg?.applied_preset === "moderado");
  banner.classList.toggle("hidden", !show);
}

function highlightActivePreset(presetId) {
  document.querySelectorAll(".config-preset-card").forEach((el) => {
    el.classList.toggle("active", el.getAttribute("data-preset") === presetId);
  });
}

async function applyAgentPreset(name) {
  const base = apiBase();
  const res = await fetch(
    `${base}/agent/config/apply-preset?name=${encodeURIComponent(name)}`,
    { method: "POST" }
  );
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Falha ao aplicar perfil");
  }
  const saved = await res.json();
  fillAgentConfigForm(saved);
  configSavedSession = true;
  return saved;
}

async function ensureConfigSeeded() {
  if (localStorage.getItem(CONFIG_SEEDED_KEY) === "1") return false;
  try {
    await applyAgentPreset("moderado");
    localStorage.setItem(CONFIG_SEEDED_KEY, "1");
    return true;
  } catch (e) {
    console.warn("config seed:", e);
    return false;
  }
}

async function fetchTickerSuggestions(query) {
  const base = apiBase();
  try {
    const res = await fetch(`${base}/agent/tickers?q=${encodeURIComponent(query)}`, {
      cache: "no-store",
    });
    if (!res.ok) throw new Error("tickers");
    const data = await res.json();
    return data.tickers || [];
  } catch {
    const q = (query || "").trim().toUpperCase();
    const fallback = agentConfigCache.presets?.length
      ? agentConfigCache.presets
      : ["PETR4", "VALE3", "ITUB4", "BBAS3", "ABEV3", "MGLU3"];
    return fallback
      .filter((s) => !q || s.includes(q))
      .slice(0, 12)
      .map((s) => ({ symbol: s, name: s }));
  }
}

function hideTickerSuggestions() {
  const list = $("ticker-suggestions");
  const inp = $("ticker-search");
  list?.classList.add("hidden");
  inp?.setAttribute("aria-expanded", "false");
  tickerSuggestIdx = -1;
}

function renderTickerSuggestions(items) {
  const list = $("ticker-suggestions");
  const inp = $("ticker-search");
  if (!list || !inp) return;
  if (!items.length) {
    hideTickerSuggestions();
    return;
  }
  list.innerHTML = items
    .map(
      (row, i) =>
        `<li class="ticker-suggestion" role="option" data-symbol="${escHtml(row.symbol)}" id="ticker-opt-${i}" aria-selected="false">
          <span class="sym">${escHtml(row.symbol)}</span>
          <span class="name">${escHtml(row.name || "")}</span>
        </li>`
    )
    .join("");
  list.classList.remove("hidden");
  inp.setAttribute("aria-expanded", "true");
  list.querySelectorAll(".ticker-suggestion").forEach((li) => {
    li.addEventListener("mousedown", (e) => {
      e.preventDefault();
      selectTickerSymbol(li.getAttribute("data-symbol"));
    });
  });
}

function scheduleTickerSymbolSave(sym) {
  if (tickerSaveDebounce) clearTimeout(tickerSaveDebounce);
  tickerSaveDebounce = setTimeout(async () => {
    tickerSaveDebounce = null;
    const status = $("cfg-save-status");
    if (!sym) return;
    try {
      const saved = await patchAgentConfig({
        symbols: [sym],
        active_symbol: sym,
        rotate_symbols: false,
      });
      fillAgentConfigForm(saved);
      configSavedSession = true;
      if (status) status.textContent = `${sym} salvo ✓`;
      setTimeout(() => {
        if (status) status.textContent = "";
      }, 2500);
    } catch (e) {
      if (status) status.textContent = "";
      console.warn("ticker save:", e);
    }
  }, 450);
}

function selectTickerSymbol(sym) {
  const raw = (sym || "").trim().toUpperCase();
  if (!raw) return;
  selectedSymbols = new Set([raw]);
  agentConfigCache.active_symbol = raw;
  syncTickerSearchDisplay({ active_symbol: raw, symbols: [raw] });
  hideTickerSuggestions();
  renderSymbolPresets();
  refreshActiveSymbolSelect();
  scheduleTickerSymbolSave(raw);
}

function initTickerSearch() {
  const inp = $("ticker-search");
  if (!inp) return;

  inp.addEventListener("input", () => {
    if (tickerSearchDebounce) clearTimeout(tickerSearchDebounce);
    tickerSearchDebounce = setTimeout(async () => {
      tickerSearchDebounce = null;
      const items = await fetchTickerSuggestions(inp.value);
      renderTickerSuggestions(items);
    }, 180);
  });

  inp.addEventListener("focus", async () => {
    const items = await fetchTickerSuggestions(inp.value);
    renderTickerSuggestions(items);
  });

  inp.addEventListener("blur", () => {
    setTimeout(hideTickerSuggestions, 150);
  });

  inp.addEventListener("keydown", (e) => {
    const list = $("ticker-suggestions");
    const opts = list ? [...list.querySelectorAll(".ticker-suggestion")] : [];
    if (!opts.length || list?.classList.contains("hidden")) {
      if (e.key === "Enter") {
        const raw = inp.value.trim().toUpperCase();
        if (raw) {
          e.preventDefault();
          selectTickerSymbol(raw);
        }
      }
      return;
    }
    if (e.key === "ArrowDown") {
      e.preventDefault();
      tickerSuggestIdx = Math.min(tickerSuggestIdx + 1, opts.length - 1);
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      tickerSuggestIdx = Math.max(tickerSuggestIdx - 1, 0);
    } else if (e.key === "Enter" && tickerSuggestIdx >= 0) {
      e.preventDefault();
      selectTickerSymbol(opts[tickerSuggestIdx].getAttribute("data-symbol"));
      return;
    } else if (e.key === "Escape") {
      hideTickerSuggestions();
      return;
    } else {
      return;
    }
    opts.forEach((li, i) => {
      li.setAttribute("aria-selected", i === tickerSuggestIdx ? "true" : "false");
    });
  });
}

async function loadAgentPresets() {
  const wrap = $("config-preset-cards");
  if (!wrap) return;
  try {
    const base = apiBase();
    const res = await fetch(`${base}/agent/presets`, { cache: "no-store" });
    if (!res.ok) return;
    const data = await res.json();
    const presets = data.presets || [];
    wrap.innerHTML = presets
      .map(
        (p) =>
          `<button type="button" class="config-preset-card" data-preset="${escHtml(p.id)}">
            <strong>${escHtml(p.label)}</strong>
            <span class="muted">${escHtml(p.description_pt)}</span>
          </button>`
      )
      .join("");
    wrap.querySelectorAll(".config-preset-card").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const id = btn.getAttribute("data-preset");
        try {
          await applyAgentPreset(id);
          const st = $("cfg-save-status");
          if (st) st.textContent = "Perfil aplicado ✓";
        } catch (e) {
          alert(e.message);
        }
      });
    });
    highlightActivePreset(agentConfigCache.applied_preset);
  } catch (e) {
    console.warn("agent presets:", e);
  }
}

async function patchState(body) {
  const base = apiBase();
  const res = await fetch(`${base}/system/state`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error("Falha ao atualizar estado");
  return res.json();
}

async function patchAgentConfig(body) {
  const base = apiBase();
  const res = await fetch(`${base}/agent/config`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Falha ao salvar configuração");
  }
  return res.json();
}

function renderLibraryFilters(index) {
  const wrap = $("library-filters");
  if (!wrap || !index) return;
  const cats = index.categories || [];
  const buttons = [
    { id: "all", label: "Todas" },
    ...cats.map((c) => ({ id: c.id, label: c.label })),
  ];
  wrap.innerHTML = buttons
    .map(
      (b) =>
        `<button type="button" class="library-filter-btn${libraryFilterCategory === b.id ? " active" : ""}" data-cat="${escHtml(b.id)}">${escHtml(b.label)}</button>`
    )
    .join("");
  wrap.querySelectorAll(".library-filter-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      libraryFilterCategory = btn.getAttribute("data-cat") || "all";
      renderLibraryCards(libraryIndexCache);
      renderLibraryFilters(libraryIndexCache);
    });
  });
}

function renderLibraryCards(index) {
  const wrap = $("library-cards");
  if (!wrap) return;
  if (!index || !Array.isArray(index.articles) || !index.articles.length) {
    wrap.innerHTML = `<p class="muted">Biblioteca indisponível.</p>`;
    return;
  }
  const catLabels = Object.fromEntries((index.categories || []).map((c) => [c.id, c.label]));
  const list =
    libraryFilterCategory === "all"
      ? index.articles
      : index.articles.filter((a) => a.category === libraryFilterCategory);
  if (!list.length) {
    wrap.innerHTML = `<p class="muted">Nenhum artigo nesta categoria.</p>`;
    return;
  }
  wrap.innerHTML = list
    .map((a) => {
      const catKey = (a.category || "default").toLowerCase();
      const catClass = LIBRARY_CAT_CLASS[catKey] || "cat-default";
      return `<button type="button" class="library-card" data-article-id="${escHtml(a.id)}">
        <span class="library-card-cat ${catClass}">${escHtml(catLabels[a.category] || a.category)}</span>
        <h4>${escHtml(a.title)}</h4>
      </button>`;
    })
    .join("");
  wrap.querySelectorAll(".library-card").forEach((card) => {
    card.addEventListener("click", () => openLibraryArticle(card.getAttribute("data-article-id")));
  });
}

async function openLibraryArticle(articleId) {
  if (!articleId) return;
  const base = apiBase();
  const dialog = $("library-dialog");
  const titleEl = $("library-article-title");
  const bodyEl = $("library-article-body");
  if (!dialog || !bodyEl) return;
  bodyEl.innerHTML = `<p class="muted">Carregando…</p>`;
  dialog.showModal();
  try {
    const res = await fetch(`${base}/library/articles/${encodeURIComponent(articleId)}`, {
      cache: "no-store",
    });
    if (!res.ok) throw new Error("Artigo não encontrado");
    const data = await res.json();
    if (titleEl) titleEl.textContent = data.title || articleId;
    const md = data.markdown || "";
    if (typeof marked !== "undefined" && marked.parse) {
      bodyEl.innerHTML = marked.parse(md);
    } else {
      bodyEl.innerHTML = `<pre>${escHtml(md)}</pre>`;
    }
  } catch (err) {
    bodyEl.innerHTML = `<p class="muted">${escHtml(err.message)}</p>`;
  }
}

function formatLibraryWordCount(n) {
  if (n == null || Number.isNaN(n)) return "—";
  if (n >= 1_000_000) return `~${(n / 1_000_000).toFixed(1).replace(".", ",")} mi`;
  if (n >= 10_000) return `~${Math.round(n / 1000)} mil`;
  return `~${n.toLocaleString("pt-BR")}`;
}

function renderLibraryStats(stats) {
  const summaryEl = $("library-stat-summary");
  const updatedEl = $("library-stat-updated");
  if (!stats || !summaryEl) return;
  const catCount =
    stats.categories?.filter((c) => (c.count ?? 0) > 0).length ??
    stats.categories?.length ??
    0;
  summaryEl.textContent = `${stats.article_count} artigos | ${catCount} categorias | ${formatLibraryWordCount(stats.total_words)} palavras`;
  if (updatedEl) {
    updatedEl.textContent = stats.last_updated
      ? `Última atualização (catálogo): ${stats.last_updated}`
      : "";
  }
}

async function loadLibraryStats() {
  const base = apiBase();
  try {
    const res = await fetch(`${base}/library/stats`, { cache: "no-store" });
    if (!res.ok) return;
    const stats = await res.json();
    renderLibraryStats(stats);
  } catch (err) {
    console.warn("library stats:", err);
  }
}

async function loadLibraryIndex() {
  const base = apiBase();
  try {
    const res = await fetch(`${base}/library`, { cache: "no-store" });
    if (!res.ok) return;
    libraryIndexCache = await res.json();
    renderLibraryFilters(libraryIndexCache);
    renderLibraryCards(libraryIndexCache);
    const countEl = $("config-kb-count");
    const n = libraryIndexCache?.articles?.length;
    if (countEl && n != null) countEl.textContent = String(n);
  } catch (err) {
    console.warn("library:", err);
    const wrap = $("library-cards");
    if (wrap) wrap.innerHTML = `<p class="muted">Não foi possível carregar a biblioteca.</p>`;
  }
  loadLibraryStats();
}

function setLibraryBackupStatus(message, isError = false) {
  const el = $("library-backup-status");
  if (!el) return;
  el.textContent = message || "";
  el.classList.toggle("library-backup-error", isError);
}

async function downloadLibraryExport() {
  const base = apiBase();
  setLibraryBackupStatus("Preparando download…");
  try {
    const res = await fetch(`${base}/library/export`, { cache: "no-store" });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "sala_sinais_conhecimento.zip";
    a.click();
    URL.revokeObjectURL(url);
    setLibraryBackupStatus("Download iniciado. Guarde o .zip em um local seguro no PC.");
  } catch (err) {
    console.warn("library export:", err);
    setLibraryBackupStatus("Não foi possível baixar. Verifique se a API está online.", true);
  }
}

async function importLibraryArchive(file) {
  if (!file) return;
  const base = apiBase();
  const mode = $("library-import-mode")?.value || "merge";
  setLibraryBackupStatus("Enviando arquivo…");
  const form = new FormData();
  form.append("file", file);
  try {
    const res = await fetch(`${base}/library/import?mode=${encodeURIComponent(mode)}`, {
      method: "POST",
      body: form,
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      const detail = data.detail || data.message || `HTTP ${res.status}`;
      throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
    }
    setLibraryBackupStatus(data.message || "Importação concluída.");
    await loadLibraryIndex();
  } catch (err) {
    console.warn("library import:", err);
    setLibraryBackupStatus(err.message || "Falha na importação.", true);
  }
}

// --- Trades (operações fechadas) ---

function sideLabelPt(side) {
  return side === "BUY" ? "Compra" : side === "SELL" ? "Venda" : side || "—";
}

function tradeRowHtml(t) {
  const net = t.net_pnl;
  const cls = net >= 0 ? "pnl-pos" : "pnl-neg";
  const closed = t.closed_at || t.opened_at;
  return `
    <tr>
      <td>${formatDate(closed)}</td>
      <td>${escHtml(t.symbol || "—")}</td>
      <td class="${t.side === "BUY" ? "side-buy" : "side-sell"}">${sideLabelPt(t.side)}</td>
      <td class="mono-num">${t.entry}</td>
      <td class="mono-num">${t.exit}</td>
      <td class="mono-num">${t.shares}</td>
      <td class="mono-num">${formatBrlPlain(t.gross_pnl)}</td>
      <td class="mono-num">${formatBrlPlain(t.fees)}</td>
      <td class="mono-num ${cls}">${formatBrl(net)}</td>
      <td>${strategyBadgeHtml({ strategy_type: t.strategy_type })}</td>
      <td>${cellTrunc(t.exit_reason)}</td>
    </tr>
  `;
}

function renderTradesBySymbol(bySymbol) {
  const el = $("trades-by-symbol");
  if (!el) return;
  const rows = Array.isArray(bySymbol) ? bySymbol : [];
  if (!rows.length) {
    el.textContent = "—";
    return;
  }
  const maxAbs = Math.max(...rows.map((r) => Math.abs(r.net_pnl_brl || 0)), 1);
  el.innerHTML = rows
    .map((r) => {
      const pct = Math.min(100, (Math.abs(r.net_pnl_brl) / maxAbs) * 100);
      const netCls = (r.net_pnl_brl || 0) >= 0 ? "pnl-pos" : "pnl-neg";
      const wr = r.win_rate != null ? `${r.win_rate}%` : "—";
      return `<div class="trades-symbol-row">
        <span>${escHtml(r.symbol)}</span>
        <div class="trades-symbol-bar-track" title="${escHtml(formatBrlPlain(r.net_pnl_brl))}">
          <div class="trades-symbol-bar-fill" style="width:${pct}%"></div>
        </div>
        <span class="mono-num ${netCls}">${formatBrl(r.net_pnl_brl)} <span class="muted">(${wr})</span></span>
      </div>`;
    })
    .join("");
}

function renderTradesZone(data) {
  const body = $("trades-body");
  const emptyEl = $("trades-empty");
  const tableWrap = $("trades-table-wrap");
  if (!body) return;

  const trades = data?.trades || [];
  const g = data?.global_summary;

  if (g) {
    setText("trades-wl", `${g.wins} vitórias / ${g.losses} derrotas`);
    const netEl = $("trades-net-total");
    if (netEl) {
      netEl.textContent = formatBrl(g.net_pnl_brl);
      netEl.classList.remove("pnl-pos", "pnl-neg");
      netEl.classList.add(g.net_pnl_brl >= 0 ? "pnl-pos" : "pnl-neg");
    }
    const bestEl = $("trades-best");
    if (bestEl) bestEl.textContent = g.best_trade_net != null ? formatBrl(g.best_trade_net) : "—";
    const worstEl = $("trades-worst");
    if (worstEl) worstEl.textContent = g.worst_trade_net != null ? formatBrl(g.worst_trade_net) : "—";
  }

  renderTradesBySymbol(data?.by_symbol);

  if (!trades.length) {
    emptyEl?.classList.remove("hidden");
    tableWrap?.classList.add("hidden");
    body.innerHTML = "";
    return;
  }
  emptyEl?.classList.add("hidden");
  tableWrap?.classList.remove("hidden");
  body.innerHTML = trades.map(tradeRowHtml).join("");
}

function populateTradesSymbolFilter(symbols, selected) {
  const sel = $("trades-filter-symbol");
  if (!sel) return;
  const list = [...new Set((symbols || []).map((s) => String(s).toUpperCase()).filter(Boolean))].sort();
  const cur = selected || sel.value || "";
  sel.innerHTML =
    `<option value="">Todos</option>` +
    list.map((s) => `<option value="${escHtml(s)}">${escHtml(s)}</option>`).join("");
  if (cur && list.includes(cur)) sel.value = cur;
}

async function loadTradesMetrics() {
  const base = apiBase();
  const sym = $("trades-filter-symbol")?.value || "";
  const todayOnly = $("trades-today-only")?.checked;
  const params = new URLSearchParams({ limit: "200" });
  if (sym) params.set("symbol", sym);
  if (todayOnly) params.set("today_only", "true");
  try {
    const res = await fetch(`${base}/metrics/trades?${params}`, { cache: "no-store" });
    if (!res.ok) return;
    const data = await res.json();
    renderTradesZone(data);
    return data;
  } catch (err) {
    console.warn("metrics/trades:", err);
    return null;
  }
}

// --- Signals table ---

function renderSignalsTable(signals) {
  const body = $("signals-body");
  const emptyEl = $("signals-empty");
  const tableWrap = $("signals-table-wrap");
  setText("signal-count", `${signals.length} registros`);
  if (!body) return;
  if (!signals.length) {
    emptyEl?.classList.remove("hidden");
    tableWrap?.classList.add("hidden");
    body.innerHTML = "";
    return;
  }
  emptyEl?.classList.add("hidden");
  tableWrap?.classList.remove("hidden");
  body.innerHTML = signals.map(rowHtml).join("");
}

// --- Dashboard load ---

async function load() {
  const base = apiBase();
  if (!apiOnline) await pollHealth();

  let signals = [];
  dashboardFetchInFlight += 1;
  setRefreshing(true);
  renderNewsSkeleton();

  try {
    const [statsRes, signalsRes, pnlRes, equityRes, stateRes, newsRes, configRes, historyRes, alertsRes, execRes] =
      await Promise.all([
        fetch(`${base}/stats`, { cache: "no-store" }),
        fetch(`${base}/signals?limit=100`, { cache: "no-store" }),
        fetch(`${base}/metrics/pnl`, { cache: "no-store" }),
        fetch(`${base}/metrics/equity-curve`, { cache: "no-store" }),
        fetch(`${base}/system/state`, { cache: "no-store" }),
        fetch(`${base}/news/headlines?limit=8`, { cache: "no-store" }),
        fetch(`${base}/agent/config`, { cache: "no-store" }),
        fetch(`${base}/market/history?limit=100`, { cache: "no-store" }),
        fetch(`${base}/alerts/recent?limit=20`, { cache: "no-store" }),
        fetch(`${base}/system/execution-status`, { cache: "no-store" }),
      ]);

    let quoteRes = null;
    try {
      quoteRes = await fetch(`${base}/market/quote`, { cache: "no-store" });
    } catch {
      /* optional */
    }

    if (!statsRes.ok || !signalsRes.ok) throw new Error("API indisponível");

    const stats = await statsRes.json();
    signals = await signalsRes.json();
    if (!Array.isArray(signals)) signals = [];

    let pnl = null;
    if (pnlRes.ok) {
      try {
        pnl = await pnlRes.json();
      } catch (err) {
        console.warn("metrics/pnl parse:", err);
      }
    }

    let equityCurve = null;
    if (equityRes.ok) {
      try {
        equityCurve = await equityRes.json();
      } catch (err) {
        console.warn("metrics/equity-curve parse:", err);
      }
    }

    const state = stateRes.ok ? await stateRes.json() : null;
    const news = newsRes.ok ? await newsRes.json() : { items: [], error: true };
    if (configRes.ok) {
      try {
        fillAgentConfigForm(await configRes.json());
      } catch (err) {
        console.warn("agent config:", err);
      }
    }

    let historyPoints = [];
    if (historyRes.ok) {
      try {
        const hist = await historyRes.json();
        historyPoints = hist.points || [];
      } catch (err) {
        console.warn("market/history:", err);
      }
    }

    setStatText("stat-today", String(stats.today_signals ?? "—"), (t) => parseInt(t, 10));
    const monthCount = pnl?.monthly?.closed_trades ?? "—";
    setStatText(
      "stat-month",
      pnl != null ? `${stats.total_signals} total · ${monthCount} fech.` : String(stats.total_signals)
    );

    if (pnl) {
      const wr = pnl.all_time?.win_rate_pct;
      setStatText("stat-winrate", wr != null ? `${wr}%` : "—", (t) => parseFloat(t));
      setPnlEl("stat-pnl-month", pnl.monthly?.net_pnl_brl);
      setPnlEl("stat-pnl-day", pnl.daily?.net_pnl_brl);
      renderPnlZone(pnl);
    }
    if (equityCurve) {
      renderWealthZone(equityCurve);
    }

    updateSessionStrip(state, agentConfigCache);
    updateStatusDashboard(state, signals);

    if (execRes.ok) {
      try {
        updateAutoExecutionPanel(await execRes.json());
      } catch (err) {
        console.warn("execution-status:", err);
      }
    }

    if (state) {
      updateEngineUi(state);
      setEngineOfflineBanner(apiOnline && !engineIsOnline(state));
    } else {
      updateLiveChips(null);
      updateOnboarding({
        apiOk: apiOnline,
        engineOk: false,
        configOk: configSavedSession || isConfigComplete(agentConfigCache),
      });
      if (apiOnline) setEngineOfflineBanner(true);
    }

    const quoteLine = $("quote-line");
    if (quoteRes && quoteRes.ok) {
      try {
        const q = await quoteRes.json();
        if (quoteLine) {
          quoteLine.textContent = `${q.symbol}  bid ${q.bid}  ask ${q.ask}  ·  ${formatDate(q.timestamp)}`;
        }
      } catch (err) {
        console.warn("market/quote:", err);
      }
    } else if (quoteLine && signals.length) {
      const last = signals[0];
      quoteLine.textContent = `Último sinal: ${last.symbol || "—"} entrada ${last.entry}`;
    }

    if (alertsRes.ok) {
      try {
        renderAlerts(await alertsRes.json());
      } catch (err) {
        console.warn("alerts:", err);
      }
    }

    renderNews(news.items || [], news.error);

    let ohlcPayload = null;
    try {
      const sym = agentConfigCache.active_symbol || signals[0]?.symbol || "PETR4";
      ohlcPayload = await fetchOhlc(sym, activeTf);
    } catch (err) {
      console.warn("ohlc:", err);
    }
    renderCharts(signals, historyPoints, ohlcPayload);
    renderSignalsTable(signals);

    const cfgSymbols = agentConfigCache?.symbols || [];
    const tradeSyms = [...cfgSymbols];
    signals.forEach((s) => {
      if (s.symbol) tradeSyms.push(s.symbol);
    });
    populateTradesSymbolFilter(tradeSyms, $("trades-filter-symbol")?.value);
    await loadTradesMetrics();

    touchLastUpdate();
  } catch (e) {
    console.error("load dashboard:", e);
    setOfflineBanner(true);
    const body = $("signals-body");
    if (body) {
      body.innerHTML = `<tr><td colspan="13">Erro: ${e.message}</td></tr>`;
    }
    renderCharts(signals, []);
  } finally {
    dashboardFetchInFlight = Math.max(0, dashboardFetchInFlight - 1);
    if (dashboardFetchInFlight === 0) setRefreshing(false);
  }
}

const legacyControls = document.querySelector(".controls-legacy");
if (
  legacyControls &&
  (window.location.pathname === "/" || window.location.pathname.startsWith("/dashboard"))
) {
  legacyControls.style.display = "none";
}

$("trades-filter-symbol")?.addEventListener("change", () => loadTradesMetrics());
$("trades-today-only")?.addEventListener("change", () => loadTradesMetrics());

$("refresh-btn")?.addEventListener("click", load);
$("btn-export-signals")?.addEventListener("click", exportSignalsCsv);
initStrategyPicker();
initTickerSearch();

$("btn-pause")?.addEventListener("click", async () => {
  try {
    await patchState({ engine_paused: true });
    await load();
  } catch (e) {
    alert(e.message);
  }
});

$("btn-resume")?.addEventListener("click", async () => {
  try {
    await patchState({ engine_paused: false });
    await load();
  } catch (e) {
    alert(e.message);
  }
});

$("cfg-pause")?.addEventListener("click", () => $("btn-pause")?.click());
$("cfg-resume")?.addEventListener("click", () => $("btn-resume")?.click());

$("cfg-asset-class")?.addEventListener("change", (e) => {
  updateAssetClassBadge(e.target.value);
});

$("symbol-add-btn")?.addEventListener("click", () => {
  const raw = ($("symbol-custom")?.value || "").trim().toUpperCase();
  if (!raw) return;
  selectedSymbols.add(raw);
  $("symbol-custom").value = "";
  renderSymbolPresets();
  refreshActiveSymbolSelect();
});

$("cfg-apply-recommended")?.addEventListener("click", async () => {
  try {
    await applyAgentPreset("moderado");
    updateOnboarding({ apiOk: apiOnline, engineOk: false, configOk: true });
  } catch (e) {
    alert(e.message);
  }
});

$("config-banner-dismiss")?.addEventListener("click", () => {
  localStorage.setItem(CONFIG_BANNER_KEY, "1");
  $("config-recommended-banner")?.classList.add("hidden");
});

$("cfg-save")?.addEventListener("click", async () => {
  const status = $("cfg-save-status");
  try {
    const patch = collectAgentConfigPatch();
    const saved = await patchAgentConfig(patch);
    fillAgentConfigForm(saved);
    configSavedSession = true;
    updateOnboarding({
      apiOk: apiOnline,
      engineOk: false,
      configOk: true,
    });
    if (status) status.textContent = "Salvo ✓";
    setTimeout(() => {
      if (status) status.textContent = "";
    }, 3000);
  } catch (e) {
    if (status) status.textContent = "";
    alert(e.message);
  }
});

$("btn-flatten")?.addEventListener("click", async () => {
  if (
    !confirm(
      "Ativar parada de emergência? Define flag na API e o engine tentará fechar posições no MT5 se LIVE_TRADING=true."
    )
  ) {
    return;
  }
  try {
    await patchState({ emergency_flatten: true, engine_paused: true });
    await load();
  } catch (e) {
    alert(e.message);
  }
});

document.querySelectorAll(".tf-tab").forEach((btn) => {
  btn.addEventListener("click", async () => {
    document.querySelectorAll(".tf-tab").forEach((b) => b.classList.remove("active"));
    btn.classList.add("active");
    activeTf = btn.getAttribute("data-tf") || "M5";
    try {
      const sym = agentConfigCache.active_symbol || "PETR4";
      const ohlc = await fetchOhlc(sym, activeTf);
      buildCandlestickChart(ohlc);
    } catch (e) {
      console.warn(e);
      setCandleChartLoading(false);
    }
  });
});

$("library-dialog-close")?.addEventListener("click", () => $("library-dialog")?.close());
$("btn-library-export")?.addEventListener("click", () => downloadLibraryExport());
$("library-import-file")?.addEventListener("change", (ev) => {
  const input = ev.target;
  const file = input?.files?.[0];
  if (file) importLibraryArchive(file);
  if (input) input.value = "";
});
document.querySelectorAll(".theme-switch-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    applyDashboardTheme(btn.getAttribute("data-theme") || "classic");
  });
});
document.querySelectorAll(".color-mode-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    applyColorMode(btn.getAttribute("data-color-mode") || "auto");
  });
});
$("btn-auto-exec-env")?.addEventListener("click", openAutoExecEnvModal);
$("auto-exec-dialog-close")?.addEventListener("click", () => $("auto-exec-dialog")?.close());
$("btn-auto-exec-copy")?.addEventListener("click", async () => {
  const ta = $("auto-exec-env-snippet");
  if (!ta?.value) return;
  try {
    await navigator.clipboard.writeText(ta.value);
  } catch {
    ta.select();
    document.execCommand("copy");
  }
});

async function bootstrapDashboard() {
  await pollHealth();
  if (apiOnline) await ensureConfigSeeded();
  loadLibraryIndex();
  loadAgentPresets();
  await load();
}

pollHealth();
setInterval(pollHealth, 5000);
bootstrapDashboard();
setInterval(load, 20000);
