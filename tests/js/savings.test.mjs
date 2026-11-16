// Tests of the savings cards of Little Monkey, run with: node --test tests/js
import assert from "node:assert/strict";
import test from "node:test";

// The module defines custom elements: a browser is not needed for the
// functions tested here
globalThis.HTMLElement = class {};
globalThis.customElements = { get: () => true };
const cards = await import(
  "../../custom_components/little_monkey/frontend/little-monkey-savings-cards.js"
);

// Sensors of a Little Monkey device and their states
function fakeHass(states = {}) {
  const entities = {};
  const keys = {
    "sensor.eco_savings": "savings_12_months",
    "sensor.eco_cost": "consumption_cost_12_months",
    "sensor.eco_reference": "reference_cost_12_months",
    "sensor.other_savings": "savings_12_months",
    "sensor.other_cost": "consumption_cost_12_months",
  };
  for (const [entityId, key] of Object.entries(keys)) {
    entities[entityId] = {
      entity_id: entityId,
      platform: "little_monkey",
      translation_key: key,
      device_id: entityId.startsWith("sensor.eco") ? "eco" : "other",
    };
  }
  return { language: "fr", entities, states };
}

const STATES = {
  "sensor.eco_savings": { state: "337.63", attributes: { savings_kwh: 1617.28 } },
  "sensor.eco_cost": { state: "483.6", attributes: { consumption: 1701.72 } },
  "sensor.eco_reference": { state: "821.23", attributes: { reference_consumption: 3319 } },
};

test("the bars of the summary are scaled on the longest", () => {
  const rows = cards.summaryRows({ consumption: 483.6, reference: 821.23, savings: 337.63 });
  assert.deepEqual(rows.map((row) => row.key), ["consumption", "reference", "savings"]);
  assert.equal(rows[1].ratio, 1);
  assert.equal(rows[0].ratio.toFixed(3), (483.6 / 821.23).toFixed(3));
  assert.equal(rows[2].label, "savings");
  assert.equal(rows[2].color, cards.SUMMARY_COLORS.savings);
});

test("negative savings are an overconsumption", () => {
  const rows = cards.summaryRows({ consumption: 900, reference: 800, savings: -100 });
  assert.equal(rows[2].label, "overconsumption");
  assert.equal(rows[2].color, cards.SUMMARY_COLORS.overconsumption);
  assert.equal(rows[2].ratio.toFixed(3), (100 / 900).toFixed(3));
});

test("unknown values have no bar", () => {
  const rows = cards.summaryRows({ consumption: null, reference: null, savings: null });
  assert.deepEqual(rows.map((row) => row.ratio), [0, 0, 0]);
});

test("the summary finds the cost sensors of the device", () => {
  const hass = fakeHass(STATES);
  assert.deepEqual(cards.summaryEntities(hass, { entity: "sensor.eco_savings" }), {
    savings: "sensor.eco_savings",
    consumption: "sensor.eco_cost",
    reference: "sensor.eco_reference",
  });
  assert.deepEqual(cards.summaryValues(hass, { entity: "sensor.eco_savings" }), {
    consumption: 483.6, reference: 821.23, savings: 337.63,
  });
  assert.deepEqual(cards.summaryValues(hass, { entity: "sensor.eco_savings", unit: "kwh" }), {
    consumption: 1701.72, reference: 3319, savings: 1617.28,
  });
});

test("unavailable sensors give no value", () => {
  const hass = fakeHass({ ...STATES, "sensor.eco_cost": { state: "unavailable", attributes: {} } });
  assert.equal(cards.summaryValues(hass, { entity: "sensor.eco_savings" }).consumption, null);
});

test("values are written in euros or kWh", () => {
  const nbsp = /[  ]/g;
  assert.equal(cards.formatValue("fr", 337.63, "eur").replace(nbsp, " "), "337,63 €");
  assert.equal(cards.formatValue("en", 337.63, "eur"), "€337.63");
  assert.equal(cards.formatValue("fr", 1617.28, "kwh").replace(nbsp, " "), "1 617 kWh");
  assert.equal(cards.formatValue("en", 2.58, "kwh"), "2.6 kWh");
  assert.equal(cards.formatValue("fr", null, "eur"), "—");
});

test("a new summary card takes the savings of the first device", () => {
  assert.deepEqual(cards.summaryStubConfig(fakeHass()), {
    type: "custom:little-monkey-savings-summary-card",
    entity: "sensor.eco_savings",
  });
  assert.deepEqual(cards.summaryStubConfig({ entities: {} }), {
    type: "custom:little-monkey-savings-summary-card",
  });
});

test("another device in the editor takes its own cost sensors", () => {
  const hass = fakeHass();
  const previous = { entity: "sensor.eco_savings", consumption_entity: "sensor.eco_cost", title: "" };
  assert.deepEqual(
    cards.editedConfig(hass, previous, { ...previous, entity: "sensor.other_savings" }),
    { entity: "sensor.other_savings", consumption_entity: "sensor.other_cost" },
  );
  // A sensor chosen by hand is kept
  const chosen = { entity: "sensor.eco_savings", consumption_entity: "sensor.mine" };
  assert.equal(
    cards.editedConfig(hass, chosen, { ...chosen, entity: "sensor.other_savings" }).consumption_entity,
    "sensor.mine",
  );
});

test("the editor of the summary has its fields", () => {
  assert.deepEqual(cards.summarySchema({ language: "fr" }).map((field) => field.name), [
    "entity", "consumption_entity", "reference_entity", "unit", "title",
  ]);
});
