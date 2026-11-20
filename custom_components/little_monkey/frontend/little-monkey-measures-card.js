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
 * production injected under the axis. The temperature and the humidity,
 * inside and outside, are curves read from the statistics of the sensors of
 * Home Assistant when they exist, from ecojoko otherwise.
 */

const DOMAIN = "little_monkey";
const MEASURES_TYPE = "little-monkey-measures-card";
const MEASURES_EDITOR_TYPE = "little-monkey-measures-card-editor";
const DOCUMENTATION =
  "https://github.com/jmcruvellier/little_monkey/blob/main/docs/cartes.md#mesures";
// The measures of the current period are read again every five minutes
const MEASURES_REFRESH = 300000;

const TRANSLATIONS = {
  en: {
    name: "Little Monkey measures",
    description: "The measures of ecojoko: power of the day and energy by tariff band, in kWh or euros.",
    title: "Measures",
    measures: { electricity: "Electricity", temperature: "Temperature", humidity: "Humidity" },
    inside: "Inside",
    outside: "Outside",
    climate_total: "Average {value}",
    climate_at: "{time}: inside {inside} · outside {outside}",
    periods: { day: "Day", week: "Week", month: "Month", year: "Year" },
    previous: "Previous period",
    next: "Next period",
    base: "Base load",
    production: "Surplus",
    purchase: "Purchase",
    resale: "Resale",
    total_label: "{label}: ",
    power_at: "{time}: {power}",
    bar: "{name}: {values}",
    error: "Measures not read",
    empty: "No measure for this period",
    missing: "Little Monkey sensor not found",
    option: "Turn on the “Measures” option in the options of the Little Monkey integration (Settings › Devices & services › Little Monkey › Configure).",
    editor: {
      entity: "A sensor of the Little Monkey device",
      period: "Period shown first",
      measure: "Measure shown first",
      unit: "Unit of the bars",
      units: { kwh: "kWh", eur: "Euros" },
      title: "Title",
    },
  },
  fr: {
    name: "Petit Singe : mesures",
    description: "Les mesures d'ecojoko : la puissance du jour et l'énergie par tranche tarifaire, en kWh ou en euros.",
    title: "Mesures",
    measures: { electricity: "Électricité", temperature: "Température", humidity: "Humidité" },
    inside: "Intérieur",
    outside: "Extérieur",
    climate_total: "Moyenne {value}",
    climate_at: "{time} : intérieur {inside} · extérieur {outside}",
    periods: { day: "Jour", week: "Semaine", month: "Mois", year: "Année" },
    previous: "Période précédente",
    next: "Période suivante",
    base: "Talon",
    production: "Surplus",
    purchase: "Achat",
    resale: "Revente",
    total_label: "{label} : ",
    power_at: "{time} : {power}",
    bar: "{name} : {values}",
    error: "Mesures non lues",
    empty: "Aucune mesure sur cette période",
    missing: "Capteur Little Monkey introuvable",
    option: "Activez l'option « Mesures » dans les options de l'intégration Little Monkey (Paramètres › Appareils et services › Little Monkey › Configurer).",
    editor: {
      entity: "Un capteur de l'appareil Little Monkey",
      period: "Période affichée d'abord",
      measure: "Mesure affichée d'abord",
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
// Colors of the totals of the period: the energy as the bars, the surplus as
// its legend, the cost apart from both, and the amount of the surplus sold
// in the green of the savings. Mixed with the color of the text, as on the
// savings cards, to be read on a light or a dark theme
const TOTAL_COLORS = { kwh: "#0087b1", production: "#ffcc47", eur: "#e8836b", resale: "#5fdcab" };
const TOTAL_MIX = { kwh: 65, production: 80, eur: 65, resale: 65 };

/**
 * Tell whether the surplus of the installation is sold: the Contract sensor
 * of its device gives then the price of a kWh sold.
 */
export function hasResaleContract(hass, entityId) {
  const entities = hass?.entities || {};
  const deviceId = entities[entityId]?.device_id;
  if (!deviceId) {
    return false;
  }
  const contract = Object.values(entities).find((entity) =>
    entity.device_id === deviceId && entity.platform === DOMAIN && entity.translation_key === "contract");
  return Number(hass.states?.[contract?.entity_id]?.attributes?.resale_price) > 0;
}

/** Return a color of a total, mixed with the color of the text. */
function totalColor(key) {
  return `color-mix(in srgb, ${TOTAL_COLORS[key]} ${TOTAL_MIX[key]}%, var(--primary-text-color, #212121))`;
}

/**
 * Return the HTML of the totals of a period of electricity: its energy and
 * its cost, the unit of the bars first, and the surplus injected between
 * them when there is one.
 *
 * When the surplus is sold, two lines instead: the energy and the cost
 * bought (« Achat »), then the surplus and the amount it was sold for
 * (« Revente »).
 */
export function electricityTotal(measures, unit, locale, text, resale = false) {
  const values = { kwh: formatValue(locale, measures?.energy, "kwh"), eur: formatValue(locale, measures?.cost, "eur") };
  const other = unit === "eur" ? "kwh" : "eur";
  const value = (key, content, title = "") =>
    `<span class="${key}" style="color: ${totalColor(key)}"${title ? ` title="${escapeHtml(title)}"` : ""}>${escapeHtml(content)}</span>`;
  const separator = ' <span class="separator">|</span> ';
  if (resale) {
    const sold = {
      kwh: value("production", formatValue(locale, measures?.production ?? 0, "kwh")),
      eur: value("resale", formatValue(locale, measures?.resale ?? 0, "eur")),
    };
    const line = (label, first, second) => `<div class="line"><span class="line-label">${
      escapeHtml(text.total_label.replace("{label}", label))}</span>${first}${separator}${second}</div>`;
    return line(text.purchase, `<span class="main">${value(unit, values[unit])}</span>`, value(other, values[other]))
      + line(text.resale, `<span class="main">${sold[unit]}</span>`, sold[other]);
  }
  const parts = [`<span class="main">${value(unit, values[unit])}</span>`];
  if (Number(measures?.production) > 0) {
    parts.push(value("production", formatValue(locale, measures.production, "kwh"), text.production));
  }
  parts.push(`<span class="other">${value(other, values[other])}</span>`);
  return parts.join(separator);
}
// Heures Pleines (2) and Heures Creuses (3) of ecojoko: the off-peak hours
// dark and the peak hours light, as on the other cards. ecojoko gives them
// the other way round
const PEAK_COLORS = { 2: "#6BBED8", 3: "#0087B1" };
// Chart, in the units of the SVG
// The left margin holds the graduations with their unit ("600 kWh")
export const CHART = { width: 280, height: 160, left: 48, right: 4, top: 8, bottom: 20 };
const SWIPE_DISTANCE = 40;
const MINUTES_A_DAY = 1440;

export const MEASURES = ["electricity", "temperature", "humidity"];
// Colors of the curves, inside and outside
export const CLIMATE_COLORS = {
  temperature: { inside: "#f28c38", outside: "#7ed2df" },
  humidity: { inside: "#00b2e2", outside: "#a9bfd0" },
};
// Sensors of the Little Monkey device that measure the temperature and the
// humidity, inside and outside, by translation key
const CLIMATE_SENSORS = {
  temperature: { inside: "indoor_temp", outside: "outdoor_temp" },
  humidity: { inside: "indoor_hum", outside: "outdoor_hum" },
};
// Period of the statistics of Home Assistant read for each period shown
const STATISTICS_PERIODS = { day: "5minute", week: "hour", month: "hour", calendar: "hour", year: "day" };

/**
 * Return the period of the dates of a measure: the month is the calendar
 * month holding a date, for the electricity as for the temperature and the
 * humidity. ecojoko answers with it, day by day, whatever the day asked.
 */
export function datesPeriod(_measure, period) {
  return period === "month" ? "calendar" : period;
}

/**
 * Return the day of the first period ecojoko has, when it answered with it
 * instead of the period asked for, null otherwise.
 *
 * Asked for a period before its first measures, ecojoko does not answer an
 * empty period: it answers with the first one it has, whose start it gives.
 * Only a period starting after the end of the one asked for counts.
 */
export function firstPeriod(period, iso, measures) {
  const actual = typeof measures?.start === "string" ? measures.start.slice(0, 10) : null;
  if (!actual) {
    return null;
  }
  return actual >= localIso(periodRange(period, iso).end) ? actual : null;
}

/** Tell whether ecojoko has no period before the measures shown. */
export function isFirstPeriod(measures) {
  return measures?.previous === null;
}

/** Return the measure shown first by a card: the electricity by default. */
export function initialMeasure(config) {
  return MEASURES.includes(config?.measure) ? config.measure : "electricity";
}

/** Return a date as an ISO date, in the time zone of the browser. */
function localIso(date) {
  const pad = (value) => String(value).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
}

/** Return the day of the period before (-1) or after (+1) a period holding a day. */
export function shiftDate(period, iso, step) {
  const [year, month, day] = iso.split("-").map(Number);
  if (period === "year") {
    return localIso(new Date(year + step, month - 1, Math.min(day, 28)));
  }
  if (period === "calendar") {
    return localIso(new Date(year, month - 1 + step, Math.min(day, 28)));
  }
  const days = { day: 1, week: 7, month: 30 }[period];
  return localIso(new Date(year, month - 1, day + step * days));
}

/**
 * Tell whether the period holding a day is the current one, or a later one:
 * the month or the year of today, whatever the day in it.
 */
export function isCurrent(period, iso, now = today()) {
  if (period === "year") {
    return iso.slice(0, 4) >= now.slice(0, 4);
  }
  if (period === "calendar") {
    return iso.slice(0, 7) >= now.slice(0, 7);
  }
  return iso >= now;
}

/**
 * Return the bounds of a period holding a day, in the time zone of the
 * browser: the day, its week from Monday, the 30 days ending on it (the
 * « Mois » of ecojoko), or its year.
 */
export function periodRange(period, iso) {
  const [year, month, day] = iso.split("-").map(Number);
  if (period === "year") {
    return { start: new Date(year, 0, 1), end: new Date(year + 1, 0, 1) };
  }
  if (period === "calendar") {
    return { start: new Date(year, month - 1, 1), end: new Date(year, month, 1) };
  }
  if (period === "week") {
    const date = new Date(year, month - 1, day);
    const monday = new Date(year, month - 1, day - ((date.getDay() + 6) % 7));
    return { start: monday, end: new Date(monday.getFullYear(), monday.getMonth(), monday.getDate() + 7) };
  }
  if (period === "month") {
    return { start: new Date(year, month - 1, day - 29), end: new Date(year, month - 1, day + 1) };
  }
  return { start: new Date(year, month - 1, day), end: new Date(year, month - 1, day + 1) };
}

/** Return the sensors of the temperature or humidity of the device of an entity. */
export function climateEntities(hass, entityId, measure) {
  const entities = hass?.entities || {};
  const deviceId = entities[entityId]?.device_id;
  const wanted = CLIMATE_SENSORS[measure] || {};
  const found = {};
  for (const entity of Object.values(entities)) {
    if (entity.device_id !== deviceId || entity.platform !== DOMAIN) {
      continue;
    }
    for (const [side, key] of Object.entries(wanted)) {
      if (entity.translation_key === key) {
        found[side] = entity.entity_id;
      }
    }
  }
  return found;
}

/** Return the time of a statistic, given in milliseconds or as an ISO text. */
function statisticTime(value) {
  const time = typeof value === "number" ? new Date(value) : new Date(value);
  return Number.isNaN(time.getTime()) ? null : time.toISOString();
}

/** Return the curves of the statistics of Home Assistant, inside and outside. */
export function climateFromStatistics(statistics, entities, unit) {
  const points = new Map();
  for (const side of ["inside", "outside"]) {
    for (const item of statistics?.[entities[side]] || []) {
      const time = statisticTime(item.start);
      const value = Number(item.mean);
      if (time && Number.isFinite(value)) {
        points.set(time, { ...(points.get(time) || { time, inside: null, outside: null }), [side]: value });
      }
    }
  }
  return { unit, points: [...points.values()].sort((a, b) => a.time.localeCompare(b.time)) };
}

// Margin of the statistics at the start of a period: their first value may
// come a few minutes, hours or days after it
const STATISTICS_MARGIN = {
  day: 15 * 60000, week: 3 * 3600000, month: 3 * 3600000, calendar: 3 * 3600000, year: 2 * 86400000,
};

/**
 * Tell whether the statistics of Home Assistant cover a period from its
 * start. They begin when the sensor was created, and the short-term ones of
 * a day are kept for ten days only: before, the curves come from ecojoko,
 * which has the whole history of the sensor.
 */
export function statisticsCover(climate, range, period) {
  const first = climate?.points?.[0];
  return Boolean(first) && new Date(first.time).getTime() <= range.start.getTime() + STATISTICS_MARGIN[period];
}

/** Return the average of the inside values of curves, null without one. */
export function climateAverage(climate) {
  const values = (climate?.points || []).map((point) => point.inside).filter((value) => Number.isFinite(value));
  return values.length ? values.reduce((sum, value) => sum + value, 0) / values.length : null;
}

/** Return the lines of the curves of a period, inside and outside, and their scale. */
export function climateLines(climate, range, box = CHART) {
  const start = range.start.getTime();
  const length = range.end.getTime() - start;
  const plot = box.width - box.left - box.right;
  const x = (time) => box.left + ((new Date(time).getTime() - start) / length) * plot;
  const points = (climate?.points || []).filter((point) => {
    const time = new Date(point.time).getTime();
    return time >= start && time <= range.end.getTime();
  });
  const values = points.flatMap((point) => [point.inside, point.outside]).filter((value) => Number.isFinite(value));
  const low = Math.min(...values);
  const high = Math.max(...values);
  // Around the values, not from zero: a temperature varies by a few degrees
  const step = values.length ? niceStep(Math.max((high - low) / 4, 0.5)) : 1;
  const scale = values.length
    ? { min: Math.floor(low / step) * step, max: Math.ceil(high / step) * step || step, step }
    : { min: 0, max: 1, step: 0.5 };
  if (scale.max === scale.min) {
    scale.max += step;
  }
  const { y, ticks } = axis(scale, box);
  const line = (side) => {
    let path = "";
    let drawing = false;
    for (const point of points) {
      if (!Number.isFinite(point[side])) {
        drawing = false;
        continue;
      }
      path += `${drawing ? "L" : "M"}${x(point.time).toFixed(1)},${y(point[side]).toFixed(1)} `;
      drawing = true;
    }
    return path.trim();
  };
  return { inside: line("inside"), outside: line("outside"), ticks, x, points };
}

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
    colors[band.id] = PEAK_COLORS[band.id]
      ?? (/^#[0-9a-f]{3,8}$/i.test(band.color || "") ? band.color : MEASURE_COLORS.band);
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
  if (period === "calendar") {
    const text = new Intl.DateTimeFormat(locale, { month: "long", year: "numeric", timeZone: "UTC" }).format(date);
    return text.charAt(0).toUpperCase() + text.slice(1);
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
  // Short names, as the savings card: "lun.", "Mon"
  return new Intl.DateTimeFormat(locale, { weekday: "short", timeZone: "UTC" }).format(date);
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

/**
 * Return the label of a graduation with its unit: euros, kWh, or watts
 * (kW from 1 000 W, so that "6 kW" fits beside the chart).
 */
export function axisLabel(locale, value, unit) {
  const number = (amount, digits) => new Intl.NumberFormat(locale, { maximumFractionDigits: digits }).format(amount);
  if (unit === "eur") {
    return `${number(value, 2)} €`;
  }
  if (unit === "w") {
    return Math.abs(value) >= 1000 ? `${number(value / 1000, 1)} kW` : `${number(value, 0)} W`;
  }
  return `${number(value, 2)} kWh`;
}

/** Return a temperature or a humidity with its unit, "—" without it. */
export function climateValue(locale, value, unit) {
  if (value === null || value === undefined || !Number.isFinite(Number(value))) {
    return "—";
  }
  const number = new Intl.NumberFormat(locale, { maximumFractionDigits: 1 }).format(Number(value));
  return unit === "%" ? `${number} %` : `${number} ${unit || ""}`.trim();
}

/** Return the labels under the curves of a period: hours, days or months. */
export function climateLabels(locale, period, range) {
  const labels = [];
  const start = range.start;
  if (period === "day") {
    for (const hour of [0, 6, 12, 18, 24]) {
      labels.push({ time: new Date(start.getFullYear(), start.getMonth(), start.getDate(), hour).toISOString(),
        text: `${hour}h`, anchor: hour === 0 ? "start" : hour === 24 ? "end" : null });
    }
  } else if (period === "year") {
    for (let month = 0; month < 12; month += 1) {
      const date = new Date(start.getFullYear(), month, 15);
      labels.push({ time: date.toISOString(), text: new Intl.DateTimeFormat(locale, { month: "narrow" }).format(date) });
    }
  } else {
    const days = period === "week" ? 7 : Math.round((range.end - range.start) / 86400000);
    const every = period === "week" ? 1 : 5;
    for (let index = 0; index < days; index += every) {
      const date = new Date(start.getFullYear(), start.getMonth(), start.getDate() + index, 12);
      labels.push({ time: date.toISOString(), text: period === "week"
        ? new Intl.DateTimeFormat(locale, { weekday: "short" }).format(date) : String(date.getDate()) });
    }
  }
  return labels;
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
      name: "measure",
      selector: { select: { mode: "dropdown", options: MEASURES.map((value) => ({ value, label: text.measures[value] })) } },
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
  .total .separator { color: var(--secondary-text-color); }
  .total .line { text-align: right; }
  .total .line-label { color: var(--secondary-text-color); }
  .details { min-height: 1.4em; font-size: 0.85em; color: var(--secondary-text-color); text-align: center; }
  svg { width: 100%; display: block; touch-action: pan-y; user-select: none; }
  .tick { fill: var(--secondary-text-color, #727272); font-size: var(--lm-axis-font, 9.5px); text-anchor: end; dominant-baseline: central; }
  .grid { stroke: var(--divider-color, #e0e0e0); stroke-width: 0.5; }
  .zero { stroke: var(--secondary-text-color, #727272); stroke-width: 0.6; }
  .label { fill: var(--secondary-text-color, #727272); font-size: var(--lm-axis-font, 9.5px); text-anchor: middle; }
  .bar { cursor: pointer; }
  .bar rect.hit { fill: transparent; }
  .bar.selected .block { stroke: var(--primary-text-color); stroke-width: 0.8; }
  .cursor { stroke: var(--primary-text-color); stroke-width: 0.8; stroke-dasharray: 2 2; }
  .message { fill: var(--secondary-text-color, #727272); font-size: 10px; text-anchor: middle; }
  .legend { display: flex; flex-wrap: wrap; justify-content: center; gap: 2px 12px; font-size: 0.8em; color: var(--secondary-text-color); margin-top: 4px; }
  .legend .swatch { display: inline-block; width: 10px; height: 10px; border-radius: 2px; margin-right: 4px; vertical-align: -1px; }
  .legend .value { color: var(--primary-text-color); }
  .legend .entity { cursor: pointer; }
  .message-option { color: var(--secondary-text-color); text-align: center; padding: 0 8px; }
  ha-card.disabled .message-option { padding: 24px 8px; }
  ha-card.disabled .tabs, ha-card.disabled .top, ha-card.disabled svg, ha-card.disabled .nav { display: none; }
  .nav { display: flex; align-items: center; justify-content: space-between; margin-top: 4px; }
  .nav button { border: none; background: none; color: var(--primary-text-color); cursor: pointer; padding: 4px 10px; font-size: 1.4em; line-height: 1; }
  .nav button:disabled { visibility: hidden; }
  .nav .name { font-size: 0.95em; color: var(--primary-text-color); text-align: center; }
`;

// Axis labels: 0.75 em, as the hours of the timelines of the activations,
// never above the size the margins of the charts are made for
const AXIS_SCALE = 0.75;
const AXIS_FONT = 9.5;

/**
 * Return the size of the axis labels in units of a chart, to show them at
 * 0.75 em. A chart is drawn in a box of fixed width: it grows with the card,
 * and its text with it.
 */
export function axisFontSize(width, boxWidth, fontSize) {
  if (!(width > 0) || !(fontSize > 0)) {
    return AXIS_FONT;
  }
  return Math.min(AXIS_FONT, Math.round((AXIS_SCALE * fontSize * boxWidth / width) * 10) / 10);
}

/** Size the axis labels of a chart for its width, on its card. */
function fitAxisLabels(host, svg, boxWidth) {
  const width = svg?.getBoundingClientRect().width;
  if (!width) {
    return;
  }
  const size = axisFontSize(width, boxWidth, parseFloat(getComputedStyle(svg).fontSize));
  host.style.setProperty("--lm-axis-font", `${size}px`);
}

class LittleMonkeyMeasuresCard extends HTMLElement {
  setConfig(config) {
    if (!config) {
      throw new Error("Invalid configuration");
    }
    const entity = this._config?.entity;
    this._config = { ...config };
    const changed = !this._cache || entity !== this._config.entity;
    if (changed) {
      this._cache = new Map();
      this._period = initialPeriod(this._config);
      this._measure = initialMeasure(this._config);
      // Day of the period shown, by period: today until the user moves
      this._dates = {};
      this._selected = null;
    }
    this._built = false;
    // Built again, the card is empty: it is drawn even if nothing changed
    this._signature = null;
    if (changed) {
      // Another installation: its measures are read at once
      this._fetch();
    }
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
    // What is asked for, kept while it is read: the user may show another
    // measure or period meanwhile
    const request = { measure: this._measure, period: this._period, date: this._date() };
    const key = this._key();
    const cached = this._cache.get(key);
    // A reading that failed is tried again
    const read = cached && !cached.error;
    if (!this._hass || !this._config?.entity || (read && !force) || cached?.loading) {
      return;
    }
    this._cache.set(key, { ...cached, loading: true });
    const entities = request.measure === "electricity"
      ? {} : climateEntities(this._hass, this._config.entity, request.measure);
    if ((entities.inside || entities.outside) && !(await this._enabled(request))) {
      // Without the option of the measures, not even the statistics
      this._cache.set(key, { measures: { enabled: false } });
      this._signature = null;
      this._render();
      return;
    }
    if (entities.inside || entities.outside) {
      await this._fetchStatistics(key, entities, cached, request);
      return;
    }
    await this._fetchService(key, cached, request);
  }

  /** Tell whether the option of the measures is on, asked once to the service. */
  async _enabled(request) {
    if (this._optionEnabled === undefined) {
      const data = { measure: request.measure, period: request.period, check: true };
      const entry = configEntryId(this._hass, this._config.entity);
      if (entry) {
        data.config_entry_id = entry;
      }
      try {
        const result = await this._hass.callWS({
          type: "call_service", domain: DOMAIN, service: "get_measures", service_data: data, return_response: true,
        });
        this._optionEnabled = result.response?.enabled !== false;
      } catch (error) {
        console.debug("Little Monkey card: option of the measures not read", error);
        return true;
      }
    }
    return this._optionEnabled;
  }

  /** Read the measures of the period from ecojoko, with the service get_measures. */
  async _fetchService(key, cached, request) {
    const data = { measure: request.measure, period: request.period, date: request.date };
    const entry = configEntryId(this._hass, this._config.entity);
    if (entry) {
      data.config_entry_id = entry;
    }
    try {
      const result = await this._hass.callWS({
        type: "call_service", domain: DOMAIN, service: "get_measures", service_data: data, return_response: true,
      });
      const period = datesPeriod(request.measure, request.period);
      const first = firstPeriod(period, request.date, result.response);
      if (first) {
        // Nothing before the first period of ecojoko: it is shown instead
        // of the one asked for, under its own date
        this._cache.delete(key);
        let shown = `${request.measure}:${request.period}:${first}`;
        if (this._key() === key) {
          this._dates[request.period] = isCurrent(period, first) ? undefined : first;
          shown = this._key();
        }
        this._cache.set(shown, { measures: result.response });
      } else {
        this._cache.set(key, { measures: result.response });
      }
    } catch (error) {
      console.debug("Little Monkey card: measures not read", error);
      this._cache.set(key, cached?.measures ? cached : { error: true });
    }
    this._signature = null;
    this._render();
  }

  /** Read the temperature or humidity of the period from the statistics of the sensors. */
  async _fetchStatistics(key, entities, cached, request) {
    const period = datesPeriod(request.measure, request.period);
    const range = periodRange(period, request.date);
    const ids = Object.values(entities);
    try {
      const statistics = await this._hass.callWS({
        type: "recorder/statistics_during_period",
        start_time: range.start.toISOString(),
        end_time: range.end.toISOString(),
        statistic_ids: ids,
        period: STATISTICS_PERIODS[period],
        types: ["mean"],
      });
      const unit = this._hass.states[ids[0]]?.attributes?.unit_of_measurement
        || (request.measure === "temperature" ? "°C" : "%");
      const climate = climateFromStatistics(statistics, entities, unit);
      if (statisticsCover(climate, range, period)) {
        this._cache.set(key, { measures: climate, entities });
        this._signature = null;
        this._render();
        return;
      }
    } catch (error) {
      console.debug("Little Monkey card: statistics not read", error);
    }
    // Home Assistant has not recorded the whole period: ecojoko has it
    await this._fetchService(key, cached, request);
  }

  _chooseMeasure(measure) {
    if (measure !== this._measure) {
      this._measure = measure;
      this._selected = null;
      this._fetch();
      this._signature = null;
      this._render();
    }
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

  /** Show the period before (-1) or after (+1). */
  _go(step) {
    const period = datesPeriod(this._measure, this._period);
    const date = shiftDate(period, this._date(), step);
    if (step > 0 && !this._dates[this._period]) {
      return;
    }
    if (step < 0 && isFirstPeriod(this._cache.get(this._key())?.measures)) {
      return;
    }
    this._dates[this._period] = isCurrent(period, date) ? undefined : date;
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
    const tabs = MEASURES.map((measure) =>
      `<button class="tab" data-measure="${measure}">${escapeHtml(text.measures[measure])}</button>`).join("");
    const periods = PERIODS.map((period) =>
      `<button class="period" data-period="${period}">${escapeHtml(text.periods[period])}</button>`).join("");
    this.shadowRoot.innerHTML = `
      <style>${STYLES}</style>
      <ha-card>
        <div class="title"></div>
        <div class="warning"></div>
        <div class="tabs">${tabs}</div>
        <div class="top"><div class="periods">${periods}</div><div class="total"></div></div>
        <div class="message-option"></div>
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
    for (const button of root.querySelectorAll(".tab")) {
      button.addEventListener("click", () => this._chooseMeasure(button.dataset.measure));
    }
    root.querySelector(".previous").addEventListener("click", () => this._go(-1));
    root.querySelector(".next").addEventListener("click", () => this._go(1));
    const svg = root.querySelector("svg");
    svg.addEventListener("click", (event) => this._select(event, svg));
    this._axisObserver?.disconnect();
    this._axisObserver = new ResizeObserver(() => fitAxisLabels(this, svg, CHART.width));
    this._axisObserver.observe(svg);
    root.querySelector(".legend").addEventListener("click", (event) => {
      const item = event.target.closest?.("[data-entity]");
      if (item) {
        this.dispatchEvent(new CustomEvent("hass-more-info", {
          detail: { entityId: item.dataset.entity }, bubbles: true, composed: true,
        }));
      }
    });
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
    } else if (this._period === "day" || this._measure !== "electricity") {
      // A share of the period, from 0 to 1
      const box = svg.getBoundingClientRect();
      const x = ((event.clientX - box.left) / box.width) * CHART.width;
      const share = (x - CHART.left) / (CHART.width - CHART.left - CHART.right);
      this._selected = share >= 0 && share <= 1 ? share : null;
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
    for (const button of root.querySelectorAll(".tab")) {
      button.classList.toggle("active", button.dataset.measure === this._measure);
    }
    const measures = shown.measures;
    root.querySelector("ha-card").classList.toggle("disabled", measures?.enabled === false);
    if (measures?.enabled === false) {
      root.querySelector(".total").innerHTML = "";
      root.querySelector(".details").textContent = "";
      root.querySelector(".legend").innerHTML = "";
      root.querySelector("svg").innerHTML = "";
      root.querySelector(".message-option").textContent = text.option;
      return;
    }
    root.querySelector(".message-option").textContent = "";
    const period = datesPeriod(this._measure, this._period);
    root.querySelector(".name").textContent = periodLabel(
      locale, period, this._measure === "electricity" && measures?.start
        ? measures.start : localIso(periodRange(period, this._date()).start));
    // ecojoko has nothing before its first period
    root.querySelector(".previous").disabled = isFirstPeriod(measures);
    root.querySelector(".next").disabled = !this._dates[this._period];
    const total = root.querySelector(".total");
    const average = this._measure === "electricity" ? null : climateAverage(measures);
    total.innerHTML = this._measure !== "electricity"
      ? (average === null ? "" : `<span class="main">${escapeHtml(text.climate_total.replace(
        "{value}", climateValue(locale, average, measures.unit)))}</span>`)
      : measures
      ? this._total(measures, unit, locale)
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
    if (this._measure !== "electricity") {
      this._renderClimate(measures, svg, details, legend, text, locale);
    } else if (this._period === "day") {
      this._renderDay(measures, svg, details, legend, text, locale);
    } else {
      this._renderBars(measures, unit, svg, details, legend, text, locale);
    }
  }

  /** Return the HTML of the energy and the cost of a period, the unit of the bars first. */
  _total(measures, unit, locale) {
    return electricityTotal(
      measures, unit, locale, this._text(), hasResaleContract(this._hass, this._config?.entity));
  }

  /** Return the SVG of the graduations of a scale, with their unit: w, kwh or eur. */
  _grid(ticks, unit, locale) {
    return ticks.map((tick) => `
      <line class="grid" x1="${CHART.left}" x2="${CHART.width - CHART.right}" y1="${tick.y}" y2="${tick.y}" />
      <text class="tick" x="${CHART.left - 4}" y="${tick.y}">${escapeHtml(axisLabel(locale, tick.value, unit))}</text>`).join("");
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
      const minutes = this._selected * MINUTES_A_DAY;
      const point = areas.points.reduce((best, item) =>
        Math.abs(item.minutes - minutes) < Math.abs(best.minutes - minutes) ? item : best);
      const time = String(point.time).slice(11, 16);
      details.textContent = text.power_at.replace("{time}", time).replace("{power}", formatValue(locale, point.power, "w"));
      cursor = `<line class="cursor" x1="${areas.x(point.minutes)}" x2="${areas.x(point.minutes)}" y1="${CHART.top}" y2="${CHART.height - CHART.bottom}" />`;
    }
    svg.innerHTML = `${this._grid(areas.ticks, "w", locale)}
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

  /** Draw the temperature or the humidity of a period, inside and outside. */
  _renderClimate(measures, svg, details, legend, text, locale) {
    const period = datesPeriod(this._measure, this._period);
    const range = periodRange(period, this._date());
    const lines = climateLines(measures, range);
    if (!lines.points.length) {
      svg.innerHTML = `<text class="message" x="${CHART.width / 2}" y="${CHART.height / 2}">${escapeHtml(text.empty)}</text>`;
      details.textContent = "";
      legend.innerHTML = "";
      return;
    }
    const colors = CLIMATE_COLORS[this._measure];
    const labels = climateLabels(locale, period, range).map((label) =>
      `<text class="label" x="${lines.x(label.time).toFixed(1)}" y="${CHART.height - 4}"${
        label.anchor ? ` style="text-anchor: ${label.anchor}"` : ""}>${escapeHtml(label.text)}</text>`).join("");
    let cursor = "";
    details.textContent = "";
    if (this._selected !== null && this._selected <= 1) {
      const time = range.start.getTime() + this._selected * (range.end.getTime() - range.start.getTime());
      const point = lines.points.reduce((best, item) =>
        Math.abs(new Date(item.time) - time) < Math.abs(new Date(best.time) - time) ? item : best);
      const when = new Intl.DateTimeFormat(locale, this._period === "day"
        ? { hour: "2-digit", minute: "2-digit" }
        : { weekday: "short", day: "numeric", month: "short", ...(this._period === "year" ? {} : { hour: "2-digit", minute: "2-digit" }) })
        .format(new Date(point.time));
      details.textContent = text.climate_at.replace("{time}", when)
        .replace("{inside}", climateValue(locale, point.inside, measures.unit))
        .replace("{outside}", climateValue(locale, point.outside, measures.unit));
      cursor = `<line class="cursor" x1="${lines.x(point.time)}" x2="${lines.x(point.time)}" y1="${CHART.top}" y2="${CHART.height - CHART.bottom}" />`;
    }
    const format = new Intl.NumberFormat(locale, { maximumFractionDigits: 1 });
    const grid = lines.ticks.map((tick) => `
      <line class="grid" x1="${CHART.left}" x2="${CHART.width - CHART.right}" y1="${tick.y}" y2="${tick.y}" />
      <text class="tick" x="${CHART.left - 4}" y="${tick.y}">${escapeHtml(`${format.format(tick.value)} ${measures.unit || ""}`.trim())}</text>`).join("");
    svg.innerHTML = `${grid}
      ${lines.outside ? `<path d="${lines.outside}" fill="none" stroke="${colors.outside}" stroke-width="1.4" />` : ""}
      ${lines.inside ? `<path d="${lines.inside}" fill="none" stroke="${colors.inside}" stroke-width="1.6" />` : ""}
      ${cursor}${labels}`;
    // The legend opens the sensors when the curves come from them
    const entities = this._cache.get(this._key())?.entities || {};
    legend.innerHTML = ["inside", "outside"].filter((side) => lines[side]).map((side) =>
      `<span${entities[side] ? ` class="entity" data-entity="${escapeHtml(entities[side])}"` : ""}><span class="swatch" style="background: ${
        colors[side]}"></span>${escapeHtml(text[side])}</span>`).join("");
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
    svg.innerHTML = `${this._grid(chart.ticks, unit, locale)}${columns}
      <line class="zero" x1="${CHART.left}" x2="${CHART.width - CHART.right}" y1="${chart.zero}" y2="${chart.zero}" />`;
    const labels = Object.fromEntries((measures.bands || []).map((band) => [band.id, band.label]));
    const bar = this._selected === null ? null : bars[this._selected];
    if (bar) {
      // In the order of the legend
      const order = (measures.bands || []).map((band) => band.id);
      const parts = [...(bar.bands || [])].sort((a, b) => order.indexOf(a.id) - order.indexOf(b.id)).map((band) =>
        `${labels[band.id] || band.id} ${formatValue(locale, unit === "eur" ? band.cost : band.energy, unit)}`);
      if (bar.production) {
        // With the amount it was sold for, when it was
        const sold = Number(bar.resale) > 0 ? ` · ${formatValue(locale, bar.resale, "eur")}` : "";
        parts.push(`${text.production} ${formatValue(locale, bar.production, "kwh")}${sold}`);
      }
      // The unit of the bars first
      const values = [formatValue(locale, bar.energy, "kwh"), formatValue(locale, bar.cost, "eur")];
      if (unit === "eur") {
        values.reverse();
      }
      details.textContent = text.bar
        .replace("{name}", barTitle(locale, this._period, bar.date))
        .replace("{values}", `${values.join(" · ")}${parts.length ? ` — ${parts.join(" · ")}` : ""}`);
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
