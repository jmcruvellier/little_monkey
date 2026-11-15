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
const DOMAIN = "little_monkey";

const TRANSLATIONS = {
  en: {
    name: "Little Monkey",
    description: "Real-time power dial of the ecojoko box",
    title: ["REAL-TIME", "POWER"],
    watts: "WATTS",
    no_entity: "Choose the real-time consumption sensor of Little Monkey",
    unavailable: "Unavailable",
  },
  fr: {
    name: "Petit Singe",
    description: "Cadran de puissance en temps réel du boîtier ecojoko",
    title: ["PUISSANCE", "TEMPS RÉEL"],
    watts: "WATTS",
    no_entity: "Choisissez le capteur Consommation Temps Réel de Little Monkey",
    unavailable: "Indisponible",
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
const LOWER_MIDDLE = 180; // 0 %
const LOWER_END = 235; // -20 %
const LOWER_LABELS = ["20", "10", "0", "-10", "-20"];

// Radii, in a 200 x 200 view box centered on (100, 100)
const R_BEZEL = 98;
const R_LABELS = 89;
const R_TRACK = 79;
const R_DISC = 60;

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

// Trend of the central disc
const TREND_PERIOD = 60 * 60 * 1000;

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
    const [wattsX, wattsY] = point(R_TRACK - 8, 0).split(" ");
    const [percentX, percentY] = point(R_TRACK - 8, 180).split(" ");

    if (!this.shadowRoot) {
      this.attachShadow({ mode: "open" });
    }
    this.shadowRoot.innerHTML = `
      <style>
        ha-card { padding: 16px; display: flex; justify-content: center; }
        svg { width: 100%; max-width: 360px; display: block; }
        .bezel { fill: var(--ha-card-background, var(--card-background-color, #fff)); stroke: var(--divider-color, #e0e0e0); stroke-width: 1; }
        .bezel-inner { fill: none; stroke: var(--divider-color, #e0e0e0); stroke-width: 0.6; }
        .track { fill: none; stroke: var(--secondary-text-color, #9e9e9e); stroke-opacity: 0.45; stroke-width: 5; stroke-linecap: round; }
        .labels text { fill: var(--secondary-text-color, #727272); font-size: 7.5px; text-anchor: middle; dominant-baseline: central; }
        .unit { fill: var(--secondary-text-color, #727272); font-size: 4px; letter-spacing: 0.3px; text-anchor: middle; dominant-baseline: central; }
        .saving { fill: none; stroke: url(#lm-saving); stroke-width: 5; stroke-linecap: round; }
        .needle { stroke: #3ea6e0; stroke-width: 5; stroke-linecap: round; transition: transform 0.8s ease-out; }
        .disc { stroke: rgba(0, 0, 0, 0.12); stroke-width: 0.6; transition: fill 0.5s; }
        .content text { text-anchor: middle; dominant-baseline: central; }
        .title { font-size: 6.5px; font-weight: 500; letter-spacing: 0.3px; }
        .value { font-size: 17px; font-weight: 500; }
        .apparent { font-size: 7px; opacity: 0.85; }
        .message { font-size: 5.5px; }
        .trend { fill: none; stroke-width: 1; stroke-linejoin: round; stroke-linecap: round; opacity: 0.9; }
        .hidden { display: none; }
      </style>
      <ha-card>
        <svg viewBox="0 0 200 200" role="img" aria-label="${text.title.join(" ")}">
          <defs>
            <linearGradient id="lm-saving" x1="0" y1="0" x2="1" y2="0">
              <stop offset="0" stop-color="#3ddc84" />
              <stop offset="1" stop-color="#26c6da" />
            </linearGradient>
          </defs>
          <circle class="bezel" cx="100" cy="100" r="${R_BEZEL}" />
          <circle class="bezel-inner" cx="100" cy="100" r="${R_BEZEL - 4}" />
          <path class="track" d="${arc(R_TRACK, POWER_START, POWER_END)}" />
          <path class="track" d="${arc(R_TRACK, LOWER_START, LOWER_MIDDLE)}" />
          <path class="saving" d="${arc(R_TRACK, LOWER_MIDDLE, LOWER_END)}" />
          <g class="labels">${ticks}${lowerTicks}</g>
          <text class="unit" x="${wattsX}" y="${wattsY}">${text.watts}</text>
          <text class="unit" x="${percentX}" y="${percentY}">%</text>
          <line class="needle" x1="100" y1="${100 - R_TRACK - 7}" x2="100" y2="${100 - R_TRACK + 7}" />
          <circle class="disc" cx="100" cy="100" r="${R_DISC}" fill="${DEFAULT_COLOR}" />
          <g class="content">
            <text class="title" x="100" y="70">${text.title[0]}</text>
            <text class="title" x="100" y="78.5">${text.title[1]}</text>
            <text class="value" x="100" y="96"></text>
            <text class="apparent" x="100" y="108"></text>
            <text class="message hidden" x="100" y="96"></text>
            <path class="trend" d="" />
          </g>
        </svg>
      </ha-card>`;
    const root = this.shadowRoot;
    this._elements = {
      needle: root.querySelector(".needle"),
      disc: root.querySelector(".disc"),
      content: root.querySelector(".content"),
      value: root.querySelector(".value"),
      apparent: root.querySelector(".apparent"),
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
    for (const entityId of [config.tariff_entity, config.tempo_color_entity]) {
      const parsed = parseTariff(entityId, entityId && hass.states[entityId]?.state);
      tariff.period = tariff.period || parsed.period;
      // The Tempo color entity has the last word on the color
      tariff.color = parsed.color || tariff.color;
    }
    const color = discColor(mode, tariff);
    el.disc.setAttribute("fill", color);
    el.content.setAttribute("fill", LIGHT_COLORS.has(color) ? "#212121" : "#ffffff");
    el.trend.setAttribute("stroke", LIGHT_COLORS.has(color) ? "#212121" : "#ffffff");

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

    this._updateTrend(power);
  }

  /** Keep the values of the last hour and draw them in the disc. */
  _updateTrend(power) {
    const entityId = this._config.entity;
    if (!entityId) {
      this._elements.trend.setAttribute("d", "");
      return;
    }
    if (this._trendEntity !== entityId) {
      this._trendEntity = entityId;
      this._trend = [];
      this._loadHistory(entityId);
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
    this._trend = this._trend.filter((sample) => sample.time >= now - TREND_PERIOD);
    this._drawTrend(now);
  }

  /** Load the history of the last hour, once per entity. */
  async _loadHistory(entityId) {
    const start = new Date(Date.now() - TREND_PERIOD).toISOString();
    try {
      const history = await this._hass.callWS({
        type: "history/history_during_period",
        start_time: start,
        entity_ids: [entityId],
        minimal_response: true,
        no_attributes: true,
        significant_changes_only: false,
      });
      if (this._trendEntity !== entityId) {
        return;
      }
      const samples = (history[entityId] || [])
        .map((item) => ({ time: item.lu * 1000, value: Number(item.s) }))
        .filter((sample) => Number.isFinite(sample.value) && Number.isFinite(sample.time));
      const first = this._trend[0]?.time ?? Infinity;
      this._trend = [...samples.filter((sample) => sample.time < first), ...this._trend];
      this._drawTrend(Date.now());
    } catch (error) {
      // No trend from the history: the card draws the values it receives
      console.debug("Little Monkey card: history not available", error);
    }
  }

  _drawTrend(now) {
    const samples = this._trend;
    if (samples.length < 2) {
      this._elements.trend.setAttribute("d", "");
      return;
    }
    const left = 76;
    const width = 48;
    const top = 114;
    const height = 12;
    const values = samples.map((sample) => sample.value);
    const low = Math.min(...values);
    const high = Math.max(...values);
    const range = high - low || 1;
    const start = now - TREND_PERIOD;
    const path = samples.map((sample, index) => {
      const x = left + (width * (sample.time - start)) / TREND_PERIOD;
      const y = top + height - (height * (sample.value - low)) / range;
      return `${index ? "L" : "M"} ${Math.max(x, left).toFixed(2)} ${y.toFixed(2)}`;
    });
    // The last value lasts until now
    const lastY = top + height - (height * (values[values.length - 1] - low)) / range;
    path.push(`L ${left + width} ${lastY.toFixed(2)}`);
    this._elements.trend.setAttribute("d", path.join(" "));
  }
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
