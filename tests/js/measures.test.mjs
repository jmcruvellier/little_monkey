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

test("the periods of the climate: the day, its week, its 30 days, its year", () => {
  const iso = (date) => `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
  const range = (period) => { const r = card.periodRange(period, "2026-11-18"); return [iso(r.start), iso(r.end)]; };
  assert.deepEqual(range("day"), ["2026-11-18", "2026-11-19"]);
  assert.deepEqual(range("week"), ["2026-11-16", "2026-11-23"]);
  assert.deepEqual(range("month"), ["2026-10-20", "2026-11-19"]);
  assert.deepEqual(range("year"), ["2026-01-01", "2027-01-01"]);
  assert.equal(card.shiftDate("day", "2026-11-01", -1), "2026-10-31");
  assert.equal(card.shiftDate("week", "2026-11-18", 1), "2026-11-25");
  assert.equal(card.shiftDate("month", "2026-11-18", -1), "2026-10-19");
  assert.equal(card.shiftDate("year", "2026-11-18", -1), "2025-11-18");
});

test("the sensors of the temperature and humidity of the device", () => {
  const entity = (id, key, device = "d") => ({ entity_id: id, platform: "little_monkey", translation_key: key, device_id: device });
  const hass = { entities: {
    "sensor.rt": entity("sensor.rt", "realtime_consumption"),
    "sensor.in": entity("sensor.in", "indoor_temp"),
    "sensor.out": entity("sensor.out", "outdoor_temp"),
    "sensor.other": entity("sensor.other", "indoor_hum", "another"),
  } };
  assert.deepEqual(card.climateEntities(hass, "sensor.rt", "temperature"), { inside: "sensor.in", outside: "sensor.out" });
  // A sensor of another installation is not taken
  assert.deepEqual(card.climateEntities(hass, "sensor.rt", "humidity"), {});
});

test("the curves come from the statistics of the sensors", () => {
  const statistics = {
    "sensor.in": [{ start: Date.UTC(2026, 10, 18, 10), mean: 21.2 }, { start: "2026-11-18T11:00:00+00:00", mean: 21.6 }],
    "sensor.out": [{ start: Date.UTC(2026, 10, 18, 10), mean: 9.5 }],
  };
  const climate = card.climateFromStatistics(statistics, { inside: "sensor.in", outside: "sensor.out" }, "°C");
  assert.deepEqual(climate.points, [
    { time: "2026-11-18T10:00:00.000Z", inside: 21.2, outside: 9.5 },
    { time: "2026-11-18T11:00:00.000Z", inside: 21.6, outside: null },
  ]);
  assert.ok(Math.abs(card.climateAverage(climate) - 21.4) < 1e-9);
  const lines = card.climateLines(climate, { start: new Date(Date.UTC(2026, 10, 18)), end: new Date(Date.UTC(2026, 10, 19)) });
  assert.ok(lines.inside.startsWith("M") && lines.inside.includes("L"));
  assert.ok(lines.outside.startsWith("M") && !lines.outside.includes("L"));
  // Around the values, not from zero
  assert.ok(lines.ticks[0].value > 0);
});

test("the values of the climate and the measure shown first", () => {
  assert.equal(card.climateValue("fr", 21.25, "°C"), "21,3 °C");
  assert.equal(card.climateValue("fr", 47, "%"), "47 %");
  assert.equal(card.climateValue("fr", null, "%"), "—");
  assert.equal(card.initialMeasure({}), "electricity");
  assert.equal(card.initialMeasure({ measure: "humidity" }), "humidity");
  assert.equal(card.climateLabels("fr", "week", card.periodRange("week", "2026-11-18")).length, 7);
});

test("the statistics are used only when they cover the period from its start", () => {
  const range = { start: new Date(Date.UTC(2026, 10, 16)), end: new Date(Date.UTC(2026, 10, 23)) };
  const climate = (time) => ({ points: [{ time, inside: 20, outside: 10 }] });
  assert.equal(card.statisticsCover(climate("2026-11-16T01:00:00.000Z"), range, "week"), true);
  // Recorded since Wednesday only: ecojoko has the week
  assert.equal(card.statisticsCover(climate("2026-11-18T14:00:00.000Z"), range, "week"), false);
  assert.equal(card.statisticsCover({ points: [] }, range, "week"), false);
});

test("the month of the temperature and humidity is the calendar month", () => {
  assert.equal(card.datesPeriod("temperature", "month"), "calendar");
  assert.equal(card.datesPeriod("electricity", "month"), "month");
  assert.equal(card.datesPeriod("humidity", "week"), "week");
  const iso = (date) => `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
  const range = card.periodRange("calendar", "2026-11-18");
  assert.deepEqual([iso(range.start), iso(range.end)], ["2026-11-01", "2026-12-01"]);
  assert.equal(card.shiftDate("calendar", "2026-01-31", -1), "2025-12-28");
  assert.equal(card.periodLabel("fr", "calendar", "2026-11-01"), "Novembre 2026");
  assert.equal(card.climateLabels("fr", "calendar", range).length, 6);
});

test("the graduations carry their unit: kW from 1 000 W, kWh, euros", () => {
  const plain = (value) => value.replace(/\s/g, " ");
  assert.equal(plain(card.axisLabel("fr", 6000, "w")), "6 kW");
  assert.equal(plain(card.axisLabel("fr", 2500, "w")), "2,5 kW");
  assert.equal(plain(card.axisLabel("fr", 500, "w")), "500 W");
  assert.equal(plain(card.axisLabel("fr", -1000, "w")), "-1 kW");
  assert.equal(plain(card.axisLabel("fr", 40, "kwh")), "40 kWh");
  assert.equal(plain(card.axisLabel("fr", 150, "eur")), "150 €");
});

test("the month and the year of today are the current ones, whatever the day", () => {
  // Back a month from the 31st gives the 28th; forward again, the 28th of this month
  assert.equal(card.shiftDate("calendar", "2026-12-28", 1), "2027-01-28");
  assert.equal(card.isCurrent("calendar", "2027-01-28", "2027-01-31"), true);
  assert.equal(card.isCurrent("calendar", "2026-12-28", "2027-01-31"), false);
  assert.equal(card.isCurrent("year", "2027-01-28", "2027-11-19"), true);
  assert.equal(card.isCurrent("year", "2026-11-19", "2027-11-19"), false);
  // A day, a week and the 30 days ending on a day: the day itself
  assert.equal(card.isCurrent("day", "2027-01-30", "2027-01-31"), false);
  assert.equal(card.isCurrent("month", "2027-01-31", "2027-01-31"), true);
});
