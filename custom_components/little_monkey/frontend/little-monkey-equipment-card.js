/*
 * Equipment card of Little Monkey for the Home Assistant dashboards.
 *
 * Served and loaded by the little_monkey integration (see card.py), like the
 * dial card: no Lovelace resource to add. Plain web component, without
 * build step and without the internal libraries of the Home Assistant
 * frontend.
 *
 * little-monkey-equipment-card: the equipments of the installation, read
 * with the service get_equipments. Each piloted equipment (water heater,
 * plug...) has its mode, its power, the buttons of ecojoko and, opened, its
 * measures and a timeline of its day; the others are listed with their
 * connection. Nothing depends on the type of an equipment: its buttons come
 * from the controls ecojoko offers for it.
 */

const DOMAIN = "little_monkey";
const EQUIPMENT_TYPE = "little-monkey-equipment-card";
const EQUIPMENT_EDITOR_TYPE = "little-monkey-equipment-card-editor";
const DOCUMENTATION =
  "https://github.com/jmcruvellier/little_monkey/blob/main/docs/cartes.md#%C3%A9quipements";
// The equipments are read again every minute: the service answers at once
const EQUIPMENT_REFRESH = 60000;
// Hours of forced mode offered, as in ecojoko
export const FORCED_HOURS = [1, 2, 3, 4];
// Longest forced mode of another duration, in minutes, as the service accepts
export const MAX_FORCED_MINUTES = 24 * 60;

/** Return the minutes of a forced mode of another duration, null if not valid. */
export function customMinutes(value) {
  const minutes = Number(value);
  return Number.isInteger(minutes) && minutes >= 1 && minutes <= MAX_FORCED_MINUTES ? minutes : null;
}

const TRANSLATIONS = {
  en: {
    name: "Little Monkey equipments",
    description: "The equipments piloted by ecojoko (water heater, plug...): mode, power, day, and the buttons of ecojoko.",
    title: "Equipments",
    auto_on: "Automatic · on",
    auto_off: "Automatic · off",
    forced_until: "Forced until {time}",
    absence_until: "Absence until {time}",
    forced: "Forced",
    absence: "Absence",
    on: "On",
    off: "Off",
    buttons: { forced: "Forced", absence: "Absence", auto: "Automatic", on: "Turn on", off: "Turn off" },
    confirm: { auto: "Back to automatic?", on: "Turn on?", off: "Turn off?" },
    forced_for: "Forced for:",
    other: "Other…",
    minutes: "min",
    absence_end: "Back on:",
    validate: "Confirm",
    cancel: "Cancel",
    hours: "{n} h",
    energy: "Today",
    cost: "Cost today",
    voltage: "Voltage",
    max_power: "Max power",
    legend: { on: "On", forced: "Forced", absence: "Absence" },
    connected: "Connected",
    disconnected: "Disconnected",
    battery: "Battery {value}",
    signal: "Signal {value}",
    none: "No equipment piloted by ecojoko",
    error: "Equipments not read",
    command_error: "Command not sent: {error}",
    missing: "Little Monkey sensor not found",
    missing_option: "Little Monkey sensor not found. If it was a sensor of an equipment, turn on the “Piloted equipments” option in the options of the integration, or choose a sensor of the Little Monkey device, such as Real-Time Consumption.",
    option: "Turn on the “Piloted equipments” option in the options of the Little Monkey integration (Settings › Devices & services › Little Monkey › Configure).",
    editor: {
      entity: "A sensor of the Little Monkey device",
      equipment: "Only this equipment (its name or ecojoko id)",
      show_list: "List the other equipments",
      title: "Title",
    },
  },
  fr: {
    name: "Petit Singe : équipements",
    description: "Les équipements pilotés par ecojoko (chauffe-eau, prise…) : mode, puissance, journée, et les boutons d'ecojoko.",
    title: "Équipements",
    auto_on: "Automatique · allumé",
    auto_off: "Automatique · éteint",
    forced_until: "Forcé jusqu'à {time}",
    absence_until: "Absence jusqu'à {time}",
    forced: "Forcé",
    absence: "Absence",
    on: "Allumé",
    off: "Éteint",
    buttons: { forced: "Forcé", absence: "Absence", auto: "Automatique", on: "Allumer", off: "Éteindre" },
    confirm: { auto: "Revenir en automatique ?", on: "Allumer ?", off: "Éteindre ?" },
    forced_for: "Forcer pendant :",
    other: "Autre…",
    minutes: "min",
    absence_end: "Retour le :",
    validate: "Valider",
    cancel: "Annuler",
    hours: "{n} h",
    energy: "Aujourd'hui",
    cost: "Coût du jour",
    voltage: "Tension",
    max_power: "Puissance max",
    legend: { on: "Allumé", forced: "Forcé", absence: "Absence" },
    connected: "Connecté",
    disconnected: "Déconnecté",
    battery: "Batterie {value}",
    signal: "Signal {value}",
    none: "Aucun équipement piloté par ecojoko",
    error: "Équipements non lus",
    command_error: "Commande non envoyée : {error}",
    missing: "Capteur Little Monkey introuvable",
    missing_option: "Capteur Little Monkey introuvable. S'il s'agissait d'un capteur d'un équipement, activez l'option « Équipements pilotés » dans les options de l'intégration, ou choisissez un capteur de l'appareil Little Monkey, comme Consommation Temps Réel.",
    option: "Activez l'option « Équipements pilotés » dans les options de l'intégration Little Monkey (Paramètres › Appareils et services › Little Monkey › Configurer).",
    editor: {
      entity: "Un capteur de l'appareil Little Monkey",
      equipment: "Seulement cet équipement (son nom ou son id ecojoko)",
      show_list: "Lister les autres équipements",
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

// Icons by type of equipment; an unknown type has a generic one
const ICONS = {
  LULO: "mdi:water-boiler",
  LULO_SUPPLY: "mdi:water-boiler",
  ON_OFF_PLUG: "mdi:power-socket-eu",
  POWER_METER: "mdi:meter-electric-outline",
  LINKY: "mdi:meter-electric-outline",
  TEMP_HUM: "mdi:thermometer",
  THERMOSTAT: "mdi:thermostat",
  GAZ_SUPPLY: "mdi:fire",
  FIOUL_SUPPLY: "mdi:barrel",
  WOOD_SUPPLY: "mdi:campfire",
  WATER_SUPPLY: "mdi:water",
  ENPHASE: "mdi:solar-power",
  AP_SYSTEMS: "mdi:solar-power",
  RENAULT: "mdi:car-electric",
};
// Colors of the states, in the timeline and on the icon
export const STATE_COLORS = { on: "#2f9e44", forced: "#f08c00", absence: "#868e96", off: "#adb5bd" };

/** Return the icon of an equipment. */
export function equipmentIcon(equipment) {
  return ICONS[equipment?.type] || "mdi:devices";
}

/** Tell whether a configured equipment (name or id) is this one. */
function isConfigured(equipment, wanted) {
  const value = String(wanted).trim().toLowerCase();
  return String(equipment.id) === value || String(equipment.name ?? "").trim().toLowerCase() === value;
}

/** Return the piloted equipments shown, in the order of ecojoko. */
export function pilotedEquipments(equipments, config) {
  return (equipments || []).filter((equipment) =>
    (equipment.controls || []).length
    && (!config?.equipment || isConfigured(equipment, config.equipment)));
}

/** Return the other equipments listed: none for a card of one equipment. */
export function otherEquipments(equipments, config) {
  if (config?.show_list === false || config?.equipment) {
    return [];
  }
  return (equipments || []).filter((equipment) => !(equipment.controls || []).length);
}

/** Return the state of an equipment for its color: on, forced, absence or off. */
export function stateKind(equipment) {
  const state = equipment?.state || {};
  if (state.mode === "forced" || state.mode === "absence") {
    return state.mode;
  }
  return state.on ? "on" : "off";
}

/** Return the local day "YYYY-MM-DD" and the minutes of an ISO time, as written. */
function localParts(iso) {
  const match = String(iso ?? "").match(/^(\d{4}-\d{2}-\d{2})T(\d{2}):(\d{2})(?::(\d{2}))?/);
  if (!match) {
    return null;
  }
  return { day: match[1], minutes: Number(match[2]) * 60 + Number(match[3]) + Number(match[4] || 0) / 60 };
}

/** Return the end of a mode as the user reads it: a time today, a day and a time later. */
export function untilLabel(locale, iso, now = new Date()) {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) {
    return "";
  }
  const time = new Intl.DateTimeFormat(locale, { hour: "2-digit", minute: "2-digit" }).format(date);
  if (date.toDateString() === now.toDateString()) {
    return time;
  }
  const day = new Intl.DateTimeFormat(locale, { weekday: "short", day: "numeric", month: "short" }).format(date);
  return `${day} ${time}`;
}

/** Return the mode of an equipment, in words. */
export function modeLabel(text, equipment, locale, now = new Date()) {
  const state = equipment?.state || {};
  switch (state.mode) {
    case "auto":
      return state.on ? text.auto_on : text.auto_off;
    case "forced":
    case "absence":
      return state.until
        ? text[`${state.mode}_until`].replace("{time}", untilLabel(locale, state.until, now))
        : text[state.mode];
    case "on":
    case "off":
      return text[state.mode];
    default:
      // A mode the integration does not know: as ecojoko words it
      return state.switch_state || "";
  }
}

/** Return the buttons of an equipment: the ones ecojoko shows in its state. */
export function equipmentButtons(equipment) {
  const controls = equipment?.controls || [];
  if (controls.includes("auto")) {
    // In a forced mode, ecojoko shows only the way back to automatic
    return equipment.state?.mode && equipment.state.mode !== "auto" ? ["auto"] : ["forced", "absence"];
  }
  return controls.filter((control) => control === "on" || control === "off");
}

/**
 * Tell whether a button is shown selected: the one whose question is open,
 * or for on and off the current state of the equipment.
 */
export function isSelected(equipment, action, panel) {
  if (panel?.id === equipment?.id && panel?.mode === action) {
    return true;
  }
  return (action === "on" || action === "off") && equipment?.state?.mode === action;
}

// Timeline of a day, in the units of the SVG: a minute a unit
export const DAY_BOX = { width: 1440, height: 40, base: 36, top: 4, band: 5 };
// Narrowest period drawn, in minutes: a forced mode of a few minutes would
// be a pixel wide, and not seen
export const MIN_PERIOD = 12;

/**
 * Return the timeline of the day of an equipment: the periods it was on,
 * forced or absent, and its power curve. A period still lasting ends now
 * (in minutes since midnight), or at the end of a past day.
 */
export function dayTimeline(day, nowMinutes = DAY_BOX.width, box = DAY_BOX) {
  const date = day?.date;
  const segments = [];
  for (const change of day?.switches || []) {
    const start = localParts(change.start);
    const end = change.end ? localParts(change.end) : null;
    if (!start || !date || (end && end.day < date) || start.day > date) {
      continue;
    }
    const kind = change.forced ? (change.on ? "forced" : "absence") : change.on ? "on" : "off";
    if (kind === "off") {
      continue;
    }
    const x = start.day < date ? 0 : start.minutes;
    const stop = end ? (end.day > date ? box.width : end.minutes) : nowMinutes;
    if (stop > x) {
      // A short period is widened, within the day, to be seen
      const width = Math.max(stop - x, MIN_PERIOD);
      segments.push({ kind, x: Math.min(x, box.width - width), width });
    }
  }
  const points = (day?.power || [])
    .map((point) => ({ at: localParts(point.time), value: Number(point.value) }))
    .filter((point) => point.at && point.at.day === date && Number.isFinite(point.value));
  const max = Math.max(1, ...points.map((point) => point.value));
  const height = box.base - box.top;
  const curve = points.map((point, index) =>
    `${index ? "L" : "M"}${point.at.minutes.toFixed(1)} ${(box.base - (point.value / max) * height).toFixed(1)}`).join(" ");
  return { segments, curve, max };
}

/** Return the default end of an absence: the next midnight, for a datetime input. */
export function absenceDefault(now = new Date()) {
  const midnight = new Date(now.getFullYear(), now.getMonth(), now.getDate() + 1);
  const pad = (value) => String(value).padStart(2, "0");
  return `${midnight.getFullYear()}-${pad(midnight.getMonth() + 1)}-${pad(midnight.getDate())}T00:00`;
}

/** Return the values of an equipment shown when it is opened. */
export function equipmentMetrics(text, equipment, locale, states) {
  const day = equipment?.day || {};
  const state = equipment?.state || {};
  const currency = new Intl.NumberFormat(locale, { style: "currency", currency: "EUR" });
  return [
    ["energy", day.energy, 2, "kWh"],
    ["cost", day.cost, 2, "EUR"],
    ["voltage", state.voltage, 0, "V"],
    ["max_power", state.max_power, 0, "W"],
  ].map(([key, value, digits, unit]) => ({ key, digits, unit, ...liveValue(states, equipment, key, value, unit) }))
    .filter((metric) => metric.value !== null)
    .map(({ key, value, digits, unit }) => ({
      key,
      label: text[key],
      value: unit === "EUR" ? currency.format(value) : formatNumber(locale, value, digits, unit),
    }));
}

/** Return a number with its unit, in the language of the user. */
function formatNumber(locale, value, digits, unit) {
  const number = new Intl.NumberFormat(locale, { maximumFractionDigits: digits }).format(value);
  return unit ? `${number} ${unit}` : number;
}

/**
 * Return the value shown for a value of an equipment. The state of its
 * entity when it has one, as in its details: the list of the equipments is
 * read by ecojoko every five minutes only, the real time power of the
 * Linky key is read at each poll. The value read with the list otherwise.
 */
export function liveValue(states, equipment, key, value, unit) {
  const entity = equipment?.entities?.[key];
  const state = entity ? states?.[entity] : undefined;
  if (state) {
    const number = Number(state.state);
    return {
      value: state.state !== "" && Number.isFinite(number) ? number : null,
      unit: state.attributes?.unit_of_measurement ?? unit,
    };
  }
  const number = Number(value);
  return { value: value !== null && value !== undefined && Number.isFinite(number) ? number : null, unit };
}

/**
 * Return the attribute that opens the details of a value: the entity of the
 * value, given by the service get_equipments, if it has one.
 */
export function entityAttribute(equipment, key) {
  const entity = equipment?.entities?.[key];
  return entity ? ` data-entity="${escapeHtml(entity)}"` : "";
}

/** Return the measures of an equipment that is not piloted: power, temperature, humidity. */
export function otherMeasures(equipment, locale, states) {
  const state = equipment?.state || {};
  return [
    ["power", state.power, 0, "W"],
    ["temperature", state.temperature, 1, "°C"],
    ["humidity", state.humidity, 0, "%"],
  ].map(([key, value, digits, unit]) => ({ key, digits, ...liveValue(states, equipment, key, value, unit) }))
    .filter((measure) => measure.value !== null)
    .map(({ key, value, digits, unit }) => ({ key, value: formatNumber(locale, value, digits, unit) }));
}

/**
 * Return the details of an equipment that is not piloted, under its name:
 * where it is placed, its connection, its batteries (level and voltage) and
 * its signal, each with the key of its entity.
 */
export function otherDetails(equipment, text, locale) {
  const details = [];
  const given = (value) => value !== null && value !== undefined;
  if (equipment?.install_state) {
    details.push({ key: "install_state", value: String(equipment.install_state) });
  }
  if (equipment?.connected === false) {
    details.push({ key: "connection", value: equipment.status || text.disconnected, disconnected: true });
  }
  if (given(equipment?.battery) || given(equipment?.battery_voltage)) {
    const values = [];
    if (given(equipment.battery)) {
      values.push(formatNumber(locale, equipment.battery, 0, "%"));
    }
    if (given(equipment.battery_voltage)) {
      values.push(formatNumber(locale, equipment.battery_voltage, 2, "V"));
    }
    details.push({ key: given(equipment.battery) ? "battery" : "battery_voltage",
      value: text.battery.replace("{value}", values.join(" · ")) });
  }
  if (given(equipment?.signal)) {
    details.push({ key: "signal", value: text.signal.replace("{value}", formatNumber(locale, equipment.signal, 0, "%")) });
  }
  return details;
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

/** Return the configuration of a new equipment card, on the first device. */
export function equipmentStubConfig(hass) {
  const config = { type: `custom:${EQUIPMENT_TYPE}` };
  const entity = findEntity(hass, "realtime_consumption");
  if (entity) {
    config.entity = entity;
  }
  return config;
}

/** Return the fields of the editor. */
export function equipmentSchema() {
  return [
    {
      name: "entity",
      required: true,
      selector: { entity: { filter: { integration: DOMAIN, domain: "sensor" } } },
    },
    { name: "equipment", selector: { text: {} } },
    { name: "show_list", default: true, selector: { boolean: {} } },
    { name: "title", selector: { text: {} } },
  ];
}

const STYLES = `
  ha-card { padding: 16px; }
  .title { font-size: 1.15em; font-weight: 500; color: var(--primary-text-color); margin-bottom: 8px; }
  .warning, .message { color: var(--secondary-text-color); text-align: center; padding: 16px 8px; }
  .error { color: var(--error-color, #db4437); font-size: 0.85em; margin: 4px 0; }
  .equipment { border: 1px solid var(--divider-color, #e0e0e0); border-radius: 12px; padding: 10px 12px; margin-bottom: 8px; }
  .head { display: flex; align-items: center; gap: 10px; }
  .equipment.many .head { cursor: pointer; }
  .icon { width: 36px; height: 36px; border-radius: 50%; flex: none; display: flex; align-items: center; justify-content: center;
    color: #fff; }
  .icon ha-icon { --mdc-icon-size: 20px; }
  .who { flex: 1; min-width: 0; }
  .who .name { color: var(--primary-text-color); font-weight: 500; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .who .mode { color: var(--secondary-text-color); font-size: 0.85em; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .power { color: var(--primary-text-color); font-weight: 500; white-space: nowrap; }
  .chevron { color: var(--secondary-text-color); transition: transform 0.2s; }
  .equipment.open .chevron { transform: rotate(180deg); }
  .actions, .panel { display: flex; flex-wrap: wrap; align-items: center; gap: 6px; margin-top: 8px; }
  .panel { background: color-mix(in srgb, var(--primary-color, #03a9f4) 8%, transparent); border-radius: 10px; padding: 6px 8px; }
  .panel .label { color: var(--secondary-text-color); font-size: 0.85em; margin-right: 4px; }
  button { border: 1px solid var(--divider-color, #e0e0e0); border-radius: 18px; background: none; color: var(--primary-text-color);
    font: inherit; font-size: 0.85em; padding: 5px 12px; cursor: pointer; display: inline-flex; align-items: center; gap: 4px; }
  button ha-icon { --mdc-icon-size: 16px; }
  button.selected { border-color: var(--primary-color, #03a9f4); font-weight: 500;
    background: color-mix(in srgb, var(--primary-color, #03a9f4) 22%, transparent); }
  input.minutes { width: 5em; }
  input.minutes, input[type=datetime-local] { font: inherit; font-size: 0.85em; padding: 3px 6px; border-radius: 8px;
    border: 1px solid var(--divider-color, #e0e0e0); background: var(--card-background-color, #fff); color: var(--primary-text-color); }
  button.primary { background: var(--primary-color, #03a9f4); border-color: var(--primary-color, #03a9f4); color: var(--text-primary-color, #fff); }
  button:disabled { opacity: 0.5; cursor: default; }
  .details { margin-top: 10px; border-top: 1px solid var(--divider-color, #e0e0e0); padding-top: 8px; }
  .metrics { display: grid; grid-template-columns: repeat(auto-fill, minmax(110px, 1fr)); gap: 4px 12px; margin-bottom: 8px; }
  .metric .label { color: var(--secondary-text-color); font-size: 0.8em; }
  .metric .value { color: var(--primary-text-color); font-weight: 500; }
  .timeline { width: 100%; height: 40px; display: block; }
  .timeline .base { stroke: var(--divider-color, #e0e0e0); stroke-width: 1; vector-effect: non-scaling-stroke; }
  .timeline .curve { fill: none; stroke: var(--primary-color, #03a9f4); stroke-width: 1.5; vector-effect: non-scaling-stroke; }
  .hours-axis { display: flex; justify-content: space-between; font-size: 0.75em; color: var(--secondary-text-color); }
  .legend { display: flex; flex-wrap: wrap; gap: 4px 12px; font-size: 0.75em; color: var(--secondary-text-color); margin-top: 4px; }
  .legend .swatch { display: inline-block; width: 10px; height: 10px; border-radius: 2px; margin-right: 4px; vertical-align: -1px; }
  .others { margin-top: 4px; }
  .other { display: flex; align-items: center; gap: 10px; padding: 4px 2px; }
  .other .icon { width: 28px; height: 28px; background: var(--secondary-background-color, #e5e5e5); color: var(--primary-text-color); }
  .other .icon ha-icon { --mdc-icon-size: 16px; }
  .other .text { flex: 1; min-width: 0; }
  .other .name { color: var(--primary-text-color); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .other .other-details { color: var(--secondary-text-color); font-size: 0.8em; line-height: 1.4; }
  .other .detail { white-space: nowrap; }
  .other .detail.disconnected { color: var(--error-color, #db4437); }
  .other .info { color: var(--secondary-text-color); font-size: 0.85em; white-space: nowrap; }
  [data-entity] { cursor: pointer; }
  [data-entity]:hover { text-decoration: underline dotted; }
  .timeline[data-entity]:hover { text-decoration: none; opacity: 0.85; }
  .other .info.measure { color: var(--primary-text-color); font-weight: 500; }
  .other .info.disconnected { color: var(--error-color, #db4437); }
`;

class LittleMonkeyEquipmentCard extends HTMLElement {
  setConfig(config) {
    if (!config) {
      throw new Error("Invalid configuration");
    }
    const entity = this._config?.entity;
    this._config = { ...config };
    if (entity !== this._config.entity) {
      this._equipments = null;
      this._error = false;
    }
    // Equipment opened, panel shown {id, kind} and command being sent
    this._opened = this._opened ?? null;
    this._panel = null;
    this._busy = null;
    this._commandError = null;
    this._built = false;
    this._render();
  }

  set hass(hass) {
    const first = !this._hass;
    this._hass = hass;
    // The mode of an equipment changed (after a command, at the end of a
    // forced mode...): the card reads the equipments at once instead of
    // waiting for its next reading. Not for every value: the power of the
    // Linky key changes every few seconds
    const states = JSON.stringify(this._modeStates());
    if (first || (this._equipments && states !== this._states)) {
      this._read();
    }
    this._states = states;
    this._render();
  }

  connectedCallback() {
    clearInterval(this._timer);
    this._timer = setInterval(() => this._read(), EQUIPMENT_REFRESH);
  }

  disconnectedCallback() {
    clearInterval(this._timer);
  }

  getCardSize() {
    // Masonry view: rows of 50 pixels, for an equipment and the list
    return 4;
  }

  getGridOptions() {
    // The whole width of a section by default, half of it at least
    return { columns: 12, min_columns: 6 };
  }

  static getConfigElement() {
    return document.createElement(EQUIPMENT_EDITOR_TYPE);
  }

  static getStubConfig(hass) {
    return equipmentStubConfig(hass);
  }

  _text() {
    return TRANSLATIONS[language(this._hass)];
  }

  _locale() {
    return this._hass.locale?.language || this._hass.language;
  }

  /** Read the equipments, as last read by the integration. */
  async _read() {
    if (!this._hass || !this._config?.entity || this._reading) {
      return;
    }
    this._reading = true;
    try {
      const data = {};
      const entry = configEntryId(this._hass, this._config.entity);
      if (entry) {
        data.config_entry_id = entry;
      }
      const result = await this._hass.callWS({
        type: "call_service", domain: DOMAIN, service: "get_equipments", service_data: data, return_response: true,
      });
      this._equipments = result.response?.equipments || [];
      // The option of the equipments is off: the card asks to turn it on
      this._disabled = result.response?.enabled === false;
      this._error = false;
      // The modes read: a change of them makes the card read again
      this._states = JSON.stringify(this._modeStates());
    } catch (error) {
      console.debug("Little Monkey card: equipments not read", error);
      this._error = true;
    } finally {
      this._reading = false;
      this._signature = null;
      this._render();
    }
  }

  /** Pilot an equipment, then read the equipments again. */
  async _send(equipment, mode, extra = {}) {
    this._busy = equipment.id;
    this._commandError = null;
    this._panel = null;
    this._signature = null;
    this._render();
    try {
      await this._hass.callWS({
        type: "call_service", domain: DOMAIN, service: "set_equipment_mode",
        service_data: { device_id: equipment.device_id, mode, ...extra },
      });
    } catch (error) {
      this._commandError = { id: equipment.id, message: error?.message || String(error) };
    } finally {
      this._busy = null;
      this._reading = false;
      await this._read();
    }
  }

  _build() {
    if (!this.shadowRoot) {
      this.attachShadow({ mode: "open" });
    }
    this.shadowRoot.innerHTML = `
      <style>${STYLES}</style>
      <ha-card>
        <div class="title"></div>
        <div class="warning"></div>
        <div class="body"></div>
      </ha-card>`;
    this.shadowRoot.querySelector(".body").addEventListener("click", (event) => this._click(event));
    this._built = true;
  }

  _click(event) {
    // A value opens its details, as in the other cards
    const value = event.target.closest?.("[data-entity]");
    if (value) {
      event.stopPropagation();
      this.dispatchEvent(new CustomEvent("hass-more-info", {
        detail: { entityId: value.dataset.entity }, bubbles: true, composed: true,
      }));
      return;
    }
    const target = event.target;
    const block = target.closest?.("[data-id]");
    const equipment = (this._equipments || []).find((item) => String(item.id) === block?.dataset.id);
    if (!equipment) {
      return;
    }
    const button = target.closest?.("button");
    if (button) {
      event.stopPropagation();
      const action = button.dataset.action;
      if (action === "cancel") {
        this._panel = null;
      } else if (action === "hours") {
        this._send(equipment, "forced", { duration: Number(button.dataset.hours) * 60 });
        return;
      } else if (action === "custom") {
        this._panel = { ...this._panel, custom: true };
        this._custom = null;
      } else if (action === "custom-ok") {
        const input = block.querySelector("input.minutes");
        const minutes = customMinutes(input?.value);
        if (minutes === null) {
          input?.focus();
          return;
        }
        this._send(equipment, "forced", { duration: minutes });
        return;
      } else if (action === "absence-ok") {
        const input = block.querySelector("input[type=datetime-local]");
        const until = new Date(input?.value || "");
        if (Number.isNaN(until.getTime()) || until <= new Date()) {
          input?.focus();
          return;
        }
        this._send(equipment, "absence", { until: until.toISOString() });
        return;
      } else if (action === "confirm") {
        this._send(equipment, button.dataset.mode);
        return;
      } else {
        // A button of ecojoko: forced and absence ask how long, the others to confirm
        this._panel = { id: equipment.id, kind: action === "forced" || action === "absence" ? action : "confirm", mode: action };
        this._absence = null;
      }
      this._signature = null;
      this._render();
      return;
    }
    if (target.closest?.(".head") && block.classList.contains("many")) {
      this._opened = this._opened === equipment.id ? null : equipment.id;
      this._signature = null;
      this._render();
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
    const now = new Date();
    const signature = JSON.stringify([
      this._equipments, this._disabled, this._error, this._opened, this._panel, this._busy, this._commandError,
      this._config, locale, now.getHours(), now.getMinutes(), this._shownStates(),
    ]);
    if (signature === this._signature) {
      return;
    }
    this._signature = signature;
    const root = this.shadowRoot;
    root.querySelector(".title").textContent = this._config.title || text.title;
    const missing = !this._config.entity || !this._hass.states[this._config.entity];
    const warning = root.querySelector(".warning");
    warning.style.display = "none";
    const body = root.querySelector(".body");
    if (missing) {
      // Its sensor is gone, most likely a sensor of an equipment removed
      // with the option of the equipments: the installation is unknown
      body.innerHTML = `<div class="message">${escapeHtml(text.missing_option)}</div>`;
      return;
    }
    if (!this._equipments) {
      body.innerHTML = `<div class="message">${escapeHtml(this._error ? text.error : "…")}</div>`;
      return;
    }
    if (this._disabled) {
      body.innerHTML = `<div class="message">${escapeHtml(text.option)}</div>`;
      return;
    }
    // The end of an absence being typed is kept when the card is drawn again
    const input = body.querySelector("input[type=datetime-local]");
    if (input && this._panel?.kind === "absence") {
      this._absence = input.value;
    }
    const minutes = body.querySelector("input.minutes");
    if (minutes && this._panel?.custom) {
      this._custom = minutes.value;
    }
    const piloted = pilotedEquipments(this._equipments, this._config);
    const others = otherEquipments(this._equipments, this._config);
    // With several piloted equipments, one line each; one opens at a time
    const many = piloted.length > 1;
    const blocks = piloted.map((equipment) =>
      this._block(equipment, text, locale, now, many, !many || this._opened === equipment.id)).join("");
    const none = piloted.length ? "" : `<div class="message">${escapeHtml(text.none)}</div>`;
    const list = others.length
      ? `<div class="others">${others.map((equipment) => this._other(equipment, text, locale)).join("")}</div>`
      : "";
    body.innerHTML = blocks + none + list;
  }

  /** Return the modes of the piloted equipments, with the time they changed. */
  _modeStates() {
    return (this._equipments || []).map((equipment) => {
      const state = this._hass.states[equipment.entities?.mode];
      return state ? [state.state, state.last_changed, state.attributes?.until] : null;
    });
  }

  /** Return the states of the entities of the values shown, to draw them again when they change. */
  _shownStates() {
    return (this._equipments || []).flatMap((equipment) =>
      Object.values(equipment.entities || {}).map((entity) => this._hass.states[entity]?.state));
  }

  /** Return the HTML of a piloted equipment. */
  _block(equipment, text, locale, now, many, open) {
    const kind = stateKind(equipment);
    const power = liveValue(this._hass.states, equipment, "power", equipment.state?.power, "W");
    const busy = this._busy === equipment.id;
    const buttons = equipmentButtons(equipment).map((action) => {
      const selected = isSelected(equipment, action, this._panel);
      return `
      <button data-action="${action}" class="${selected ? "selected" : ""}" aria-pressed="${selected}"${busy ? " disabled" : ""}>${escapeHtml(text.buttons[action])}</button>`;
    }).join("");
    const error = this._commandError?.id === equipment.id
      ? `<div class="error">${escapeHtml(text.command_error.replace("{error}", this._commandError.message))}</div>` : "";
    return `
      <div class="equipment${many ? " many" : ""}${open ? " open" : ""}" data-id="${escapeHtml(equipment.id)}">
        <div class="head">
          <div class="icon" style="background: ${STATE_COLORS[kind]}"><ha-icon icon="${equipmentIcon(equipment)}"></ha-icon></div>
          <div class="who">
            <div class="name">${escapeHtml(equipment.name)}</div>
            <div class="mode"${entityAttribute(equipment, "mode")}>${escapeHtml(modeLabel(text, equipment, locale, now))}</div>
          </div>
          <div class="power"${entityAttribute(equipment, "power")}>${power.value === null ? "" : escapeHtml(formatNumber(locale, power.value, 0, power.unit))}</div>
          ${many ? '<ha-icon class="chevron" icon="mdi:chevron-down"></ha-icon>' : ""}
        </div>
        <div class="actions">${buttons}</div>
        ${this._panel?.id === equipment.id ? this._panelHtml(text, now) : ""}
        ${error}
        ${open ? this._details(equipment, text, locale, now) : ""}
      </div>`;
  }

  /** Return the HTML of the question of a button: how long, until when, or sure. */
  _panelHtml(text, now) {
    const cancel = `<button data-action="cancel">${escapeHtml(text.cancel)}</button>`;
    if (this._panel.kind === "forced") {
      const hours = FORCED_HOURS.map((n) =>
        `<button class="primary" data-action="hours" data-hours="${n}">${escapeHtml(text.hours.replace("{n}", n))}</button>`).join("");
      // Another duration, in minutes
      const custom = this._panel.custom
        ? `<input class="minutes" type="number" min="1" max="${MAX_FORCED_MINUTES}" step="5" value="${escapeHtml(this._custom ?? "30")}"
            aria-label="${escapeHtml(text.minutes)}"><span class="label">${escapeHtml(text.minutes)}</span>
          <button class="primary" data-action="custom-ok">${escapeHtml(text.validate)}</button>`
        : `<button data-action="custom">${escapeHtml(text.other)}</button>`;
      return `<div class="panel"><span class="label">${escapeHtml(text.forced_for)}</span>${hours}${custom}${cancel}</div>`;
    }
    if (this._panel.kind === "absence") {
      return `<div class="panel"><span class="label">${escapeHtml(text.absence_end)}</span>
        <input type="datetime-local" value="${escapeHtml(this._absence || absenceDefault(now))}">
        <button class="primary" data-action="absence-ok">${escapeHtml(text.validate)}</button>${cancel}</div>`;
    }
    const mode = this._panel.mode;
    return `<div class="panel"><span class="label">${escapeHtml(text.confirm[mode] || "")}</span>
      <button class="primary" data-action="confirm" data-mode="${escapeHtml(mode)}">${escapeHtml(text.validate)}</button>${cancel}</div>`;
  }

  /** Return the HTML of the measures and of the timeline of the day. */
  _details(equipment, text, locale, now) {
    const metrics = equipmentMetrics(text, equipment, locale, this._hass.states).map((metric) => `
      <div class="metric"${entityAttribute(equipment, metric.key)}><div class="label">${escapeHtml(metric.label)}</div><div class="value">${escapeHtml(metric.value)}</div></div>`).join("");
    const day = equipment.day;
    let timeline = "";
    if (day && (day.switches?.length || day.power?.length)) {
      const today = day.date === `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(now.getDate()).padStart(2, "0")}`;
      const { segments, curve } = dayTimeline(day, today ? now.getHours() * 60 + now.getMinutes() : DAY_BOX.width);
      // Each period: a pale area, and a band of its plain color at the top
      const rects = segments.map((segment) => `
        <rect x="${segment.x.toFixed(1)}" y="${DAY_BOX.top}" width="${segment.width.toFixed(1)}" height="${DAY_BOX.base - DAY_BOX.top}" fill="${STATE_COLORS[segment.kind]}" opacity="0.3" />
        <rect x="${segment.x.toFixed(1)}" y="0" width="${segment.width.toFixed(1)}" height="${DAY_BOX.band}" fill="${STATE_COLORS[segment.kind]}" />`).join("");
      const kinds = [...new Set(segments.map((segment) => segment.kind))];
      const legend = kinds.length
        ? `<div class="legend">${kinds.map((kind) =>
          `<span><span class="swatch" style="background: ${STATE_COLORS[kind]}"></span>${escapeHtml(text.legend[kind])}</span>`).join("")}</div>`
        : "";
      timeline = `
        <svg class="timeline"${entityAttribute(equipment, "mode")} viewBox="0 0 ${DAY_BOX.width} ${DAY_BOX.height}" preserveAspectRatio="none" role="img">
          ${rects}<line class="base" x1="0" x2="${DAY_BOX.width}" y1="${DAY_BOX.base}" y2="${DAY_BOX.base}" />
          ${curve ? `<path class="curve" d="${curve}" />` : ""}
        </svg>
        <div class="hours-axis"><span>0h</span><span>6h</span><span>12h</span><span>18h</span><span>24h</span></div>${legend}`;
    }
    if (!metrics && !timeline) {
      return "";
    }
    return `<div class="details">${metrics ? `<div class="metrics">${metrics}</div>` : ""}${timeline}</div>`;
  }

  /** Return the HTML of an equipment that is not piloted. */
  _other(equipment, text, locale) {
    // Its measures first, then its connection
    const measures = otherMeasures(equipment, locale, this._hass.states).map((measure) =>
      `<span class="info measure"${entityAttribute(equipment, measure.key)}>${escapeHtml(measure.value)}</span>`);
    // Under its name, where it is placed, its connection, batteries and signal
    const details = otherDetails(equipment, text, locale).map((detail) =>
      `<span class="detail${detail.disconnected ? " disconnected" : ""}"${entityAttribute(equipment, detail.key)}>${
        escapeHtml(detail.value)}</span>`);
    return `
      <div class="other" data-id="${escapeHtml(equipment.id)}">
        <div class="icon"><ha-icon icon="${equipmentIcon(equipment)}"></ha-icon></div>
        <div class="text">
          <div class="name">${escapeHtml(equipment.name)}</div>
          ${details.length ? `<div class="other-details">${details.join('<span class="separator"> · </span>')}</div>` : ""}
        </div>
        ${measures.join("")}
      </div>`;
  }
}

class LittleMonkeyEquipmentCardEditor extends HTMLElement {
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
          // The list is shown by default
          if (value === undefined || value === null || value === "" || (key === "show_list" && value === true)) {
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
    this._form.data = { show_list: true, ...this._config };
    this._form.schema = equipmentSchema();
  }
}

if (!customElements.get(EQUIPMENT_EDITOR_TYPE)) {
  customElements.define(EQUIPMENT_EDITOR_TYPE, LittleMonkeyEquipmentCardEditor);
}
if (!customElements.get(EQUIPMENT_TYPE)) {
  customElements.define(EQUIPMENT_TYPE, LittleMonkeyEquipmentCard);
  const text = TRANSLATIONS[language({ language: navigator.language })];
  window.customCards = window.customCards || [];
  window.customCards.push({
    type: EQUIPMENT_TYPE,
    name: text.name,
    description: text.description,
    preview: true,
    documentationURL: DOCUMENTATION,
  });
}
