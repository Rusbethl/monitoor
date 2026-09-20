"use strict";

/* ============================================================
   Config / constantes
   ============================================================ */
const REFRESH_MS = 30_000;

const CATEGORY_META = {
  bitcoin:     { label: "Bitcoin",         icon: "₿",  tag: "tag-bitcoin",     ph: "ph-bitcoin" },
  macro:       { label: "Bancos centrales",icon: "🌐", tag: "tag-macro",       ph: "ph-macro" },
  geopolitica: { label: "Geopolítica",     icon: "🌍", tag: "tag-geopolitica", ph: "ph-geopolitica" },
  petroleo:    { label: "Petróleo",        icon: "🛢️", tag: "tag-petroleo",    ph: "ph-petroleo" },
  dolar:       { label: "Dólar",           icon: "💵", tag: "tag-dolar",       ph: "ph-dolar" },
  regulacion:  { label: "Regulación",      icon: "⚖️", tag: "tag-regulacion",  ph: "ph-regulacion" },
  exchange:    { label: "Exchange",        icon: "🔁", tag: "tag-exchange",    ph: "ph-exchange" },
  general:     { label: "Noticia",         icon: "📰", tag: "tag-general",     ph: "ph-general" },
};

const HIGH_IMPACT_KW = [
  "fomc", "fed", "powell", "rate cut", "rate hike", "cpi", "etf approval",
  "sec", "ban", "hack", "liquidation", "war", "sanctions", "bankruptcy",
  "halving", "blackrock", "emergency", "opec", "opec+", "ecb", "boj",
  "dxy", "invasion", "ceasefire", "missile", "airstrike",
];
const BULLISH_KW = ["surge", "rally", "approval", "approved", "record", "bullish", "gain", "soar", "buy", "inflow"];
const BEARISH_KW = ["crash", "ban", "hack", "bearish", "drop", "plunge", "sell-off", "selloff", "lawsuit", "outflow", "liquidation"];

// Heurística simple por palabras clave — no es una clasificación confiable,
// solo una pista visual para que decidas si vale la pena leerla ahora.
const RUMOR_KW = [
  "rumor", "rumour", "reportedly", "sources say", "according to sources",
  "unconfirmed", "alleged", "allegedly", "could be", "may consider",
  "in talks", "speculat", "said to be", "considering",
];

/* ============================================================
   Helpers
   ============================================================ */
function categoryMeta(cat) {
  return CATEGORY_META[cat] || CATEGORY_META.general;
}

function impactLevel(title) {
  const t = (title || "").toLowerCase();
  return HIGH_IMPACT_KW.some((kw) => t.includes(kw)) ? "alto" : null;
}

function sentimentOf(title) {
  const t = (title || "").toLowerCase();
  const bull = BULLISH_KW.some((kw) => t.includes(kw));
  const bear = BEARISH_KW.some((kw) => t.includes(kw));
  if (bull && !bear) return "bullish";
  if (bear && !bull) return "bearish";
  return "neutral";
}

function isRumor(title) {
  const t = (title || "").toLowerCase();
  return RUMOR_KW.some((kw) => t.includes(kw));
}

function fmtRelative(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  const diffMs = Date.now() - d.getTime();
  const min = Math.round(diffMs / 60000);
  if (min < 1) return "justo ahora";
  if (min < 60) return `hace ${min} min`;
  const hr = Math.round(min / 60);
  if (hr < 24) return `hace ${hr} h`;
  const days = Math.round(hr / 24);
  return `hace ${days} d`;
}

function fmtClock(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  return d.toLocaleTimeString("es-MX", { hour: "2-digit", minute: "2-digit" });
}

function fmtUsd(n, decimals = 0) {
  if (n === null || n === undefined || isNaN(n)) return "—";
  return "$" + Number(n).toLocaleString("en-US", { minimumFractionDigits: decimals, maximumFractionDigits: decimals });
}

function escapeHtml(s) {
  const div = document.createElement("div");
  div.textContent = s || "";
  return div.innerHTML;
}

async function fetchJson(url) {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`${url} -> ${res.status}`);
  return res.json();
}

// Todas las imágenes pasan por el proxy del backend (descarga + caché en
// disco), porque muchos sitios de noticias bloquean la carga directa desde
// otro dominio y eso era lo que hacía que tardaran o nunca cargaran.
function proxiedImg(url) {
  return `/api/img?u=${encodeURIComponent(url)}`;
}

function thumbClasses(base, item) {
  return item.image_url ? base : `${base} ${categoryMeta(item.category).ph}`;
}

function thumbInner(item) {
  const meta = categoryMeta(item.category);
  if (!item.image_url) {
    return `<span class="ph-icon">${meta.icon}</span>`;
  }
  return `<img class="thumb-img" src="${proxiedImg(item.image_url)}" alt=""
            loading="lazy" decoding="async"
            data-ph="${meta.ph}" data-icon="${meta.icon}"
            onerror="handleThumbError(this)" />`;
}

// Si la imagen igual falla (fuente caída, formato no soportado, etc.), cae
// al placeholder con ícono de categoría en vez de dejar un hueco roto.
function handleThumbError(img) {
  const wrap = img.parentElement;
  if (!wrap) return;
  wrap.classList.add(img.dataset.ph);
  wrap.innerHTML = `<span class="ph-icon">${img.dataset.icon}</span>`;
}
window.handleThumbError = handleThumbError;

// El hero es distinto: la imagen no vive dentro de un wrapper propio, va
// directo sobre la tarjeta (detrás del degradado con el título). Si falla,
// la tarjeta necesita el fondo con gradiente + ícono, si no se queda en negro.
function handleHeroImgError(img) {
  const card = img.closest(".hero-card");
  img.remove();
  if (!card) return;
  card.classList.add(img.dataset.ph);
  card.insertAdjacentHTML("afterbegin", `<span class="ph-icon hero-ph-icon">${img.dataset.icon}</span>`);
}
window.handleHeroImgError = handleHeroImgError;

function tagHtml(item) {
  const meta = categoryMeta(item.category);
  return `<span class="tag ${meta.tag}">${meta.icon} ${meta.label}</span>`;
}

function impactBadgeHtml(item, pulse = false) {
  const level = impactLevel(item.title);
  if (!level) return "";
  return `<span class="badge-impact ${pulse ? "pulse" : ""}">🚨 Alto impacto</span>`;
}

function rumorBadgeHtml(item) {
  // El backend ya clasifica is_rumor al momento de guardar la noticia; si por
  // algún motivo no viene (ítems muy viejos), caemos a la heurística local.
  const rumor = item.is_rumor ?? isRumor(item.title);
  if (!rumor) return "";
  return `<span class="badge-rumor">🗣️ Posible rumor</span>`;
}

function cssVar(name) {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

function hexToRgba(hex, alpha) {
  const clean = (hex || "#3987e5").replace("#", "");
  const full = clean.length === 3 ? clean.split("").map((c) => c + c).join("") : clean;
  const n = parseInt(full, 16);
  const r = (n >> 16) & 255, g = (n >> 8) & 255, b = n & 255;
  return `rgba(${r},${g},${b},${alpha})`;
}

/* ============================================================
   Estado global
   ============================================================ */
let priceChart = null;
let rsiThresholds = { alto: 70, bajo: 30 };
let lastHistory = [];
let newsCache = [];          // snapshot estable — no se reordena solo por auto-refresh
let newsGridVisible = 9;     // paginación client-side del grid "Más noticias"
let currentNewsFilter = "all"; // "all" | "bitcoin" | "macro" | "geopolitica" | "petroleo" | "dolar" | "regulacion" | "exchange" | "rumor"
let assistantBusy = false;

/* ============================================================
   Render: ticker
   ============================================================ */
function renderTicker(snap) {
  const priceEl = document.getElementById("tk-price");
  const changeEl = document.getElementById("tk-change");
  const fundingEl = document.getElementById("tk-funding");
  const statePill = document.getElementById("tk-state");
  const stateLabel = document.getElementById("tk-state-label");

  if (!snap || !snap.price) return;

  const prevPrice = priceEl.dataset.raw ? Number(priceEl.dataset.raw) : null;
  priceEl.textContent = fmtUsd(snap.price, 2);
  priceEl.dataset.raw = snap.price;

  if (prevPrice !== null && prevPrice !== Number(snap.price)) {
    const pill = document.querySelector(".ticker-price");
    pill.classList.remove("flash");
    void pill.offsetWidth;
    pill.classList.add("flash");
    const up = Number(snap.price) > prevPrice;
    changeEl.textContent = up ? "▲" : "▼";
    changeEl.className = `ticker-change ${up ? "up" : "down"}`;
  }

  fundingEl.textContent = snap.funding_rate != null ? `${(snap.funding_rate * 100).toFixed(4)}%` : "—";

  const rsi = snap.rsi_1h;
  let stateClass = "state-neutral", label = "Neutral";
  if (rsi != null) {
    if (rsi >= rsiThresholds.alto) { stateClass = "state-sell"; label = "Sobrecompra"; }
    else if (rsi <= rsiThresholds.bajo) { stateClass = "state-buy"; label = "Sobreventa"; }
  }
  statePill.className = `ticker-pill state-pill ${stateClass}`;
  stateLabel.textContent = label;

  document.getElementById("last-update").textContent = "Actualizado " + fmtClock(new Date().toISOString());
}

/* ============================================================
   Render: mercado (stats + estado)
   ============================================================ */
function renderMarketStats(snap) {
  document.getElementById("m-price").textContent = snap && snap.price ? fmtUsd(snap.price, 2) : "—";
  document.getElementById("m-funding").textContent = snap && snap.funding_rate != null ? `${(snap.funding_rate * 100).toFixed(4)}%` : "—";

  const el = document.getElementById("m-state");
  const rsi = snap ? snap.rsi_1h : null;
  let cls = "state-neutral", label = "Neutral";
  if (rsi != null) {
    if (rsi >= rsiThresholds.alto) { cls = "state-sell"; label = `Sobrecompra (RSI ${rsi.toFixed(0)})`; }
    else if (rsi <= rsiThresholds.bajo) { cls = "state-buy"; label = `Sobreventa (RSI ${rsi.toFixed(0)})`; }
    else { label = `Neutral (RSI ${rsi.toFixed(0)})`; }
  }
  el.className = `stat-value state-badge ${cls}`;
  el.textContent = label;
}

function buildOrUpdateChart(history) {
  lastHistory = history;
  const canvas = document.getElementById("chart-price");
  if (typeof Chart === "undefined" || !canvas) return;

  const labels = history.map((h) => fmtClock(h.ts));
  const prices = history.map((h) => Number(h.price));
  const lineColor = cssVar("--cat-macro") || "#3987e5";

  if (!priceChart) {
    const ctx = canvas.getContext("2d");
    const gradient = ctx.createLinearGradient(0, 0, 0, 220);
    gradient.addColorStop(0, hexToRgba(lineColor, 0.35));
    gradient.addColorStop(1, hexToRgba(lineColor, 0));

    priceChart = new Chart(ctx, {
      type: "line",
      data: {
        labels,
        datasets: [{
          data: prices,
          borderColor: lineColor,
          backgroundColor: gradient,
          borderWidth: 2,
          fill: true,
          tension: 0.3,
          pointRadius: 0,
          pointHoverRadius: 4,
          pointHoverBackgroundColor: lineColor,
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { intersect: false, mode: "index" },
        plugins: {
          legend: { display: false },
          tooltip: {
            backgroundColor: cssVar("--surface-2") || "#212120",
            borderColor: cssVar("--border") || "rgba(255,255,255,0.1)",
            borderWidth: 1,
            titleColor: cssVar("--ink-2") || "#c3c2b7",
            bodyColor: cssVar("--ink") || "#ffffff",
            padding: 10,
            displayColors: false,
            callbacks: {
              label: (ctx) => fmtUsd(ctx.parsed.y, 2),
            },
          },
        },
        scales: {
          x: { grid: { display: false }, ticks: { color: cssVar("--ink-muted") || "#898781", maxTicksLimit: 6, font: { size: 10.5 } } },
          y: { grid: { color: cssVar("--hairline") || "#2c2c2a" }, ticks: { color: cssVar("--ink-muted") || "#898781", font: { size: 10.5 }, callback: (v) => fmtUsd(v, 0) } },
        },
      },
    });
  } else {
    priceChart.data.labels = labels;
    priceChart.data.datasets[0].data = prices;
    priceChart.update("none");
  }
}

// Chart.js no lee variables CSS en vivo — cuando cambia el tema, se destruye
// y se reconstruye con los colores nuevos usando los mismos datos.
function rebuildChartForTheme() {
  if (priceChart) {
    priceChart.destroy();
    priceChart = null;
  }
  if (lastHistory.length) buildOrUpdateChart(lastHistory);
}

/* ============================================================
   Render: noticias
   ============================================================ */
function stripCardHtml(item) {
  const high = impactLevel(item.title) ? "impact-high" : "";
  return `
    <a class="strip-card ${high}" href="${item.link}" target="_blank" rel="noopener">
      <div class="${thumbClasses("strip-thumb", item)}">
        ${thumbInner(item)}
      </div>
      <div class="strip-body">
        ${tagHtml(item)}
        <div class="strip-title">${escapeHtml(item.title)}</div>
      </div>
    </a>`;
}

function heroCardHtml(item) {
  const recent = (Date.now() - new Date(item.published_at || item.ts).getTime()) < 15 * 60 * 1000;
  const high = impactLevel(item.title);
  const meta = categoryMeta(item.category);
  const imgTag = item.image_url
    ? `<img class="hero-img" src="${proxiedImg(item.image_url)}" alt="" loading="lazy" decoding="async" data-ph="${meta.ph}" data-icon="${meta.icon}" onerror="handleHeroImgError(this)" />`
    : `<span class="ph-icon hero-ph-icon">${meta.icon}</span>`;
  return `
    <a class="hero-card ${high ? "impact-high" : ""} ${thumbClasses("", item)}" href="${item.link}" target="_blank" rel="noopener">
      ${imgTag}
      <div class="hero-overlay">
        <div class="hero-tags">
          ${tagHtml(item)}
          ${impactBadgeHtml(item, high && recent)}
          ${rumorBadgeHtml(item)}
        </div>
        <div class="hero-title">${escapeHtml(item.title)}</div>
        <div class="hero-meta">${escapeHtml(item.source || "")} · ${fmtClock(item.published_at || item.ts)} · ${fmtRelative(item.published_at || item.ts)}</div>
      </div>
    </a>`;
}

function listItemHtml(item) {
  const high = impactLevel(item.title) ? "impact-high" : "";
  return `
    <a class="list-item ${high}" href="${item.link}" target="_blank" rel="noopener">
      <div class="${thumbClasses("list-thumb", item)}">${thumbInner(item)}</div>
      <div class="list-content">
        <div style="display:flex; gap:6px; flex-wrap:wrap;">${tagHtml(item)}${impactLevel(item.title) ? impactBadgeHtml(item) : ""}</div>
        <div class="list-title">${escapeHtml(item.title)}</div>
        <div class="list-meta">${fmtRelative(item.published_at || item.ts)}</div>
      </div>
    </a>`;
}

function newsCardHtml(item) {
  const sentiment = sentimentOf(item.title);
  const sentClass = sentiment === "bullish" ? "sentiment-bullish" : sentiment === "bearish" ? "sentiment-bearish" : "";
  const high = impactLevel(item.title) ? "impact-high" : "";
  return `
    <a class="news-card ${sentClass} ${high}" href="${item.link}" target="_blank" rel="noopener">
      <div class="${thumbClasses("news-thumb", item)}">
        ${thumbInner(item)}
        <div class="news-thumb-tags">${tagHtml(item)}${impactLevel(item.title) ? impactBadgeHtml(item) : ""}${rumorBadgeHtml(item)}</div>
      </div>
      <div class="news-body">
        <div class="news-title">${escapeHtml(item.title)}</div>
        <div class="news-meta">
          <span>${escapeHtml(item.source || "")}</span>
          <span>${fmtRelative(item.published_at || item.ts)}</span>
        </div>
      </div>
    </a>`;
}

// Nota de diseño: esta función NO vuelve a pedir datos al servidor. Trabaja
// siempre sobre `newsCache` (un snapshot fijo, cargado una vez con loadNews()
// o al darle "Actualizar"), para que el feed no se reordene solo mientras lo
// estás leyendo. "Ver más noticias" solo revela más del mismo snapshot.
function renderNews(items) {
  const stripEl = document.getElementById("news-strip");
  const featuredEl = document.getElementById("featured-grid");
  const gridEl = document.getElementById("news-grid");
  const countEl = document.getElementById("news-count");
  const moreBtn = document.getElementById("btn-more-news");

  if (!items || !items.length) {
    const msg = currentNewsFilter === "all"
      ? "Sin noticias recientes todavía."
      : "No hay noticias que coincidan con este filtro por ahora.";
    stripEl.innerHTML = `<div class="empty-state">${msg}</div>`;
    featuredEl.innerHTML = "";
    gridEl.innerHTML = `<div class="empty-state">${msg}</div>`;
    moreBtn.style.display = "none";
    return;
  }

  countEl.textContent = `${items.length} noticias`;

  // Strip: las 8 más recientes
  stripEl.innerHTML = items.slice(0, 8).map(stripCardHtml).join("");

  // Destacadas: 1 hero + 4 en lista (prioriza alto impacto reciente, si no la más nueva)
  const highImpactFirst = [...items].sort((a, b) => {
    const aHigh = impactLevel(a.title) ? 1 : 0;
    const bHigh = impactLevel(b.title) ? 1 : 0;
    return bHigh - aHigh;
  });
  const hero = highImpactFirst[0];
  const listItems = items.filter((i) => i.link !== hero.link).slice(0, 4);

  featuredEl.innerHTML = `
    ${heroCardHtml(hero)}
    <div class="featured-list">${listItems.map(listItemHtml).join("")}</div>
  `;

  // Resto de noticias — paginado: solo se muestran `newsGridVisible`, con
  // botón para pedir más del mismo snapshot ya cargado (sin recargar nada).
  const usedLinks = new Set([hero.link, ...listItems.map((i) => i.link), ...items.slice(0, 8).map((i) => i.link)]);
  const rest = items.filter((i) => !usedLinks.has(i.link));
  const restOrFallback = rest.length ? rest : items.filter((i) => i.link !== hero.link);

  gridEl.innerHTML = restOrFallback.slice(0, newsGridVisible).map(newsCardHtml).join("");

  if (restOrFallback.length > newsGridVisible) {
    moreBtn.style.display = "inline-flex";
  } else {
    moreBtn.style.display = "none";
  }
}

/* ============================================================
   Filtro rápido de noticias (chips)
   ============================================================ */
function newsMatchingFilter(filter) {
  if (filter === "rumor") return newsCache.filter((i) => (i.is_rumor ?? isRumor(i.title)));
  if (filter === "all") return newsCache;
  return newsCache.filter((i) => i.category === filter);
}

// resetPagination=false se usa desde "Ver más noticias": no queremos que
// cambiar de página reinicie el conteo visible.
function applyNewsFilter({ resetPagination = true } = {}) {
  if (resetPagination) newsGridVisible = 9;
  renderNews(newsMatchingFilter(currentNewsFilter));
}

function initNewsFilters() {
  const chips = document.querySelectorAll("#news-filters .chip");
  chips.forEach((chip) => {
    chip.addEventListener("click", () => {
      currentNewsFilter = chip.dataset.filter;
      chips.forEach((c) => c.classList.toggle("active", c === chip));
      applyNewsFilter();
    });
  });
}

/* ============================================================
   Fear & Greed Index
   ============================================================ */
async function loadFearGreed() {
  const pill = document.getElementById("tk-fng");
  const valueEl = document.getElementById("tk-fng-value");
  try {
    const data = await fetchJson("/api/fng");
    valueEl.textContent = `${data.value} · ${translateFng(data.classification)}`;
    pill.classList.remove("fng-fear", "fng-greed", "fng-neutral");
    if (data.value <= 45) pill.classList.add("fng-fear");
    else if (data.value >= 56) pill.classList.add("fng-greed");
    else pill.classList.add("fng-neutral");
  } catch (e) {
    valueEl.textContent = "—";
  }
}

function translateFng(classification) {
  const map = {
    "Extreme Fear": "Miedo extremo",
    "Fear": "Miedo",
    "Neutral": "Neutral",
    "Greed": "Codicia",
    "Extreme Greed": "Codicia extrema",
  };
  return map[classification] || classification;
}

function renderRumors(items) {
  const el = document.getElementById("rumors-list");
  if (!items || !items.length) {
    el.innerHTML = `<div class="empty-state">Sin rumores detectados en las últimas 72 horas.</div>`;
    return;
  }
  el.innerHTML = items.slice(0, 20).map((r) => `
    <a class="row-item" href="${r.link}" target="_blank" rel="noopener">
      <span class="row-dot"></span>
      <div class="row-main">
        <div class="row-title">${escapeHtml(r.title)}</div>
        <div class="row-sub">${escapeHtml(r.source || "")} · ${fmtRelative(r.published_at || r.ts)}</div>
      </div>
    </a>
  `).join("");
}

/* ============================================================
   Render: actividad (alertas, whales, calendario)
   ============================================================ */
function renderAlerts(items) {
  const el = document.getElementById("alerts-list");
  if (!items || !items.length) {
    el.innerHTML = `<div class="empty-state">Sin alertas recientes.</div>`;
    return;
  }
  el.innerHTML = items.slice(0, 12).map((a) => `
    <div class="row-item">
      <span class="row-dot warn"></span>
      <div class="row-main">
        <div class="row-title">${escapeHtml(a.message)}</div>
        <div class="row-sub">${fmtRelative(a.ts)}</div>
      </div>
    </div>
  `).join("");
}

function renderWhales(items) {
  const el = document.getElementById("whales-list");
  if (!items || !items.length) {
    el.innerHTML = `<div class="empty-state">Sin movimientos grandes recientes.</div>`;
    return;
  }
  el.innerHTML = items.slice(0, 12).map((w) => {
    const isBuy = w.side === "compra";
    return `
    <div class="row-item">
      <span class="row-dot ${isBuy ? "good" : "bad"}"></span>
      <div class="row-main">
        <div class="row-title">${isBuy ? "Compra" : "Venta"} · ${Number(w.quantity).toFixed(2)} BTC</div>
        <div class="row-sub">${fmtRelative(w.ts)} · a ${fmtUsd(w.price, 0)}</div>
      </div>
      <span class="row-value ${isBuy ? "good" : "bad"}">${fmtUsd(w.quote_value_usd, 0)}</span>
    </div>`;
  }).join("");
}

function renderCalendar(items) {
  const el = document.getElementById("calendar-list");
  if (!items || !items.length) {
    el.innerHTML = `<div class="empty-state">Sin eventos próximos.</div>`;
    return;
  }
  el.innerHTML = items.slice(0, 12).map((e) => {
    const d = new Date(e.event_date);
    const dateLabel = d.toLocaleDateString("es-MX", { day: "2-digit", month: "short" });
    const isHigh = e.impact === "alto";
    return `
    <div class="row-item">
      <span class="row-dot ${isHigh ? "warn" : ""}"></span>
      <div class="row-main">
        <div class="row-title">${escapeHtml(e.title)}</div>
        <div class="row-sub">${dateLabel}${isHigh ? " · alto impacto" : ""}</div>
      </div>
    </div>`;
  }).join("");
}

/* ============================================================
   Asistente (Claude) — chat de una sola pregunta por turno
   ============================================================ */
function assistantAppend(role, text, opts = {}) {
  const log = document.getElementById("assistant-log");
  const empty = document.getElementById("assistant-empty");
  if (empty) empty.remove();

  const bubble = document.createElement("div");
  bubble.className = `assistant-msg assistant-msg-${role}${opts.error ? " assistant-msg-error" : ""}`;
  if (opts.pending) bubble.classList.add("assistant-msg-pending");
  bubble.textContent = text;
  log.appendChild(bubble);
  log.scrollTop = log.scrollHeight;
  return bubble;
}

async function assistantAsk(question) {
  if (assistantBusy) return;
  assistantBusy = true;

  const sendBtn = document.getElementById("assistant-send");
  const input = document.getElementById("assistant-input");
  sendBtn.disabled = true;
  input.disabled = true;

  assistantAppend("user", question);
  const pending = assistantAppend("assistant", "Pensando…", { pending: true });

  try {
    const res = await fetch("/api/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "No se pudo obtener respuesta.");
    pending.textContent = data.answer;
    pending.classList.remove("assistant-msg-pending");
  } catch (e) {
    pending.textContent = e.message || "No se pudo obtener respuesta del asistente.";
    pending.classList.remove("assistant-msg-pending");
    pending.classList.add("assistant-msg-error");
  } finally {
    assistantBusy = false;
    sendBtn.disabled = false;
    input.disabled = false;
    input.focus();
  }
}

function setAssistantOpen(open) {
  const panel = document.getElementById("assistant-panel");
  const fab = document.getElementById("assistant-fab");
  panel.hidden = !open;
  fab.setAttribute("aria-expanded", String(open));
  fab.classList.toggle("is-active", open);
  if (open) {
    document.getElementById("assistant-input").focus();
  }
}

function initAssistant() {
  const form = document.getElementById("assistant-form");
  const input = document.getElementById("assistant-input");
  const fab = document.getElementById("assistant-fab");
  const closeBtn = document.getElementById("assistant-close");
  const log = document.getElementById("assistant-log");

  fab.addEventListener("click", () => {
    const panel = document.getElementById("assistant-panel");
    setAssistantOpen(panel.hidden);
  });
  closeBtn.addEventListener("click", () => setAssistantOpen(false));

  // Cerrar con Escape, solo si el panel está abierto.
  document.addEventListener("keydown", (e) => {
    const panel = document.getElementById("assistant-panel");
    if (e.key === "Escape" && !panel.hidden) setAssistantOpen(false);
  });

  // Sugerencias iniciales: un clic las pregunta directo.
  log.addEventListener("click", (e) => {
    const btn = e.target.closest(".assistant-suggestion");
    if (!btn) return;
    assistantAsk(btn.dataset.q);
  });

  form.addEventListener("submit", (e) => {
    e.preventDefault();
    const question = input.value.trim();
    if (!question) return;
    input.value = "";
    assistantAsk(question);
  });
}

/* ============================================================
   Refresh orquestador
   ============================================================ */
function showSectionError(elId, msg = "No se pudo cargar esta sección.") {
  const el = document.getElementById(elId);
  if (el) el.innerHTML = `<div class="empty-state">${msg}</div>`;
}

// Ciclo automático (cada 30s): precio, alertas, whales, calendario y
// rumores. Las noticias NO van aquí a propósito — ver loadNews().
async function refresh() {
  const results = await Promise.allSettled([
    fetchJson("/api/snapshot/latest"),
    fetchJson("/api/snapshot/history?hours=24&limit=200"),
    fetchJson("/api/alerts?limit=15"),
    fetchJson("/api/whales?limit=15"),
    fetchJson("/api/calendar?upcoming_only=true&limit=20"),
    fetchJson("/api/news?is_rumor=true&hours=72&limit=25"),
  ]);

  const [snapR, histR, alertsR, whalesR, calR, rumorsR] = results;

  if (snapR.status === "fulfilled") {
    renderTicker(snapR.value);
    renderMarketStats(snapR.value);
  } else {
    showSectionError("m-price", "—");
  }

  if (histR.status === "fulfilled" && histR.value.length) {
    try { buildOrUpdateChart(histR.value); } catch (e) { console.error("chart error", e); }
  }

  if (alertsR.status === "fulfilled") renderAlerts(alertsR.value);
  else showSectionError("alerts-list");

  if (whalesR.status === "fulfilled") renderWhales(whalesR.value);
  else showSectionError("whales-list");

  if (calR.status === "fulfilled") renderCalendar(calR.value);
  else showSectionError("calendar-list");

  if (rumorsR.status === "fulfilled") renderRumors(rumorsR.value);
  else showSectionError("rumors-list");
}

// Las noticias se cargan como un snapshot estable, una sola vez (o cuando el
// usuario pide "Actualizar" explícitamente). Así la página no se reordena
// sola de fondo mientras la estás leyendo.
async function loadNews() {
  try {
    newsCache = await fetchJson("/api/news?limit=90");
    applyNewsFilter(); // respeta el chip activo, si el usuario ya había filtrado
  } catch (e) {
    console.error(e);
    showSectionError("news-grid", "No se pudieron cargar las noticias.");
  }
}

async function refreshNewsClick() {
  const btn = document.getElementById("btn-refresh-news");
  btn.classList.add("spinning");
  try {
    await loadNews();
  } finally {
    setTimeout(() => btn.classList.remove("spinning"), 400);
  }
}

/* ============================================================
   Tema (oscuro / claro / azul noche / ámbar terminal)
   ============================================================ */
const THEME_KEY = "btcmonitor-theme";

function applyTheme(theme) {
  document.documentElement.setAttribute("data-theme", theme);
  try { localStorage.setItem(THEME_KEY, theme); } catch (e) { /* modo privado: ignorar */ }
  rebuildChartForTheme();
}

function initTheme() {
  let saved = "dark";
  try { saved = localStorage.getItem(THEME_KEY) || "dark"; } catch (e) { /* ignorar */ }
  document.documentElement.setAttribute("data-theme", saved);
  const select = document.getElementById("theme-select");
  select.value = saved;
  select.addEventListener("change", () => applyTheme(select.value));
}

/* ============================================================
   Init
   ============================================================ */
async function init() {
  initTheme();

  try {
    const health = await fetchJson("/api/health");
    rsiThresholds = { alto: health.rsi_sobrecompra ?? 70, bajo: health.rsi_sobreventa ?? 30 };
  } catch (e) {
    console.warn("No se pudo leer /api/health, uso umbrales por defecto.", e);
  }

  document.getElementById("btn-refresh-news").addEventListener("click", refreshNewsClick);
  document.getElementById("btn-more-news").addEventListener("click", () => {
    newsGridVisible += 9;
    applyNewsFilter({ resetPagination: false });
  });
  initNewsFilters();
  initAssistant();

  await Promise.all([refresh(), loadNews(), loadFearGreed()]);
  setInterval(refresh, REFRESH_MS);
  // El índice Fear & Greed se actualiza ~1 vez al día — no tiene sentido
  // pedirlo cada 30s como el resto. Cada 10 min es más que suficiente.
  setInterval(loadFearGreed, 10 * 60 * 1000);
}

window.refresh = refresh; // útil para depurar desde la consola
init();
