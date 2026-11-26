// Tests of the navigation of the analysis card, run with: node --test tests/js
//
// A tiny stand-in for the shadow root: each selector gives its own element,
// so that writing to the wrong element is seen. Its own file: the custom
// elements are kept here instead of being ignored as in analysis.test.mjs
import assert from "node:assert/strict";
import test from "node:test";

const defined = new Map();
globalThis.HTMLElement = class {};
globalThis.window = globalThis;
globalThis.customElements = {
  get: (name) => defined.get(name),
  define: (name, element) => defined.set(name, element),
};
await import("../../custom_components/little_monkey/frontend/little-monkey-analysis-cards.js");
const AnalysisCard = defined.get("little-monkey-analysis-card");

function fakeElement() {
  return {
    textContent: "", innerHTML: "", disabled: false, style: {}, dataset: {},
    classList: { toggle() {} },
    addEventListener() {},
  };
}

function fakeRoot() {
  const elements = new Map();
  return {
    elements,
    innerHTML: "",
    querySelector(selector) {
      if (!elements.has(selector)) {
        elements.set(selector, fakeElement());
      }
      return elements.get(selector);
    },
    querySelectorAll: () => [],
  };
}

const ANALYSIS = (start, name) => ({
  available: true, start, total: 10,
  categories: [{ id: 7, name, color: "#022469", consumption: 10, cost: 2 }],
});

test("the name of the period follows the arrows, even for a period already read", () => {
  const card = new AnalysisCard();
  const root = fakeRoot();
  card.shadowRoot = root;
  card._hass = { states: { "sensor.eco": { state: "1" } }, locale: { language: "fr" }, language: "fr", entities: {},
    // Never answers: the months are already read
    callWS: () => new Promise(() => {}) };
  card.setConfig({ entity: "sensor.eco", period: "month" });
  card._period = "month";
  // Both months already read: no request, the categories are on the card
  card._cache.set("month:latest", ANALYSIS("2026-10-01", "Talon de consommation"));
  card._cache.set("month:2026-09-01", ANALYSIS("2026-09-01", "Frigos, Congélateurs"));
  card._latest.month = "2026-10-01";
  const name = () => root.querySelector(".nav .name").textContent;
  // The name of a category, before the navigation in the card, is a .name
  // too: the name of the period must not be written there
  const category = root.querySelector(".name");

  card._signature = null;
  card._render();
  assert.equal(name(), "Octobre 2026");
  card._go(-1);
  assert.equal(name(), "Septembre 2026");
  card._go(1);
  assert.equal(name(), "Octobre 2026");
  assert.equal(category.textContent, "");
});
