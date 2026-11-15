/*
 * Little Monkey card for the Home Assistant dashboards.
 *
 * Served and loaded by the little_monkey integration (see card.py): no
 * Lovelace resource to add. Plain web component drawn in SVG, without build
 * step and without the internal libraries of the Home Assistant frontend.
 *
 * The dial of the ecojoko box: the real-time power on a logarithmic arc, and
 * in the central disc the power, the apparent power and the trend of the
 * last hour. The disc takes the color of the current tariff period when the
 * HC/HP or Tempo option of the integration is enabled.
 */

const CARD_TYPE = "little-monkey-card";
const EDITOR_TYPE = "little-monkey-card-editor";
const DOMAIN = "little_monkey";

const TRANSLATIONS = {
  en: {
    name: "Little Monkey",
    description: "Real-time power dial of the ecojoko box",
    title: ["REAL-TIME", "POWER"],
    watts: "WATTS",
    no_entity: "Choose the real-time consumption sensor of Little Monkey",
    unavailable: "Unavailable",
    periods: { hc: "OFF-PEAK HOURS", hp: "PEAK HOURS" },
    colors: { blue: "BLUE DAY", white: "WHITE DAY", red: "RED DAY" },
    editor: {
      entity: "Real-time consumption",
      apparent_power_entity: "Apparent power (optional)",
      tariff_entity: "Current tariff period (optional)",
      tempo_color_entity: "Tempo color of the day (optional)",
      max_power: "Power of the MAX graduation",
      trend_minutes: "Duration of the curve (3 min by default)",
      savings_entity: "Savings over 7 days (optional)",
      tariff_helper: "Entity giving the current period: HC / HP, Tempo color, both (\"HC Blue\"), Linky period (HCJB...), or a binary sensor on during the off-peak hours. By default, the Current Tariff Period sensor of Little Monkey.",
      tempo_helper: "Only when the entity above does not give the Tempo color.",
    },
  },
  fr: {
    name: "Petit Singe",
    description: "Cadran de puissance en temps réel du boîtier ecojoko",
    title: ["PUISSANCE", "TEMPS RÉEL"],
    watts: "WATTS",
    no_entity: "Choisissez le capteur Consommation Temps Réel de Little Monkey",
    unavailable: "Indisponible",
    periods: { hc: "HEURES CREUSES", hp: "HEURES PLEINES" },
    colors: { blue: "JOUR BLEU", white: "JOUR BLANC", red: "JOUR ROUGE" },
    editor: {
      entity: "Consommation temps réel",
      apparent_power_entity: "Puissance apparente (facultatif)",
      tariff_entity: "Période tarifaire en cours (facultatif)",
      tempo_color_entity: "Couleur Tempo du jour (facultatif)",
      max_power: "Puissance de la graduation MAX",
      trend_minutes: "Durée de la courbe (3 min par défaut)",
      savings_entity: "Économies sur 7 jours (facultatif)",
      tariff_helper: "Entité donnant la période en cours : HC / HP, couleur Tempo, les deux (« HC Bleu »), période Linky (HCJB...), ou capteur binaire allumé en heures creuses. Par défaut, le capteur Période Tarifaire en Cours de Little Monkey.",
      tempo_helper: "Seulement si l'entité ci-dessus ne donne pas la couleur Tempo.",
    },
  },
};

/** Return the language of the user, English when it is not translated. */
function language(hass) {
  const lang = (hass?.locale?.language || hass?.language || "en").split("-")[0];
  return TRANSLATIONS[lang] ? lang : "en";
}

// Upper arc: the power, between these clock angles (0 = top, clockwise)
const POWER_START = -100;
const POWER_END = 100;
// Graduations, evenly spaced; logarithmic between them except the first one
const POWER_TICKS = [0, 50, 100, 500, 1000, 5000, 10000];
const POWER_LABELS = ["0", "50", "100", "500", "1K", "5K", "10K", "MAX"];
const DEFAULT_MAX_POWER = 12000;
// Lower arc, decorative until the integration provides its value
const LOWER_START = 125; // +20 %
const LOWER_END = 235; // -20 %
const LOWER_RANGE = 20;
// Needle of the savings, light blue like on the ecojoko dial
const SAVINGS_COLOR = "#6dcfd9";
const LOWER_LABELS = ["20", "10", "0", "-10", "-20"];

// Radii, in a 200 x 200 view box centered on (100, 100)
const R_BEZEL = 98;
const R_LABELS = 89;
const R_TRACK = 79;
const R_DISC = 64;
// Legends WATTS and %, halfway between the disc and the inner edge of the arcs
const R_LEGEND = (R_DISC + R_TRACK - 2.5) / 2;
// End of the needle, just beyond the arc
const R_NEEDLE = R_TRACK + 4.5;

// Colors of the central disc
const DEFAULT_COLOR = "#0b6aae";
const TEMPO_COLORS = {
  blue: { hc: "#00008B", hp: "#0000FF" },
  white: { hc: "#D3D3D3", hp: "#FFFFFF" },
  red: { hc: "#8B0000", hp: "#FF0000" },
};
const LIGHT_COLORS = new Set(["#D3D3D3", "#FFFFFF"]);

// Sensors of the integration, by translation key
const TEMPO_KEYS = [
  "blue_hc_grid_consumption", "blue_hp_grid_consumption",
  "white_hc_grid_consumption", "white_hp_grid_consumption",
  "red_hc_grid_consumption", "red_hp_grid_consumption",
];
const HCHP_KEYS = ["hc_grid_consumption", "hp_grid_consumption"];

// Trend of the central disc: minutes shown, and number of points drawn
// The ecojoko dial shows the last 3 minutes
const DEFAULT_TREND_MINUTES = 3;
// One point per reading of 5 seconds, between 12 and 40 points: more would
// draw the noise, fewer would draw steps
const TREND_POINT_PERIOD = 5000;
const TREND_MIN_POINTS = 12;
const TREND_MAX_POINTS = 40;
// Box of the trend in the disc
const TREND_BOX = { left: 70, top: 116, width: 60, height: 16 };

// Greys of the ecojoko dial, from the lightest to the darkest: the same in
// the light and dark themes, they stay visible on both
const GREYS = ["#c4c1c1", "#aaa7a7", "#8e8b8b", "#6f6c6c"];
// Power zones of the upper arc: limits in W, and their greys
const POWER_ZONES = [100, 1000, 5000];
const POWER_ZONE_COLORS = GREYS;
// Segments of the lower arc, from +20 % to -20 % (clockwise)
const LOWER_COLORS = [
  GREYS[3],
  GREYS[2],
  "#5cbf8f",
  "#1ed98a",
];

const UNKNOWN_STATES = new Set(["unavailable", "unknown", "none", ""]);

/** Return the point at a radius and a clock angle, as "x y". */
function point(radius, angle) {
  const rad = (angle * Math.PI) / 180;
  const x = 100 + radius * Math.sin(rad);
  const y = 100 - radius * Math.cos(rad);
  return `${x.toFixed(2)} ${y.toFixed(2)}`;
}

/** Return the path of an arc drawn clockwise from one angle to another. */
function arc(radius, from, to) {
  const large = to - from > 180 ? 1 : 0;
  return `M ${point(radius, from)} A ${radius} ${radius} 0 ${large} 1 ${point(radius, to)}`;
}

/**
 * Return the paths of an arc made of colored segments, rounded at both ends.
 *
 * angles: limits of the segments, increasing; colors: one per segment. The
 * end segments are drawn first with round caps, the others over them with
 * square ends: the joints stay straight.
 */
function segmentedArc(radius, angles, colors, className) {
  const segment = (index, cap) =>
    `<path class="${className}" stroke-linecap="${cap}" stroke="${colors[index]}" ` +
    `d="${arc(radius, angles[index], angles[index + 1])}" />`;
  const last = colors.length - 1;
  const inner = colors.slice(1, last).map((_color, index) => segment(index + 1, "butt"));
  return [segment(0, "round"), segment(last, "round"), ...inner].join("");
}

/** Return the clock angle of a power on the upper arc. */
export function powerAngle(power, maxPower = DEFAULT_MAX_POWER) {
  const ticks = [...POWER_TICKS, Math.max(maxPower, 10001)];
  const step = (POWER_END - POWER_START) / (ticks.length - 1);
  const value = Math.min(Math.max(power, 0), ticks[ticks.length - 1]);
  let index = 0;
  while (index < ticks.length - 2 && value > ticks[index + 1]) {
    index += 1;
  }
  const low = ticks[index];
  const high = ticks[index + 1];
  const ratio = index === 0
    ? (value - low) / (high - low)
    : Math.log(value / low) / Math.log(high / low);
  return POWER_START + step * (index + ratio);
}

/**
 * Return the clock angle of the savings needle on the lower arc.
 *
 * savings: gap in % to the reference consumption, negative for a saving,
 * drawn on the green side; beyond 20 %, the needle stays at the end.
 */
export function savingsAngle(savings) {
  const value = Math.min(Math.max(savings, -LOWER_RANGE), LOWER_RANGE);
  const middle = (LOWER_START + LOWER_END) / 2;
  return middle - (value * (LOWER_END - LOWER_START)) / (2 * LOWER_RANGE);
}

/** Return the words of a state: "HC Bleu" gives ["hc", "bleu"]. */
function words(state) {
  return String(state)
    .toLowerCase()
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .split(/[^a-z]+/)
    .filter((word) => word);
}

/**
 * Read the tariff period in the state of an entity.
 *
 * Understood: "HC" / "HP" (or "heures creuses", "off-peak"...), the Tempo
 * color in French or English, both together ("HC Bleu", "hp_red"), the
 * period codes of the Linky meter (HCJB, HPJR...), and a binary sensor which
 * is on during the off-peak hours. Returns { period, color }, either of
 * them null when the state does not give it.
 */
export function parseTariff(entityId, state) {
  const result = { period: null, color: null };
  if (state === undefined || state === null || UNKNOWN_STATES.has(String(state).toLowerCase())) {
    return result;
  }
  if (entityId?.startsWith("binary_sensor.")) {
    result.period = state === "on" ? "hc" : "hp";
    return result;
  }
  const linky = String(state).toLowerCase().match(/^h([cp])j([bwr])$/);
  if (linky) {
    result.period = `h${linky[1]}`;
    result.color = { b: "blue", w: "white", r: "red" }[linky[2]];
    return result;
  }
  const list = words(state);
  const has = (...candidates) => candidates.some((word) => list.includes(word));
  if (has("hc", "creuse", "creuses", "off", "offpeak")) {
    result.period = "hc";
  } else if (has("hp", "pleine", "pleines", "peak")) {
    result.period = "hp";
  }
  if (has("bleu", "blue")) {
    result.color = "blue";
  } else if (has("blanc", "white")) {
    result.color = "white";
  } else if (has("rouge", "red")) {
    result.color = "red";
  }
  return result;
}

/**
 * Return the name of the current tariff period, shown under the curve.
 *
 * mode: "tempo", "hchp" or null, from the options of the integration.
 * Empty without option or when the period is not known, like the color of
 * the disc. A known Tempo color without period gives the color of the day.
 */
export function tariffLabel(lang, mode, tariff) {
  const text = TRANSLATIONS[lang] || TRANSLATIONS.en;
  const period = tariff.period && text.periods[tariff.period];
  if (mode === "tempo" && tariff.color) {
    const color = text.colors[tariff.color];
    return period ? `${period} · ${color}` : color;
  }
  if (mode === "hchp" && period) {
    return period;
  }
  return "";
}

/**
 * Return the color of the central disc.
 *
 * mode: "tempo", "hchp" or null, from the options of the integration.
 * Without option, or when the current period is not known, the disc keeps
 * the blue of the ecojoko dial. A known Tempo color without period gives
 * its HP color.
 */
export function discColor(mode, tariff) {
  if (mode === "tempo" && tariff.color) {
    return TEMPO_COLORS[tariff.color][tariff.period || "hp"];
  }
  if (mode === "hchp" && tariff.period) {
    return TEMPO_COLORS.blue[tariff.period];
  }
  return DEFAULT_COLOR;
}

/**
 * Return the smoothed path of the power over a period ending now.
 *
 * samples: { time, value } sorted by time; a value lasts until the next one.
 * The period is cut into intervals, each drawn at the mean of the values it
 * holds (weighted by their duration), which keeps a short spike from
 * flattening the curve. Returns an empty path with less than two points.
 */
export function trendPath(samples, now, period, box = TREND_BOX, points = trendPoints(period)) {
  // Intervals on fixed multiples of their length, the last one complete: the
  // curve moves by steps when a new interval ends, like the ecojoko dial,
  // instead of changing shape at each redraw
  const step = period / points;
  const start = Math.floor(now / step) * step - period;
  const values = [];
  let index = 0;
  let current = null;
  for (let point = 0; point < points; point += 1) {
    const from = start + step * point;
    const to = from + step;
    // Value at the start of the interval: the last one received before
    while (index < samples.length && samples[index].time <= from) {
      current = samples[index].value;
      index += 1;
    }
    let sum = 0;
    let duration = 0;
    let time = from;
    while (index < samples.length && samples[index].time < to) {
      if (current !== null) {
        sum += current * (samples[index].time - time);
        duration += samples[index].time - time;
      }
      time = samples[index].time;
      current = samples[index].value;
      index += 1;
    }
    if (current !== null) {
      sum += current * (to - time);
      duration += to - time;
    }
    if (duration > 0) {
      values.push({ point, value: sum / duration });
    }
  }
  if (values.length < 2) {
    return "";
  }
  // From the lowest to the highest point, like the ecojoko dial: the peaks
  // stay sharp, and a short spike is already damped by the mean
  const numbers = values.map((item) => item.value);
  const low = Math.min(...numbers);
  const range = Math.max(...numbers) - low;
  const coordinates = values.map((item) => ({
    x: box.left + (box.width * item.point) / (points - 1),
    y: range > 0
      ? box.top + box.height - (box.height * (item.value - low)) / range
      : box.top + box.height / 2,
  }));
  // Catmull-Rom spline through the points, drawn as cubic Bezier curves
  const format = (number) => number.toFixed(2);
  // The control points stay in the box: no overshoot above or below
  const clamp = (y) => Math.min(Math.max(y, box.top), box.top + box.height);
  let path = `M ${format(coordinates[0].x)} ${format(coordinates[0].y)}`;
  for (let i = 0; i < coordinates.length - 1; i += 1) {
    const p0 = coordinates[Math.max(i - 1, 0)];
    const p1 = coordinates[i];
    const p2 = coordinates[i + 1];
    const p3 = coordinates[Math.min(i + 2, coordinates.length - 1)];
    const c1x = p1.x + (p2.x - p0.x) / 6;
    const c1y = clamp(p1.y + (p2.y - p0.y) / 6);
    const c2x = p2.x - (p3.x - p1.x) / 6;
    const c2y = clamp(p2.y - (p3.y - p1.y) / 6);
    path += ` C ${format(c1x)} ${format(c1y)} ${format(c2x)} ${format(c2y)} ${format(p2.x)} ${format(p2.y)}`;
  }
  return path;
}

/** Return the number of points of a trend period. */
export function trendPoints(period) {
  return Math.round(Math.min(Math.max(period / TREND_POINT_PERIOD, TREND_MIN_POINTS), TREND_MAX_POINTS));
}

/** Return the minutes of the trend from the configuration (1 to 60). */
export function trendMinutes(config) {
  const minutes = Number(config.trend_minutes);
  return Number.isFinite(minutes) && minutes >= 1 ? Math.min(minutes, 60) : DEFAULT_TREND_MINUTES;
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

/** Return the tariff option enabled on the device: "tempo", "hchp" or null. */
function tariffMode(sensors) {
  if (TEMPO_KEYS.some((key) => sensors[key])) {
    return "tempo";
  }
  if (HCHP_KEYS.some((key) => sensors[key])) {
    return "hchp";
  }
  return null;
}

/** Return the entity of the integration with a translation key, if any. */
function findEntity(hass, translationKey) {
  return Object.values(hass?.entities || {}).find(
    (entity) => entity.platform === DOMAIN && entity.translation_key === translationKey,
  )?.entity_id;
}

// Options set automatically to a sensor of the device, by translation key
const AUTOMATIC = {
  apparent_power_entity: "realtime_apparent_power",
  tariff_entity: "current_tariff_period",
  savings_entity: "savings_7_days",
};

/**
 * Return the configuration of a new card: the sensors of the first Little
 * Monkey device, chosen automatically.
 */
export function stubConfig(hass) {
  const config = { type: `custom:${CARD_TYPE}` };
  const entity = findEntity(hass, "realtime_consumption");
  if (entity) {
    config.entity = entity;
    const sensors = deviceEntities(hass, entity);
    for (const [option, key] of Object.entries(AUTOMATIC)) {
      if (sensors[key]) {
        config[option] = sensors[key];
      }
    }
  }
  return config;
}

/**
 * Return the configuration after a change in the editor.
 *
 * Choosing another Little Monkey device also takes its apparent power and
 * tariff period sensors, unless other sensors were chosen by hand. Empty
 * options are removed from the configuration.
 */
export function editedConfig(hass, previous, value) {
  const config = { ...value };
  if (config.entity !== previous.entity) {
    const before = deviceEntities(hass, previous.entity);
    const after = deviceEntities(hass, config.entity);
    for (const [option, key] of Object.entries(AUTOMATIC)) {
      if (!config[option] || config[option] === before[key]) {
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

/** Return the fields of the editor, depending on the options of the device. */
export function editorSchema(hass, config) {
  const mode = tariffMode(deviceEntities(hass, config.entity));
  const schema = [
    {
      name: "entity",
      required: true,
      selector: { entity: { filter: { integration: DOMAIN, domain: "sensor", device_class: "power" } } },
    },
    {
      name: "apparent_power_entity",
      selector: { entity: { filter: { domain: "sensor", device_class: "apparent_power" } } },
    },
  ];
  if (mode || config.tariff_entity) {
    schema.push({
      name: "tariff_entity",
      selector: { entity: { filter: { domain: ["sensor", "binary_sensor", "input_select", "select"] } } },
    });
  }
  if (mode === "tempo" || config.tempo_color_entity) {
    schema.push({
      name: "tempo_color_entity",
      selector: { entity: { filter: { domain: ["sensor", "input_select", "select"] } } },
    });
  }
  schema.push({
    name: "savings_entity",
    selector: { entity: { filter: { domain: "sensor" } } },
  });
  schema.push({
    name: "max_power",
    selector: { number: { min: 10001, max: 100000, step: 1, mode: "box", unit_of_measurement: "W" } },
  });
  schema.push({
    name: "trend_minutes",
    selector: { number: { min: 1, max: 60, step: 1, mode: "slider", unit_of_measurement: "min" } },
  });
  return schema;
}

/** Return the numeric value of an entity, null when it has none. */
function numericState(hass, entityId) {
  const state = entityId && hass.states[entityId];
  if (!state || UNKNOWN_STATES.has(state.state)) {
    return null;
  }
  const value = Number(state.state);
  return Number.isFinite(value) ? value : null;
}

class LittleMonkeyCard extends HTMLElement {
  setConfig(config) {
    if (!config) {
      throw new Error("Invalid configuration");
    }
    this._config = { ...config };
    this._built = false;
    this._trend = [];
    this._trendEntity = null;
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  getCardSize() {
    return 6;
  }

  static getConfigElement() {
    return document.createElement(EDITOR_TYPE);
  }

  static getStubConfig(hass) {
    return stubConfig(hass);
  }

  getGridOptions() {
    return { columns: 6, min_columns: 4 };
  }

  /** Build the dial once; the updates only change its moving parts. */
  _build() {
    const text = TRANSLATIONS[language(this._hass)];
    const ticks = POWER_LABELS.map((label, index) => {
      const angle = POWER_START + ((POWER_END - POWER_START) * index) / (POWER_LABELS.length - 1);
      const [x, y] = point(R_LABELS, angle).split(" ");
      return `<text x="${x}" y="${y}" transform="rotate(${angle} ${x} ${y})">${label}</text>`;
    }).join("");
    const lowerTicks = LOWER_LABELS.map((label, index) => {
      const angle = LOWER_START + ((LOWER_END - LOWER_START) * index) / (LOWER_LABELS.length - 1);
      const [x, y] = point(R_LABELS, angle).split(" ");
      return `<text x="${x}" y="${y}" transform="rotate(${angle - 180} ${x} ${y})">${label}</text>`;
    }).join("");
    const [wattsX, wattsY] = point(R_LEGEND, 0).split(" ");
    // Zones of the upper arc, and quarters of the lower arc
    const maxPower = Number(this._config.max_power) || DEFAULT_MAX_POWER;
    const powerZoneAngles = [
      POWER_START, ...POWER_ZONES.map((power) => powerAngle(power, maxPower)), POWER_END,
    ];
    const lowerAngles = [0, 1, 2, 3, 4].map(
      (quarter) => LOWER_START + ((LOWER_END - LOWER_START) * quarter) / 4,
    );
    const [percentX, percentY] = point(R_LEGEND, 180).split(" ");

    if (!this.shadowRoot) {
      this.attachShadow({ mode: "open" });
    }
    this.shadowRoot.innerHTML = `
      <style>
        ha-card { padding: 16px; display: flex; justify-content: center; }
        svg { width: 100%; max-width: 360px; display: block; }
        .bezel { fill: var(--lm-background); stroke: var(--divider-color, #e0e0e0); stroke-width: 1; }
        .bezel-inner { fill: none; stroke: var(--divider-color, #e0e0e0); stroke-width: 0.6; }
        :host { --lm-background: var(--ha-card-background, var(--card-background-color, #fff)); }
        .track { fill: none; stroke-width: 5; }
        .labels text { fill: var(--secondary-text-color, #727272); font-size: 7.5px; text-anchor: middle; dominant-baseline: central; }
        .unit { fill: var(--secondary-text-color, #727272); font-size: 6px; letter-spacing: 0.3px; text-anchor: middle; dominant-baseline: central; }
        .needle { transition: transform 0.8s ease-out; }
        .needle line { stroke-linecap: round; transition: stroke 0.5s; }
        .needle-body { stroke-width: 6; }
        .needle-outline { stroke-width: 7.4; stroke: #9e9e9e; }
        .savings-needle { transition: transform 0.8s ease-out; }
        .savings-needle line { stroke-linecap: round; stroke-width: 6; }
        .disc { stroke: rgba(0, 0, 0, 0.12); stroke-width: 0.6; transition: fill 0.5s; filter: url(#lm-shadow); }
        .content text { text-anchor: middle; dominant-baseline: central; }
        .title { font-size: 8.5px; font-weight: 400; letter-spacing: 0.2px; }
        .value { font-size: 21px; font-weight: 400; }
        .apparent { font-size: 7.5px; opacity: 0.85; }
        .message { font-size: 5.5px; }
        .tariff { font-size: 6px; letter-spacing: 0.3px; opacity: 0.9; }
        .trend { fill: none; stroke-width: 1.1; stroke-linejoin: round; stroke-linecap: round; }
        .hidden { display: none; }
      </style>
      <ha-card>
        <svg viewBox="0 0 200 200" role="img" aria-label="${text.title.join(" ")}">
          <defs>
            <filter id="lm-shadow" x="-20%" y="-20%" width="140%" height="140%">
              <feDropShadow dx="0" dy="1.5" stdDeviation="2" flood-opacity="0.35" />
            </filter>
          </defs>
          <circle class="bezel" cx="100" cy="100" r="${R_BEZEL}" />
          <circle class="bezel-inner" cx="100" cy="100" r="${R_BEZEL - 4}" />
          ${segmentedArc(R_TRACK, powerZoneAngles, POWER_ZONE_COLORS, "track")}
          ${segmentedArc(R_TRACK, lowerAngles, LOWER_COLORS, "track")}
          <g class="labels">${ticks}${lowerTicks}</g>
          <text class="unit" x="${wattsX}" y="${wattsY}">${text.watts}</text>
          <text class="unit" x="${percentX}" y="${percentY}">%</text>
          <g class="savings-needle hidden">
            <line x1="100" y1="${100 - R_NEEDLE}" x2="100" y2="${100 - R_DISC}" stroke="${SAVINGS_COLOR}" />
          </g>
          <g class="needle">
            <line class="needle-outline hidden" x1="100" y1="${100 - R_NEEDLE}" x2="100" y2="${100 - R_DISC}" />
            <line class="needle-body" x1="100" y1="${100 - R_NEEDLE}" x2="100" y2="${100 - R_DISC}" stroke="${DEFAULT_COLOR}" />
          </g>
          <circle class="disc" cx="100" cy="100" r="${R_DISC}" fill="${DEFAULT_COLOR}" />
          <g class="content">
            <text class="title" x="100" y="63">${text.title[0]}</text>
            <text class="title" x="100" y="74">${text.title[1]}</text>
            <text class="value" x="100" y="96"></text>
            <text class="apparent" x="100" y="110"></text>
            <text class="message hidden" x="100" y="96"></text>
            <text class="tariff" x="100" y="140"></text>
            <path class="trend" d="" />
          </g>
        </svg>
      </ha-card>`;
    const root = this.shadowRoot;
    this._elements = {
      needle: root.querySelector(".needle"),
      savingsNeedle: root.querySelector(".savings-needle"),
      needleBody: root.querySelector(".needle-body"),
      needleOutline: root.querySelector(".needle-outline"),
      disc: root.querySelector(".disc"),
      content: root.querySelector(".content"),
      value: root.querySelector(".value"),
      apparent: root.querySelector(".apparent"),
      tariff: root.querySelector(".tariff"),
      message: root.querySelector(".message"),
      trend: root.querySelector(".trend"),
    };
    this._language = language(this._hass);
    this._built = true;
  }

  _render() {
    if (!this._config || !this._hass) {
      return;
    }
    if (!this._built || this._language !== language(this._hass)) {
      this._build();
    }
    const hass = this._hass;
    const config = this._config;
    const text = TRANSLATIONS[this._language];
    const el = this._elements;

    // Sensors of the device, read again when the entity registry changes
    if (this._entities !== hass.entities || this._sensorsOf !== config.entity) {
      this._entities = hass.entities;
      this._sensorsOf = config.entity;
      this._sensors = deviceEntities(hass, config.entity);
    }
    const sensors = this._sensors;

    // Color of the central disc
    const mode = tariffMode(sensors);
    const tariff = { period: null, color: null };
    // Without entity chosen, the period sensor of the integration
    const tariffEntity = config.tariff_entity || sensors.current_tariff_period;
    for (const entityId of [tariffEntity, config.tempo_color_entity]) {
      const parsed = parseTariff(entityId, entityId && hass.states[entityId]?.state);
      tariff.period = tariff.period || parsed.period;
      // The Tempo color entity has the last word on the color
      tariff.color = parsed.color || tariff.color;
    }
    const color = discColor(mode, tariff);
    el.tariff.textContent = tariffLabel(this._language, mode, tariff);
    const light = LIGHT_COLORS.has(color);
    el.disc.setAttribute("fill", color);
    el.content.setAttribute("fill", light ? "#212121" : "#ffffff");
    el.trend.setAttribute("stroke", light ? "#212121" : "#ffffff");
    // The needle has the color of the disc, outlined when it is light
    el.needleBody.setAttribute("stroke", color);
    el.needleOutline.classList.toggle("hidden", !light);

    // Power and apparent power
    const power = numericState(hass, config.entity);
    const apparentEntity = config.apparent_power_entity || sensors.realtime_apparent_power;
    const apparent = numericState(hass, apparentEntity);
    const format = new Intl.NumberFormat(hass.locale?.language || this._language, {
      maximumFractionDigits: 0,
    });
    const problem = !config.entity ? text.no_entity : power === null ? text.unavailable : null;
    el.message.textContent = problem || "";
    el.message.classList.toggle("hidden", !problem);
    el.value.classList.toggle("hidden", Boolean(problem));
    el.value.textContent = problem ? "" : `${format.format(power)} W`;
    el.apparent.textContent = !problem && apparent !== null ? `${format.format(apparent)} VA` : "";
    el.needle.classList.toggle("hidden", power === null);
    if (power !== null) {
      const angle = powerAngle(power, Number(config.max_power) || DEFAULT_MAX_POWER);
      el.needle.style.transformOrigin = "100px 100px";
      el.needle.style.transform = `rotate(${angle}deg)`;
    }

    // Savings over 7 days on the lower arc, by default the sensor of the device
    const savings = numericState(hass, config.savings_entity || sensors.savings_7_days);
    el.savingsNeedle.classList.toggle("hidden", savings === null);
    if (savings !== null) {
      el.savingsNeedle.style.transformOrigin = "100px 100px";
      el.savingsNeedle.style.transform = `rotate(${savingsAngle(savings)}deg)`;
    }

    this._updateTrend(power);
  }

  /** Keep the values of the trend period and draw them in the disc. */
  _updateTrend(power) {
    const entityId = this._config.entity;
    if (!entityId) {
      this._elements.trend.setAttribute("d", "");
      return;
    }
    const period = trendMinutes(this._config) * 60 * 1000;
    const key = `${entityId} ${period}`;
    if (this._trendEntity !== key) {
      this._trendEntity = key;
      this._trend = [];
      this._loadHistory(entityId, key, period);
    }
    const state = this._hass.states[entityId];
    const now = Date.now();
    if (power !== null && state) {
      const time = new Date(state.last_updated).getTime() || now;
      const last = this._trend[this._trend.length - 1];
      if (!last || time > last.time) {
        this._trend.push({ time, value: power });
      }
    }
    // The last value before the period is kept: it lasts into the period
    const firstInside = this._trend.findIndex((sample) => sample.time >= now - period);
    const keepFrom = firstInside === -1 ? this._trend.length - 1 : firstInside - 1;
    if (keepFrom > 0) {
      this._trend = this._trend.slice(keepFrom);
    }
    this._drawTrend(now, period);
  }

  /** Load the history of the trend period, once per entity and period. */
  async _loadHistory(entityId, key, period) {
    const start = new Date(Date.now() - period).toISOString();
    try {
      const history = await this._hass.callWS({
        type: "history/history_during_period",
        start_time: start,
        entity_ids: [entityId],
        minimal_response: true,
        no_attributes: true,
        significant_changes_only: false,
      });
      if (this._trendEntity !== key) {
        return;
      }
      const samples = (history[entityId] || [])
        .map((item) => ({ time: item.lu * 1000, value: Number(item.s) }))
        .filter((sample) => Number.isFinite(sample.value) && Number.isFinite(sample.time));
      const first = this._trend[0]?.time ?? Infinity;
      this._trend = [...samples.filter((sample) => sample.time < first), ...this._trend];
      this._drawTrend(Date.now(), period);
    } catch (error) {
      // No trend from the history: the card draws the values it receives
      console.debug("Little Monkey card: history not available", error);
    }
  }

  _drawTrend(now, period) {
    this._elements.trend.setAttribute("d", trendPath(this._trend, now, period));
  }
}

/** Visual editor of the card, built on the form of Home Assistant. */
class LittleMonkeyCardEditor extends HTMLElement {
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

  _render() {
    if (!this._config || !this._hass) {
      return;
    }
    if (!this._form) {
      this._form = document.createElement("ha-form");
      this._form.computeLabel = (field) => this._text().editor[field.name] || field.name;
      this._form.computeHelper = (field) =>
        ({ tariff_entity: this._text().editor.tariff_helper, tempo_color_entity: this._text().editor.tempo_helper })[field.name];
      this._form.addEventListener("value-changed", (event) => this._changed(event));
      this.appendChild(this._form);
    }
    this._form.hass = this._hass;
    this._form.data = this._config;
    this._form.schema = editorSchema(this._hass, this._config);
  }

  _text() {
    return TRANSLATIONS[language(this._hass)];
  }

  _changed(event) {
    event.stopPropagation();
    const config = editedConfig(this._hass, this._config, event.detail.value);
    this._config = config;
    this._render();
    this.dispatchEvent(new CustomEvent("config-changed", {
      detail: { config }, bubbles: true, composed: true,
    }));
  }
}

if (!customElements.get(EDITOR_TYPE)) {
  customElements.define(EDITOR_TYPE, LittleMonkeyCardEditor);
}

if (!customElements.get(CARD_TYPE)) {
  customElements.define(CARD_TYPE, LittleMonkeyCard);
  const text = TRANSLATIONS[language({ language: navigator.language })];
  window.customCards = window.customCards || [];
  window.customCards.push({
    type: CARD_TYPE,
    name: text.name,
    description: text.description,
    preview: true,
    documentationURL: "https://github.com/jmcruvellier/little_monkey/blob/main/CONFIGURATION.md#carte-du-tableau-de-bord",
  });
}
