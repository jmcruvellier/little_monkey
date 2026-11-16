/*
 * Analysis cards of Little Monkey for the Home Assistant dashboards.
 *
 * Served and loaded by the little_monkey integration (see card.py), like the
 * dial card: no Lovelace resource to add. Plain web components, without
 * build step and without the internal libraries of the Home Assistant
 * frontend.
 *
 * The "analysis of your consumption" page of the ecojoko application:
 * - little-monkey-analysis-card: the consumption of a week, a month or a
 *   year by category (standby, lighting, cooling...), read with the
 *   get_consumption_analysis service.
 */

const DOMAIN = "little_monkey";
const ANALYSIS_TYPE = "little-monkey-analysis-card";
const ANALYSIS_EDITOR_TYPE = "little-monkey-analysis-card-editor";
const DOCUMENTATION =
  "https://github.com/jmcruvellier/little_monkey/blob/main/CONFIGURATION.md#cartes-de-lanalyse-de-la-consommation";

const TRANSLATIONS = {
  en: {
    analysis: {
      name: "Little Monkey consumption analysis",
      description: "Your consumption by category (standby, lighting, cooling...), as in the ecojoko application.",
      title: "Consumption analysis",
      periods: { week: "Week", month: "Month", year: "Year" },
      previous: "Previous period",
      next: "Next period",
      error: "The analysis of this period could not be read",
      missing: "Little Monkey sensor not found",
      up: "Up on the previous period",
      down: "Down on the previous period",
    },
    categories: {
      1: "Heating", 2: "Electric vehicle", 3: "Hot water", 4: "Cooking", 5: "Large appliances",
      6: "Fridges, freezers", 7: "Standby consumption", 8: "Lighting", 9: "Other appliances",
      11: "Air conditioning", 12: "Dishwasher", 13: "Washing", 14: "Drying",
    },
    editor: {
      entity: "A sensor of the Little Monkey device",
      period: "Period shown first",
      title: "Title",
    },
  },
  fr: {
    analysis: {
      name: "Petit Singe : analyse de la conso",
      description: "Votre consommation par poste (talon, éclairage, froid…), comme dans l'application ecojoko.",
      title: "Analyse de la conso",
      periods: { week: "Semaine", month: "Mois", year: "Année" },
      previous: "Période précédente",
      next: "Période suivante",
      error: "L'analyse de cette période n'a pas pu être lue",
      missing: "Capteur Little Monkey introuvable",
      up: "En hausse par rapport à la période précédente",
      down: "En baisse par rapport à la période précédente",
    },
    categories: {},
    editor: {
      entity: "Un capteur de l'appareil Little Monkey",
      period: "Période affichée d'abord",
      title: "Titre",
    },
  },
};

/** Return the language of the user, English when it is not translated. */
function language(hass) {
  const lang = (hass?.locale?.language || hass?.language || "en").split("-")[0];
  return TRANSLATIONS[lang] ? lang : "en";
}

export const PERIODS = ["week", "month", "year"];
// Icons of the categories of ecojoko, by id
const CATEGORY_ICONS = {
  1: "mdi:radiator", 2: "mdi:car-electric", 3: "mdi:water-boiler", 4: "mdi:stove",
  5: "mdi:washing-machine", 6: "mdi:fridge-outline", 7: "mdi:power-sleep", 8: "mdi:lightbulb-outline",
  9: "mdi:dots-horizontal", 11: "mdi:air-conditioner", 12: "mdi:dishwasher", 13: "mdi:washing-machine",
  14: "mdi:tumble-dryer",
};
// Trend arrows, colored as in ecojoko
export const TREND_COLORS = { up: "#f7b500", down: "#0b6aae" };
// Distance of a swipe that changes the period, in pixels
const SWIPE_DISTANCE = 40;
// Ring of the categories, in the units of the SVG
const RING = { size: 160, radius: 62, width: 18, gap: 1.2 };

/** Escape a text for the HTML of a card. */
function escapeHtml(text) {
  return String(text ?? "").replace(/[&<>"']/g, (character) => `&#${character.charCodeAt(0)};`);
}

/** Return the name of a category: translated when known, else ecojoko's. */
export function categoryName(lang, category) {
  return TRANSLATIONS[lang]?.categories?.[category?.id] || category?.name || "";
}

/** Return the icon of a category. */
export function categoryIcon(category) {
  return CATEGORY_ICONS[category?.id] || "mdi:flash";
}

/**
 * Return the color of an icon on a category color: dark on a light color
 * (lighting in yellow), white on the others.
 */
export function iconColor(color) {
  const match = String(color || "").trim().match(/^#([0-9a-f]{6})$/i);
  if (!match) {
    return "#fff";
  }
  const [r, g, b] = [0, 2, 4].map((index) => parseInt(match[1].slice(index, index + 2), 16) / 255)
    .map((c) => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4));
  const luminance = 0.2126 * r + 0.7152 * g + 0.0722 * b;
  // The better contrast of black and white (WCAG)
  return (luminance + 0.05) / 0.05 > 1.05 / (luminance + 0.05) ? "rgba(0, 0, 0, 0.75)" : "#fff";
}

/** Return a value in euros or kWh, in the format of the user. */
export function formatValue(locale, value, unit) {
  if (value === null || value === undefined) {
    return "—";
  }
  if (unit === "kwh") {
    const digits = Math.abs(value) >= 100 ? 0 : Math.abs(value) >= 10 ? 1 : 2;
    return `${new Intl.NumberFormat(locale, { maximumFractionDigits: digits }).format(value)} kWh`;
  }
  return new Intl.NumberFormat(locale, { style: "currency", currency: "EUR" }).format(value);
}

/** Return a percentage, in the format of the user. */
export function formatPercent(locale, value) {
  if (value === null || value === undefined) {
    return "";
  }
  return `${new Intl.NumberFormat(locale, { maximumFractionDigits: value < 1 ? 1 : 0 }).format(value)} %`;
}

/** Return an ISO date "YYYY-MM-DD" as a date at midnight UTC. */
function utcDate(iso) {
  return new Date(`${iso}T00:00:00Z`);
}

/** Return a date at midnight UTC as an ISO date "YYYY-MM-DD". */
function isoDate(date) {
  return date.toISOString().slice(0, 10);
}

/** Return the first day of the week (Monday), month or year of a day. */
export function periodStart(period, iso) {
  if (period === "year") {
    return `${iso.slice(0, 4)}-01-01`;
  }
  if (period === "month") {
    return `${iso.slice(0, 7)}-01`;
  }
  const date = utcDate(iso);
  date.setUTCDate(date.getUTCDate() - ((date.getUTCDay() + 6) % 7));
  return isoDate(date);
}

/** Return the first day of the period before (step -1) or after (+1). */
export function shiftPeriod(period, iso, step) {
  const date = utcDate(periodStart(period, iso));
  if (period === "year") {
    date.setUTCFullYear(date.getUTCFullYear() + step);
  } else if (period === "month") {
    date.setUTCMonth(date.getUTCMonth() + step);
  } else {
    date.setUTCDate(date.getUTCDate() + 7 * step);
  }
  return isoDate(date);
}

/** Return the name of a period: its days, its month or its year. */
export function periodLabel(locale, period, iso) {
  const start = utcDate(periodStart(period, iso));
  if (period === "year") {
    return String(start.getUTCFullYear());
  }
  if (period === "month") {
    const text = new Intl.DateTimeFormat(locale, { month: "long", year: "numeric", timeZone: "UTC" }).format(start);
    return text.charAt(0).toUpperCase() + text.slice(1);
  }
  const end = new Date(start);
  end.setUTCDate(end.getUTCDate() + 6);
  return new Intl.DateTimeFormat(locale, {
    day: "numeric", month: "short", year: "numeric", timeZone: "UTC",
  }).formatRange(start, end);
}

/** Return a point of the circle of a ring, at an angle in degrees (0 = top). */
function ringPoint(ring, angle) {
  const radians = ((angle - 90) * Math.PI) / 180;
  const center = ring.size / 2;
  return [center + ring.radius * Math.cos(radians), center + ring.radius * Math.sin(radians)];
}

/**
 * Return the arcs of the ring: one by category, proportional to its
 * consumption, from the top and clockwise, separated by a small gap.
 */
export function ringArcs(categories, ring = RING) {
  const values = (categories || []).map((category) => Math.max(Number(category.consumption) || 0, 0));
  const total = values.reduce((sum, value) => sum + value, 0);
  if (total === 0) {
    return [];
  }
  const arcs = [];
  let angle = 0;
  values.forEach((value, index) => {
    const sweep = (value / total) * 360;
    const gap = values.length > 1 ? Math.min(ring.gap, sweep / 3) : 0;
    const start = angle + gap / 2;
    const end = angle + sweep - gap / 2;
    angle += sweep;
    if (end <= start) {
      return;
    }
    // A full circle is two half circles: an arc cannot start and end at the same point
    const [x1, y1] = ringPoint(ring, start);
    const [x2, y2] = ringPoint(ring, Math.min(end, start + 359.99));
    const large = end - start > 180 ? 1 : 0;
    arcs.push({
      index,
      color: categories[index].color || "#9e9e9e",
      start,
      end,
      path: `M ${x1.toFixed(2)} ${y1.toFixed(2)} A ${ring.radius} ${ring.radius} 0 ${large} 1 ${x2.toFixed(2)} ${y2.toFixed(2)}`,
    });
  });
  return arcs;
}

/** Return the sensors of the Little Monkey device of an entity, by key. */
function deviceEntities(hass, entityId) {
  const entities = hass?.entities || {};
  const deviceId = entities[entityId]?.device_id;
  const result = {};
  if (!deviceId) {
    return result;
  }
  for (const entity of Object.values(entities)) {
    if (entity.device_id === deviceId && entity.platform === DOMAIN && entity.translation_key) {
      result[entity.translation_key] = entity.entity_id;
    }
  }
  return result;
}

/** Return the entity of the integration with a translation key, if any. */
function findEntity(hass, translationKey) {
  return Object.values(hass?.entities || {}).find(
    (entity) => entity.platform === DOMAIN && entity.translation_key === translationKey,
  )?.entity_id;
}

/** Return the config entry of the device of an entity, when there is one. */
export function configEntryId(hass, entityId) {
  const deviceId = hass?.entities?.[entityId]?.device_id;
  const entries = hass?.devices?.[deviceId]?.config_entries || [];
  return entries.length === 1 ? entries[0] : undefined;
}

/** Return the period shown first by a card: week by default. */
export function initialPeriod(config) {
  return PERIODS.includes(config?.period) ? config.period : "week";
}

/** Return the configuration of a new analysis card, on the first device. */
export function analysisStubConfig(hass) {
  const config = { type: `custom:${ANALYSIS_TYPE}` };
  const entity = findEntity(hass, "realtime_consumption");
  if (entity) {
    config.entity = entity;
  }
  return config;
}

/** Return the fields of the editor of the analysis. */
export function analysisSchema(hass) {
  const text = TRANSLATIONS[language(hass)].analysis;
  return [
    {
      name: "entity",
      required: true,
      selector: { entity: { filter: { integration: DOMAIN, domain: "sensor" } } },
    },
    {
      name: "period",
      selector: {
        select: {
          mode: "dropdown",
          options: PERIODS.map((value) => ({ value, label: text.periods[value] })),
        },
      },
    },
    { name: "title", selector: { text: {} } },
  ];
}

/** Read data with a service of the integration, for the device of an entity. */
async function callService(hass, entityId, service, data) {
  const serviceData = { ...data };
  const entry = configEntryId(hass, entityId);
  if (entry) {
    serviceData.config_entry_id = entry;
  }
  const result = await hass.callWS({
    type: "call_service",
    domain: DOMAIN,
    service,
    service_data: serviceData,
    return_response: true,
  });
  return result.response;
}

// Styles shared by the analysis cards
const STYLES = `
  ha-card { padding: 16px; }
  .header { margin-bottom: 12px; }
  .title { font-size: 1.15em; font-weight: 500; color: var(--primary-text-color); }
  .warning { color: var(--warning-color, #ffa600); }
  .periods { display: inline-flex; border: 1px solid var(--divider-color, #e0e0e0); border-radius: 18px; overflow: hidden; }
  .period { border: none; background: none; color: var(--primary-text-color); font: inherit; font-size: 0.9em; padding: 6px 12px; cursor: pointer; }
  .period.active { background: var(--primary-color, #03a9f4); color: var(--text-primary-color, #fff); }
  .nav { display: flex; align-items: center; justify-content: space-between; margin-top: 8px; }
  .nav button { border: none; background: none; color: var(--primary-text-color); cursor: pointer; padding: 4px 10px; font-size: 1.4em; line-height: 1; }
  .nav button:disabled { visibility: hidden; }
  .nav .name { font-size: 0.95em; color: var(--primary-text-color); text-align: center; }
  .message { color: var(--secondary-text-color); text-align: center; padding: 24px 8px; }
`;

class LittleMonkeyAnalysisCard extends HTMLElement {
  setConfig(config) {
    if (!config) {
      throw new Error("Invalid configuration");
    }
    this._config = { ...config };
    this._period = initialPeriod(this._config);
    // First day of the period shown; null for the last one analysed
    this._start = null;
    // Last period analysed by ecojoko, by period: the next ones do not exist
    this._latest = {};
    this._cache = new Map();
    this._pending = new Set();
    this._errors = new Set();
    this._open = new Set();
    this._built = false;
    this._signature = null;
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  getCardSize() {
    return 7;
  }

  getGridOptions() {
    // Height of the content: a fixed number of rows would cut it
    return { columns: 6, min_columns: 4 };
  }

  static getConfigElement() {
    return document.createElement(ANALYSIS_EDITOR_TYPE);
  }

  static getStubConfig(hass) {
    return analysisStubConfig(hass);
  }

  _text() {
    return TRANSLATIONS[language(this._hass)].analysis;
  }

  _locale() {
    return this._hass.locale?.language || this._hass.language;
  }

  _key(period = this._period, start = this._start) {
    return `${period}:${start || "latest"}`;
  }

  /** Show another period: the last one analysed. */
  _choose(period) {
    this._period = period;
    this._start = null;
    this._render();
  }

  /** Show the period before (-1) or after (+1). */
  _go(step) {
    const shown = this._cache.get(this._key());
    const from = this._start || shown?.start || this._latest[this._period];
    if (!from) {
      return;
    }
    const start = shiftPeriod(this._period, from, step);
    const latest = this._latest[this._period];
    if (latest && start > latest) {
      return;
    }
    this._start = latest && start === latest ? null : start;
    this._errors.delete(this._key());
    this._render();
  }

  /** Return the analysis shown, reading it when needed. */
  _analysis() {
    const key = this._key();
    if (this._errors.has(key)) {
      return { error: true };
    }
    if (!this._cache.has(key)) {
      this._fetch(this._period, this._start);
      return { loading: true };
    }
    return this._cache.get(key);
  }

  async _fetch(period, start) {
    const key = this._key(period, start);
    if (this._pending.has(key) || !this._config.entity) {
      return;
    }
    this._pending.add(key);
    const data = { period };
    if (start) {
      data.date = start;
    }
    try {
      const analysis = await callService(this._hass, this._config.entity, "get_consumption_analysis", data);
      this._cache.set(key, analysis);
      if (!start && analysis?.start) {
        this._latest[period] = analysis.start;
      }
    } catch (error) {
      console.debug("Little Monkey card: analysis not read", error);
      this._errors.add(key);
    } finally {
      this._pending.delete(key);
      this._signature = null;
      this._render();
    }
  }

  _build() {
    if (!this.shadowRoot) {
      this.attachShadow({ mode: "open" });
    }
    const text = this._text();
    const buttons = PERIODS.map((period) =>
      `<button class="period" data-period="${period}">${escapeHtml(text.periods[period])}</button>`).join("");
    this.shadowRoot.innerHTML = `
      <style>
        ${STYLES}
        .top { margin-bottom: 8px; }
        .ring { display: flex; justify-content: center; margin: 4px 0 8px; }
        .ring svg { width: 100%; max-width: 200px; display: block; touch-action: pan-y; user-select: none; }
        .ring .total { fill: var(--primary-text-color); font-size: 17px; font-weight: 600; text-anchor: middle; }
        .ring .energy { fill: var(--secondary-text-color); font-size: 11px; text-anchor: middle; }
        .ring .track { fill: none; stroke: var(--secondary-background-color, rgba(127, 127, 127, 0.15)); }
        .rows { display: flex; flex-direction: column; }
        .row { display: flex; align-items: center; gap: 10px; padding: 6px 4px; border-radius: 8px; }
        .row.child { padding-left: 32px; }
        .row.parent { cursor: pointer; }
        .icon { width: 30px; height: 30px; border-radius: 50%; display: flex; align-items: center; justify-content: center; flex: none; }
        .icon ha-icon { --mdc-icon-size: 18px; }
        .row.child .icon { width: 24px; height: 24px; }
        .row.child .icon ha-icon { --mdc-icon-size: 14px; }
        .name { flex: 1; min-width: 0; }
        .name .label { color: var(--primary-text-color); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
        .name .share { color: var(--secondary-text-color); font-size: 0.85em; }
        .values { text-align: right; white-space: nowrap; }
        .values .cost { color: var(--primary-text-color); font-weight: 500; }
        .values .energy { color: var(--secondary-text-color); font-size: 0.85em; }
        .trend { width: 16px; text-align: center; font-weight: 700; flex: none; }
        .chevron { width: 16px; color: var(--secondary-text-color); flex: none; transition: transform 0.2s; }
        .row.open .chevron { transform: rotate(90deg); }
      </style>
      <ha-card>
        <div class="header"><div class="title"></div></div>
        <div class="warning"></div>
        <div class="top"><div class="periods">${buttons}</div></div>
        <div class="body"></div>
        <div class="nav">
          <button class="previous" aria-label="${escapeHtml(text.previous)}">‹</button>
          <div class="name"></div>
          <button class="next" aria-label="${escapeHtml(text.next)}">›</button>
        </div>
      </ha-card>`;
    const root = this.shadowRoot;
    for (const button of root.querySelectorAll(".period")) {
      button.addEventListener("click", () => this._choose(button.dataset.period));
    }
    root.querySelector(".previous").addEventListener("click", () => this._go(-1));
    root.querySelector(".next").addEventListener("click", () => this._go(1));
    const body = root.querySelector(".body");
    body.addEventListener("click", (event) => this._clicked(event));
    body.addEventListener("pointerdown", (event) => {
      this._swipeStart = event.clientX;
    });
    body.addEventListener("pointerup", (event) => {
      const distance = event.clientX - (this._swipeStart ?? event.clientX);
      this._swipeStart = null;
      if (Math.abs(distance) >= SWIPE_DISTANCE) {
        this._go(distance > 0 ? -1 : 1);
      }
    });
    this._built = true;
  }

  /** Open or close the sub-categories of a category. */
  _clicked(event) {
    const row = event.target.closest?.(".row.parent");
    if (!row) {
      return;
    }
    const id = row.dataset.id;
    if (this._open.has(id)) {
      this._open.delete(id);
    } else {
      this._open.add(id);
    }
    this._signature = null;
    this._render();
  }

  _render() {
    if (!this._config || !this._hass) {
      return;
    }
    if (!this._built) {
      this._build();
    }
    const text = this._text();
    const locale = this._locale();
    const analysis = this._analysis();
    const signature = JSON.stringify([this._period, this._start, analysis, [...this._open], this._config.title, locale]);
    if (signature === this._signature) {
      return;
    }
    this._signature = signature;
    const root = this.shadowRoot;
    root.querySelector(".title").textContent = this._config.title || text.title;
    const missing = !this._config.entity || !this._hass.states[this._config.entity];
    const warning = root.querySelector(".warning");
    warning.textContent = missing ? text.missing : "";
    warning.style.display = missing ? "" : "none";
    for (const button of root.querySelectorAll(".period")) {
      button.classList.toggle("active", button.dataset.period === this._period);
    }
    const start = this._start || analysis.start || this._latest[this._period];
    root.querySelector(".name").textContent = start ? periodLabel(locale, this._period, start) : "";
    root.querySelector(".previous").disabled = !start;
    root.querySelector(".next").disabled = !this._start;
    root.querySelector(".body").innerHTML = this._body(analysis, locale, text);
  }

  /** Return the HTML of the ring and of the categories. */
  _body(analysis, locale, text) {
    if (analysis.loading) {
      return `<div class="message">…</div>`;
    }
    if (analysis.error) {
      return `<div class="message">${escapeHtml(text.error)}</div>`;
    }
    if (!analysis.available) {
      return `<div class="message">${escapeHtml(analysis.message || text.error)}</div>`;
    }
    const lang = language(this._hass);
    const categories = analysis.categories || [];
    const center = RING.size / 2;
    const arcs = ringArcs(categories).map((arc) =>
      `<path d="${arc.path}" fill="none" stroke="${escapeHtml(arc.color)}" stroke-width="${RING.width}" />`).join("");
    const ring = `
      <div class="ring"><svg viewBox="0 0 ${RING.size} ${RING.size}" role="img">
        <circle class="track" cx="${center}" cy="${center}" r="${RING.radius}" stroke-width="${RING.width}" />
        ${arcs}
        <text class="total" x="${center}" y="${center + 2}">${escapeHtml(formatValue(locale, analysis.cost, "eur"))}</text>
        <text class="energy" x="${center}" y="${center + 20}">${escapeHtml(formatValue(locale, analysis.consumption, "kwh"))}</text>
      </svg></div>`;
    const rows = categories.map((category) => {
      const children = category.children || [];
      const open = this._open.has(String(category.id));
      const trend = category.trend
        ? `<span class="trend" title="${escapeHtml(text[category.trend])}" style="color: ${TREND_COLORS[category.trend]}">${category.trend === "up" ? "↑" : "↓"}</span>`
        : `<span class="trend"></span>`;
      const chevron = children.length ? `<span class="chevron">›</span>` : `<span class="chevron"></span>`;
      const parent = this._row(category, lang, locale, children.length ? "parent" : "", open, trend + chevron);
      const details = open
        ? children.map((child) => this._row({ ...child, color: child.color || category.color }, lang, locale, "child", false, `<span class="trend"></span><span class="chevron"></span>`)).join("")
        : "";
      return parent + details;
    }).join("");
    return `${ring}<div class="rows">${rows}</div>`;
  }

  /** Return the HTML of a row of a category. */
  _row(category, lang, locale, kind, open, end) {
    return `
      <div class="row ${kind}${open ? " open" : ""}" data-id="${escapeHtml(category.id)}">
        <div class="icon" style="background: ${escapeHtml(category.color || "#9e9e9e")}; color: ${iconColor(category.color)}"><ha-icon icon="${categoryIcon(category)}"></ha-icon></div>
        <div class="name"><div class="label">${escapeHtml(categoryName(lang, category))}</div><div class="share">${escapeHtml(formatPercent(locale, category.percentage))}</div></div>
        <div class="values"><div class="cost">${escapeHtml(formatValue(locale, category.cost, "eur"))}</div><div class="energy">${escapeHtml(formatValue(locale, category.consumption, "kwh"))}</div></div>
        ${end}
      </div>`;
  }
}

/** Editor of an analysis card: a form of Home Assistant. */
class AnalysisEditor extends HTMLElement {
  setConfig(config) {
    this._config = { ...config };
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  connectedCallback() {
    this._loadForm();
  }

  /** Make sure the form and the entity pickers of Home Assistant are loaded. */
  async _loadForm() {
    if (customElements.get("ha-form") && customElements.get("ha-entity-picker")) {
      return;
    }
    try {
      // The editor of a core card loads them
      const helpers = await window.loadCardHelpers();
      const card = await helpers.createCardElement({ type: "entities", entities: [] });
      await card.constructor.getConfigElement();
    } catch (error) {
      console.debug("Little Monkey card: form of Home Assistant not loaded", error);
    }
  }

  _schema() {
    return [];
  }

  _render() {
    if (!this._config || !this._hass) {
      return;
    }
    if (!this._form) {
      this._form = document.createElement("ha-form");
      this._form.computeLabel = (field) =>
        TRANSLATIONS[language(this._hass)].editor[field.name] || field.name;
      this._form.addEventListener("value-changed", (event) => this._changed(event));
      this.appendChild(this._form);
    }
    this._form.hass = this._hass;
    this._form.data = this._config;
    this._form.schema = this._schema();
  }

  _changed(event) {
    event.stopPropagation();
    const config = { ...event.detail.value };
    for (const [key, value] of Object.entries(config)) {
      if (value === undefined || value === null || value === "") {
        delete config[key];
      }
    }
    this._config = config;
    this._render();
    this.dispatchEvent(new CustomEvent("config-changed", {
      detail: { config }, bubbles: true, composed: true,
    }));
  }
}

class LittleMonkeyAnalysisCardEditor extends AnalysisEditor {
  _schema() {
    return analysisSchema(this._hass);
  }
}

/** Define a card and its editor, and show the card in the card picker. */
function defineCard(type, card, editorType, editor, key) {
  if (!customElements.get(editorType)) {
    customElements.define(editorType, editor);
  }
  if (!customElements.get(type)) {
    customElements.define(type, card);
    const text = TRANSLATIONS[language({ language: navigator.language })][key];
    window.customCards = window.customCards || [];
    window.customCards.push({
      type,
      name: text.name,
      description: text.description,
      preview: true,
      documentationURL: DOCUMENTATION,
    });
  }
}

defineCard(
  ANALYSIS_TYPE, LittleMonkeyAnalysisCard,
  ANALYSIS_EDITOR_TYPE, LittleMonkeyAnalysisCardEditor, "analysis",
);
