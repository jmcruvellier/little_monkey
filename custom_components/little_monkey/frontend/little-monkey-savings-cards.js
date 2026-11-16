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
 */

const DOMAIN = "little_monkey";
const SUMMARY_TYPE = "little-monkey-savings-summary-card";
const SUMMARY_EDITOR_TYPE = "little-monkey-savings-summary-card-editor";
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
    },
    editor: {
      entity: "Savings over 12 months",
      consumption_entity: "Consumption cost over 12 months",
      reference_entity: "Reference cost over 12 months",
      unit: "Unit",
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
    },
    editor: {
      entity: "Économies sur 12 mois",
      consumption_entity: "Coût de la consommation sur 12 mois",
      reference_entity: "Coût de référence sur 12 mois",
      unit: "Unité",
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
    const digits = Math.abs(value) >= 100 ? 0 : 1;
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
    return 3;
  }

  getGridOptions() {
    return { columns: 6, min_columns: 4, rows: 3, min_rows: 3 };
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
    const missing = !this._config.entity || !this._hass.states[this._config.entity];
    warning.textContent = missing ? text.missing : "";
    warning.style.display = missing ? "" : "none";

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
