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
  assert.equal(cards.formatValue("en", 2.58, "kwh"), "2.58 kWh");
  assert.equal(cards.formatValue("en", 55.65, "kwh"), "55.7 kWh");
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

// --- Detail of the savings

test("periods start on Monday, on the first of the month, on January 1st", () => {
  assert.equal(cards.periodStart("week", "2026-11-16"), "2026-11-16");
  assert.equal(cards.periodStart("week", "2026-11-22"), "2026-11-16");
  assert.equal(cards.periodStart("week", "2026-11-01"), "2026-10-26");
  assert.equal(cards.periodStart("month", "2026-11-16"), "2026-11-01");
  assert.equal(cards.periodStart("year", "2026-11-16"), "2026-01-01");
});

test("the previous and next periods", () => {
  assert.equal(cards.shiftPeriod("week", "2026-11-18", -1), "2026-11-09");
  assert.equal(cards.shiftPeriod("week", "2026-01-01", -1), "2025-12-22");
  assert.equal(cards.shiftPeriod("month", "2026-03-31", -1), "2026-02-01");
  assert.equal(cards.shiftPeriod("month", "2026-12-15", 1), "2027-01-01");
  assert.equal(cards.shiftPeriod("year", "2026-11-16", -1), "2025-01-01");
});

test("the names of the periods and of the bars", () => {
  assert.equal(cards.periodLabel("fr", "week", "2026-11-18"), "16–22 nov. 2026");
  // Intl puts thin or non-breaking spaces around the dash
  const spaces = (text) => text.replace(/[   ]/g, " ");
  assert.equal(spaces(cards.periodLabel("fr", "week", "2026-10-28")), "26 oct. – 1 nov. 2026");
  assert.equal(spaces(cards.periodLabel("en", "week", "2026-11-18")), "Nov 16 – 22, 2026");
  assert.equal(cards.periodLabel("fr", "month", "2026-11-18"), "Novembre 2026");
  assert.equal(cards.periodLabel("en", "year", "2026-11-18"), "2026");
  assert.equal(cards.barLabel("fr", "week", "2026-11-16"), "lun.");
  assert.equal(cards.barLabel("fr", "month", "2026-11-02"), "2–8");
  assert.equal(cards.barLabel("fr", "month", "2026-11-30"), "30–6");
  assert.equal(cards.barLabel("fr", "year", "2026-03-01"), "M");
  assert.equal(cards.barTitle("fr", "week", "2026-11-16"), "Lundi 16 novembre");
  assert.equal(cards.barTitle("fr", "year", "2026-03-01"), "Mars 2026");
});

test("today is the day of the browser", () => {
  assert.equal(cards.today(new Date(2026, 0, 5, 23, 30)), "2026-01-05");
});

test("the scale shows zero, and the negative side only when needed", () => {
  assert.deepEqual(cards.chartScale([25.85, 0, 67.62, null]), { min: 0, max: 80, step: 20 });
  assert.deepEqual(cards.chartScale([-0.35, null]), { min: -0.1 * 4, max: 0, step: 0.1 });
  assert.deepEqual(cards.chartScale([-3.09, 1.2]), { min: -4, max: 2, step: 1 });
  assert.deepEqual(cards.chartScale([null, 0]), { min: 0, max: 1, step: 0.5 });
});

test("the bars go up for a saving and down for an overconsumption", () => {
  const box = { width: 100, height: 110, left: 0, right: 0, top: 0, bottom: 10 };
  const { rects, zero, ticks } = cards.chartGeometry([2, -2, null, 0], box);
  assert.equal(zero, 50);
  assert.equal(rects[0].y, 0);
  assert.equal(rects[0].height, 50);
  assert.equal(rects[0].color, cards.DETAIL_COLORS.savings);
  assert.equal(rects[1].y, 50);
  assert.equal(rects[1].color, cards.DETAIL_COLORS.overconsumption);
  assert.equal(rects[2].y, undefined);
  assert.equal(rects[3].height, 0);
  assert.deepEqual(ticks.map((tick) => tick.value), [-2, -1.5, -1, -0.5, 0, 0.5, 1, 1.5, 2]);
});

test("the bars are in euros or in kWh", () => {
  const bars = [{ savings: -0.35, savings_kwh: -2.58 }, { savings: null, savings_kwh: null }];
  assert.deepEqual(cards.barValues(bars, "eur"), [-0.35, null]);
  assert.deepEqual(cards.barValues(bars, "kwh"), [-2.58, null]);
  assert.deepEqual(cards.barValues(undefined, "eur"), []);
});

function detailHass(states = {}) {
  const entities = {};
  for (const key of ["savings_week", "savings_month", "savings_year"]) {
    entities[`sensor.eco_${key}`] = {
      entity_id: `sensor.eco_${key}`, platform: "little_monkey", translation_key: key, device_id: "eco",
    };
  }
  return { language: "fr", entities, states, devices: { eco: { config_entries: ["entry1"] } } };
}

test("the detail finds the sensors of the current periods", () => {
  const hass = detailHass();
  assert.deepEqual(cards.periodEntities(hass, "sensor.eco_savings_month"), {
    week: "sensor.eco_savings_week",
    month: "sensor.eco_savings_month",
    year: "sensor.eco_savings_year",
  });
  assert.equal(cards.configEntryId(hass, "sensor.eco_savings_week"), "entry1");
  assert.equal(cards.configEntryId(hass, "sensor.unknown"), undefined);
});

test("the current period comes from its sensor", () => {
  const bars = [{ date: "2026-11-16", savings: -0.35 }];
  const hass = detailHass({
    "sensor.eco_savings_week": { state: "-0.35", attributes: { savings_kwh: -2.58, bars } },
    "sensor.eco_savings_month": { state: "unavailable", attributes: {} },
  });
  assert.deepEqual(cards.sensorSavings(hass, "sensor.eco_savings_week"), {
    savings: -0.35, savings_kwh: -2.58, bars,
  });
  assert.equal(cards.sensorSavings(hass, "sensor.eco_savings_month"), null);
});

test("a new detail card shows the week of the first device", () => {
  assert.deepEqual(cards.detailStubConfig(detailHass()), {
    type: "custom:little-monkey-savings-detail-card",
    entity: "sensor.eco_savings_week",
  });
  assert.equal(cards.initialPeriod({}), "week");
  assert.equal(cards.initialPeriod({ period: "year" }), "year");
  assert.equal(cards.initialPeriod({ period: "day" }), "week");
  assert.deepEqual(cards.detailSchema({ language: "en" }).map((field) => field.name), [
    "entity", "period", "unit", "title",
  ]);
});

test("the savings cards need the option of the savings", () => {
  const sensor = (key) => ({ entity_id: `sensor.${key}`, platform: "little_monkey", translation_key: key });
  assert.equal(cards.savingsEnabled({ entities: { "sensor.a": sensor("realtime_consumption") } }), false);
  assert.equal(cards.savingsEnabled({ entities: { "sensor.b": sensor("savings_week") } }), true);
});
