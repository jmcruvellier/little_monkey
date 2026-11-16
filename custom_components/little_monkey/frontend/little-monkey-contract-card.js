/*
 * Contract card of Little Monkey for the Home Assistant dashboards.
 *
 * Served and loaded by the little_monkey integration (see card.py), like the
 * dial card: no Lovelace resource to add. Plain web component, without
 * build step and without the internal libraries of the Home Assistant
 * frontend.
 *
 * little-monkey-contract-card: the contract of the installation, read from
 * the Contract sensor: the offer, a dial of the 24 hours with the off-peak
 * hours and the current time, the current period and the next change, the
 * tariff bands with their energy of the day, and the subscription.
 */

const DOMAIN = "little_monkey";
const CONTRACT_TYPE = "little-monkey-contract-card";
const CONTRACT_EDITOR_TYPE = "little-monkey-contract-card-editor";
const DOCUMENTATION =
  "https://github.com/jmcruvellier/little_monkey/blob/main/CONFIGURATION.md#carte-du-contrat";

const TRANSLATIONS = {
  en: {
    name: "Little Monkey contract",
    description: "Your electricity contract: offer, off-peak hours, current period and tariff bands.",
    since: "Since {date}",
    now: "Now",
    today: "Today",
    off_peak: "Off-peak hours",
    peak: "Peak hours",
    next: "{period} at {time}",
    in: "in {duration}",
    hours: "{h} h {m}",
    minutes: "{m} min",
    tempo: { blue: "Blue day", white: "White day", red: "Red day" },
    subscription: "Subscription",
    off_peak_legend: "Off-peak hours",
    unknown: "Contract not read yet",
    missing: "Contract sensor not found",
    editor: { entity: "Contract sensor", title: "Title" },
  },
  fr: {
    name: "Petit Singe : contrat",
    description: "Votre contrat d'électricité : offre, heures creuses, période en cours et tranches tarifaires.",
    since: "Depuis le {date}",
    now: "Maintenant",
    today: "Aujourd'hui",
    off_peak: "Heures creuses",
    peak: "Heures pleines",
    next: "{period} à {time}",
    in: "dans {duration}",
    hours: "{h} h {m}",
    minutes: "{m} min",
    tempo: { blue: "Jour bleu", white: "Jour blanc", red: "Jour rouge" },
    subscription: "Abonnement",
    off_peak_legend: "Heures creuses",
    unknown: "Contrat pas encore lu",
    missing: "Capteur Contrat introuvable",
    editor: { entity: "Capteur Contrat", title: "Titre" },
  },
};

/** Return the language of the user, English when it is not translated. */
function language(hass) {
  const lang = (hass?.locale?.language || hass?.language || "en").split("-")[0];
  return TRANSLATIONS[lang] ? lang : "en";
}

// Colors of the dial: off-peak and peak hours, by kind of day
export const DIAL_COLORS = {
  hchp: { off: "#85b7eb", peak: "#185fa5" },
  blue: { off: "#00008b", peak: "#2f6fe0" },
  white: { off: "#9e9e9e", peak: "#e0e0e0" },
  red: { off: "#8b0000", peak: "#ff3b3b" },
};
// Dial of the 24 hours, in the units of the SVG
const DIAL = { size: 160, radius: 60, width: 16 };
const UNKNOWN_STATES = new Set(["unavailable", "unknown", "none", ""]);

/** Escape a text for the HTML of a card. */
function escapeHtml(text) {
  return String(text ?? "").replace(/[&<>"']/g, (character) => `&#${character.charCodeAt(0)};`);
}

/** Return a time "HH:MM" as minutes since midnight, null when it is not one. */
export function minutesOf(time) {
  const match = String(time ?? "").match(/^(\d{1,2}):(\d{2})/);
  if (!match) {
    return null;
  }
  const minutes = Number(match[1]) * 60 + Number(match[2]);
  return minutes >= 0 && minutes <= 24 * 60 ? minutes : null;
}

/** Return a number of minutes since midnight as "HH:MM". */
export function timeOf(minutes) {
  const value = ((minutes % 1440) + 1440) % 1440;
  return `${String(Math.floor(value / 60)).padStart(2, "0")}:${String(value % 60).padStart(2, "0")}`;
}

/**
 * Return the off-peak slots as [start, end] in minutes, an end before its
 * start meaning the next day (22:00 - 06:00).
 */
export function offPeakSlots(timeslots) {
  return (timeslots || [])
    .map((slot) => [minutesOf(slot?.start), minutesOf(slot?.stop)])
    .filter(([start, end]) => start !== null && end !== null && start !== end);
}

/** Tell whether a time, in minutes since midnight, is in the off-peak hours. */
export function isOffPeak(slots, minutes) {
  return slots.some(([start, end]) =>
    start < end ? minutes >= start && minutes < end : minutes >= start || minutes < end);
}

/**
 * Return the next change of period after a time: the minutes of the change
 * and whether off-peak hours start then. null without off-peak hours.
 */
export function nextChange(slots, minutes) {
  if (!slots.length) {
    return null;
  }
  const now = isOffPeak(slots, minutes);
  for (let step = 1; step <= 1440; step += 1) {
    const time = (minutes + step) % 1440;
    if (isOffPeak(slots, time) !== now) {
      return { minutes: time, offPeak: !now, wait: step };
    }
  }
  return null;
}

/** Return a duration in minutes: "1 h 45", "20 min". */
export function durationLabel(text, minutes) {
  if (minutes < 60) {
    return text.minutes.replace("{m}", minutes);
  }
  return text.hours.replace("{h}", Math.floor(minutes / 60)).replace("{m}", String(minutes % 60).padStart(2, "0"));
}

/** Return the color of the Tempo day of a period ("hp_white"), or null. */
export function tempoDay(period) {
  const match = String(period ?? "").match(/_(blue|white|red)$/);
  return match ? match[1] : null;
}

/** Return the initials of the supplier for its badge: "EDF", "TE". */
export function supplierBadge(supplier) {
  const text = String(supplier ?? "").trim();
  if (!text) {
    return "?";
  }
  const words = text.split(/\s+/);
  if (words.length === 1) {
    return text.slice(0, 4).toUpperCase();
  }
  return words.slice(0, 3).map((word) => word[0]).join("").toUpperCase();
}

/** Return a point of the dial at a time, in minutes since midnight (0 h = top). */
function dialPoint(minutes, radius = DIAL.radius) {
  const radians = ((minutes / 1440) * 360 - 90) * (Math.PI / 180);
  const center = DIAL.size / 2;
  return [center + radius * Math.cos(radians), center + radius * Math.sin(radians)];
}

/** Return the SVG path of an arc of the dial between two times. */
export function dialArc(start, end, radius = DIAL.radius) {
  const length = (((end - start) % 1440) + 1440) % 1440 || 1440;
  const [x1, y1] = dialPoint(start, radius);
  const [x2, y2] = dialPoint(start + Math.min(length, 1439.9), radius);
  const large = length > 720 ? 1 : 0;
  return `M ${x1.toFixed(2)} ${y1.toFixed(2)} A ${radius} ${radius} 0 ${large} 1 ${x2.toFixed(2)} ${y2.toFixed(2)}`;
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

/** Return the configuration of a new contract card, on the first device. */
export function contractStubConfig(hass) {
  const config = { type: `custom:${CONTRACT_TYPE}` };
  const entity = findEntity(hass, "contract");
  if (entity) {
    config.entity = entity;
  }
  return config;
}

/** Return the fields of the editor. */
export function contractSchema() {
  return [
    {
      name: "entity",
      required: true,
      selector: { entity: { filter: { integration: DOMAIN, domain: "sensor" } } },
    },
    { name: "title", selector: { text: {} } },
  ];
}

/** Return the numeric value of an entity, null when it has none. */
function numericState(hass, entityId) {
  const state = entityId && hass?.states?.[entityId];
  if (!state || UNKNOWN_STATES.has(state.state)) {
    return null;
  }
  const value = Number(state.state);
  return Number.isFinite(value) ? value : null;
}

/** Return what the card shows, from the states of the device. */
export function contractView(hass, entityId, now = new Date()) {
  const state = hass?.states?.[entityId];
  if (!state || UNKNOWN_STATES.has(state.state)) {
    return null;
  }
  const attributes = state.attributes || {};
  const sensors = deviceEntities(hass, entityId);
  const period = hass.states?.[sensors.current_tariff_period]?.state;
  const slots = offPeakSlots(attributes.off_peak_timeslots);
  const minutes = now.getHours() * 60 + now.getMinutes();
  // The off-peak hours of the contract give the period at once; the period
  // of the integration, deduced from the counters a few minutes late, is
  // taken only without them. It always gives the Tempo color of the day
  const offPeak = slots.length ? isOffPeak(slots, minutes) : /^hc/.test(period ?? "");
  const bands = (attributes.bands || []).map((band) => ({
    ...band,
    energy: numericState(hass, sensors[band.key]),
    entity: sensors[band.key],
  }));
  return {
    offer: state.state,
    supplier: attributes.supplier,
    power: attributes.power,
    subscription: attributes.subscription_price,
    start: attributes.start_date,
    slots,
    minutes,
    offPeak,
    tempo: tempoDay(period),
    next: nextChange(slots, minutes),
    bands,
  };
}

const STYLES = `
  ha-card { padding: 16px; }
  .title { font-size: 1.15em; font-weight: 500; color: var(--primary-text-color); margin-bottom: 12px; }
  .warning, .message { color: var(--secondary-text-color); text-align: center; padding: 16px 8px; }
  .offer { display: flex; align-items: center; gap: 12px; margin-bottom: 8px; }
  .badge { width: 44px; height: 44px; border-radius: 50%; flex: none; display: flex; align-items: center; justify-content: center;
    font-weight: 600; font-size: 0.85em; background: color-mix(in srgb, var(--primary-color, #03a9f4) 18%, transparent); color: var(--primary-text-color); }
  .offer .name { font-weight: 500; color: var(--primary-text-color); }
  .offer .details { font-size: 0.85em; color: var(--secondary-text-color); }
  .now { display: flex; align-items: center; gap: 16px; }
  .now svg { width: 150px; flex: none; }
  .dial-label { fill: var(--secondary-text-color, #727272); font-size: 12px; text-anchor: middle; dominant-baseline: central; }
  .needle { stroke: var(--primary-text-color, #212121); stroke-width: 2.5; stroke-linecap: round; }
  .pivot { fill: var(--primary-text-color, #212121); }
  .state .caption { font-size: 0.85em; color: var(--secondary-text-color); }
  .state .period { font-size: 1.3em; font-weight: 500; margin: 2px 0 6px; }
  .state .change { font-size: 0.85em; color: var(--secondary-text-color); }
  .legend { font-size: 0.8em; color: var(--secondary-text-color); margin: 6px 0 10px; display: flex; align-items: center; gap: 6px; }
  .legend .swatch { width: 10px; height: 10px; border-radius: 2px; flex: none; }
  .rows { border-top: 1px solid var(--divider-color, #e0e0e0); padding-top: 8px; font-size: 0.95em; }
  .row { display: flex; justify-content: space-between; align-items: center; padding: 3px 0; gap: 8px; }
  .row.band { cursor: pointer; }
  .tag { border-radius: 6px; padding: 1px 6px; font-size: 0.8em; margin-right: 6px; font-weight: 500; }
  .tag.hc { background: color-mix(in srgb, #85b7eb 35%, transparent); }
  .tag.hp { background: color-mix(in srgb, #185fa5 35%, transparent); }
  .row .label { color: var(--primary-text-color); }
  .row .value { color: var(--primary-text-color); white-space: nowrap; }
  .row.subscription .label, .row.subscription .value { color: var(--secondary-text-color); }
`;

class LittleMonkeyContractCard extends HTMLElement {
  setConfig(config) {
    if (!config) {
      throw new Error("Invalid configuration");
    }
    this._config = { ...config };
    this._signature = null;
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  connectedCallback() {
    // The needle and the next change move with the time
    clearInterval(this._timer);
    this._timer = setInterval(() => this._render(), 60 * 1000);
  }

  disconnectedCallback() {
    clearInterval(this._timer);
  }

  getCardSize() {
    return 5;
  }

  getGridOptions() {
    // Height of the content: a fixed number of rows would cut it
    return { columns: 6, min_columns: 4 };
  }

  static getConfigElement() {
    return document.createElement(CONTRACT_EDITOR_TYPE);
  }

  static getStubConfig(hass) {
    return contractStubConfig(hass);
  }

  _render() {
    if (!this._config || !this._hass) {
      return;
    }
    if (!this.shadowRoot) {
      this.attachShadow({ mode: "open" });
      this.shadowRoot.addEventListener("click", (event) => {
        const row = event.target.closest?.("[data-entity]");
        if (row) {
          this.dispatchEvent(new CustomEvent("hass-more-info", {
            detail: { entityId: row.dataset.entity }, bubbles: true, composed: true,
          }));
        }
      });
    }
    const text = TRANSLATIONS[language(this._hass)];
    const locale = this._hass.locale?.language || this._hass.language;
    const view = contractView(this._hass, this._config.entity);
    const signature = JSON.stringify([view, this._config.title, locale]);
    if (signature === this._signature) {
      return;
    }
    this._signature = signature;
    const title = this._config.title ? `<div class="title">${escapeHtml(this._config.title)}</div>` : "";
    let body;
    if (!this._hass.states[this._config.entity]) {
      body = `<div class="warning">${escapeHtml(text.missing)}</div>`;
    } else if (!view) {
      body = `<div class="message">${escapeHtml(text.unknown)}</div>`;
    } else {
      body = this._body(view, text, locale);
    }
    this.shadowRoot.innerHTML = `<style>${STYLES}</style><ha-card>${title}${body}</ha-card>`;
  }

  _body(view, text, locale) {
    const details = [];
    if (view.start) {
      const date = new Intl.DateTimeFormat(locale, { day: "numeric", month: "long", year: "numeric", timeZone: "UTC" })
        .format(new Date(`${view.start}T00:00:00Z`));
      details.push(text.since.replace("{date}", date));
    }
    if (view.power) {
      details.push(`${view.power} kVA`);
    }
    const colors = DIAL_COLORS[view.tempo || "hchp"];
    const center = DIAL.size / 2;
    const offArcs = view.slots.map(([start, end]) =>
      `<path d="${dialArc(start, end)}" fill="none" stroke="${colors.off}" stroke-width="${DIAL.width}" />`).join("");
    const [needleX, needleY] = dialPoint(view.minutes, DIAL.radius - DIAL.width / 2 - 6);
    const labels = [[0, "0h"], [360, "6h"], [720, "12h"], [1080, "18h"]].map(([minutes, label]) => {
      const [x, y] = dialPoint(minutes, DIAL.radius + DIAL.width / 2 + 10);
      return `<text class="dial-label" x="${x.toFixed(1)}" y="${y.toFixed(1)}">${label}</text>`;
    }).join("");
    const periodName = view.offPeak ? text.off_peak : text.peak;
    const caption = view.tempo ? `${text.today} · ${text.tempo[view.tempo]}` : text.now;
    const periodColor = view.offPeak ? colors.off : colors.peak;
    let change = "";
    if (view.next) {
      change = `<div class="change">${escapeHtml(text.next
        .replace("{period}", view.next.offPeak ? text.off_peak : text.peak)
        .replace("{time}", timeOf(view.next.minutes)))}</div>
        <div class="change">${escapeHtml(text.in.replace("{duration}", durationLabel(text, view.next.wait)))}</div>`;
    }
    const legend = view.slots.length
      ? `<div class="legend"><span class="swatch" style="background: ${colors.off}"></span>${escapeHtml(text.off_peak_legend)} ${
        escapeHtml(view.slots.map(([start, end]) => `${timeOf(start)}–${timeOf(end)}`).join(", "))}</div>`
      : "";
    const energy = new Intl.NumberFormat(locale, { maximumFractionDigits: 2 });
    const bands = view.bands.map((band) => {
      const tag = band.category === "hc" || band.category === "hp"
        ? `<span class="tag ${band.category}">${band.category.toUpperCase()}</span>` : "";
      const value = band.energy === null ? "—" : `${energy.format(band.energy)} kWh`;
      return `<div class="row band"${band.entity ? ` data-entity="${escapeHtml(band.entity)}"` : ""}>
        <span class="label">${tag}${escapeHtml(band.name)}</span><span class="value">${escapeHtml(value)}</span></div>`;
    }).join("");
    const subscription = Number.isFinite(Number(view.subscription)) && view.subscription !== null
      ? `<div class="row subscription"><span class="label">${escapeHtml(text.subscription)}</span><span class="value">${
        escapeHtml(new Intl.NumberFormat(locale, { style: "currency", currency: "EUR" }).format(view.subscription))}</span></div>`
      : "";
    const rows = bands || subscription ? `<div class="rows">${bands}${subscription}</div>` : "";
    return `
      <div class="offer">
        <div class="badge">${escapeHtml(supplierBadge(view.supplier))}</div>
        <div><div class="name">${escapeHtml(view.offer)}</div><div class="details">${escapeHtml(details.join(" · "))}</div></div>
      </div>
      <div class="now">
        <svg viewBox="-14 -14 188 188" role="img" aria-label="${escapeHtml(periodName)}">
          <circle cx="${center}" cy="${center}" r="${DIAL.radius}" fill="none" stroke="${colors.peak}" stroke-width="${DIAL.width}" />
          ${offArcs}${labels}
          <line class="needle" x1="${center}" y1="${center}" x2="${needleX.toFixed(2)}" y2="${needleY.toFixed(2)}" />
          <circle class="pivot" cx="${center}" cy="${center}" r="4" />
        </svg>
        <div class="state">
          <div class="caption">${escapeHtml(caption)}</div>
          <div class="period" style="color: color-mix(in srgb, ${periodColor} 75%, var(--primary-text-color, #212121))">${escapeHtml(periodName)}</div>
          ${change}
        </div>
      </div>
      ${legend}${rows}`;
  }
}

class LittleMonkeyContractCardEditor extends HTMLElement {
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
    this._form.schema = contractSchema();
  }
}

if (!customElements.get(CONTRACT_EDITOR_TYPE)) {
  customElements.define(CONTRACT_EDITOR_TYPE, LittleMonkeyContractCardEditor);
}
if (!customElements.get(CONTRACT_TYPE)) {
  customElements.define(CONTRACT_TYPE, LittleMonkeyContractCard);
  const text = TRANSLATIONS[language({ language: navigator.language })];
  window.customCards = window.customCards || [];
  window.customCards.push({
    type: CONTRACT_TYPE,
    name: text.name,
    description: text.description,
    preview: true,
    documentationURL: DOCUMENTATION,
  });
}
