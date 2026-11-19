/*
 * Savings cards of Little Monkey for the Home Assistant dashboards.
 *
 * Served and loaded by the little_monkey integration (see card.py), like the
 * dial card: no Lovelace resource to add. Plain web components, without
 * build step and without the internal libraries of the Home Assistant
 * frontend.
 *
 * The savings tab of the ecojoko application:
 * - little-monkey-savings-summary-card: over the last 12 months, the cost of
 *   the consumption, the cost of the reference consumption and the savings.
 * - little-monkey-savings-detail-card: the savings of a week, a month or a
 *   year in bars, with the previous periods read by the get_savings service.
 */

const DOMAIN = "little_monkey";
const SUMMARY_TYPE = "little-monkey-savings-summary-card";
const SUMMARY_EDITOR_TYPE = "little-monkey-savings-summary-card-editor";
const DETAIL_TYPE = "little-monkey-savings-detail-card";
const DETAIL_EDITOR_TYPE = "little-monkey-savings-detail-card-editor";
const DOCUMENTATION =
  "https://github.com/jmcruvellier/little_monkey/blob/main/CONFIGURATION.md#cartes-des-%C3%A9conomies";

const TRANSLATIONS = {
  en: {
    summary: {
      name: "Little Monkey savings summary",
      description: "Your savings over the last 12 months, as in the ecojoko application.",
      title: "Savings",
      subtitle: "Over the last 12 months",
      consumption: "Current consumption",
      reference: "Reference consumption",
      savings: "Savings",
      overconsumption: "Overconsumption",
      missing: "Savings sensor not found",
      option: "Turn on the “Savings” option in the options of the Little Monkey integration (Settings › Devices & services › Little Monkey › Configure).",
    },
    editor: {
      entity: "Savings over 12 months",
      consumption_entity: "Consumption cost over 12 months",
      reference_entity: "Reference cost over 12 months",
      unit: "Unit",
      units: { eur: "Euros", kwh: "kWh" },
      title: "Title",
    },
    detail: {
      name: "Little Monkey savings in detail",
      description: "Your savings by day, week or month, as in the ecojoko application.",
      title: "Savings in detail",
      periods: { week: "Week", month: "Month", year: "Year" },
      previous: "Previous period",
      next: "Next period",
      bar: "{name}: {savings} · {energy}",
      error: "The savings of this period could not be read",
      missing: "Savings sensor not found",
      option: "Turn on the “Savings” option in the options of the Little Monkey integration (Settings › Devices & services › Little Monkey › Configure).",
    },
    detail_editor: {
      entity: "Savings this week (or month, or year)",
      period: "Period shown first",
      unit: "Unit of the bars",
      units: { eur: "Euros", kwh: "kWh" },
      title: "Title",
    },
  },
  fr: {
    summary: {
      name: "Petit Singe : résumé des économies",
      description: "Vos économies sur les 12 derniers mois, comme dans l'application ecojoko.",
      title: "Économies",
      subtitle: "Sur les 12 derniers mois",
      consumption: "Conso en cours",
      reference: "Conso de référence",
      savings: "Économies",
      overconsumption: "Surconsommation",
      missing: "Capteur des économies introuvable",
      option: "Activez l'option « Économies » dans les options de l'intégration Little Monkey (Paramètres › Appareils et services › Little Monkey › Configurer).",
    },
    editor: {
      entity: "Économies sur 12 mois",
      consumption_entity: "Coût de la consommation sur 12 mois",
      reference_entity: "Coût de référence sur 12 mois",
      unit: "Unité",
      units: { eur: "Euros", kwh: "kWh" },
      title: "Titre",
    },
    detail: {
      name: "Petit Singe : détail des économies",
      description: "Vos économies par jour, semaine ou mois, comme dans l'application ecojoko.",
      title: "Économies en détail",
      periods: { week: "Semaine", month: "Mois", year: "Année" },
      previous: "Période précédente",
      next: "Période suivante",
      bar: "{name} : {savings} · {energy}",
      error: "Les économies de cette période n'ont pas pu être lues",
      missing: "Capteur des économies introuvable",
      option: "Activez l'option « Économies » dans les options de l'intégration Little Monkey (Paramètres › Appareils et services › Little Monkey › Configurer).",
    },
    detail_editor: {
      entity: "Économies de la semaine (ou du mois, ou de l'année)",
      period: "Période affichée d'abord",
      unit: "Unité des barres",
      units: { eur: "Euros", kwh: "kWh" },
      title: "Titre",
    },
  },
};

/** Return the language of the user, English when it is not translated. */
function language(hass) {
  const lang = (hass?.locale?.language || hass?.language || "en").split("-")[0];
  return TRANSLATIONS[lang] ? lang : "en";
}

// Colors of the bars, those of the ecojoko application
export const SUMMARY_COLORS = {
  consumption: "#0087b1",
  reference: "#bccfdc",
  savings: "#5fdcab",
  overconsumption: "#f0a35e",
};
const SUMMARY_ICONS = {
  consumption: "mdi:lightning-bolt",
  reference: "mdi:target",
  savings: "mdi:piggy-bank-outline",
};
const UNKNOWN_STATES = new Set(["unavailable", "unknown", "none", ""]);

/** Return a number, or null when it is not one. */
function asNumber(value) {
  if (value === null || value === undefined || value === "" || typeof value === "boolean") {
    return null;
  }
  const number = Number(value);
  return Number.isFinite(number) ? number : null;
}

/** Return the numeric state of an entity, null when it has none. */
function numericState(hass, entityId) {
  const state = entityId && hass?.states?.[entityId];
  if (!state || UNKNOWN_STATES.has(state.state)) {
    return null;
  }
  return asNumber(state.state);
}

/** Return an attribute of an entity as a number, null when it has none. */
function numericAttribute(hass, entityId, attribute) {
  const state = entityId && hass?.states?.[entityId];
  if (!state || UNKNOWN_STATES.has(state.state)) {
    return null;
  }
  return asNumber(state.attributes?.[attribute]);
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

/**
 * Return the rows of the summary: consumption, reference and savings.
 *
 * values: {consumption, reference, savings}, in euros or kWh. The bars are
 * scaled on the longest; savings below zero are an overconsumption, drawn
 * by their absolute value.
 */
export function summaryRows(values) {
  const longest = Math.max(
    ...["consumption", "reference", "savings"].map((key) => Math.abs(values[key] ?? 0)),
  );
  return ["consumption", "reference", "savings"].map((key) => {
    const value = values[key] ?? null;
    const over = key === "savings" && value !== null && value < 0;
    return {
      key,
      label: over ? "overconsumption" : key,
      value,
      ratio: value === null || longest === 0 ? 0 : Math.abs(value) / longest,
      color: SUMMARY_COLORS[over ? "overconsumption" : key],
    };
  });
}

/**
 * Return the color of the value of a row: the savings take the color of
 * their bar, mixed with the text color to stay readable on a light or a dark
 * card; the other values have the colors of the text.
 */
export function valueColor(row) {
  if (row.key === "savings") {
    return `color-mix(in srgb, ${row.color} 65%, var(--primary-text-color, #212121))`;
  }
  return row.key === "reference" ? "var(--secondary-text-color, #727272)" : "var(--primary-text-color, #212121)";
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

// Options of the summary set automatically to a sensor of the device
const SUMMARY_AUTOMATIC = {
  consumption_entity: "consumption_cost_12_months",
  reference_entity: "reference_cost_12_months",
};

/** Return the sensors of the summary: the chosen ones, else the device's. */
export function summaryEntities(hass, config) {
  const sensors = deviceEntities(hass, config.entity);
  return {
    savings: config.entity,
    consumption: config.consumption_entity || sensors.consumption_cost_12_months,
    reference: config.reference_entity || sensors.reference_cost_12_months,
  };
}

/** Return the values of the summary, in euros or in kWh. */
export function summaryValues(hass, config) {
  const entities = summaryEntities(hass, config);
  if (config.unit === "kwh") {
    return {
      consumption: numericAttribute(hass, entities.consumption, "consumption"),
      reference: numericAttribute(hass, entities.reference, "reference_consumption"),
      savings: numericAttribute(hass, entities.savings, "savings_kwh"),
    };
  }
  return {
    consumption: numericState(hass, entities.consumption),
    reference: numericState(hass, entities.reference),
    savings: numericState(hass, entities.savings),
  };
}

/** Return the configuration of a new summary card, on the first device. */
export function summaryStubConfig(hass) {
  const config = { type: `custom:${SUMMARY_TYPE}` };
  const entity = findEntity(hass, "savings_12_months");
  if (entity) {
    config.entity = entity;
  }
  return config;
}

/**
 * Return the configuration after a change in the editor.
 *
 * Choosing the sensor of another device also takes its cost sensors, unless
 * other sensors were chosen by hand. Empty options are removed.
 */
export function editedConfig(hass, previous, value, automatic = SUMMARY_AUTOMATIC) {
  const config = { ...value };
  if (config.entity !== previous.entity) {
    const before = deviceEntities(hass, previous.entity);
    const after = deviceEntities(hass, config.entity);
    for (const [option, key] of Object.entries(automatic)) {
      if (config[option] && config[option] === before[key]) {
        config[option] = after[key];
      }
    }
  }
  for (const [key, option] of Object.entries(config)) {
    if (option === undefined || option === null || option === "") {
      delete config[key];
    }
  }
  return config;
}

/** Return the fields of the editor of the summary. */
export function summarySchema(hass) {
  const text = TRANSLATIONS[language(hass)].editor;
  const monetary = { entity: { filter: { domain: "sensor", device_class: "monetary" } } };
  return [
    {
      name: "entity",
      required: true,
      selector: { entity: { filter: { integration: DOMAIN, domain: "sensor", device_class: "monetary" } } },
    },
    { name: "consumption_entity", selector: monetary },
    { name: "reference_entity", selector: monetary },
    {
      name: "unit",
      selector: {
        select: {
          mode: "dropdown",
          options: ["eur", "kwh"].map((value) => ({ value, label: text.units[value] })),
        },
      },
    },
    { name: "title", selector: { text: {} } },
  ];
}

// --- Detail of the savings

export const PERIODS = ["week", "month", "year"];
// Sensor of the current period, by period
const PERIOD_SENSORS = { week: "savings_week", month: "savings_month", year: "savings_year" };
// Bars: savings in green, overconsumption in grey blue, as in ecojoko
export const DETAIL_COLORS = { savings: "#5fdcab", overconsumption: "#a9bfd0" };
// Drawing of the bars, in the units of the SVG
const CHART = { width: 280, height: 160, left: 40, right: 4, top: 8, bottom: 20 };
// Distance of a swipe that changes the period, in pixels
const SWIPE_DISTANCE = 40;

/** Return an ISO date "YYYY-MM-DD" as a date at midnight UTC. */
function utcDate(iso) {
  return new Date(`${iso}T00:00:00Z`);
}

/** Return a date at midnight UTC as an ISO date "YYYY-MM-DD". */
function isoDate(date) {
  return date.toISOString().slice(0, 10);
}

/** Return today as an ISO date, in the time zone of the browser. */
export function today(now = new Date()) {
  const pad = (value) => String(value).padStart(2, "0");
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
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
  // Short enough for a narrow card: "9–15 nov. 2026", "Nov 9 – 15, 2026"
  return new Intl.DateTimeFormat(locale, {
    day: "numeric", month: "short", year: "numeric", timeZone: "UTC",
  }).formatRange(start, end);
}

/** Return the label of a bar: a day of the week, the days of a week, a month. */
export function barLabel(locale, period, iso) {
  if (!iso) {
    return "";
  }
  const date = utcDate(iso);
  if (period === "year") {
    // The initial of the month: twelve short names do not fit on a card
    return new Intl.DateTimeFormat(locale, { month: "narrow", timeZone: "UTC" }).format(date);
  }
  if (period === "month") {
    const end = new Date(date);
    end.setUTCDate(end.getUTCDate() + 6);
    return `${date.getUTCDate()}–${end.getUTCDate()}`;
  }
  return new Intl.DateTimeFormat(locale, { weekday: "short", timeZone: "UTC" }).format(date);
}

/** Return the long label of a bar, for its details. */
export function barTitle(locale, period, iso) {
  if (!iso) {
    return "";
  }
  const date = utcDate(iso);
  if (period === "year") {
    return periodLabel(locale, "month", iso);
  }
  if (period === "month") {
    return periodLabel(locale, "week", iso);
  }
  const text = new Intl.DateTimeFormat(locale, {
    weekday: "long", day: "numeric", month: "long", timeZone: "UTC",
  }).format(date);
  return text.charAt(0).toUpperCase() + text.slice(1);
}

/** Return a round step above a value: 1, 2, 2.5 or 5 times a power of ten. */
function niceStep(value) {
  const power = 10 ** Math.floor(Math.log10(value));
  const factor = [1, 2, 2.5, 5, 10].find((candidate) => candidate * power >= value * (1 - 1e-9));
  return factor * power;
}

/**
 * Return the scale of the bars: its bottom, its top and its step.
 *
 * It shows zero, and the negative side only with an overconsumption, with
 * at most four graduations on the longest side.
 */
export function chartScale(values) {
  const known = values.filter((value) => Number.isFinite(value));
  const top = Math.max(0, ...known);
  const bottom = Math.min(0, ...known);
  const longest = Math.max(top, -bottom);
  if (longest === 0) {
    return { min: 0, max: 1, step: 0.5 };
  }
  const step = niceStep(longest / 4);
  const max = Math.ceil(top / step - 1e-9) * step;
  return {
    min: -Math.ceil(-bottom / step - 1e-9) * step || 0,
    max: max || (bottom < 0 ? 0 : step),
    step,
  };
}

/** Return the values of the bars, in euros or in kWh. */
export function barValues(bars, unit) {
  return (bars || []).map((bar) => {
    const value = unit === "kwh" ? bar?.savings_kwh : bar?.savings;
    return Number.isFinite(value) ? value : null;
  });
}

/**
 * Return the rectangles of the bars and the graduations of the scale, in
 * the units of the SVG.
 */
export function chartGeometry(values, box = CHART) {
  const scale = chartScale(values);
  const plotHeight = box.height - box.top - box.bottom;
  const plotWidth = box.width - box.left - box.right;
  const y = (value) => box.top + ((scale.max - value) / (scale.max - scale.min)) * plotHeight;
  const slot = plotWidth / Math.max(values.length, 1);
  const width = Math.min(slot * 0.62, 36);
  const zero = y(0);
  const rects = values.map((value, index) => {
    const x = box.left + slot * index + (slot - width) / 2;
    const rect = { x, width, center: x + width / 2, slot, value };
    if (value === null) {
      return rect;
    }
    const height = Math.abs(y(value) - zero);
    return {
      ...rect,
      y: Math.min(y(value), zero),
      // A small saving stays visible
      height: value === 0 ? 0 : Math.max(height, 1),
      color: DETAIL_COLORS[value < 0 ? "overconsumption" : "savings"],
    };
  });
  const ticks = [];
  for (let value = scale.min; value <= scale.max + scale.step / 1000; value += scale.step) {
    // No "-0" at zero
    ticks.push({ value: Math.round(value * 1000) / 1000 || 0, y: y(value) });
  }
  return { rects, ticks, zero, scale };
}

/**
 * Tell whether the savings sensors exist: they are created only with the
 * option « Économies » of the integration.
 */
export function savingsEnabled(hass) {
  return Boolean(findEntity(hass, "savings_12_months") || findEntity(hass, "savings_week"));
}

/** Return the sensors of the current periods of the device of an entity. */
export function periodEntities(hass, entityId) {
  const sensors = deviceEntities(hass, entityId);
  return Object.fromEntries(PERIODS.map((period) => [period, sensors[PERIOD_SENSORS[period]]]));
}

/** Return the savings of a current period, as given by its sensor. */
export function sensorSavings(hass, entityId) {
  const state = entityId && hass?.states?.[entityId];
  if (!state || UNKNOWN_STATES.has(state.state) || !Array.isArray(state.attributes?.bars)) {
    return null;
  }
  return { ...state.attributes, savings: asNumber(state.state) };
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

/** Return the configuration of a new detail card, on the first device. */
export function detailStubConfig(hass) {
  const config = { type: `custom:${DETAIL_TYPE}` };
  const entity = findEntity(hass, "savings_week");
  if (entity) {
    config.entity = entity;
  }
  return config;
}

/** Return the fields of the editor of the detail. */
export function detailSchema(hass) {
  const text = TRANSLATIONS[language(hass)];
  return [
    {
      name: "entity",
      required: true,
      selector: { entity: { filter: { integration: DOMAIN, domain: "sensor", device_class: "monetary" } } },
    },
    {
      name: "period",
      selector: {
        select: {
          mode: "dropdown",
          options: PERIODS.map((value) => ({ value, label: text.detail.periods[value] })),
        },
      },
    },
    {
      name: "unit",
      selector: {
        select: {
          mode: "dropdown",
          options: ["eur", "kwh"].map((value) => ({ value, label: text.detail_editor.units[value] })),
        },
      },
    },
    { name: "title", selector: { text: {} } },
  ];
}

// Styles shared by the savings cards
const STYLES = `
  ha-card { padding: 16px; }
  .header { margin-bottom: 12px; }
  .title { font-size: 1.15em; font-weight: 500; color: var(--primary-text-color); }
  .subtitle { font-size: 0.9em; color: var(--secondary-text-color); margin-top: 2px; }
  .warning { color: var(--warning-color, #ffa600); }
`;

class LittleMonkeySavingsSummaryCard extends HTMLElement {
  setConfig(config) {
    if (!config) {
      throw new Error("Invalid configuration");
    }
    this._config = { ...config };
    this._built = false;
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  getCardSize() {
    // Masonry view: rows of 50 pixels
    return 4;
  }

  getGridOptions() {
    // The whole width of a section (12 columns): a list or a chart is cut
    // in half a section. The height follows the content
    return { columns: 12, min_columns: 6 };
  }

  static getConfigElement() {
    return document.createElement(SUMMARY_EDITOR_TYPE);
  }

  static getStubConfig(hass) {
    return summaryStubConfig(hass);
  }

  _text() {
    return TRANSLATIONS[language(this._hass)].summary;
  }

  /** Build the card once; the updates only change its values. */
  _build() {
    if (!this.shadowRoot) {
      this.attachShadow({ mode: "open" });
    }
    const rows = ["consumption", "reference", "savings"].map((key) => `
      <div class="row" data-key="${key}" tabindex="0" role="button">
        <ha-icon icon="${SUMMARY_ICONS[key]}"></ha-icon>
        <div class="line">
          <div class="text"><span class="label"></span><span class="value"></span></div>
          <div class="track"><div class="bar"></div></div>
        </div>
      </div>`).join("");
    this.shadowRoot.innerHTML = `
      <style>
        ${STYLES}
        .row { display: flex; align-items: center; gap: 12px; padding: 6px 0; cursor: pointer; }
        .row ha-icon { color: var(--secondary-text-color); --mdc-icon-size: 22px; flex: none; }
        .line { flex: 1; min-width: 0; }
        .text { display: flex; justify-content: space-between; gap: 8px; font-size: 0.95em; margin-bottom: 4px; }
        .label { color: var(--primary-text-color); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
        .value { font-weight: 500; white-space: nowrap; transition: color 0.5s; }
        .track { height: 12px; border-radius: 6px; background: var(--secondary-background-color, rgba(127, 127, 127, 0.12)); overflow: hidden; }
        .bar { height: 100%; width: 0; border-radius: 6px; transition: width 0.8s ease-out, background-color 0.5s; }
      </style>
      <ha-card>
        <div class="header"><div class="title"></div><div class="subtitle"></div></div>
        <div class="warning"></div>
        <div class="rows">${rows}</div>
      </ha-card>`;
    for (const row of this.shadowRoot.querySelectorAll(".row")) {
      const open = () => this._moreInfo(summaryEntities(this._hass, this._config)[row.dataset.key]);
      row.addEventListener("click", open);
      row.addEventListener("keydown", (event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          open();
        }
      });
    }
    this._built = true;
  }

  /** Open the dialog of an entity, as the core cards do. */
  _moreInfo(entityId) {
    if (!entityId) {
      return;
    }
    this.dispatchEvent(new CustomEvent("hass-more-info", {
      detail: { entityId }, bubbles: true, composed: true,
    }));
  }

  _render() {
    if (!this._config || !this._hass) {
      return;
    }
    if (!this._built) {
      this._build();
    }
    const text = this._text();
    const root = this.shadowRoot;
    root.querySelector(".title").textContent = this._config.title || text.title;
    root.querySelector(".subtitle").textContent = text.subtitle;
    const warning = root.querySelector(".warning");
    // Without the option of the savings, the card only asks to turn it on
    const enabled = savingsEnabled(this._hass);
    const missing = !this._config.entity || !this._hass.states[this._config.entity];
    warning.textContent = !enabled ? text.option : missing ? text.missing : "";
    warning.style.display = !enabled || missing ? "" : "none";
    // Not an error: an option to turn on
    warning.style.color = enabled ? "" : "var(--secondary-text-color)";
    root.querySelector(".rows").style.display = enabled ? "" : "none";
    if (!enabled) {
      return;
    }

    const locale = this._hass.locale?.language || this._hass.language;
    const unit = this._config.unit === "kwh" ? "kwh" : "eur";
    for (const row of summaryRows(summaryValues(this._hass, this._config))) {
      const element = root.querySelector(`.row[data-key="${row.key}"]`);
      element.querySelector(".label").textContent = text[row.label];
      const value = element.querySelector(".value");
      value.textContent = formatValue(locale, row.value === null ? null : Math.abs(row.value), unit);
      value.style.color = valueColor(row);
      const bar = element.querySelector(".bar");
      bar.style.width = `${(row.ratio * 100).toFixed(1)}%`;
      bar.style.backgroundColor = row.color;
    }
  }
}

/** Editor of a savings card: a form of Home Assistant. */
class SavingsEditor extends HTMLElement {
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

  _automatic() {
    return {};
  }

  _labels() {
    return "editor";
  }

  _render() {
    if (!this._config || !this._hass) {
      return;
    }
    if (!this._form) {
      this._form = document.createElement("ha-form");
      this._form.computeLabel = (field) =>
        TRANSLATIONS[language(this._hass)][this._labels()][field.name] || field.name;
      this._form.addEventListener("value-changed", (event) => this._changed(event));
      this.appendChild(this._form);
    }
    this._form.hass = this._hass;
    this._form.data = this._config;
    this._form.schema = this._schema();
  }

  _changed(event) {
    event.stopPropagation();
    const config = editedConfig(this._hass, this._config, event.detail.value, this._automatic());
    this._config = config;
    this._render();
    this.dispatchEvent(new CustomEvent("config-changed", {
      detail: { config }, bubbles: true, composed: true,
    }));
  }
}

class LittleMonkeySavingsSummaryCardEditor extends SavingsEditor {
  _schema() {
    return summarySchema(this._hass);
  }

  _automatic() {
    return SUMMARY_AUTOMATIC;
  }
}

/** Escape a text for the HTML of a card. */
function escapeHtml(text) {
  return String(text).replace(/[&<>"']/g, (character) => `&#${character.charCodeAt(0)};`);
}

class LittleMonkeySavingsDetailCard extends HTMLElement {
  setConfig(config) {
    if (!config) {
      throw new Error("Invalid configuration");
    }
    this._config = { ...config };
    this._period = initialPeriod(this._config);
    this._start = null;
    this._selected = null;
    // Savings of the past periods, read by the service: by "period:start"
    this._cache = new Map();
    this._pending = new Set();
    this._errors = new Set();
    this._built = false;
    this._signature = null;
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  getCardSize() {
    // Masonry view: rows of 50 pixels
    return 7;
  }

  getGridOptions() {
    // The whole width of a section (12 columns): a list or a chart is cut
    // in half a section. The height follows the content
    return { columns: 12, min_columns: 6 };
  }

  static getConfigElement() {
    return document.createElement(DETAIL_EDITOR_TYPE);
  }

  static getStubConfig(hass) {
    return detailStubConfig(hass);
  }

  _text() {
    return TRANSLATIONS[language(this._hass)].detail;
  }

  _locale() {
    return this._hass.locale?.language || this._hass.language;
  }

  /** Return the first day of the current period. */
  _current() {
    return periodStart(this._period, today());
  }

  /** Show another period: week, month or year, from the current one. */
  _choose(period) {
    this._period = period;
    this._start = null;
    this._selected = null;
    this._render();
  }

  /** Show the period before (-1) or after (+1). */
  _go(step) {
    const start = shiftPeriod(this._period, this._start || this._current(), step);
    if (start > this._current()) {
      return;
    }
    this._start = start === this._current() ? null : start;
    this._selected = null;
    this._errors.delete(`${this._period}:${start}`);
    this._render();
  }

  /** Return the savings shown: from the sensor now, from the service before. */
  _savings() {
    const start = this._start || this._current();
    if (!this._start) {
      const sensor = periodEntities(this._hass, this._config.entity)[this._period];
      const savings = sensorSavings(this._hass, sensor);
      if (savings) {
        return { savings, start };
      }
    }
    const key = `${this._period}:${start}`;
    if (this._errors.has(key)) {
      return { error: true, start };
    }
    if (!this._cache.has(key)) {
      this._fetch(this._period, start);
      return { loading: true, start };
    }
    return { savings: this._cache.get(key), start };
  }

  /** Read the savings of a period with the get_savings service. */
  async _fetch(period, start) {
    const key = `${period}:${start}`;
    if (this._pending.has(key)) {
      return;
    }
    this._pending.add(key);
    const data = { period, date: start };
    const entry = configEntryId(this._hass, this._config.entity);
    if (entry) {
      data.config_entry_id = entry;
    }
    try {
      const result = await this._hass.callWS({
        type: "call_service",
        domain: DOMAIN,
        service: "get_savings",
        service_data: data,
        return_response: true,
      });
      this._cache.set(key, result.response);
    } catch (error) {
      console.debug("Little Monkey card: savings not read", error);
      this._errors.add(key);
    } finally {
      this._pending.delete(key);
      this._signature = null;
      this._render();
    }
  }

  /** Build the card once; the updates redraw its bars. */
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
        .top { display: flex; align-items: center; justify-content: space-between; gap: 8px; flex-wrap: wrap; margin-bottom: 8px; }
        .periods { display: inline-flex; border: 1px solid var(--divider-color, #e0e0e0); border-radius: 18px; overflow: hidden; }
        .period { border: none; background: none; color: var(--primary-text-color); font: inherit; font-size: 0.9em; padding: 6px 12px; cursor: pointer; }
        .period.active { background: var(--primary-color, #03a9f4); color: var(--text-primary-color, #fff); }
        .total { font-size: 0.95em; white-space: nowrap; }
        .total .money { font-weight: 600; }
        .total .energy { color: var(--secondary-text-color); }
        .details { min-height: 1.4em; font-size: 0.9em; color: var(--secondary-text-color); text-align: center; }
        svg { width: 100%; display: block; touch-action: pan-y; user-select: none; }
        .tick { fill: var(--secondary-text-color, #727272); font-size: 9.5px; text-anchor: end; dominant-baseline: central; }
        .grid { stroke: var(--divider-color, #e0e0e0); stroke-width: 0.5; }
        .zero { stroke: var(--secondary-text-color, #727272); stroke-width: 0.6; }
        .label { fill: var(--secondary-text-color, #727272); font-size: 9.5px; text-anchor: middle; }
        .bar { cursor: pointer; }
        .bar rect.hit { fill: transparent; }
        .bar.selected rect.value { stroke: var(--primary-text-color); stroke-width: 1; }
        .message { fill: var(--secondary-text-color, #727272); font-size: 10px; text-anchor: middle; }
        .nav { display: flex; align-items: center; justify-content: space-between; margin-top: 4px; }
        .nav button { border: none; background: none; color: var(--primary-text-color); cursor: pointer; padding: 4px 10px; font-size: 1.4em; line-height: 1; border-radius: 50%; }
        .nav button:disabled { visibility: hidden; }
        .nav .name { font-size: 0.95em; color: var(--primary-text-color); text-align: center; }
        ha-card.disabled .top, ha-card.disabled .details, ha-card.disabled svg, ha-card.disabled .nav { display: none; }
      </style>
      <ha-card>
        <div class="header"><div class="title"></div></div>
        <div class="warning"></div>
        <div class="top"><div class="periods">${buttons}</div><div class="total"></div></div>
        <div class="details"></div>
        <svg viewBox="0 0 ${CHART.width} ${CHART.height}" role="img"></svg>
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
    svg.addEventListener("click", (event) => {
      const bar = event.target.closest?.(".bar");
      if (bar) {
        const index = Number(bar.dataset.index);
        this._selected = this._selected === index ? null : index;
        this._signature = null;
        this._render();
      }
    });
    // Swipe to the previous or next period
    svg.addEventListener("pointerdown", (event) => {
      this._swipeStart = event.clientX;
    });
    svg.addEventListener("pointerup", (event) => {
      const distance = event.clientX - (this._swipeStart ?? event.clientX);
      this._swipeStart = null;
      if (Math.abs(distance) >= SWIPE_DISTANCE) {
        this._go(distance > 0 ? -1 : 1);
      }
    });
    this._built = true;
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
    const unit = this._config.unit === "kwh" ? "kwh" : "eur";
    const shown = this._savings();
    const enabled = savingsEnabled(this._hass);
    const signature = JSON.stringify([this._period, shown, this._selected, unit, this._config.title, locale, enabled]);
    if (signature === this._signature) {
      return;
    }
    this._signature = signature;
    const root = this.shadowRoot;
    root.querySelector(".title").textContent = this._config.title || text.title;
    const missing = !this._config.entity || !this._hass.states[this._config.entity];
    const warning = root.querySelector(".warning");
    // Without the option of the savings, the card only asks to turn it on
    warning.textContent = !enabled ? text.option : missing ? text.missing : "";
    warning.style.display = !enabled || missing ? "" : "none";
    // Not an error: an option to turn on
    warning.style.color = enabled ? "" : "var(--secondary-text-color)";
    root.querySelector("ha-card").classList.toggle("disabled", !enabled);
    if (!enabled) {
      return;
    }
    for (const button of root.querySelectorAll(".period")) {
      button.classList.toggle("active", button.dataset.period === this._period);
    }
    root.querySelector(".name").textContent = periodLabel(locale, this._period, shown.start);
    root.querySelector(".next").disabled = shown.start >= this._current();

    const savings = shown.savings;
    const total = root.querySelector(".total");
    if (savings && savings.savings !== null && savings.savings !== undefined) {
      const color = DETAIL_COLORS[savings.savings < 0 ? "overconsumption" : "savings"];
      total.innerHTML = `<span class="money" style="color: color-mix(in srgb, ${color} 65%, var(--primary-text-color, #212121))">${
        escapeHtml(formatValue(locale, savings.savings, "eur"))}</span> <span class="energy">| ${
        escapeHtml(formatValue(locale, savings.savings_kwh, "kwh"))}</span>`;
    } else {
      total.textContent = "";
    }

    const bars = savings?.bars || [];
    const details = root.querySelector(".details");
    const bar = this._selected === null ? null : bars[this._selected];
    if (bar && bar.savings !== null && bar.savings !== undefined) {
      details.textContent = text.bar
        .replace("{name}", barTitle(locale, this._period, bar.date))
        .replace("{savings}", formatValue(locale, bar.savings, "eur"))
        .replace("{energy}", formatValue(locale, bar.savings_kwh, "kwh"));
    } else {
      details.textContent = "";
    }
    root.querySelector("svg").innerHTML = this._chart(shown, bars, unit, locale, text);
  }

  /** Return the SVG of the bars, their scale and their labels. */
  _chart(shown, bars, unit, locale, text) {
    if (shown.loading || shown.error || !bars.length) {
      const message = shown.error ? text.error : "…";
      return `<text class="message" x="${CHART.width / 2}" y="${CHART.height / 2}">${escapeHtml(message)}</text>`;
    }
    const { rects, ticks, zero } = chartGeometry(barValues(bars, unit));
    const format = new Intl.NumberFormat(locale, { maximumFractionDigits: 2 });
    const suffix = unit === "kwh" ? "" : " €";
    const grid = ticks.map((tick) => `
      <line class="grid" x1="${CHART.left}" x2="${CHART.width - CHART.right}" y1="${tick.y}" y2="${tick.y}" />
      <text class="tick" x="${CHART.left - 4}" y="${tick.y}">${escapeHtml(format.format(tick.value) + suffix)}</text>`).join("");
    const columns = rects.map((rect, index) => {
      const value = rect.value === null ? "" : `<rect class="value" x="${rect.x}" y="${rect.y}" width="${rect.width}" height="${rect.height}" rx="1.5" fill="${rect.color}" />`;
      const selected = index === this._selected ? " selected" : "";
      return `<g class="bar${selected}" data-index="${index}">
        <rect class="hit" x="${rect.center - rect.slot / 2}" y="${CHART.top}" width="${rect.slot}" height="${CHART.height - CHART.top}" />
        ${value}
        <text class="label" x="${rect.center}" y="${CHART.height - 4}">${escapeHtml(barLabel(locale, this._period, bars[index]?.date))}</text>
      </g>`;
    }).join("");
    return `${grid}<line class="zero" x1="${CHART.left}" x2="${CHART.width - CHART.right}" y1="${zero}" y2="${zero}" />${columns}`;
  }
}

class LittleMonkeySavingsDetailCardEditor extends SavingsEditor {
  _schema() {
    return detailSchema(this._hass);
  }

  _labels() {
    return "detail_editor";
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
  SUMMARY_TYPE, LittleMonkeySavingsSummaryCard,
  SUMMARY_EDITOR_TYPE, LittleMonkeySavingsSummaryCardEditor, "summary",
);
defineCard(
  DETAIL_TYPE, LittleMonkeySavingsDetailCard,
  DETAIL_EDITOR_TYPE, LittleMonkeySavingsDetailCardEditor, "detail",
);
