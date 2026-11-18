/*
 * Measures card of Little Monkey for the Home Assistant dashboards.
 *
 * Served and loaded by the little_monkey integration (see card.py), like the
 * dial card: no Lovelace resource to add. Plain web component, without
 * build step and without the internal libraries of the Home Assistant
 * frontend.
 *
 * little-monkey-measures-card: the page « Mesures » of ecojoko, read with
 * the get_measures service. The electricity of a day is its power curve,
 * coloured by tariff band over the base load; of a week, 30 days or a year,
 * its days or months in bars stacked by band, in kWh or in euros, with the
 * production injected under the axis.
 */

const DOMAIN = "little_monkey";
const MEASURES_TYPE = "little-monkey-measures-card";
const MEASURES_EDITOR_TYPE = "little-monkey-measures-card-editor";
const DOCUMENTATION =
  "https://github.com/jmcruvellier/little_monkey/blob/main/CONFIGURATION.md#carte-des-mesures";
// The measures of the current period are read again every five minutes
const MEASURES_REFRESH = 300000;

const TRANSLATIONS = {
  en: {
    name: "Little Monkey measures",
    description: "The measures of ecojoko: power of the day and energy by tariff band, in kWh or euros.",
    title: "Measures",
    measures: { electricity: "Electricity" },
    periods: { day: "Day", week: "Week", month: "Month", year: "Year" },
    previous: "Previous period",
    next: "Next period",
    base: "Base load",
    production: "Production",
    power_at: "{time}: {power}",
    error: "Measures not read",
    empty: "No measure for this period",
    missing: "Little Monkey sensor not found",
    editor: {
      entity: "A sensor of the Little Monkey device",
      period: "Period shown first",
      unit: "Unit of the bars",
      units: { kwh: "kWh", eur: "Euros" },
      title: "Title",
    },
  },
  fr: {
    name: "Petit Singe : mesures",
    description: "Les mesures d'ecojoko : la puissance du jour et l'énergie par tranche tarifaire, en kWh ou en euros.",
    title: "Mesures",
    measures: { electricity: "Électricité" },
    periods: { day: "Jour", week: "Semaine", month: "Mois", year: "Année" },
    previous: "Période précédente",
    next: "Période suivante",
    base: "Talon",
    production: "Production",
    power_at: "{time} : {power}",
    error: "Mesures non lues",
    empty: "Aucune mesure sur cette période",
    missing: "Capteur Little Monkey introuvable",
    editor: {
      entity: "Un capteur de l'appareil Little Monkey",
      period: "Période affichée d'abord",
      unit: "Unité des barres",
      units: { kwh: "kWh", eur: "Euros" },
      title: "Titre",
    },
  },
};

/** Return the language of the user, English when it is not translated. */
function language(hass) {
  const lang = (hass?.locale?.language || hass?.language || "en").split("-")[0];
  return TRANSLATIONS[lang] ? lang : "en";
}

function escapeHtml(text) {
  return String(text ?? "").replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
}

export const PERIODS = ["day", "week", "month", "year"];
// Colors of ecojoko: base load, production, and a band without its color
export const MEASURE_COLORS = { base: "#022469", production: "#ffcc47", band: "#7ed2df" };
// Chart, in the units of the SVG
export const CHART = { width: 280, height: 160, left: 40, right: 4, top: 8, bottom: 20 };
const SWIPE_DISTANCE = 40;
const MINUTES_A_DAY = 1440;

/** Return the period shown first by a card: the day by default. */
export function initialPeriod(config) {
  return PERIODS.includes(config?.period) ? config.period : "day";
}

/** Return the unit of the bars: kWh by default, or euros. */
export function barUnit(config) {
  return config?.unit === "eur" ? "eur" : "kwh";
}

/** Return today as an ISO date, in the time zone of the browser. */
export function today(now = new Date()) {
  const pad = (value) => String(value).padStart(2, "0");
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
}

function utcDate(iso) {
  return new Date(`${String(iso).slice(0, 10)}T00:00:00Z`);
}

/** Return the minutes since midnight of an ISO time, as written. */
export function minutesOf(iso) {
  const match = String(iso ?? "").match(/T(\d{2}):(\d{2})(?::(\d{2}))?/);
  return match ? Number(match[1]) * 60 + Number(match[2]) + Number(match[3] || 0) / 60 : null;
}

/** Return a round step above a value: 1, 2, 2.5 or 5 times a power of ten. */
function niceStep(value) {
  const power = 10 ** Math.floor(Math.log10(value));
  const factor = [1, 2, 2.5, 5, 10].find((candidate) => candidate * power >= value * (1 - 1e-9));
  return factor * power;
}

/** Return the scale of a chart: zero shown, at most four graduations on the longest side. */
export function chartScale(top, bottom = 0) {
  const high = Math.max(0, top);
  const low = Math.min(0, bottom);
  const longest = Math.max(high, -low);
  if (!(longest > 0)) {
    return { min: 0, max: 1, step: 0.5 };
  }
  const step = niceStep(longest / 4);
  return {
    min: -Math.ceil(-low / step - 1e-9) * step || 0,
    max: Math.ceil(high / step - 1e-9) * step || step,
    step,
  };
}

/** Return the y of a value on a scale, and the graduations of the scale. */
function axis(scale, box) {
  const plot = box.height - box.top - box.bottom;
  const y = (value) => box.top + ((scale.max - value) / (scale.max - scale.min)) * plot;
  const ticks = [];
  for (let value = scale.min; value <= scale.max + scale.step / 1000; value += scale.step) {
    ticks.push({ value: Math.round(value * 1000) / 1000 || 0, y: y(value) });
  }
  return { y, ticks };
}

/** Return the color of each tariff band, by id. */
export function bandColors(bands) {
  const colors = {};
  for (const band of bands || []) {
    colors[band.id] = /^#[0-9a-f]{3,8}$/i.test(band.color || "") ? band.color : MEASURE_COLORS.band;
  }
  return colors;
}

/**
 * Return the bars of a week, 30 days or a year stacked by tariff band, in
 * kWh or euros, with the production under the axis.
 */
export function stackedBars(measures, unit, box = CHART) {
  const bars = measures?.bars || [];
  const colors = bandColors(measures?.bands);
  const key = unit === "eur" ? "cost" : "energy";
  const order = (measures?.bands || []).map((band) => band.id);
  const totals = bars.map((bar) => {
    const bands = bar.bands || [];
    // A bar without bands (a contract without them) is one block
    return bands.length ? bands.reduce((sum, band) => sum + (Number(band[key]) || 0), 0) : Number(bar[key]) || 0;
  });
  const productions = unit === "eur" ? bars.map(() => 0) : bars.map((bar) => Number(bar.production) || 0);
  const scale = chartScale(Math.max(0, ...totals), -Math.max(0, ...productions));
  const { y, ticks } = axis(scale, box);
  const slot = (box.width - box.left - box.right) / Math.max(bars.length, 1);
  const width = Math.min(slot * 0.62, 36);
  const zero = y(0);
  const rects = bars.map((bar, index) => {
    const x = box.left + slot * index + (slot - width) / 2;
    const bands = [...(bar.bands || [])].sort((a, b) => order.indexOf(a.id) - order.indexOf(b.id));
    const parts = bands.length ? bands : (totals[index] ? [{ id: null, [key]: totals[index] }] : []);
    let top = 0;
    const blocks = parts.map((band) => {
      const value = Number(band[key]) || 0;
      const block = {
        id: band.id, value, x, width, y: y(top + value), height: Math.max(zero - y(value), 0),
        color: colors[band.id] || MEASURE_COLORS.band,
      };
      top += value;
      return block;
    }).filter((block) => block.height > 0);
    const production = productions[index] ? {
      x, width, y: zero, height: y(-productions[index]) - zero, color: MEASURE_COLORS.production,
    } : null;
    return { index, x, width, center: x + width / 2, slot, total: totals[index], blocks, production };
  });
  return { rects, ticks, zero, scale };
}

/**
 * Return the areas of the power of a day: the base load, and the power
 * above it coloured by the band of its time, as runs of the same band.
 */
export function dayAreas(measures, box = CHART) {
  const points = (measures?.points || [])
    .map((point) => ({ ...point, minutes: minutesOf(point.time) }))
    .filter((point) => point.minutes !== null && Number.isFinite(Number(point.power)));
  const colors = bandColors(measures?.bands);
  const powers = points.map((point) => Number(point.power));
  const scale = chartScale(Math.max(0, ...powers), Math.min(0, ...powers));
  const { y, ticks } = axis(scale, box);
  const plot = box.width - box.left - box.right;
  const x = (minutes) => box.left + (minutes / MINUTES_A_DAY) * plot;
  const zero = y(0);
  const runs = [];
  points.forEach((point, index) => {
    const last = runs[runs.length - 1];
    if (last && last.band === point.band) {
      last.points.push(point);
    } else {
      // Each run starts where the previous one ends, without a gap
      runs.push({ band: point.band, points: index ? [points[index - 1], point] : [point] });
    }
  });
  const area = (list, value) => {
    const top = list.map((point) => `${x(point.minutes).toFixed(1)},${y(Math.max(value(point), 0)).toFixed(1)}`);
    return `M${x(list[0].minutes).toFixed(1)},${zero.toFixed(1)} L${top.join(" L")} L${x(list[list.length - 1].minutes).toFixed(1)},${zero.toFixed(1)} Z`;
  };
  const bands = runs.map((run) => ({
    band: run.band, color: colors[run.band] || MEASURE_COLORS.band, path: area(run.points, (point) => Number(point.power)),
  }));
  const base = points.length && points.some((point) => Number(point.base) > 0)
    ? area(points, (point) => Math.min(Number(point.base) || 0, Number(point.power))) : "";
  // Power injected into the grid, under the axis
  const injected = points.some((point) => Number(point.power) < 0)
    ? `M${x(points[0].minutes).toFixed(1)},${zero.toFixed(1)} L${points.map((point) =>
      `${x(point.minutes).toFixed(1)},${y(Math.min(Number(point.power), 0)).toFixed(1)}`).join(" L")} L${
      x(points[points.length - 1].minutes).toFixed(1)},${zero.toFixed(1)} Z` : "";
  return { bands, base, injected, ticks, zero, scale, x, points };
}

/** Return the name of a period: its day, its days or its year. */
export function periodLabel(locale, period, start) {
  if (!start) {
    return "";
  }
  const date = utcDate(start);
  if (period === "year") {
    return String(date.getUTCFullYear());
  }
  if (period === "day") {
    const text = new Intl.DateTimeFormat(locale, {
      weekday: "long", day: "numeric", month: "long", year: "numeric", timeZone: "UTC",
    }).format(date);
    return text.charAt(0).toUpperCase() + text.slice(1);
  }
  const end = new Date(date);
  end.setUTCDate(end.getUTCDate() + (period === "week" ? 6 : 29));
  return new Intl.DateTimeFormat(locale, {
    day: "numeric", month: "short", year: "numeric", timeZone: "UTC",
  }).formatRange(date, end);
}

/** Return the label of a bar: a day of the week, a day of the month, a month. */
export function barLabel(locale, period, iso, index) {
  if (!iso) {
    return "";
  }
  const date = utcDate(iso);
  if (period === "year") {
    return new Intl.DateTimeFormat(locale, { month: "narrow", timeZone: "UTC" }).format(date);
  }
  if (period === "month") {
    // One day out of five: thirty days do not fit
    return index % 5 === 0 ? String(date.getUTCDate()) : "";
  }
  return new Intl.DateTimeFormat(locale, { weekday: "narrow", timeZone: "UTC" }).format(date);
}

/** Return the long label of a bar, for its details. */
export function barTitle(locale, period, iso) {
  if (!iso) {
    return "";
  }
  const options = period === "year"
    ? { month: "long", year: "numeric", timeZone: "UTC" }
    : { weekday: "long", day: "numeric", month: "long", timeZone: "UTC" };
  const text = new Intl.DateTimeFormat(locale, options).format(utcDate(iso));
  return text.charAt(0).toUpperCase() + text.slice(1);
}

/** Return an energy, a cost or a power, in the language of the user. */
export function formatValue(locale, value, unit) {
  if (value === null || value === undefined || !Number.isFinite(Number(value))) {
    return "—";
  }
  const number = Number(value);
  if (unit === "eur") {
    return new Intl.NumberFormat(locale, { style: "currency", currency: "EUR" }).format(number);
  }
  const digits = unit === "w" || number >= 100 ? 0 : 2;
  const text = new Intl.NumberFormat(locale, { maximumFractionDigits: digits }).format(number);
  return `${text} ${unit === "w" ? "W" : "kWh"}`;
}

/** Return the totals of each tariff band over the bars of a period. */
export function bandTotals(measures) {
  const totals = {};
  for (const bar of measures?.bars || []) {
    for (const band of bar.bands || []) {
      const total = totals[band.id] || { energy: 0, cost: 0 };
      total.energy += Number(band.energy) || 0;
      total.cost += Number(band.cost) || 0;
      totals[band.id] = total;
    }
  }
  return totals;
}

/** Return the entity of the integration with a translation key, if any. */
function findEntity(hass, translationKey) {
  return Object.values(hass?.entities || {}).find(
    (entity) => entity.platform === DOMAIN && entity.translation_key === translationKey,
  )?.entity_id;
}

/** Return the config entry of the device of an entity, if there is one. */
export function configEntryId(hass, entityId) {
  const deviceId = hass?.entities?.[entityId]?.device_id;
  const entries = hass?.devices?.[deviceId]?.config_entries || [];
  return entries.length === 1 ? entries[0] : undefined;
}

/** Return the configuration of a new measures card, on the first device. */
export function measuresStubConfig(hass) {
  const config = { type: `custom:${MEASURES_TYPE}` };
  const entity = findEntity(hass, "realtime_consumption");
  if (entity) {
    config.entity = entity;
  }
  return config;
}

/** Return the fields of the editor. */
export function measuresSchema(hass) {
  const text = TRANSLATIONS[language(hass)];
  return [
    {
      name: "entity",
      required: true,
      selector: { entity: { filter: { integration: DOMAIN, domain: "sensor" } } },
    },
    {
      name: "period",
      selector: { select: { mode: "dropdown", options: PERIODS.map((value) => ({ value, label: text.periods[value] })) } },
    },
    {
      name: "unit",
      selector: { select: { mode: "dropdown", options: ["kwh", "eur"].map((value) => ({ value, label: text.editor.units[value] })) } },
    },
    { name: "title", selector: { text: {} } },
  ];
}

const STYLES = `
  ha-card { padding: 16px; }
  .title { font-size: 1.15em; font-weight: 500; color: var(--primary-text-color); margin-bottom: 8px; }
  .warning { color: var(--warning-color, #ffa600); }
  .tabs { display: flex; gap: 4px; margin-bottom: 8px; }
  .tab { border: none; background: none; color: var(--secondary-text-color); font: inherit; font-size: 0.9em; padding: 4px 8px; cursor: pointer;
    border-bottom: 2px solid transparent; }
  .tab.active { color: var(--primary-text-color); border-bottom-color: var(--primary-color, #03a9f4); }
  .top { display: flex; align-items: center; justify-content: space-between; gap: 8px; flex-wrap: wrap; margin-bottom: 8px; }
  .periods { display: inline-flex; border: 1px solid var(--divider-color, #e0e0e0); border-radius: 18px; overflow: hidden; }
  .period { border: none; background: none; color: var(--primary-text-color); font: inherit; font-size: 0.9em; padding: 6px 10px; cursor: pointer; }
  .period.active { background: var(--primary-color, #03a9f4); color: var(--text-primary-color, #fff); }
  .total { font-size: 0.95em; white-space: nowrap; }
  .total .main { font-weight: 600; color: var(--primary-text-color); }
  .total .other { color: var(--secondary-text-color); }
  .details { min-height: 1.4em; font-size: 0.85em; color: var(--secondary-text-color); text-align: center; }
  svg { width: 100%; display: block; touch-action: pan-y; user-select: none; }
  .tick { fill: var(--secondary-text-color, #727272); font-size: 9.5px; text-anchor: end; dominant-baseline: central; }
  .grid { stroke: var(--divider-color, #e0e0e0); stroke-width: 0.5; }
  .zero { stroke: var(--secondary-text-color, #727272); stroke-width: 0.6; }
  .label { fill: var(--secondary-text-color, #727272); font-size: 9.5px; text-anchor: middle; }
  .bar { cursor: pointer; }
  .bar rect.hit { fill: transparent; }
  .bar.selected .block { stroke: var(--primary-text-color); stroke-width: 0.8; }
  .cursor { stroke: var(--primary-text-color); stroke-width: 0.8; stroke-dasharray: 2 2; }
  .message { fill: var(--secondary-text-color, #727272); font-size: 10px; text-anchor: middle; }
  .legend { display: flex; flex-wrap: wrap; justify-content: center; gap: 2px 12px; font-size: 0.8em; color: var(--secondary-text-color); margin-top: 4px; }
  .legend .swatch { display: inline-block; width: 10px; height: 10px; border-radius: 2px; margin-right: 4px; vertical-align: -1px; }
  .legend .value { color: var(--primary-text-color); }
  .nav { display: flex; align-items: center; justify-content: space-between; margin-top: 4px; }
  .nav button { border: none; background: none; color: var(--primary-text-color); cursor: pointer; padding: 4px 10px; font-size: 1.4em; line-height: 1; }
  .nav button:disabled { visibility: hidden; }
  .nav .name { font-size: 0.95em; color: var(--primary-text-color); text-align: center; }
`;

class LittleMonkeyMeasuresCard extends HTMLElement {
  setConfig(config) {
    if (!config) {
      throw new Error("Invalid configuration");
    }
    const entity = this._config?.entity;
    this._config = { ...config };
    if (!this._cache || entity !== this._config.entity) {
      this._cache = new Map();
      this._period = initialPeriod(this._config);
      this._measure = "electricity";
      // Day of the period shown, by period: today until the user moves
      this._dates = {};
      this._selected = null;
    }
    this._built = false;
    this._render();
  }

  set hass(hass) {
    const first = !this._hass;
    this._hass = hass;
    if (first) {
      this._fetch();
    }
    this._render();
  }

  connectedCallback() {
    clearInterval(this._timer);
    this._timer = setInterval(() => this._refresh(), MEASURES_REFRESH);
  }

  disconnectedCallback() {
    clearInterval(this._timer);
  }

  getCardSize() {
    // Masonry view: rows of 50 pixels, for the chart and its legend
    return 6;
  }

  getGridOptions() {
    // The whole width of a section by default, half of it at least
    return { columns: 12, min_columns: 6 };
  }

  static getConfigElement() {
    return document.createElement(MEASURES_EDITOR_TYPE);
  }

  static getStubConfig(hass) {
    return measuresStubConfig(hass);
  }

  _text() {
    return TRANSLATIONS[language(this._hass)];
  }

  _locale() {
    return this._hass.locale?.language || this._hass.language;
  }

  _date() {
    return this._dates[this._period] || today();
  }

  _key() {
    return `${this._measure}:${this._period}:${this._date()}`;
  }

  /** Read the measures of the period shown, unless they are read. */
  async _fetch(force = false) {
    const key = this._key();
    const cached = this._cache.get(key);
    if (!this._hass || !this._config?.entity || (cached && !force) || cached?.loading) {
      return;
    }
    this._cache.set(key, { ...cached, loading: true });
    const data = { measure: this._measure, period: this._period, date: this._date() };
    const entry = configEntryId(this._hass, this._config.entity);
    if (entry) {
      data.config_entry_id = entry;
    }
    try {
      const result = await this._hass.callWS({
        type: "call_service", domain: DOMAIN, service: "get_measures", service_data: data, return_response: true,
      });
      this._cache.set(key, { measures: result.response });
    } catch (error) {
      console.debug("Little Monkey card: measures not read", error);
      this._cache.set(key, cached?.measures ? cached : { error: true });
    }
    this._signature = null;
    this._render();
  }

  /** Read the current period again: its measures go on. */
  _refresh() {
    if (!this._dates[this._period]) {
      this._fetch(true);
    }
  }

  _choose(period) {
    if (period !== this._period) {
      this._period = period;
      this._selected = null;
      this._fetch();
      this._signature = null;
      this._render();
    }
  }

  /** Show the period before (-1) or after (+1), as ecojoko gives them. */
  _go(step) {
    const measures = this._cache.get(this._key())?.measures;
    const start = step < 0 ? measures?.previous : measures?.next;
    if (!start) {
      return;
    }
    // ecojoko gives the start of a period; its month ends on the date asked
    let date = start.slice(0, 10);
    if (this._period === "month") {
      const end = utcDate(date);
      end.setUTCDate(end.getUTCDate() + 29);
      date = end.toISOString().slice(0, 10);
    }
    this._dates[this._period] = date >= today() ? undefined : date;
    this._selected = null;
    this._fetch();
    this._signature = null;
    this._render();
  }

  _build() {
    if (!this.shadowRoot) {
      this.attachShadow({ mode: "open" });
    }
    const text = this._text();
    const periods = PERIODS.map((period) =>
      `<button class="period" data-period="${period}">${escapeHtml(text.periods[period])}</button>`).join("");
    this.shadowRoot.innerHTML = `
      <style>${STYLES}</style>
      <ha-card>
        <div class="title"></div>
        <div class="warning"></div>
        <div class="top"><div class="periods">${periods}</div><div class="total"></div></div>
        <div class="details"></div>
        <svg viewBox="0 0 ${CHART.width} ${CHART.height}" role="img"></svg>
        <div class="legend"></div>
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
    const svg = root.querySelector("svg");
    svg.addEventListener("click", (event) => this._select(event, svg));
    svg.addEventListener("pointerdown", (event) => {
      this._swipeStart = event.clientX;
    });
    svg.addEventListener("pointerup", (event) => {
      const distance = event.clientX - (this._swipeStart ?? event.clientX);
      this._swipeStart = null;
      if (Math.abs(distance) >= SWIPE_DISTANCE) {
        this._swiped = true;
        this._go(distance > 0 ? -1 : 1);
      }
    });
    this._built = true;
  }

  /** Select a bar, or a time of the day. */
  _select(event, svg) {
    if (this._swiped) {
      this._swiped = false;
      return;
    }
    const bar = event.target.closest?.(".bar");
    if (bar) {
      const index = Number(bar.dataset.index);
      this._selected = this._selected === index ? null : index;
    } else if (this._period === "day") {
      const box = svg.getBoundingClientRect();
      const x = ((event.clientX - box.left) / box.width) * CHART.width;
      const minutes = ((x - CHART.left) / (CHART.width - CHART.left - CHART.right)) * MINUTES_A_DAY;
      this._selected = minutes >= 0 && minutes <= MINUTES_A_DAY ? minutes : null;
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
    const unit = barUnit(this._config);
    const shown = this._cache.get(this._key()) || {};
    const signature = JSON.stringify([
      this._measure, this._period, this._date(), shown, this._selected, unit, this._config.title, locale]);
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
    const measures = shown.measures;
    root.querySelector(".name").textContent = periodLabel(locale, this._period, measures?.start || this._date());
    root.querySelector(".previous").disabled = !measures?.previous;
    root.querySelector(".next").disabled = !this._dates[this._period];
    const total = root.querySelector(".total");
    total.innerHTML = measures
      ? `<span class="main">${escapeHtml(formatValue(locale, measures.energy, "kwh"))}</span> <span class="other">| ${
        escapeHtml(formatValue(locale, measures.cost, "eur"))}</span>`
      : "";
    const svg = root.querySelector("svg");
    const details = root.querySelector(".details");
    const legend = root.querySelector(".legend");
    if (!measures) {
      svg.innerHTML = `<text class="message" x="${CHART.width / 2}" y="${CHART.height / 2}">${
        escapeHtml(shown.error ? text.error : "…")}</text>`;
      details.textContent = "";
      legend.innerHTML = "";
      return;
    }
    if (this._period === "day") {
      this._renderDay(measures, svg, details, legend, text, locale);
    } else {
      this._renderBars(measures, unit, svg, details, legend, text, locale);
    }
  }

  /** Return the SVG of the graduations of a scale, with their unit. */
  _grid(ticks, suffix, locale) {
    const format = new Intl.NumberFormat(locale, { maximumFractionDigits: 2, notation: "compact" });
    return ticks.map((tick) => `
      <line class="grid" x1="${CHART.left}" x2="${CHART.width - CHART.right}" y1="${tick.y}" y2="${tick.y}" />
      <text class="tick" x="${CHART.left - 4}" y="${tick.y}">${escapeHtml(format.format(tick.value) + suffix)}</text>`).join("");
  }

  /** Draw the power of a day. */
  _renderDay(measures, svg, details, legend, text, locale) {
    const areas = dayAreas(measures);
    if (!areas.points.length) {
      svg.innerHTML = `<text class="message" x="${CHART.width / 2}" y="${CHART.height / 2}">${escapeHtml(text.empty)}</text>`;
      details.textContent = "";
      legend.innerHTML = "";
      return;
    }
    // The first and last hours inside the chart
    const anchors = { 0: "start", 24: "end" };
    const hours = [0, 6, 12, 18, 24].map((hour) =>
      `<text class="label" x="${areas.x(hour * 60).toFixed(1)}" y="${CHART.height - 4}"${
        anchors[hour] ? ` style="text-anchor: ${anchors[hour]}"` : ""}>${hour}h</text>`).join("");
    let cursor = "";
    details.textContent = "";
    if (this._selected !== null) {
      const point = areas.points.reduce((best, item) =>
        Math.abs(item.minutes - this._selected) < Math.abs(best.minutes - this._selected) ? item : best);
      const time = String(point.time).slice(11, 16);
      details.textContent = text.power_at.replace("{time}", time).replace("{power}", formatValue(locale, point.power, "w"));
      cursor = `<line class="cursor" x1="${areas.x(point.minutes)}" x2="${areas.x(point.minutes)}" y1="${CHART.top}" y2="${CHART.height - CHART.bottom}" />`;
    }
    svg.innerHTML = `${this._grid(areas.ticks, " W", locale)}
      ${areas.bands.map((band) => `<path d="${band.path}" fill="${band.color}" />`).join("")}
      ${areas.base ? `<path d="${areas.base}" fill="${MEASURE_COLORS.base}" />` : ""}
      ${areas.injected ? `<path d="${areas.injected}" fill="${MEASURE_COLORS.production}" />` : ""}
      <line class="zero" x1="${CHART.left}" x2="${CHART.width - CHART.right}" y1="${areas.zero}" y2="${areas.zero}" />
      ${cursor}${hours}`;
    const used = new Set(areas.bands.map((band) => band.band));
    const items = (measures.bands || []).filter((band) => used.has(band.id)).map((band) =>
      `<span><span class="swatch" style="background: ${bandColors([band])[band.id]}"></span>${escapeHtml(band.label)}</span>`);
    if (areas.base) {
      items.push(`<span><span class="swatch" style="background: ${MEASURE_COLORS.base}"></span>${escapeHtml(text.base)}</span>`);
    }
    if (areas.injected) {
      items.push(`<span><span class="swatch" style="background: ${MEASURE_COLORS.production}"></span>${escapeHtml(text.production)}</span>`);
    }
    legend.innerHTML = items.join("");
  }

  /** Draw the bars of a week, 30 days or a year. */
  _renderBars(measures, unit, svg, details, legend, text, locale) {
    const chart = stackedBars(measures, unit);
    if (!chart.rects.length) {
      svg.innerHTML = `<text class="message" x="${CHART.width / 2}" y="${CHART.height / 2}">${escapeHtml(text.empty)}</text>`;
      details.textContent = "";
      legend.innerHTML = "";
      return;
    }
    const bars = measures.bars;
    const columns = chart.rects.map((rect) => {
      const selected = rect.index === this._selected ? " selected" : "";
      const blocks = rect.blocks.map((block) =>
        `<rect class="block" x="${block.x}" y="${block.y}" width="${block.width}" height="${block.height}" fill="${block.color}" />`).join("");
      const production = rect.production
        ? `<rect class="block" x="${rect.production.x}" y="${rect.production.y}" width="${rect.production.width}" height="${rect.production.height}" fill="${rect.production.color}" />` : "";
      return `<g class="bar${selected}" data-index="${rect.index}">
        <rect class="hit" x="${rect.center - rect.slot / 2}" y="${CHART.top}" width="${rect.slot}" height="${CHART.height - CHART.top}" />
        ${blocks}${production}
        <text class="label" x="${rect.center}" y="${CHART.height - 4}">${escapeHtml(barLabel(locale, this._period, bars[rect.index]?.date, rect.index))}</text>
      </g>`;
    }).join("");
    svg.innerHTML = `${this._grid(chart.ticks, unit === "eur" ? " €" : "", locale)}${columns}
      <line class="zero" x1="${CHART.left}" x2="${CHART.width - CHART.right}" y1="${chart.zero}" y2="${chart.zero}" />`;
    const labels = Object.fromEntries((measures.bands || []).map((band) => [band.id, band.label]));
    const bar = this._selected === null ? null : bars[this._selected];
    if (bar) {
      // In the order of the legend
      const order = (measures.bands || []).map((band) => band.id);
      const parts = [...(bar.bands || [])].sort((a, b) => order.indexOf(a.id) - order.indexOf(b.id)).map((band) =>
        `${labels[band.id] || band.id} ${formatValue(locale, unit === "eur" ? band.cost : band.energy, unit)}`);
      if (bar.production) {
        parts.push(`${text.production} ${formatValue(locale, bar.production, "kwh")}`);
      }
      details.textContent = `${barTitle(locale, this._period, bar.date)} : ${
        formatValue(locale, bar.energy, "kwh")} · ${formatValue(locale, bar.cost, "eur")}${parts.length ? ` — ${parts.join(" · ")}` : ""}`;
    } else {
      details.textContent = "";
    }
    const totals = bandTotals(measures);
    const colors = bandColors(measures.bands);
    const items = (measures.bands || []).filter((band) => totals[band.id]).map((band) =>
      `<span><span class="swatch" style="background: ${colors[band.id]}"></span>${escapeHtml(band.label)} <span class="value">${
        escapeHtml(formatValue(locale, unit === "eur" ? totals[band.id].cost : totals[band.id].energy, unit))}</span></span>`);
    if (unit !== "eur" && Number(measures.production) > 0) {
      items.push(`<span><span class="swatch" style="background: ${MEASURE_COLORS.production}"></span>${escapeHtml(text.production)} <span class="value">${
        escapeHtml(formatValue(locale, measures.production, "kwh"))}</span></span>`);
    }
    legend.innerHTML = items.join("");
  }
}

class LittleMonkeyMeasuresCardEditor extends HTMLElement {
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
      const helpers = await window.loadCardHelpers();
      const card = await helpers.createCardElement({ type: "entities", entities: [] });
      await card.constructor.getConfigElement();
    } catch (error) {
      console.debug("Little Monkey card: form of Home Assistant not loaded", error);
    }
  }

  _render() {
    if (!this._config || !this._hass) {
      return;
    }
    if (!this._form) {
      this._form = document.createElement("ha-form");
      this._form.computeLabel = (field) => TRANSLATIONS[language(this._hass)].editor[field.name] || field.name;
      this._form.addEventListener("value-changed", (event) => {
        event.stopPropagation();
        const config = { ...event.detail.value };
        for (const [key, value] of Object.entries(config)) {
          if (value === undefined || value === null || value === "") {
            delete config[key];
          }
        }
        this._config = config;
        this._render();
        this.dispatchEvent(new CustomEvent("config-changed", { detail: { config }, bubbles: true, composed: true }));
      });
      this.appendChild(this._form);
    }
    this._form.hass = this._hass;
    this._form.data = this._config;
    this._form.schema = measuresSchema(this._hass);
  }
}

if (!customElements.get(MEASURES_EDITOR_TYPE)) {
  customElements.define(MEASURES_EDITOR_TYPE, LittleMonkeyMeasuresCardEditor);
}
if (!customElements.get(MEASURES_TYPE)) {
  customElements.define(MEASURES_TYPE, LittleMonkeyMeasuresCard);
  const text = TRANSLATIONS[language({ language: navigator.language })];
  window.customCards = window.customCards || [];
  window.customCards.push({
    type: MEASURES_TYPE,
    name: text.name,
    description: text.description,
    preview: true,
    documentationURL: DOCUMENTATION,
  });
}
