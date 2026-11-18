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
 *   month by category (standby, lighting, cooling...), read with the
 *   get_consumption_analysis service; a category shows its history, week
 *   by week over a year (get_category_history service).
 * - little-monkey-activations-card: the starts of the appliances detected
 *   by ecojoko, day by day (get_activations service).
 */

const DOMAIN = "little_monkey";
const ANALYSIS_TYPE = "little-monkey-analysis-card";
const ANALYSIS_EDITOR_TYPE = "little-monkey-analysis-card-editor";
const ACTIVATIONS_TYPE = "little-monkey-activations-card";
const ACTIVATIONS_EDITOR_TYPE = "little-monkey-activations-card-editor";
const DOCUMENTATION =
  "https://github.com/jmcruvellier/little_monkey/blob/main/CONFIGURATION.md#cartes-de-lanalyse-de-la-consommation";

const TRANSLATIONS = {
  en: {
    analysis: {
      name: "Little Monkey consumption analysis",
      description: "Your consumption by category (standby, lighting, cooling...), as in the ecojoko application.",
      title: "Consumption analysis",
      periods: { week: "Week", month: "Month" },
      previous: "Previous period",
      next: "Next period",
      error: "The analysis of this period could not be read",
      missing: "Little Monkey sensor not found",
      up: "Up on the previous period",
      down: "Down on the previous period",
      back: "Back to the categories",
      history: "History of the category",
      history_error: "The history of this category could not be read",
      week_of: "Week of {date}",
      bar: "{name}: {cost} · {energy}",
      show_all: "Show the {n} categories",
      show_less: "Show fewer categories",
    },
    categories: {
      1: "Heating", 2: "Electric vehicle", 3: "Hot water", 4: "Cooking", 5: "Large appliances",
      6: "Fridges, freezers", 7: "Standby consumption", 8: "Lighting", 9: "Other appliances",
      11: "Air conditioning", 12: "Dishwasher", 13: "Washing", 14: "Drying",
    },
    activations: {
      name: "Little Monkey appliance activations",
      description: "The starts of your appliances detected by ecojoko, as in its application.",
      title: "Appliance activations",
      more: "Load the next ones",
      none: "No activation detected over these 48 hours",
      error: "The activations could not be read",
      missing: "Little Monkey sensor not found",
      average: "Average {power}",
      seconds: "{n} s",
      minutes: "{n} min",
      hours: "{h} h {m} min",
      count: "{n} activations",
      older: "Previous 48 hours",
      newer: "Next 48 hours",
      show_more: "Show more",
    },
    editor: {
      entity: "A sensor of the Little Monkey device",
      period: "Period shown first",
      max_categories: "Categories shown (0 for all)",
      mode: "Display",
      modes: { timeline: "One timeline a day", list: "List" },
      title: "Title",
    },
  },
  fr: {
    analysis: {
      name: "Petit Singe : analyse de la conso",
      description: "Votre consommation par poste (talon, éclairage, froid…), comme dans l'application ecojoko.",
      title: "Analyse de la conso",
      periods: { week: "Semaine", month: "Mois" },
      previous: "Période précédente",
      next: "Période suivante",
      error: "L'analyse de cette période n'a pas pu être lue",
      missing: "Capteur Little Monkey introuvable",
      up: "En hausse par rapport à la période précédente",
      down: "En baisse par rapport à la période précédente",
      back: "Retour aux postes",
      history: "Historique du poste",
      history_error: "L'historique de ce poste n'a pas pu être lu",
      week_of: "Semaine du {date}",
      bar: "{name} : {cost} · {energy}",
      show_all: "Afficher les {n} postes",
      show_less: "Afficher moins de postes",
    },
    categories: {},
    activations: {
      name: "Petit Singe : activations des appareils",
      description: "Les démarrages de vos appareils détectés par ecojoko, comme dans son application.",
      title: "Activations des appareils",
      more: "Charger les suivantes",
      none: "Aucune activation détectée sur ces 48 heures",
      error: "Les activations n'ont pas pu être lues",
      missing: "Capteur Little Monkey introuvable",
      average: "Moyenne {power}",
      seconds: "{n} s",
      minutes: "{n} min",
      hours: "{h} h {m} min",
      count: "{n} activations",
      older: "48 heures précédentes",
      newer: "48 heures suivantes",
      show_more: "Voir plus",
    },
    editor: {
      entity: "Un capteur de l'appareil Little Monkey",
      period: "Période affichée d'abord",
      max_categories: "Postes affichés (0 pour tous)",
      mode: "Affichage",
      modes: { timeline: "Une frise par jour", list: "Liste" },
      title: "Titre",
    },
  },
};

/** Return the language of the user, English when it is not translated. */
function language(hass) {
  const lang = (hass?.locale?.language || hass?.language || "en").split("-")[0];
  return TRANSLATIONS[lang] ? lang : "en";
}

// Periods analysed by ecojoko: its page « Analyse de votre conso » offers
// the week and the month only (the year is commented out in its page, and
// asking for a year gives the current week)
export const PERIODS = ["week", "month"];
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

// Bars of the history, in the units of the SVG
const HISTORY = { width: 280, height: 150, left: 40, right: 4, top: 8, bottom: 18 };

/** Return a round step above a value: 1, 2, 2.5 or 5 times a power of ten. */
function niceStep(value) {
  const power = 10 ** Math.floor(Math.log10(value));
  const factor = [1, 2, 2.5, 5, 10].find((candidate) => candidate * power >= value * (1 - 1e-9));
  return factor * power;
}

/**
 * Return the bars of the history of a category and its graduations, in the
 * units of the SVG: one bar a week, from zero.
 */
export function historyGeometry(values, box = HISTORY) {
  const known = values.filter((value) => Number.isFinite(value));
  const top = Math.max(0, ...known);
  const step = top > 0 ? niceStep(top / 4) : 0.5;
  const max = top > 0 ? Math.ceil(top / step - 1e-9) * step : 1;
  const plotHeight = box.height - box.top - box.bottom;
  const plotWidth = box.width - box.left - box.right;
  const y = (value) => box.top + ((max - value) / max) * plotHeight;
  const slot = plotWidth / Math.max(values.length, 1);
  const width = Math.max(slot * 0.7, 0.5);
  const bars = values.map((value, index) => {
    const x = box.left + slot * index + (slot - width) / 2;
    const height = Number.isFinite(value) && value > 0 ? Math.max(y(0) - y(value), 0.8) : 0;
    return { x, width, slot, height, y: y(0) - height, value: Number.isFinite(value) ? value : null };
  });
  const ticks = [];
  for (let value = 0; value <= max + step / 1000; value += step) {
    ticks.push({ value: Math.round(value * 1000) / 1000, y: y(value) });
  }
  return { bars, ticks, zero: y(0) };
}

/** Return the totals of the history of a category: cost and energy. */
export function historyTotals(bars) {
  const sum = (key) => (bars || []).reduce((total, bar) => total + (Number(bar?.[key]) || 0), 0);
  return { cost: Math.round(sum("cost") * 100) / 100, consumption: Math.round(sum("consumption") * 100) / 100 };
}

/** Return the labels of the months under the bars of a year of weeks. */
export function monthLabels(locale, bars) {
  const labels = [];
  let month = null;
  (bars || []).forEach((bar, index) => {
    const current = bar?.date?.slice(0, 7);
    if (current && current !== month) {
      month = current;
      labels.push({
        index,
        label: new Intl.DateTimeFormat(locale, { month: "narrow", timeZone: "UTC" }).format(utcDate(`${current}-01`)),
      });
    }
  });
  return labels;
}

// --- Activations of the appliances

// The first page is read again after this many milliseconds
const ACTIVATIONS_REFRESH = 10 * 60 * 1000;

/** Return the activations of the pages read, without the repeated ones. */
export function mergeActivations(pages) {
  const seen = new Set();
  const result = [];
  for (const page of pages) {
    for (const activation of page?.activations || []) {
      if (activation?.start && !seen.has(activation.start)) {
        seen.add(activation.start);
        result.push(activation);
      }
    }
  }
  // The most recent first
  return result.sort((a, b) => (a.start < b.start ? 1 : a.start > b.start ? -1 : 0));
}

/**
 * Return the activations grouped by day, the day in the time zone of
 * ecojoko (the date of their ISO time).
 */
export function groupByDay(activations) {
  const days = [];
  for (const activation of activations) {
    const day = activation.start.slice(0, 10);
    if (!days.length || days[days.length - 1].day !== day) {
      days.push({ day, activations: [] });
    }
    days[days.length - 1].activations.push(activation);
  }
  return days;
}

/** Return the name of a day: "Lundi 16 novembre 2026". */
export function dayLabel(locale, day) {
  const text = new Intl.DateTimeFormat(locale, {
    weekday: "long", day: "numeric", month: "long", year: "numeric", timeZone: "UTC",
  }).format(utcDate(day));
  return text.charAt(0).toUpperCase() + text.slice(1);
}

/** Return the hours of an activation: "00:03 – 02:29". */
export function timeRange(activation) {
  const time = (iso) => (iso ? iso.slice(11, 16) : "");
  return `${time(activation.start)} – ${time(activation.end)}`;
}

/** Return the duration of an activation: "30 s", "13 min", "2 h 26 min". */
export function durationLabel(text, activation) {
  const seconds = Math.max(Math.round((Date.parse(activation.end) - Date.parse(activation.start)) / 1000), 0);
  if (!Number.isFinite(seconds)) {
    return "";
  }
  if (seconds < 60) {
    return text.seconds.replace("{n}", seconds);
  }
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) {
    return text.minutes.replace("{n}", minutes);
  }
  return text.hours.replace("{h}", Math.floor(minutes / 60)).replace("{m}", String(minutes % 60).padStart(2, "0"));
}

/**
 * Return the SVG of the shape ecojoko draws for an activation: a pulse on a
 * baseline, as wide as the activation is long and as high as its power.
 */
export function shapeSvg(shape) {
  const width = Math.min(Math.max(Number(shape?.width) || 3, 2), 96);
  const height = Math.min(Math.max(Number(shape?.height) || 4, 2), 40);
  const color = /^#[0-9a-f]{3,8}$/i.test(shape?.color || "") ? shape.color : "#5fc2ff";
  const base = 42;
  return `<svg class="shape" viewBox="0 0 104 44" aria-hidden="true">
    <path d="M 0 ${base} H 4 V ${base - height} H ${4 + width} V ${base} H 104" fill="none" stroke="${color}" stroke-width="2.5" stroke-linejoin="round" />
  </svg>`;
}

// Timeline of a day, in the units of the SVG: a minute a unit
const TIMELINE = { width: 1440, height: 48, base: 44, min: 6, max: 40, hit: 14 };
// Activations of the list shown before "show more"
export const LIST_LENGTH = 8;

/** Return the minutes since midnight of an ISO time, in its time zone. */
function minutesOfDay(iso) {
  const match = String(iso ?? "").match(/T(\d{2}):(\d{2})(?::(\d{2}))?/);
  return match ? Number(match[1]) * 60 + Number(match[2]) + Number(match[3] || 0) / 60 : null;
}

/**
 * Return the timelines of the activations: one a day, the most recent
 * first, each activation a pulse at its time, as wide as it lasts (two
 * minutes at least, to be seen) and as high as its power, compared with the
 * most powerful one shown.
 */
export function timelines(activations, box = TIMELINE) {
  const powers = activations.map((activation) => Number(activation.power) || 0);
  const strongest = Math.max(1, ...powers);
  return groupByDay(activations).map((group) => ({
    day: group.day,
    pulses: group.activations.map((activation) => {
      const start = minutesOfDay(activation.start) ?? 0;
      const lasting = Math.max((Date.parse(activation.end) - Date.parse(activation.start)) / 60000, 0) || 0;
      const width = Math.min(Math.max(lasting, 2), box.width - start);
      const ratio = Math.min(Math.max(Number(activation.power) || 0, 0) / strongest, 1);
      const height = box.min + (box.max - box.min) * ratio;
      const color = /^#[0-9a-f]{3,8}$/i.test(activation.shape?.color || "") ? activation.shape.color : "#5fc2ff";
      return { start: activation.start, x: start, width, height, y: box.base - height, color };
    }).reverse(),
  }));
}

/** Return the display of an activations card: "timeline" by default, or "list". */
export function activationsMode(config) {
  return config?.mode === "list" ? "list" : "timeline";
}

/** Return the configuration of a new activations card, on the first device. */
export function activationsStubConfig(hass) {
  const config = { type: `custom:${ACTIVATIONS_TYPE}` };
  const entity = findEntity(hass, "realtime_consumption");
  if (entity) {
    config.entity = entity;
  }
  return config;
}

/** Return the fields of the editor of the activations. */
export function activationsSchema(hass) {
  const text = TRANSLATIONS[language(hass)].editor;
  return [
    {
      name: "entity",
      required: true,
      selector: { entity: { filter: { integration: DOMAIN, domain: "sensor" } } },
    },
    {
      name: "mode",
      selector: {
        select: {
          mode: "dropdown",
          options: ["timeline", "list"].map((value) => ({ value, label: text.modes[value] })),
        },
      },
    },
    { name: "title", selector: { text: {} } },
  ];
}

// Categories shown before "show all", by default
export const DEFAULT_MAX_CATEGORIES = 5;

/** Return the number of categories shown by a card: 0 for all of them. */
export function maxCategories(config) {
  const value = Number(config?.max_categories);
  return Number.isInteger(value) && value >= 0 ? value : DEFAULT_MAX_CATEGORIES;
}

/**
 * Return the categories shown: the largest ones (by consumption), in the
 * order of ecojoko, all of them with a maximum of 0 or when expanded.
 */
export function shownCategories(categories, max, expanded = false) {
  const list = categories || [];
  if (expanded || max <= 0 || list.length <= max) {
    return list;
  }
  const largest = new Set(
    list.map((category, index) => ({ index, value: Number(category.consumption) || 0 }))
      .sort((a, b) => b.value - a.value)
      .slice(0, max)
      .map((item) => item.index),
  );
  return list.filter((_category, index) => largest.has(index));
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
    {
      name: "max_categories",
      selector: { number: { min: 0, max: 20, step: 1, mode: "box" } },
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
    // Category whose history is shown, and the year shown
    this._history = null;
    // All the categories shown, or the largest ones only
    this._expanded = false;
    this._selected = null;
    this._built = false;
    this._signature = null;
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  getCardSize() {
    // Masonry view: rows of 50 pixels, for the ring beside five categories
    return 6;
  }

  getGridOptions() {
    // The whole width of a section (12 columns): a list or a chart is cut
    // in half a section. The height follows the content
    return { columns: 12, min_columns: 6 };
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
    this._history = null;
    this._render();
  }

  /** Show the history of a category, for the year of the period shown. */
  _showHistory(category, year) {
    this._history = { category, year };
    this._selected = null;
    this._signature = null;
    this._render();
  }

  /** Return the history shown, reading it when needed. */
  _historyData() {
    const { category, year } = this._history;
    const key = `history:${category.id}:${year}`;
    if (this._errors.has(key)) {
      return { error: true };
    }
    if (!this._cache.has(key)) {
      this._fetchHistory(category.id, year, key);
      return { loading: true };
    }
    return this._cache.get(key);
  }

  async _fetchHistory(id, year, key) {
    if (this._pending.has(key)) {
      return;
    }
    this._pending.add(key);
    // The current year up to today, a past year as a whole
    const thisYear = new Date().getFullYear();
    const date = year >= thisYear ? undefined : `${year}-12-31`;
    try {
      const data = { category: Number(id) };
      if (date) {
        data.date = date;
      }
      this._cache.set(key, await callService(this._hass, this._config.entity, "get_category_history", data));
    } catch (error) {
      console.debug("Little Monkey card: history not read", error);
      this._errors.add(key);
    } finally {
      this._pending.delete(key);
      this._signature = null;
      this._render();
    }
  }

  /** Show the period before (-1) or after (+1). */
  _go(step) {
    if (this._history) {
      const year = this._history.year + step;
      if (year <= new Date().getFullYear()) {
        this._history = { ...this._history, year };
        this._selected = null;
        this._errors.delete(`history:${this._history.category.id}:${year}`);
        this._render();
      }
      return;
    }
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
        .body { container-type: inline-size; }
        .layout { display: grid; grid-template-columns: minmax(0, 1fr); gap: 4px 16px; align-items: center; }
        /* A wide card puts the ring beside the categories */
        @container (min-width: 420px) { .layout { grid-template-columns: 140px minmax(0, 1fr); } }
        /* A narrow card keeps the names and the costs, and leaves out the shares */
        @container (max-width: 380px) { .share { display: none; } }
        .ring { display: flex; justify-content: center; }
        .ring svg { width: 100%; max-width: 150px; display: block; touch-action: pan-y; user-select: none; }
        .more-categories { border: none; background: none; color: var(--primary-color, #03a9f4); font: inherit; font-size: 0.85em;
          cursor: pointer; padding: 4px; text-align: left; }
        .ring .total { fill: var(--primary-text-color); font-size: 17px; font-weight: 600; text-anchor: middle; }
        .ring .energy { fill: var(--secondary-text-color); font-size: 11px; text-anchor: middle; }
        .ring .track { fill: none; stroke: var(--secondary-background-color, rgba(127, 127, 127, 0.15)); }
        .rows { display: flex; flex-direction: column; }
        .row { display: flex; align-items: center; gap: 8px; padding: 3px 4px; border-radius: 8px; }
        .row.child { padding-left: 28px; }
        .row { cursor: pointer; }
        .row:hover { background: var(--secondary-background-color, rgba(127, 127, 127, 0.08)); }
        .toggle { cursor: pointer; padding: 6px 0; font-size: 1.2em; text-align: center; }
        .history-head { display: flex; align-items: center; gap: 8px; margin-bottom: 4px; }
        .back { border: none; background: none; color: var(--primary-text-color); cursor: pointer; font-size: 1.3em; padding: 2px 6px; }
        .history-head .label { flex: 1; color: var(--primary-text-color); font-weight: 500; }
        .history-total { font-size: 0.95em; color: var(--secondary-text-color); margin: 2px 0 4px; }
        .history-total .cost { color: var(--primary-text-color); font-weight: 600; }
        .details { min-height: 1.4em; font-size: 0.9em; color: var(--secondary-text-color); text-align: center; }
        .chart { width: 100%; display: block; touch-action: pan-y; user-select: none; }
        .chart .tick { fill: var(--secondary-text-color, #727272); font-size: 9.5px; text-anchor: end; dominant-baseline: central; }
        .chart .month { fill: var(--secondary-text-color, #727272); font-size: 9.5px; text-anchor: start; }
        .chart .grid { stroke: var(--divider-color, #e0e0e0); stroke-width: 0.5; }
        .chart .zero { stroke: var(--secondary-text-color, #727272); stroke-width: 0.6; }
        .chart .hit { fill: transparent; }
        .chart .bar { cursor: pointer; }
        .chart .bar.selected rect.value { stroke: var(--primary-text-color); stroke-width: 0.8; }
        .icon { width: 30px; height: 30px; border-radius: 50%; display: flex; align-items: center; justify-content: center; flex: none; }
        .icon ha-icon { --mdc-icon-size: 18px; }
        .row .icon { width: 24px; height: 24px; }
        .row .icon ha-icon { --mdc-icon-size: 14px; }
        .row.child .icon { width: 20px; height: 20px; }
        .row.child .icon ha-icon { --mdc-icon-size: 12px; }
        .name { flex: 1; min-width: 0; color: var(--primary-text-color); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; font-size: 0.95em; }
        .share { color: var(--secondary-text-color); font-size: 0.85em; width: 2.8em; text-align: right; flex: none; }
        .cost { color: var(--primary-text-color); font-weight: 500; white-space: nowrap; text-align: right; min-width: 4em; font-size: 0.95em; }
        .row .trend, .row .chevron { width: 12px; }
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

  /**
   * Open the history of a category, open or close its sub-categories with
   * its chevron, go back to the categories, or select a bar of the history.
   */
  _clicked(event) {
    const target = event.target;
    if (target.closest?.(".back")) {
      this._history = null;
      this._signature = null;
      this._render();
      return;
    }
    if (target.closest?.(".more-categories")) {
      this._expanded = !this._expanded;
      this._signature = null;
      this._render();
      return;
    }
    const bar = target.closest?.(".bar");
    if (bar) {
      const index = Number(bar.dataset.index);
      this._selected = this._selected === index ? null : index;
      this._signature = null;
      this._render();
      return;
    }
    const row = target.closest?.(".row");
    if (!row) {
      return;
    }
    const id = row.dataset.id;
    if (target.closest(".toggle")) {
      if (this._open.has(id)) {
        this._open.delete(id);
      } else {
        this._open.add(id);
      }
      this._signature = null;
      this._render();
      return;
    }
    const analysis = this._cache.get(this._key());
    const categories = (analysis?.categories || []).flatMap((category) => [
      category, ...(category.children || []).map((child) => ({ ...child, color: child.color || category.color })),
    ]);
    const category = categories.find((item) => String(item.id) === id);
    if (category) {
      const start = this._start || analysis.start || "";
      this._showHistory(category, Number(start.slice(0, 4)) || new Date().getFullYear());
    }
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
    const analysis = this._history ? this._historyData() : this._analysis();
    const signature = JSON.stringify([
      this._period, this._start, this._history, this._selected, analysis, [...this._open], this._expanded,
      this._config.title, this._config.max_categories, locale,
    ]);
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
      button.classList.toggle("active", !this._history && button.dataset.period === this._period);
    }
    if (this._history) {
      root.querySelector(".name").textContent = String(this._history.year);
      root.querySelector(".previous").disabled = false;
      root.querySelector(".next").disabled = this._history.year >= new Date().getFullYear();
      root.querySelector(".body").innerHTML = this._historyBody(analysis, locale, text);
      return;
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
    const max = maxCategories(this._config);
    const shown = shownCategories(categories, max, this._expanded);
    const rows = shown.map((category) => {
      const children = category.children || [];
      const open = this._open.has(String(category.id));
      const trend = category.trend
        ? `<span class="trend" title="${escapeHtml(text[category.trend])}" style="color: ${TREND_COLORS[category.trend]}">${category.trend === "up" ? "↑" : "↓"}</span>`
        : `<span class="trend"></span>`;
      const chevron = children.length ? `<span class="chevron toggle" role="button">›</span>` : `<span class="chevron"></span>`;
      const parent = this._row(category, lang, locale, children.length ? "parent" : "", open, trend + chevron);
      const details = open
        ? children.map((child) => this._row({ ...child, color: child.color || category.color }, lang, locale, "child", false, `<span class="trend"></span><span class="chevron"></span>`)).join("")
        : "";
      return parent + details;
    }).join("");
    const toggle = max > 0 && categories.length > max
      ? `<button class="more-categories">${escapeHtml(this._expanded
        ? text.show_less : text.show_all.replace("{n}", categories.length))}</button>`
      : "";
    return `<div class="layout">${ring}<div class="rows">${rows}${toggle}</div></div>`;
  }

  /** Return the HTML of the history of a category: a bar a week. */
  _historyBody(history, locale, text) {
    const lang = language(this._hass);
    const category = this._history.category;
    const head = `
      <div class="history-head">
        <button class="back" aria-label="${escapeHtml(text.back)}">‹</button>
        <div class="icon" style="background: ${escapeHtml(category.color || "#9e9e9e")}; color: ${iconColor(category.color)}"><ha-icon icon="${categoryIcon(category)}"></ha-icon></div>
        <div class="label">${escapeHtml(categoryName(lang, category))}</div>
      </div>`;
    if (history.loading) {
      return `${head}<div class="message">…</div>`;
    }
    if (history.error) {
      return `${head}<div class="message">${escapeHtml(text.history_error)}</div>`;
    }
    const bars = history.bars || [];
    const totals = historyTotals(bars);
    const { bars: rects, ticks, zero } = historyGeometry(bars.map((bar) => bar.cost));
    const format = new Intl.NumberFormat(locale, { maximumFractionDigits: 2 });
    const color = escapeHtml(category.color || "#9e9e9e");
    const grid = ticks.map((tick) => `
      <line class="grid" x1="${HISTORY.left}" x2="${HISTORY.width - HISTORY.right}" y1="${tick.y}" y2="${tick.y}" />
      <text class="tick" x="${HISTORY.left - 4}" y="${tick.y}">${escapeHtml(`${format.format(tick.value)} €`)}</text>`).join("");
    const columns = rects.map((rect, index) => `
      <g class="bar${index === this._selected ? " selected" : ""}" data-index="${index}">
        <rect class="hit" x="${rect.x - (rect.slot - rect.width) / 2}" y="${HISTORY.top}" width="${rect.slot}" height="${zero - HISTORY.top}" />
        <rect class="value" x="${rect.x}" y="${rect.y}" width="${rect.width}" height="${rect.height}" fill="${color}" />
      </g>`).join("");
    const months = monthLabels(locale, bars).map((month) =>
      `<text class="month" x="${rects[month.index]?.x ?? 0}" y="${HISTORY.height - 4}">${escapeHtml(month.label)}</text>`).join("");
    const bar = this._selected === null ? null : bars[this._selected];
    const details = bar
      ? text.bar
        .replace("{name}", text.week_of.replace("{date}", new Intl.DateTimeFormat(locale, {
          day: "numeric", month: "long", timeZone: "UTC",
        }).format(utcDate(bar.date))))
        .replace("{cost}", formatValue(locale, bar.cost, "eur"))
        .replace("{energy}", formatValue(locale, bar.consumption, "kwh"))
      : "";
    return `${head}
      <div class="history-total"><span class="cost">${escapeHtml(formatValue(locale, totals.cost, "eur"))}</span> | ${escapeHtml(formatValue(locale, totals.consumption, "kwh"))}</div>
      <div class="details">${escapeHtml(details)}</div>
      <svg class="chart" viewBox="0 0 ${HISTORY.width} ${HISTORY.height}" role="img" aria-label="${escapeHtml(text.history)}">
        ${grid}<line class="zero" x1="${HISTORY.left}" x2="${HISTORY.width - HISTORY.right}" y1="${zero}" y2="${zero}" />${columns}${months}
      </svg>`;
  }

  /** Return the HTML of a row of a category. */
  _row(category, lang, locale, kind, open, end) {
    // One line a category; its energy is in its history, shown on a touch
    const name = categoryName(lang, category);
    const energy = formatValue(locale, category.consumption, "kwh");
    return `
      <div class="row ${kind}${open ? " open" : ""}" data-id="${escapeHtml(category.id)}" title="${escapeHtml(`${name} · ${energy}`)}">
        <div class="icon" style="background: ${escapeHtml(category.color || "#9e9e9e")}; color: ${iconColor(category.color)}"><ha-icon icon="${categoryIcon(category)}"></ha-icon></div>
        <div class="name">${escapeHtml(name)}</div>
        <div class="share">${escapeHtml(formatPercent(locale, category.percentage))}</div>
        <div class="cost">${escapeHtml(formatValue(locale, category.cost, "eur"))}</div>
        ${end}
      </div>`;
  }
}

class LittleMonkeyActivationsCard extends HTMLElement {
  setConfig(config) {
    if (!config) {
      throw new Error("Invalid configuration");
    }
    const entity = this._config?.entity;
    this._config = { ...config };
    if (!this._pages || entity !== this._config.entity) {
      // Pages read: 0 for the last 48 hours, 1 for the 48 hours before...
      this._pages = [];
      this._loaded = 0;
      // Page shown by the timelines, and the activation selected
      this._page = 0;
      this._selected = null;
      this._expanded = false;
    }
    this._built = false;
    this._render();
  }

  set hass(hass) {
    const first = !this._hass;
    this._hass = hass;
    if (first) {
      this._read(0);
    }
    this._render();
  }

  connectedCallback() {
    clearInterval(this._timer);
    this._timer = setInterval(() => this._read(0), ACTIVATIONS_REFRESH);
  }

  disconnectedCallback() {
    clearInterval(this._timer);
  }

  getCardSize() {
    // Masonry view: rows of 50 pixels, for two or three timelines
    return 5;
  }

  getGridOptions() {
    // The whole width of a section (12 columns): a list or a chart is cut
    // in half a section. The height follows the content
    return { columns: 12, min_columns: 6 };
  }

  static getConfigElement() {
    return document.createElement(ACTIVATIONS_EDITOR_TYPE);
  }

  static getStubConfig(hass) {
    return activationsStubConfig(hass);
  }

  _text() {
    return TRANSLATIONS[language(this._hass)].activations;
  }

  /** Read a page of activations: the first one again, or an older one. */
  async _read(page) {
    if (!this._hass || !this._config?.entity || this._reading === page) {
      return;
    }
    this._reading = page;
    try {
      const answer = await callService(this._hass, this._config.entity, "get_activations", { page });
      this._pages[page] = answer;
      this._loaded = Math.max(this._loaded, page + 1);
      this._error = false;
    } catch (error) {
      console.debug("Little Monkey card: activations not read", error);
      this._error = true;
    } finally {
      this._reading = null;
      this._signature = null;
      this._render();
    }
  }

  /** Show the 48 hours before (+1) or after (-1) the ones shown. */
  _go(step) {
    const page = Math.max(this._page + step, 0);
    this._page = page;
    this._selected = null;
    if (!this._pages[page]) {
      this._read(page);
    }
    this._signature = null;
    this._render();
  }

  _build() {
    if (!this.shadowRoot) {
      this.attachShadow({ mode: "open" });
    }
    this.shadowRoot.innerHTML = `
      <style>
        ${STYLES}
        .header { display: flex; justify-content: space-between; align-items: baseline; gap: 8px; }
        .count { color: var(--secondary-text-color); font-size: 0.85em; white-space: nowrap; }
        .day { margin: 10px 0 2px; color: var(--secondary-text-color); font-size: 0.85em; font-weight: 500; }
        .day:first-child { margin-top: 0; }
        .timeline { width: 100%; height: 48px; display: block; touch-action: pan-y; }
        .timeline .base { stroke: var(--divider-color, #e0e0e0); stroke-width: 2; vector-effect: non-scaling-stroke; }
        .timeline .tick { stroke: var(--divider-color, #e0e0e0); stroke-width: 1; stroke-dasharray: 2 3; vector-effect: non-scaling-stroke; }
        .timeline .pulse { cursor: pointer; }
        .timeline .hit { fill: transparent; }
        .timeline .pulse.selected .value { stroke: var(--primary-text-color); stroke-width: 2; vector-effect: non-scaling-stroke; }
        .hours-axis { display: flex; justify-content: space-between; font-size: 0.75em; color: var(--secondary-text-color); }
        .selection { border-top: 1px solid var(--divider-color, #e0e0e0); margin-top: 10px; padding-top: 8px;
          display: flex; justify-content: space-between; flex-wrap: wrap; gap: 2px 12px; font-size: 0.9em; }
        .selection .when { color: var(--primary-text-color); font-weight: 500; }
        .selection .dim { color: var(--secondary-text-color); font-weight: 400; }
        .nav { margin-top: 6px; }
        .nav button { font-size: 0.9em; }
        .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(min(290px, 100%), 1fr)); gap: 8px; }
        .item { display: grid; grid-template-columns: 40px max-content minmax(0, 1fr); grid-template-rows: auto auto; column-gap: 10px; align-items: center;
          border: 1px solid var(--divider-color, #e0e0e0); border-radius: 12px; padding: 8px 10px; }
        .shape { grid-row: span 2; width: 40px; height: 20px; }
        .item .hours { color: var(--primary-text-color); font-weight: 500; font-size: 0.95em; }
        .item .energy { color: var(--primary-text-color); font-weight: 500; font-size: 0.95em; text-align: right; }
        .item .duration, .item .power { color: var(--secondary-text-color); font-size: 0.85em; }
        .item > * { min-width: 0; }
        .body { container-type: inline-size; }
        /* A narrow card keeps the power and leaves out its word */
        @container (max-width: 330px) { .power .word { display: none; } }
        .item .hours, .item .energy, .item .duration, .item .power { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
        .item .power { text-align: right; }
        .more { display: block; margin: 12px auto 0; border: 1px solid var(--divider-color, #e0e0e0); border-radius: 18px; background: none;
          color: var(--primary-text-color); font: inherit; font-size: 0.9em; padding: 6px 14px; cursor: pointer; }
        .more:disabled { opacity: 0.5; cursor: default; }
      </style>
      <ha-card>
        <div class="header"><div class="title"></div><div class="count"></div></div>
        <div class="warning"></div>
        <div class="body"></div>
      </ha-card>`;
    const body = this.shadowRoot.querySelector(".body");
    body.addEventListener("click", (event) => {
      const target = event.target;
      const pulse = target.closest?.(".pulse");
      if (pulse) {
        this._selected = pulse.dataset.start;
        this._signature = null;
        this._render();
      } else if (target.closest?.(".older")) {
        this._go(1);
      } else if (target.closest?.(".newer")) {
        this._go(-1);
      } else if (target.closest?.(".more")) {
        // The list: everything read, then 48 hours more
        if (this._expanded) {
          this._read(this._loaded);
        }
        this._expanded = true;
        this._signature = null;
        this._render();
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
    const locale = this._hass.locale?.language || this._hass.language;
    const mode = activationsMode(this._config);
    const activations = mode === "list"
      ? mergeActivations(this._pages)
      : mergeActivations([this._pages[this._page]]);
    const signature = JSON.stringify([
      mode, activations, this._page, this._selected, this._expanded, this._error, this._reading, this._loaded,
      this._config.title, locale,
    ]);
    if (signature === this._signature) {
      return;
    }
    this._signature = signature;
    const root = this.shadowRoot;
    root.querySelector(".title").textContent = this._config.title || text.title;
    root.querySelector(".count").textContent = mode === "timeline" && activations.length
      ? text.count.replace("{n}", activations.length) : "";
    const missing = !this._config.entity || !this._hass.states[this._config.entity];
    const warning = root.querySelector(".warning");
    warning.textContent = missing ? text.missing : "";
    warning.style.display = missing ? "" : "none";
    const body = root.querySelector(".body");
    if (!activations.length) {
      const read = mode === "list" ? this._loaded : this._pages[this._page];
      const message = this._error ? text.error : read ? text.none : "…";
      body.innerHTML = `<div class="message">${escapeHtml(message)}</div>${mode === "timeline" ? this._nav(text, locale) : ""}`;
      return;
    }
    body.innerHTML = mode === "list"
      ? this._list(activations, text, locale)
      : this._timelines(activations, text, locale);
  }

  /** Return the HTML of the arrows between the pages of 48 hours, and their days. */
  _nav(text, locale) {
    const page = this._pages[this._page];
    let name = "";
    if (page?.start && page?.end) {
      const format = new Intl.DateTimeFormat(locale, { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit", timeZone: "UTC" });
      // The times of ecojoko are in its time zone: shown as they are written
      const asWritten = (iso) => new Date(`${iso.slice(0, 19)}Z`);
      name = format.formatRange(asWritten(page.start), asWritten(page.end));
    }
    return `
      <div class="nav">
        <button class="older" aria-label="${escapeHtml(text.older)}">‹</button>
        <div class="name">${escapeHtml(name)}</div>
        <button class="newer" aria-label="${escapeHtml(text.newer)}"${this._page ? "" : " disabled"}>›</button>
      </div>`;
  }

  /** Return the HTML of the timelines of the days, and of the activation selected. */
  _timelines(activations, text, locale) {
    const selected = activations.find((activation) => activation.start === this._selected) || activations[0];
    const grid = [360, 720, 1080].map((minutes) =>
      `<line class="tick" x1="${minutes}" x2="${minutes}" y1="4" y2="${TIMELINE.base}" />`).join("");
    const days = timelines(activations).map((day) => {
      const pulses = day.pulses.map((pulse) => {
        // A short activation is easier to touch with a wider area
        const hit = Math.max(pulse.width, TIMELINE.hit);
        return `<g class="pulse${pulse.start === selected.start ? " selected" : ""}" data-start="${escapeHtml(pulse.start)}">
          <rect class="hit" x="${(pulse.x + pulse.width / 2 - hit / 2).toFixed(1)}" y="0" width="${hit}" height="${TIMELINE.base}" />
          <rect class="value" x="${pulse.x.toFixed(1)}" y="${pulse.y.toFixed(1)}" width="${pulse.width.toFixed(1)}" height="${pulse.height.toFixed(1)}" fill="${pulse.color}" />
        </g>`;
      }).join("");
      return `
        <div class="day">${escapeHtml(dayLabel(locale, day.day))}</div>
        <svg class="timeline" viewBox="0 0 ${TIMELINE.width} ${TIMELINE.height}" preserveAspectRatio="none" role="img" aria-label="${escapeHtml(dayLabel(locale, day.day))}">
          ${grid}<line class="base" x1="0" x2="${TIMELINE.width}" y1="${TIMELINE.base}" y2="${TIMELINE.base}" />${pulses}
        </svg>
        <div class="hours-axis"><span>0h</span><span>6h</span><span>12h</span><span>18h</span><span>24h</span></div>`;
    }).join("");
    const power = new Intl.NumberFormat(locale, { maximumFractionDigits: 0 });
    const day = new Intl.DateTimeFormat(locale, { weekday: "short", day: "numeric", month: "short", timeZone: "UTC" })
      .format(utcDate(selected.start.slice(0, 10)));
    const selection = `
      <div class="selection">
        <span class="when">${escapeHtml(timeRange(selected))} <span class="dim">· ${escapeHtml(day)} · ${escapeHtml(durationLabel(text, selected))}</span></span>
        <span>${escapeHtml(formatValue(locale, selected.energy, "kwh"))} <span class="dim">· ${
          escapeHtml(text.average.replace("{power}", `${power.format(selected.power ?? 0)} W`))}</span></span>
      </div>`;
    return days + selection + this._nav(text, locale);
  }

  /** Return the HTML of the list of the activations, the most recent first. */
  _list(activations, text, locale) {
    const shown = this._expanded ? activations : activations.slice(0, LIST_LENGTH);
    const power = new Intl.NumberFormat(locale, { maximumFractionDigits: 0 });
    const days = groupByDay(shown).map((group) => `
      <div class="day">${escapeHtml(dayLabel(locale, group.day))}</div>
      <div class="grid">${group.activations.map((activation) => `
        <div class="item">
          ${shapeSvg(activation.shape)}
          <div class="hours">${escapeHtml(timeRange(activation))}</div>
          <div class="energy">${escapeHtml(formatValue(locale, activation.energy, "kwh"))}</div>
          <div class="duration">${escapeHtml(durationLabel(text, activation))}</div>
          <div class="power"><span class="word">${escapeHtml(text.average.replace("{power}", "").trim())} </span>${
            escapeHtml(`${power.format(activation.power ?? 0)} W`)}</div>
        </div>`).join("")}
      </div>`).join("");
    const busy = this._reading !== null && this._reading !== undefined;
    const label = this._expanded ? text.more : text.show_more;
    return `${days}<button class="more"${busy ? " disabled" : ""}>${escapeHtml(label)}</button>`;
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

class LittleMonkeyActivationsCardEditor extends AnalysisEditor {
  _schema() {
    return activationsSchema(this._hass);
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
defineCard(
  ACTIVATIONS_TYPE, LittleMonkeyActivationsCard,
  ACTIVATIONS_EDITOR_TYPE, LittleMonkeyActivationsCardEditor, "activations",
);
