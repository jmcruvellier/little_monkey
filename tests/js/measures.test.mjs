// Tests of the measures card of Little Monkey, run with: node --test tests/js
import assert from "node:assert/strict";
import test from "node:test";

// The module defines custom elements: a browser is not needed for the
// functions tested here
globalThis.HTMLElement = class {};
globalThis.customElements = { get: () => true };
const card = await import(
  "../../custom_components/little_monkey/frontend/little-monkey-measures-card.js"
);

const BANDS = [
  { id: 2, label: "Heures Pleines", color: "#0087B1" },
  { id: 3, label: "Heures Creuses", color: "#6BBED8" },
];
const WEEK = {
  start: "2026-11-16T00:00:00+01:00", energy: 50, cost: 8, production: 1.5, bands: BANDS,
  bars: [
    { date: "2026-11-16", energy: 30, cost: 5, production: 1.5, bands: [
      { id: 3, energy: 10, cost: 1.5 }, { id: 2, energy: 20, cost: 3.5 }] },
    { date: "2026-11-17", energy: 20, cost: 3, production: 0, bands: [
      { id: 2, energy: 12, cost: 2 }, { id: 3, energy: 8, cost: 1 }] },
    { date: "2026-11-18", energy: 0, cost: 0, production: 0, bands: [] },
  ],
};

test("the bars are stacked by band, in the order of ecojoko, with its colors", () => {
  const chart = card.stackedBars(WEEK, "kwh");
  const first = chart.rects[0];
  assert.deepEqual(first.blocks.map((block) => [block.id, block.value, block.color]), [
    [2, 20, "#0087B1"], [3, 10, "#6BBED8"],
  ]);
  // The blocks touch each other, the first one on the axis
  assert.ok(Math.abs(first.blocks[0].y + first.blocks[0].height - chart.zero) < 1e-9);
  assert.ok(Math.abs(first.blocks[1].y + first.blocks[1].height - first.blocks[0].y) < 1e-9);
  // The production is under the axis, a day to come is empty
  assert.equal(first.production.y, chart.zero);
  assert.ok(chart.scale.min < 0);
  assert.deepEqual(chart.rects[2].blocks, []);
});

test("in euros the bars are costs, without production", () => {
  const chart = card.stackedBars(WEEK, "eur");
  assert.deepEqual(chart.rects[0].blocks.map((block) => block.value), [3.5, 1.5]);
  assert.equal(chart.rects[0].production, null);
  assert.equal(chart.scale.min, 0);
});

test("a bar without bands is a single block", () => {
  const chart = card.stackedBars({ bands: [], bars: [{ date: "2026-11-16", energy: 7, bands: [] }] }, "kwh");
  assert.equal(chart.rects[0].blocks.length, 1);
  assert.equal(chart.rects[0].blocks[0].value, 7);
});

test("the power of a day is coloured by band, over the base load", () => {
  const day = { bands: BANDS, points: [
    { time: "2026-11-18T00:00:00+01:00", power: 300, base: 6, band: 3 },
    { time: "2026-11-18T07:30:00+01:00", power: 1200, base: 6, band: 2 },
    { time: "2026-11-18T12:00:00+01:00", power: 800, base: 6, band: 2 },
    { time: "2026-11-18T13:00:00+01:00", power: -500, base: 6, band: 2 },
  ] };
  const areas = card.dayAreas(day);
  assert.deepEqual(areas.bands.map((band) => [band.band, band.color]), [[3, "#6BBED8"], [2, "#0087B1"]]);
  assert.ok(areas.base.startsWith("M"));
  // Injected power under the axis
  assert.ok(areas.injected.startsWith("M"));
  assert.ok(areas.scale.min < 0);
  assert.equal(card.dayAreas({ points: [] }).points.length, 0);
});

test("the totals of the bands over a period", () => {
  assert.deepEqual(card.bandTotals(WEEK), { 2: { energy: 32, cost: 5.5 }, 3: { energy: 18, cost: 2.5 } });
});

test("the names of the periods and of the bars", () => {
  assert.equal(card.periodLabel("fr", "day", "2026-11-18T00:00:00+01:00"), "Mercredi 18 novembre 2026");
  assert.equal(card.periodLabel("fr", "year", "2026-01-01T00:00:00+01:00"), "2026");
  assert.match(card.periodLabel("fr", "week", "2026-11-16T00:00:00+01:00"), /^16.+22 nov\. 2026$/);
  assert.equal(card.barLabel("fr", "year", "2026-03-01"), "M");
  assert.equal(card.barLabel("fr", "month", "2026-10-20", 5), "20");
  assert.equal(card.barLabel("fr", "month", "2026-10-21", 6), "");
  assert.equal(card.barTitle("fr", "week", "2026-11-17"), "Mardi 17 novembre");
});

test("values in the language of the user", () => {
  const plain = (value) => value.replace(/\s/g, " ");
  assert.equal(plain(card.formatValue("fr", 15.37, "kwh")), "15,37 kWh");
  assert.equal(plain(card.formatValue("fr", 3.06, "eur")), "3,06 €");
  assert.equal(plain(card.formatValue("fr", 2784, "w")), "2 784 W");
  assert.equal(card.formatValue("fr", null, "kwh"), "—");
});

test("the configuration: the day and kWh by default", () => {
  assert.equal(card.initialPeriod({}), "day");
  assert.equal(card.initialPeriod({ period: "year" }), "year");
  assert.equal(card.barUnit({}), "kwh");
  assert.equal(card.barUnit({ unit: "eur" }), "eur");
  assert.equal(card.minutesOf("2026-11-18T07:30:00+01:00"), 450);
});
