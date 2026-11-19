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
    injection_title: ["GRID", "INJECTION"],
    savings_title: ["SAVING", "OVER 7 DAYS"],
    overconsumption_title: ["OVERCONSUMPTION", "OVER 7 DAYS"],
    savings_reference: ["COMPARED WITH THE", "REFERENCE CONSUMPTION"],
    savings_need_7d: "NEEDS 7 DAYS OF MEASURES",
    over_7_days: "OVER 7 DAYS",
    max_title: "MAX POWER",
    max_month: "THIS MONTH",
    max_year: "THIS YEAR",
    max_alltime: "SINCE THE START",
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
      savings_entity: "Gap over 7 days (optional)",
      return_seconds: "Back to the real-time power after (s)",
      relief: "Relief of the dial",
      dial_mode: "Background of the dial",
      dial_modes: {
        default: "Default (shade of the theme)",
        none: "Transparent",
        palette: "Home Assistant palette",
        custom: "Custom color",
      },
      dial_color: "Color of the palette",
      dial_rgb: "Custom color",
      return_helper: "After another face of the disc was chosen. 0 to stay on it.",
      tariff_helper: "Entity giving the current period: HC / HP, Tempo color, both (\"HC Blue\"), Linky period (HCJB...), or a binary sensor on during the off-peak hours. By default, the Current Tariff Period sensor of Little Monkey.",
      tempo_helper: "Only when the entity above does not give the Tempo color.",
    },
  },
  fr: {
    name: "Petit Singe",
    description: "Cadran de puissance en temps réel du boîtier ecojoko",
    title: ["PUISSANCE", "TEMPS RÉEL"],
    injection_title: ["INJECTION", "RÉSEAU"],
    savings_title: ["ÉCONOMIE", "SUR 7 JOURS"],
    overconsumption_title: ["SURCONSOMMATION", "SUR 7 JOURS"],
    savings_reference: ["PAR RAPPORT À LA CONSOMMATION", "DE RÉFÉRENCE"],
    savings_need_7d: "NÉCESSITE 7 JOURS DE MESURES",
    over_7_days: "SUR 7 JOURS",
    max_title: "PUISSANCE MAX",
    max_month: "MOIS EN COURS",
    max_year: "ANNÉE EN COURS",
    max_alltime: "DEPUIS DÉBUT",
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
      savings_entity: "Écart sur 7 jours (facultatif)",
      return_seconds: "Retour à la puissance temps réel après (s)",
      relief: "Relief du cadran",
      dial_mode: "Fond du cadran",
      dial_modes: {
        default: "Par défaut (teinte du thème)",
        none: "Transparent",
        palette: "Palette de Home Assistant",
        custom: "Couleur libre",
      },
      dial_color: "Couleur de la palette",
      dial_rgb: "Couleur libre",
      return_helper: "Après le choix d'une autre face du disque. 0 pour y rester.",
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
// Lower arc: the savings over 7 days, in % of the reference consumption
const LOWER_START = 125; // +20 %
const LOWER_END = 235; // -20 %
const LOWER_RANGE = 20;
// Needle of the savings, light blue like on the ecojoko dial
const SAVINGS_COLOR = "#6dcfd9";
const LOWER_LABELS = ["20", "10", "0", "-10", "-20"];

// Radii, in a 200 x 200 view box centered on (100, 100)
// The bezel goes a little beyond the 200 x 200 box: the view box is wider
const R_BEZEL = 108;
// Graduations, beyond the rounded tips of the needles and away from the rim
const R_LABELS = 90;
const R_TRACK = 79;
const R_DISC = 64;
// Legends WATTS and %, halfway between the disc and the inner edge of the arcs
const R_LEGEND = (R_DISC + R_TRACK - 2.5) / 2;
// End of the needle, just beyond the arc
const R_NEEDLE = R_TRACK + 4.5;

// Colors of the central disc
const DEFAULT_COLOR = "#0b6aae";
// Color of the disc while power is injected into the grid (solar surplus)
const INJECTION_COLOR = "#11AF00";
const TEMPO_COLORS = {
  blue: { hc: "#00008B", hp: "#0000FF" },
  white: { hc: "#D3D3D3", hp: "#FFFFFF" },
  red: { hc: "#8B0000", hp: "#FF0000" },
};
const LIGHT_COLORS = new Set(["#D3D3D3", "#FFFFFF"]);

// Faces of the central disc, in their order, and the color of the disc on
// each of them; the first one takes the color of the tariff period
const FACES = ["power", "savings", "cost", "max"];
const FACE_COLORS = { savings: "#4fb8cf", cost: "#3fae5c", max: "#6fc0d8" };
// Back to the first face after this many seconds by default
const DEFAULT_RETURN_SECONDS = 30;
// Box of the histogram of the last 7 days, on the cost face
const HISTOGRAM_BOX = { left: 74, top: 96, width: 52, height: 28 };
// Horizontal move, in pixels, that changes the face
const SWIPE_DISTANCE = 30;

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
 * A negative power (injection of a solar surplus) gives green, whatever the
 * tariff. Without option, or when the current period is not known, the disc
 * keeps the blue of the ecojoko dial. A known Tempo color without period
 * gives its HP color.
 */
export function discColor(mode, tariff, power = null) {
  if (power !== null && power < 0) {
    return INJECTION_COLOR;
  }
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

// Colors of the palette of Home Assistant, used when the theme does not
// define them
const PALETTE = {
  primary: "#03a9f4", accent: "#ff9800", red: "#f44336", pink: "#e91e63",
  purple: "#926bc7", "deep-purple": "#6e41ab", indigo: "#3f51b5", blue: "#2196f3",
  "light-blue": "#03a9f4", cyan: "#00bcd4", teal: "#009688", green: "#4caf50",
  "light-green": "#8bc34a", lime: "#cddc39", yellow: "#ffeb3b", amber: "#ffc107",
  orange: "#ff9800", "deep-orange": "#ff6f22", brown: "#795548",
  "light-grey": "#bdbdbd", grey: "#9e9e9e", "dark-grey": "#606060",
  "blue-grey": "#607d8b", black: "#000000", white: "#ffffff",
};
// Graduations on a colored dial: dark or light, whichever reads better
const DARK_LABEL = "rgba(0, 0, 0, 0.7)";
const LIGHT_LABEL = "rgba(255, 255, 255, 0.85)";

/** Return a CSS color "#rrggbb", "#rgb" or "rgb(r, g, b)" as [r, g, b]. */
export function parseColor(color) {
  const text = String(color || "").trim().toLowerCase();
  let match = text.match(/^#([0-9a-f]{3})$/);
  if (match) {
    return [...match[1]].map((digit) => parseInt(digit + digit, 16));
  }
  match = text.match(/^#([0-9a-f]{6})$/);
  if (match) {
    return [0, 2, 4].map((index) => parseInt(match[1].slice(index, index + 2), 16));
  }
  match = text.match(/^rgba?\(\s*(\d+)[\s,]+(\d+)[\s,]+(\d+)/);
  return match ? match.slice(1, 4).map(Number) : null;
}

/**
 * Return the color of the graduations on a dial of a given color: the one,
 * dark or light, with the best contrast (WCAG relative luminance).
 */
export function labelColor(rgb) {
  const channel = (value) => {
    const c = value / 255;
    return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
  };
  const [r, g, b] = rgb.map(channel);
  const luminance = 0.2126 * r + 0.7152 * g + 0.0722 * b;
  // Contrast with black: (L + 0.05) / 0.05; with white: 1.05 / (L + 0.05)
  return (luminance + 0.05) / 0.05 >= 1.05 / (luminance + 0.05) ? DARK_LABEL : LIGHT_LABEL;
}

/** Return the kind of a dial_color: "default", "none", "palette" or "custom". */
export function dialMode(dialColor) {
  if (dialColor === undefined || dialColor === null || dialColor === "" || dialColor === "default") {
    return "default";
  }
  if (dialColor === "none" || dialColor === "transparent") {
    return "none";
  }
  return Array.isArray(dialColor) || parseColor(dialColor) ? "custom" : "palette";
}

/**
 * Return the fill of the inside of the dial.
 *
 * dial_color: "default" (or absent) for a shade of the theme, a little
 * lighter than the card in a dark theme and a little greyer in a light one;
 * "none" or "transparent" for the background of the card; a color of the
 * Home Assistant palette (red, light-blue...), which follows the theme; or a
 * custom color, [r, g, b] as given by the color picker, "#rrggbb" or
 * "rgb(r, g, b)".
 */
export function dialFill(dialColor) {
  const mode = dialMode(dialColor);
  if (mode === "default") {
    return "color-mix(in srgb, var(--primary-text-color, #212121) 7%, var(--lm-background))";
  }
  if (mode === "none") {
    return "none";
  }
  if (mode === "custom") {
    const rgb = Array.isArray(dialColor) ? dialColor.map(Number) : parseColor(dialColor);
    if (rgb.length === 3 && rgb.every((value) => Number.isFinite(value))) {
      return `rgb(${rgb.map((value) => Math.round(Math.min(Math.max(value, 0), 255))).join(", ")})`;
    }
    return dialFill("default");
  }
  // A name of the palette is a CSS variable of the theme
  return `var(--${String(dialColor).replace(/[^a-z0-9-]/gi, "")}-color)`;
}

/** Return the values shown by the editor: the background as a menu. */
export function formData(config) {
  const data = { ...config };
  const mode = dialMode(config.dial_color);
  delete data.dial_color;
  data.dial_mode = mode;
  if (mode === "palette") {
    data.dial_color = config.dial_color;
  } else if (mode === "custom") {
    data.dial_rgb = Array.isArray(config.dial_color)
      ? config.dial_color
      : parseColor(config.dial_color);
  }
  return data;
}

/** Return the configuration from the values of the editor. */
export function fromFormData(previous, value) {
  const config = { ...value };
  const mode = config.dial_mode || "default";
  const color = config.dial_color;
  const rgb = config.dial_rgb;
  delete config.dial_mode;
  delete config.dial_rgb;
  delete config.dial_color;
  if (mode === "none") {
    config.dial_color = "none";
  } else if (mode === "palette") {
    // The color chosen in the palette, the previous one, or blue
    const kept = dialMode(previous.dial_color) === "palette" ? previous.dial_color : "blue";
    config.dial_color = color || kept;
  } else if (mode === "custom") {
    config.dial_color = Array.isArray(rgb) ? rgb : [240, 240, 240];
  }
  return config;
}

/**
 * Return the faces of the disc that have their sensors, in their order.
 *
 * The real-time power is always there; the other faces need the sensors of
 * the activity of the account (integration 2.0.0 or later).
 */
export function availableFaces(sensors, savingsEntity) {
  const faces = ["power"];
  if (savingsEntity) {
    faces.push("savings");
  }
  if (sensors.cost_7_days || sensors.consumption_7_days) {
    faces.push("cost");
  }
  if (sensors.max_power_month || sensors.max_power_year || sensors.max_power_alltime) {
    faces.push("max");
  }
  return faces;
}

/** Return the face reached by a step (+1 or -1) from a face, in a loop. */
export function nextFace(faces, face, step) {
  const index = Math.max(faces.indexOf(face), 0);
  return faces[(index + step + faces.length) % faces.length];
}

/** Return the seconds before going back to the first face (0: never). */
export function returnSeconds(config) {
  const seconds = Number(config.return_seconds);
  return Number.isFinite(seconds) && seconds >= 0 ? seconds : DEFAULT_RETURN_SECONDS;
}

/**
 * Return the path of the histogram of the last 7 days: one bar per day,
 * from zero to the highest day, like the ecojoko dial. Empty without values.
 */
export function histogramPath(values, box = HISTOGRAM_BOX) {
  if (!Array.isArray(values) || values.length === 0) {
    return "";
  }
  const numbers = values.map((value) => Math.max(Number(value) || 0, 0));
  const high = Math.max(...numbers);
  const step = box.width / numbers.length;
  const width = step * 0.6;
  const format = (number) => number.toFixed(2);
  return numbers.map((value, index) => {
    const height = high > 0 ? (box.height * value) / high : 0;
    const x = box.left + step * index + (step - width) / 2;
    const y = box.top + box.height - height;
    return `M ${format(x)} ${format(y)} h ${format(width)} v ${format(height)} h ${format(-width)} Z`;
  }).join(" ");
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

/**
 * Tell whether a sensor is no longer provided by the integration: Home
 * Assistant keeps the entity of a tariff band left by a previous contract,
 * or of an option turned off, with its history, and restores its state.
 */
function isOrphan(hass, entityId) {
  return hass?.states?.[entityId]?.attributes?.restored === true;
}

/**
 * Return the tariff option enabled on the device: "tempo", "hchp" or null.
 *
 * The sensors left by a previous contract do not count: after a change from
 * Tempo to HC/HP, the Tempo sensors are still in Home Assistant.
 */
export function tariffMode(sensors, hass) {
  const provided = (key) => sensors[key] && !isOrphan(hass, sensors[key]);
  if (TEMPO_KEYS.some(provided)) {
    return "tempo";
  }
  if (HCHP_KEYS.some(provided)) {
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
  const mode = tariffMode(deviceEntities(hass, config.entity), hass);
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
    name: "return_seconds",
    selector: { number: { min: 0, max: 600, step: 5, mode: "box", unit_of_measurement: "s" } },
  });
  schema.push({
    name: "relief",
    default: true,
    selector: { boolean: {} },
  });
  const background = dialMode(config.dial_color);
  schema.push({
    name: "dial_mode",
    selector: {
      select: {
        mode: "dropdown",
        options: ["default", "none", "palette", "custom"].map((value) => ({
          value,
          label: (TRANSLATIONS[language(hass)] || TRANSLATIONS.en).editor.dial_modes[value],
        })),
      },
    },
  });
  if (background === "palette") {
    schema.push({ name: "dial_color", selector: { ui_color: {} } });
  } else if (background === "custom") {
    schema.push({ name: "dial_rgb", selector: { color_rgb: {} } });
  }
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
    this._face = "power";
    this._faces = ["power"];
    this._trend = [];
    this._trendEntity = null;
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  getCardSize() {
    // Masonry view: rows of 50 pixels, for a dial of 360 pixels at most
    return 7;
  }

  disconnectedCallback() {
    clearTimeout(this._returnTimer);
  }

  /** Show a face of the disc; the first one comes back after a while. */
  _showFace(face) {
    this._face = face;
    clearTimeout(this._returnTimer);
    const seconds = returnSeconds(this._config);
    if (face !== "power" && seconds > 0) {
      this._returnTimer = setTimeout(() => this._showFace("power"), seconds * 1000);
    }
    this._render();
  }

  static getConfigElement() {
    return document.createElement(EDITOR_TYPE);
  }

  static getStubConfig(hass) {
    return stubConfig(hass);
  }

  getGridOptions() {
    // Half a section, at least: narrower, the graduations do not read.
    // Square, its height follows its width
    return { columns: 6, min_columns: 6 };
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
        svg { width: 100%; max-width: 360px; display: block; overflow: visible; }
        .bezel { fill: var(--lm-background); stroke: var(--divider-color, #e0e0e0); stroke-width: 1; }
        .bezel-inner { stroke: var(--divider-color, #e0e0e0); stroke-width: 0.6; transition: fill 0.5s; }
        .relief .bezel { filter: url(#lm-outer-shadow); }
        .relief .disc { filter: url(#lm-shadow); }
        .inner-shadow { display: none; }
        .relief .inner-shadow { display: inline; }
        :host { --lm-background: var(--ha-card-background, var(--card-background-color, #fff)); }
        .track { fill: none; stroke-width: 5; }
        .labels text { fill: var(--lm-label-color, var(--secondary-text-color, #727272)); font-size: 7.5px; text-anchor: middle; dominant-baseline: central; }
        .unit { fill: var(--lm-label-color, var(--secondary-text-color, #727272)); font-size: 6px; letter-spacing: 0.3px; text-anchor: middle; dominant-baseline: central; }
        .needle { transition: transform 0.8s ease-out; }
        .needle line { stroke-linecap: round; transition: stroke 0.5s; }
        .needle-body { stroke-width: 6; }
        .needle-outline { stroke-width: 7.4; stroke: #9e9e9e; }
        .savings-needle { transition: transform 0.8s ease-out; }
        .savings-needle line { stroke-linecap: round; stroke-width: 6; }
        .disc { stroke: rgba(0, 0, 0, 0.12); stroke-width: 0.6; transition: fill 0.5s; }
        .content text { text-anchor: middle; dominant-baseline: central; }
        .title { font-size: 8.5px; font-weight: 400; letter-spacing: 0.2px; }
        .value { font-size: 21px; font-weight: 400; }
        .apparent { font-size: 7.5px; opacity: 0.85; }
        .message { font-size: 5.5px; }
        .tariff { font-size: 6px; letter-spacing: 0.3px; opacity: 0.9; }
        .trend { fill: none; stroke-width: 1.1; stroke-linejoin: round; stroke-linecap: round; }
        svg { touch-action: pan-y; user-select: none; }
        .small { font-size: 6px; letter-spacing: 0.3px; }
        .medium { font-size: 8px; }
        .large { font-size: 17px; font-weight: 400; }
        .dot { cursor: pointer; }
        .dot circle.mark { stroke-width: 0.6; }
        .hidden { display: none; }
      </style>
      <ha-card>
        <svg viewBox="-10 -10 220 220" role="img" aria-label="${text.title.join(" ")}">
          <defs>
            <filter id="lm-outer-shadow" x="-20%" y="-20%" width="140%" height="140%">
              <feDropShadow dx="0" dy="3" stdDeviation="4" flood-opacity="0.5" />
            </filter>
            <filter id="lm-blur" x="-20%" y="-20%" width="140%" height="140%">
              <feGaussianBlur stdDeviation="1.1" />
            </filter>
            <clipPath id="lm-inside">
              <circle cx="100" cy="100" r="${R_BEZEL - 4}" />
            </clipPath>
            <filter id="lm-shadow" x="-20%" y="-20%" width="140%" height="140%">
              <feDropShadow dx="0" dy="1.5" stdDeviation="2" flood-opacity="0.45" />
            </filter>
          </defs>
          <circle class="bezel" cx="100" cy="100" r="${R_BEZEL}" />
          <circle class="bezel-inner" cx="100" cy="100" r="${R_BEZEL - 4}" />
          <g class="inner-shadow" clip-path="url(#lm-inside)">
            <circle cx="100" cy="101.5" r="${R_BEZEL - 4}" fill="none" stroke="rgba(0, 0, 0, 0.5)" stroke-width="2.6" filter="url(#lm-blur)" />
          </g>
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
            <g class="face" data-face="power">
              <text class="title power-title" x="100" y="63">${text.title[0]}</text>
              <text class="title power-title" x="100" y="74">${text.title[1]}</text>
              <text class="value" x="100" y="96"></text>
              <text class="apparent" x="100" y="110"></text>
              <text class="message hidden" x="100" y="96"></text>
              <text class="tariff" x="100" y="140"></text>
              <path class="trend" d="" />
            </g>
            <g class="face hidden" data-face="savings">
              <text class="title savings-title" x="100" y="64"></text>
              <text class="title savings-title" x="100" y="75"></text>
              <text class="value savings-value" x="100" y="97"></text>
              <text class="small savings-message hidden" x="100" y="97">${text.savings_need_7d}</text>
              <text class="small" x="100" y="117">${text.savings_reference[0]}</text>
              <text class="small" x="100" y="125">${text.savings_reference[1]}</text>
            </g>
            <g class="face hidden" data-face="cost">
              <text class="large cost-value" x="100" y="71"></text>
              <text class="medium cost-energy" x="100" y="86"></text>
              <path class="histogram" d="" />
              <text class="small" x="100" y="135">${text.over_7_days}</text>
            </g>
            <g class="face hidden" data-face="max">
              <text class="title" x="100" y="61">${text.max_title}</text>
              <text class="small" x="100" y="75">${text.max_month}</text>
              <text class="medium max-month" x="100" y="84"></text>
              <text class="small" x="100" y="97">${text.max_year}</text>
              <text class="medium max-year" x="100" y="106"></text>
              <text class="small" x="100" y="119">${text.max_alltime}</text>
              <text class="medium max-alltime" x="100" y="128"></text>
            </g>
            <g class="dots"></g>
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
      faces: Object.fromEntries(
        [...root.querySelectorAll(".face")].map((face) => [face.dataset.face, face]),
      ),
      powerTitle: [...root.querySelectorAll(".power-title")],
      savingsTitle: [...root.querySelectorAll(".savings-title")],
      savingsValue: root.querySelector(".savings-value"),
      savingsMessage: root.querySelector(".savings-message"),
      costValue: root.querySelector(".cost-value"),
      costEnergy: root.querySelector(".cost-energy"),
      histogram: root.querySelector(".histogram"),
      maxMonth: root.querySelector(".max-month"),
      maxYear: root.querySelector(".max-year"),
      maxAlltime: root.querySelector(".max-alltime"),
      dots: root.querySelector(".dots"),
      svg: root.querySelector("svg"),
      dial: root.querySelector(".bezel-inner"),
    };
    this._dotsKey = null;
    // Swipe to the next or to the previous face
    const svg = root.querySelector("svg");
    svg.addEventListener("pointerdown", (event) => {
      this._swipeStart = event.clientX;
    });
    svg.addEventListener("pointerup", (event) => {
      if (this._swipeStart === undefined || this._faces.length < 2) {
        return;
      }
      const distance = event.clientX - this._swipeStart;
      this._swipeStart = undefined;
      if (Math.abs(distance) >= SWIPE_DISTANCE) {
        this._showFace(nextFace(this._faces, this._face, distance < 0 ? 1 : -1));
      }
    });
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
    const mode = tariffMode(sensors, hass);
    const tariff = { period: null, color: null };
    // Without entity chosen, the period sensor of the integration
    const tariffEntity = config.tariff_entity || sensors.current_tariff_period;
    for (const entityId of [tariffEntity, config.tempo_color_entity]) {
      const parsed = parseTariff(entityId, entityId && hass.states[entityId]?.state);
      tariff.period = tariff.period || parsed.period;
      // The Tempo color entity has the last word on the color
      tariff.color = parsed.color || tariff.color;
    }
    const power = numericState(hass, config.entity);
    const color = discColor(mode, tariff, power);
    el.tariff.textContent = tariffLabel(this._language, mode, tariff);
    const powerTitle = power !== null && power < 0 ? text.injection_title : text.title;
    el.powerTitle.forEach((line, index) => {
      line.textContent = powerTitle[index];
    });

    // Relief and color of the dial
    el.svg.classList.toggle("relief", config.relief !== false);
    el.dial.setAttribute("fill", dialFill(config.dial_color));
    this._updateLabelColor(config.dial_color);

    // Faces of the disc: the first one has the color of the tariff period,
    // and the power needle keeps it on the other faces
    const savingsEntity = config.savings_entity || sensors.savings_7_days;
    this._faces = availableFaces(sensors, savingsEntity);
    if (!this._faces.includes(this._face)) {
      this._face = "power";
    }
    const face = this._face;
    const light = face === "power" && LIGHT_COLORS.has(color);
    el.disc.setAttribute("fill", face === "power" ? color : FACE_COLORS[face]);
    el.content.setAttribute("fill", light ? "#212121" : "#ffffff");
    el.trend.setAttribute("stroke", light ? "#212121" : "#ffffff");
    for (const [name, group] of Object.entries(el.faces)) {
      group.classList.toggle("hidden", name !== face);
    }
    this._drawDots(light);
    // The needle has the color of the first face, outlined when it is light
    el.needleBody.setAttribute("stroke", color);
    el.needleOutline.classList.toggle("hidden", !LIGHT_COLORS.has(color));

    // Power and apparent power
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
      // An injected power is shown on the arc by its absolute value
      const angle = powerAngle(Math.abs(power), Number(config.max_power) || DEFAULT_MAX_POWER);
      el.needle.style.transformOrigin = "100px 100px";
      el.needle.style.transform = `rotate(${angle}deg)`;
    }

    // Savings over 7 days on the lower arc, by default the sensor of the device
    const savings = numericState(hass, savingsEntity);
    el.savingsNeedle.classList.toggle("hidden", savings === null);
    if (savings !== null) {
      el.savingsNeedle.style.transformOrigin = "100px 100px";
      el.savingsNeedle.style.transform = `rotate(${savingsAngle(savings)}deg)`;
    }
    this._renderFaces(savings);

    this._updateTrend(power);
  }

  /**
   * Give the graduations a color that reads on the dial: the color of the
   * theme on the default or transparent dial, dark or light on a custom
   * color or on a color of the palette, as defined by the theme.
   */
  _updateLabelColor(dialColor) {
    const fill = dialFill(dialColor);
    let label = "";
    if (fill.startsWith("var(")) {
      const name = fill.slice(6, -7);
      const themed = getComputedStyle(this).getPropertyValue(`--${name}-color`);
      const rgb = parseColor(themed) || parseColor(PALETTE[name]);
      label = rgb ? labelColor(rgb) : "";
    } else if (fill.startsWith("rgb(")) {
      label = labelColor(parseColor(fill));
    }
    if (label !== this._labelColor) {
      this._labelColor = label;
      this._elements.svg.style.setProperty("--lm-label-color", label || null);
    }
  }

  /** Fill the faces other than the real-time power. */
  _renderFaces(savings) {
    const hass = this._hass;
    const sensors = this._sensors;
    const text = TRANSLATIONS[this._language];
    const el = this._elements;
    const locale = hass.locale?.language || this._language;
    const number = (value, digits = 0) =>
      new Intl.NumberFormat(locale, { maximumFractionDigits: digits, minimumFractionDigits: digits }).format(value);
    const shown = (value, write) => (value === null ? "—" : write(value));

    // Savings over 7 days: unknown until ecojoko has a reference week
    const savingsTitle = savings !== null && savings > 0 ? text.overconsumption_title : text.savings_title;
    el.savingsTitle.forEach((line, index) => {
      line.textContent = savingsTitle[index];
    });
    el.savingsValue.textContent = savings === null ? "" : `${number(savings)} %`;
    el.savingsMessage.classList.toggle("hidden", savings !== null);

    // Cost and consumption over 7 days, with the consumption of each day
    const cost = numericState(hass, sensors.cost_7_days);
    const energy = numericState(hass, sensors.consumption_7_days);
    el.costValue.textContent = shown(cost, (value) => `${number(value, 2)} €`);
    el.costEnergy.textContent = shown(energy, (value) => `${number(value, 1)} kWh`);
    const daily = hass.states[sensors.consumption_7_days]?.attributes?.daily_consumption;
    el.histogram.setAttribute("d", histogramPath(daily));

    // Max power of the month, of the year and since the start
    const watts = (key) => shown(numericState(hass, sensors[key]), (value) => `${number(value)} W`);
    el.maxMonth.textContent = watts("max_power_month");
    el.maxYear.textContent = watts("max_power_year");
    el.maxAlltime.textContent = watts("max_power_alltime");
  }

  /** Draw one dot per face at the bottom of the disc, the current one filled. */
  _drawDots(light) {
    const faces = this._faces;
    const key = faces.join(" ");
    if (this._dotsKey !== key) {
      this._dotsKey = key;
      const spacing = 7;
      const first = 100 - (spacing * (faces.length - 1)) / 2;
      // A single face needs no dot
      this._elements.dots.innerHTML = faces.length < 2 ? "" : faces.map((face, index) => `
        <g class="dot" data-face="${face}">
          <circle cx="${first + spacing * index}" cy="150" r="3.5" fill="transparent" />
          <circle class="mark" cx="${first + spacing * index}" cy="150" r="1.6" />
        </g>`).join("");
      for (const dot of this._elements.dots.querySelectorAll(".dot")) {
        dot.addEventListener("pointerup", (event) => {
          // Not a swipe: the dot shows its face
          event.stopPropagation();
          this._swipeStart = undefined;
          this._showFace(dot.dataset.face);
        });
      }
    }
    const ink = light ? "#212121" : "#ffffff";
    for (const mark of this._elements.dots.querySelectorAll(".mark")) {
      const current = mark.parentElement.dataset.face === this._face;
      mark.setAttribute("fill", current ? ink : "none");
      mark.setAttribute("stroke", ink);
    }
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
      this._form.computeHelper = (field) => ({
        tariff_entity: this._text().editor.tariff_helper,
        tempo_color_entity: this._text().editor.tempo_helper,
        return_seconds: this._text().editor.return_helper,
      })[field.name];
      this._form.addEventListener("value-changed", (event) => this._changed(event));
      this.appendChild(this._form);
    }
    this._form.hass = this._hass;
    this._form.data = formData(this._config);
    this._form.schema = editorSchema(this._hass, this._config);
  }

  _text() {
    return TRANSLATIONS[language(this._hass)];
  }

  _changed(event) {
    event.stopPropagation();
    const config = editedConfig(
      this._hass, this._config, fromFormData(this._config, event.detail.value));
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
    documentationURL: "https://github.com/jmcruvellier/little_monkey/blob/main/docs/cartes.md#little-monkey-cadran",
  });
}
