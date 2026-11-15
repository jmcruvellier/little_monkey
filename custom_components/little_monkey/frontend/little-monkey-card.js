/*
 * Little Monkey card for the Home Assistant dashboards.
 *
 * Served and loaded by the little_monkey integration (see card.py): no
 * Lovelace resource to add. Plain web component, without build step.
 *
 * This first version only shows the real-time power: the gauge comes next.
 */

const CARD_TYPE = "little-monkey-card";

const TRANSLATIONS = {
  en: {
    name: "Little Monkey",
    description: "Real-time power of the ecojoko box",
    no_entity: "Choose the real-time consumption sensor of Little Monkey (entity)",
    unavailable: "Unavailable",
  },
  fr: {
    name: "Petit Singe",
    description: "Puissance en temps réel du boîtier ecojoko",
    no_entity: "Choisissez le capteur Consommation Temps Réel de Little Monkey (entity)",
    unavailable: "Indisponible",
  },
};

/** Return the labels in the language of the user, English by default. */
function labels(hass) {
  const language = (hass?.locale?.language || hass?.language || "en").split("-")[0];
  return TRANSLATIONS[language] || TRANSLATIONS.en;
}

class LittleMonkeyCard extends HTMLElement {
  setConfig(config) {
    this._config = { ...config };
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  getCardSize() {
    return 2;
  }

  _render() {
    if (!this._config || !this._hass) {
      return;
    }
    if (!this.shadowRoot) {
      this.attachShadow({ mode: "open" });
    }
    const text = labels(this._hass);
    const state = this._config.entity && this._hass.states[this._config.entity];
    let value;
    if (!this._config.entity) {
      value = text.no_entity;
    } else if (!state || ["unavailable", "unknown"].includes(state.state)) {
      value = text.unavailable;
    } else {
      value = this._hass.formatEntityState
        ? this._hass.formatEntityState(state)
        : `${state.state} ${state.attributes.unit_of_measurement || ""}`;
    }
    this.shadowRoot.innerHTML = `
      <style>
        ha-card { padding: 16px; text-align: center; }
        .value { font-size: 2em; color: var(--primary-text-color); }
      </style>
      <ha-card header="${text.name}">
        <div class="value"></div>
      </ha-card>`;
    // Text set apart from the markup: it is never interpreted as HTML
    this.shadowRoot.querySelector(".value").textContent = value;
  }
}

if (!customElements.get(CARD_TYPE)) {
  customElements.define(CARD_TYPE, LittleMonkeyCard);
  const text = labels({ language: navigator.language });
  window.customCards = window.customCards || [];
  window.customCards.push({
    type: CARD_TYPE,
    name: text.name,
    description: text.description,
    documentationURL: "https://github.com/jmcruvellier/little_monkey/blob/main/CONFIGURATION.md",
  });
}
