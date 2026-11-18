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
    "entity", "period", "max_categories", "title",
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

// --- Activations of the appliances

const ACTIVATIONS = [
  { start: "2026-11-16T00:03:00+01:00", end: "2026-11-16T02:29:00+01:00", power: 694, energy: 1.69,
    shape: { width: 96, height: 16, color: "#FA6200" } },
  { start: "2026-11-15T20:15:00+01:00", end: "2026-11-15T20:15:30+01:00", power: 1260, energy: 0.01,
    shape: { width: 3, height: 29, color: "#5FC2FF" } },
  { start: "2026-11-15T14:38:00+01:00", end: "2026-11-15T14:51:00+01:00", power: 496, energy: 0.11,
    shape: { width: 22, height: 12, color: "#5FC2FF" } },
];

test("the pages of activations are merged, the most recent first", () => {
  const merged = cards.mergeActivations([
    { activations: [ACTIVATIONS[0], ACTIVATIONS[1]] },
    undefined,
    { activations: [ACTIVATIONS[1], ACTIVATIONS[2]] },
  ]);
  assert.deepEqual(merged.map((activation) => activation.power), [694, 1260, 496]);
});

test("the activations are grouped by day", () => {
  const days = cards.groupByDay(ACTIVATIONS);
  assert.deepEqual(days.map((day) => [day.day, day.activations.length]), [
    ["2026-11-16", 1], ["2026-11-15", 2],
  ]);
  assert.equal(cards.dayLabel("fr", "2026-11-16"), "Lundi 16 novembre 2026");
  assert.equal(cards.dayLabel("en", "2026-11-16"), "Monday, November 16, 2026");
});

test("the hours and the duration of an activation", () => {
  const text = { seconds: "{n} s", minutes: "{n} min", hours: "{h} h {m} min" };
  assert.equal(cards.timeRange(ACTIVATIONS[0]), "00:03 – 02:29");
  assert.equal(cards.durationLabel(text, ACTIVATIONS[0]), "2 h 26 min");
  assert.equal(cards.durationLabel(text, ACTIVATIONS[1]), "30 s");
  assert.equal(cards.durationLabel(text, ACTIVATIONS[2]), "13 min");
});

test("the shape of an activation is a pulse on a baseline", () => {
  assert.match(cards.shapeSvg(ACTIVATIONS[0].shape), /d="M 0 42 H 4 V 26 H 100 V 42 H 104"/);
  assert.match(cards.shapeSvg(ACTIVATIONS[0].shape), /stroke="#FA6200"/);
  // Shapes stay in their box, and an unexpected color is not written
  assert.match(cards.shapeSvg({ width: 500, height: 90, color: "red;" }), /V 2 H 100 V 42 H 104" fill="none" stroke="#5fc2ff"/);
});

test("a new activations card takes a sensor of the first device", () => {
  const hass = {
    entities: {
      "sensor.eco_power": {
        entity_id: "sensor.eco_power", platform: "little_monkey", translation_key: "realtime_consumption",
      },
    },
  };
  assert.deepEqual(cards.activationsStubConfig(hass), {
    type: "custom:little-monkey-activations-card", entity: "sensor.eco_power",
  });
  assert.deepEqual(cards.activationsSchema({ language: "fr" }).map((field) => field.name), ["entity", "mode", "title"]);
  assert.equal(cards.activationsMode({}), "timeline");
  assert.equal(cards.activationsMode({ mode: "list" }), "list");
});

test("the largest categories are shown first, in the order of ecojoko", () => {
  const categories = [
    { id: 7, consumption: 359 }, { id: 5, consumption: 103 }, { id: 6, consumption: 81 },
    { id: 3, consumption: 75 }, { id: 11, consumption: 44 }, { id: 4, consumption: 29 },
    { id: 9, consumption: 398 },
  ];
  assert.deepEqual(cards.shownCategories(categories, 3).map((category) => category.id), [7, 5, 9]);
  assert.equal(cards.shownCategories(categories, 3, true).length, 7);
  assert.equal(cards.shownCategories(categories, 0).length, 7);
  assert.equal(cards.shownCategories(categories, 10).length, 7);
  assert.equal(cards.maxCategories({}), 5);
  assert.equal(cards.maxCategories({ max_categories: 0 }), 0);
  assert.equal(cards.maxCategories({ max_categories: -2 }), 5);
});

test("the timelines put each activation at its time, as high as its power", () => {
  const box = { width: 1440, height: 48, base: 44, min: 6, max: 40, hit: 14 };
  const days = cards.timelines(ACTIVATIONS, box);
  assert.deepEqual(days.map((day) => [day.day, day.pulses.length]), [["2026-11-16", 1], ["2026-11-15", 2]]);
  const night = days[0].pulses[0];
  // 00:03 to 02:29: 146 minutes from minute 3, the most powerful one shown
  assert.equal(night.x, 3);
  assert.equal(night.width, 146);
  assert.equal(night.color, "#FA6200");
  const [afternoon, evening] = days[1].pulses;
  // In the order of the day; 30 seconds are drawn as two minutes
  assert.equal(afternoon.x, 14 * 60 + 38);
  assert.equal(evening.width, 2);
  assert.equal(evening.height, 40);
  assert.equal(evening.y, 4);
  assert.equal(afternoon.height.toFixed(2), (6 + 34 * (496 / 1260)).toFixed(2));
});

test("the analysis offers the week and the month only, as ecojoko", () => {
  assert.deepEqual(cards.PERIODS, ["week", "month"]);
  // A card configured on the year, which ecojoko does not analyse, shows the week
  assert.equal(cards.initialPeriod({ period: "year" }), "week");
  assert.equal(cards.initialPeriod({ period: "month" }), "month");
});
