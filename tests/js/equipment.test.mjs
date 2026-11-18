// Tests of the equipment card of Little Monkey, run with: node --test tests/js
import assert from "node:assert/strict";
import test from "node:test";

// The module defines custom elements: a browser is not needed for the
// functions tested here
globalThis.HTMLElement = class {};
globalThis.customElements = { get: () => true };
const card = await import(
  "../../custom_components/little_monkey/frontend/little-monkey-equipment-card.js"
);

const TEXT = {
  auto_on: "Automatique · allumé",
  auto_off: "Automatique · éteint",
  forced_until: "Forcé jusqu'à {time}",
  absence_until: "Absence jusqu'à {time}",
  forced: "Forcé",
  absence: "Absence",
  on: "Allumé",
  off: "Éteint",
  energy: "Aujourd'hui",
  cost: "Coût du jour",
  voltage: "Tension",
  max_power: "Puissance max",
};

function heater(state = {}, extra = {}) {
  return {
    id: "630220", type: "LULO", name: "Chauffe-eau", controls: ["forced", "absence", "auto"],
    state: { mode: "auto", on: false, power: 0, ...state }, ...extra,
  };
}
const PLUG = { id: "7", type: "SOMETHING_NEW", name: "Prise", controls: ["on", "off"], state: { mode: "on", on: true } };
const SENSOR = { id: "3", type: "TEMP_HUM", name: "Sonde", controls: [], state: {} };

test("the piloted equipments come from their controls, whatever their type", () => {
  const all = [SENSOR, heater(), PLUG];
  assert.deepEqual(card.pilotedEquipments(all, {}).map((item) => item.id), ["630220", "7"]);
  assert.deepEqual(card.otherEquipments(all, {}).map((item) => item.id), ["3"]);
  assert.deepEqual(card.otherEquipments(all, { show_list: false }), []);
});

test("a card can show one equipment, by its name or its id", () => {
  const all = [SENSOR, heater(), PLUG];
  assert.deepEqual(card.pilotedEquipments(all, { equipment: " chauffe-EAU " }).map((item) => item.id), ["630220"]);
  assert.deepEqual(card.pilotedEquipments(all, { equipment: "7" }).map((item) => item.id), ["7"]);
  // Without the list of the others
  assert.deepEqual(card.otherEquipments(all, { equipment: "7" }), []);
});

test("the buttons are the ones ecojoko shows in each state", () => {
  assert.deepEqual(card.equipmentButtons(heater()), ["forced", "absence"]);
  assert.deepEqual(card.equipmentButtons(heater({ mode: "forced" })), ["auto"]);
  assert.deepEqual(card.equipmentButtons(heater({ mode: "absence" })), ["auto"]);
  assert.deepEqual(card.equipmentButtons(PLUG), ["on", "off"]);
  assert.deepEqual(card.equipmentButtons(SENSOR), []);
});

test("the mode is written with its end", () => {
  const now = new Date(2026, 10, 18, 20, 0);
  assert.equal(card.modeLabel(TEXT, heater({ on: true }), "fr", now), "Automatique · allumé");
  assert.equal(card.modeLabel(TEXT, heater(), "fr", now), "Automatique · éteint");
  const until = new Date(2026, 10, 18, 21, 30).toISOString();
  assert.equal(card.modeLabel(TEXT, heater({ mode: "forced", until }), "fr", now), "Forcé jusqu'à 21:30");
  // Another day: the day is written too
  const later = new Date(2026, 10, 20, 0, 0).toISOString();
  assert.match(card.modeLabel(TEXT, heater({ mode: "absence", until: later }), "fr", now), /^Absence jusqu'à ven\. 20 nov\. 00:00$/);
  assert.equal(card.modeLabel(TEXT, heater({ mode: "forced" }), "fr", now), "Forcé");
  assert.equal(card.modeLabel(TEXT, PLUG, "fr", now), "Allumé");
  // A mode the card does not know: as ecojoko words it
  assert.equal(card.modeLabel(TEXT, { state: { switch_state: "Éteint depuis 05:24" } }, "fr", now), "Éteint depuis 05:24");
});

test("the color follows the state", () => {
  assert.equal(card.stateKind(heater({ mode: "forced", on: true })), "forced");
  assert.equal(card.stateKind(heater({ mode: "absence" })), "absence");
  assert.equal(card.stateKind(heater({ on: true })), "on");
  assert.equal(card.stateKind(SENSOR), "off");
});

test("the timeline of the day shows the periods on, forced or absent", () => {
  const day = {
    date: "2026-11-18",
    switches: [
      // Started the day before: from midnight
      { start: "2026-11-17T23:24:00+01:00", end: "2026-11-18T05:24:00+01:00", on: true, forced: false },
      { start: "2026-11-18T05:24:00+01:00", end: "2026-11-18T20:20:00+01:00", on: false, forced: false },
      { start: "2026-11-18T20:20:00+01:00", end: "2026-11-18T20:21:00+01:00", on: false, forced: true },
      { start: "2026-11-18T20:22:48+01:00", end: "2026-11-18T20:27:48+01:00", on: true, forced: true },
      // Still lasting: until now
      { start: "2026-11-18T22:00:00+01:00", end: null, on: true, forced: false },
      // An older day is left out
      { start: "2026-11-04T23:24:00+01:00", end: "2026-11-05T05:24:00+01:00", on: true, forced: false },
    ],
    power: [
      { time: "2026-11-18T00:00:00+01:00", value: 2784 },
      { time: "2026-11-18T06:00:00+01:00", value: 0 },
    ],
  };
  const { segments, curve, max } = card.dayTimeline(day, 23 * 60);
  assert.deepEqual(segments.map((segment) => [segment.kind, Math.round(segment.x), Math.round(segment.width)]), [
    ["on", 0, 324],
    ["absence", 1220, 1],
    ["forced", 1223, 5],
    ["on", 1320, 60],
  ]);
  assert.equal(max, 2784);
  assert.equal(curve, "M0.0 4.0 L360.0 36.0");
});

test("an empty day has an empty timeline", () => {
  assert.deepEqual(card.dayTimeline(undefined), { segments: [], curve: "", max: 1 });
});

test("an absence ends at the next midnight by default", () => {
  assert.equal(card.absenceDefault(new Date(2026, 10, 18, 20, 0)), "2026-11-19T00:00");
  assert.equal(card.absenceDefault(new Date(2026, 11, 31, 9, 0)), "2027-01-01T00:00");
});

test("the measures shown are the ones ecojoko gives", () => {
  const metrics = card.equipmentMetrics(TEXT, heater({ voltage: 232.5, max_power: 3131 }, { day: { energy: 0.97, cost: 0.14 } }), "fr");
  assert.deepEqual(metrics.map((metric) => metric.key), ["energy", "cost", "voltage", "max_power"]);
  assert.equal(metrics[0].value, "0,97 kWh");
  assert.equal(metrics[2].value, "233 V");
  assert.deepEqual(card.equipmentMetrics(TEXT, PLUG, "fr"), []);
});

test("icons by type, a generic one for an unknown type", () => {
  assert.equal(card.equipmentIcon(heater()), "mdi:water-boiler");
  assert.equal(card.equipmentIcon(PLUG), "mdi:devices");
});

test("a new card uses the first Little Monkey device", () => {
  const hass = { entities: { "sensor.x": { entity_id: "sensor.x", platform: "little_monkey", translation_key: "realtime_consumption" } } };
  assert.deepEqual(card.equipmentStubConfig(hass), { type: "custom:little-monkey-equipment-card", entity: "sensor.x" });
  assert.deepEqual(card.equipmentSchema().map((field) => field.name), ["entity", "equipment", "show_list", "title"]);
});

test("the button whose question is open is shown selected, and the state of on and off", () => {
  assert.equal(card.isSelected(heater(), "forced", { id: "630220", mode: "forced" }), true);
  assert.equal(card.isSelected(heater(), "absence", { id: "630220", mode: "forced" }), false);
  // The question of another equipment
  assert.equal(card.isSelected(heater(), "forced", { id: "7", mode: "forced" }), false);
  assert.equal(card.isSelected(heater(), "forced", null), false);
  assert.equal(card.isSelected(PLUG, "on", null), true);
  assert.equal(card.isSelected(PLUG, "off", null), false);
});

test("a forced mode of another duration lasts 1 minute to 24 hours", () => {
  assert.equal(card.customMinutes("90"), 90);
  assert.equal(card.customMinutes("1440"), 1440);
  for (const value of ["0", "1441", "12.5", "", "abc", undefined]) {
    assert.equal(card.customMinutes(value), null, value);
  }
});
