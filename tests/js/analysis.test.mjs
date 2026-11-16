// Tests of the analysis cards of Little Monkey, run with: node --test tests/js
import assert from "node:assert/strict";
import test from "node:test";

// The module defines custom elements: a browser is not needed for the
// functions tested here
globalThis.HTMLElement = class {};
globalThis.customElements = { get: () => true };
const cards = await import(
  "../../custom_components/little_monkey/frontend/little-monkey-analysis-cards.js"
);

const CATEGORIES = [
  { id: 7, name: "Talon de consommation", color: "#022469", consumption: 37.1 },
  { id: 8, name: "Éclairage", color: "#ffed21", consumption: 4.22 },
  { id: 99, name: "Nouveau poste", color: "#123456", consumption: 0 },
  { id: 9, name: "Autres appareils", color: "#acc5cf", consumption: 12.4 },
];

test("the ring has an arc by category, proportional to its consumption", () => {
  const ring = { size: 100, radius: 40, width: 10, gap: 0 };
  const arcs = cards.ringArcs(CATEGORIES, ring);
  // An empty category has no arc
  assert.deepEqual(arcs.map((arc) => arc.index), [0, 1, 3]);
  const total = 37.1 + 4.22 + 12.4;
  assert.equal(arcs[0].start, 0);
  assert.equal(arcs[0].end.toFixed(3), ((37.1 / total) * 360).toFixed(3));
  assert.equal(arcs[2].end.toFixed(3), "360.000");
  assert.equal(arcs[1].color, "#ffed21");
  assert.match(arcs[0].path, /^M 50\.00 10\.00 A 40 40 0 1 1 /);
});

test("a single category is a full ring, and nothing gives no ring", () => {
  const arcs = cards.ringArcs([{ id: 7, color: "#022469", consumption: 3 }]);
  assert.equal(arcs.length, 1);
  assert.equal(arcs[0].end - arcs[0].start, 360);
  assert.deepEqual(cards.ringArcs([]), []);
  assert.deepEqual(cards.ringArcs([{ id: 7, consumption: 0 }]), []);
});

test("the categories have a translated name and an icon", () => {
  assert.equal(cards.categoryName("en", CATEGORIES[0]), "Standby consumption");
  assert.equal(cards.categoryName("fr", CATEGORIES[0]), "Talon de consommation");
  // A category unknown to the card keeps the name given by ecojoko
  assert.equal(cards.categoryName("en", CATEGORIES[2]), "Nouveau poste");
  assert.equal(cards.categoryIcon(CATEGORIES[1]), "mdi:lightbulb-outline");
  assert.equal(cards.categoryIcon(CATEGORIES[2]), "mdi:flash");
});

test("icons stay readable on light and dark colors", () => {
  assert.equal(cards.iconColor("#ffed21"), "rgba(0, 0, 0, 0.75)");
  assert.equal(cards.iconColor("#01d7fe"), "rgba(0, 0, 0, 0.75)");
  assert.equal(cards.iconColor("#022469"), "#fff");
  assert.equal(cards.iconColor("#5d1f9e"), "#fff");
  assert.equal(cards.iconColor(undefined), "#fff");
});

test("values and shares are written in the format of the user", () => {
  const spaces = (text) => text.replace(/[  ]/g, " ");
  assert.equal(spaces(cards.formatValue("fr", 5.03, "eur")), "5,03 €");
  assert.equal(cards.formatValue("en", 37.1, "kwh"), "37.1 kWh");
  assert.equal(spaces(cards.formatPercent("fr", 61)), "61 %");
  assert.equal(spaces(cards.formatPercent("fr", 0.7)), "0,7 %");
  assert.equal(cards.formatPercent("fr", null), "");
});

test("the periods of the analysis", () => {
  assert.equal(cards.periodStart("week", "2026-11-04"), "2026-11-02");
  assert.equal(cards.shiftPeriod("week", "2026-11-02", -1), "2026-10-26");
  assert.equal(cards.shiftPeriod("month", "2026-10-01", 1), "2026-11-01");
  assert.equal(cards.periodLabel("fr", "month", "2026-10-01"), "Octobre 2026");
  assert.equal(cards.periodLabel("fr", "week", "2026-11-02"), "2–8 nov. 2026");
});

test("a new analysis card takes a sensor of the first device", () => {
  const hass = {
    entities: {
      "sensor.eco_power": {
        entity_id: "sensor.eco_power", platform: "little_monkey",
        translation_key: "realtime_consumption", device_id: "eco",
      },
    },
    devices: { eco: { config_entries: ["entry1"] } },
  };
  assert.deepEqual(cards.analysisStubConfig(hass), {
    type: "custom:little-monkey-analysis-card", entity: "sensor.eco_power",
  });
  assert.equal(cards.configEntryId(hass, "sensor.eco_power"), "entry1");
  assert.equal(cards.initialPeriod({ period: "month" }), "month");
  assert.equal(cards.initialPeriod({}), "week");
  assert.deepEqual(cards.analysisSchema({ language: "fr" }).map((field) => field.name), [
    "entity", "period", "title",
  ]);
});

// --- History of a category

test("the history has a bar a week, from zero", () => {
  const box = { width: 100, height: 110, left: 0, right: 0, top: 0, bottom: 10 };
  const { bars, ticks, zero } = cards.historyGeometry([0, 0.5, 1.2, null], box);
  assert.equal(zero, 100);
  assert.equal(bars.length, 4);
  assert.equal(bars[0].height, 0);
  assert.equal(bars[3].value, null);
  // 1.2 on a scale up to 1.5
  assert.equal(bars[2].height.toFixed(3), ((1.2 / 1.5) * 100).toFixed(3));
  assert.deepEqual(ticks.map((tick) => tick.value), [0, 0.5, 1, 1.5]);
  assert.deepEqual(cards.historyGeometry([0, 0], box).ticks.map((tick) => tick.value), [0, 0.5, 1]);
});

test("the totals of the history", () => {
  assert.deepEqual(
    cards.historyTotals([{ cost: 0.11, consumption: 0.67 }, { cost: 0.12, consumption: 0.78 }, {}]),
    { cost: 0.23, consumption: 1.45 },
  );
  assert.deepEqual(cards.historyTotals(undefined), { cost: 0, consumption: 0 });
});

test("the months are written under their first week", () => {
  const bars = ["2026-01-05", "2026-01-12", "2026-02-02", "2026-02-09", "2026-03-02"].map((date) => ({ date }));
  assert.deepEqual(cards.monthLabels("fr", bars), [
    { index: 0, label: "J" }, { index: 2, label: "F" }, { index: 4, label: "M" },
  ]);
});
