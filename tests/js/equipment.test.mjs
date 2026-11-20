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
    // Short periods are widened to be seen
    ["absence", 1220, 12],
    ["forced", 1223, 12],
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

test("an equipment that is not piloted shows its measures", () => {
  assert.deepEqual(card.otherMeasures({ state: { temperature: 20.8, humidity: 50 } }, "fr"),
    [{ key: "temperature", value: "20,8 °C" }, { key: "humidity", value: "50 %" }]);
  assert.deepEqual(card.otherMeasures({ state: { power: 3326 } }, "fr"), [{ key: "power", value: `3${" "}326 W` }]);
  assert.deepEqual(card.otherMeasures(SENSOR, "fr"), []);
});

test("a value with an entity opens its details", () => {
  const equipment = { entities: { power: "sensor.chauffe_eau_power", odd: 'sensor.a"b' } };
  assert.equal(card.entityAttribute(equipment, "power"), ' data-entity="sensor.chauffe_eau_power"');
  assert.equal(card.entityAttribute(equipment, "odd"), ' data-entity="sensor.a&quot;b"');
  assert.equal(card.entityAttribute(equipment, "voltage"), "");
  assert.equal(card.entityAttribute(SENSOR, "power"), "");
});

test("a value with an entity shows the state of the entity, as its details", () => {
  const linky = { type: "POWER_METER", state: { power: 4636 }, entities: { power: "sensor.ecojoko_rt" } };
  const states = { "sensor.ecojoko_rt": { state: "243", attributes: { unit_of_measurement: "W" } } };
  assert.deepEqual(card.otherMeasures(linky, "fr", states), [{ key: "power", value: "243 W" }]);
  // Without its state yet: the value of the list
  assert.deepEqual(card.otherMeasures(linky, "fr", {}), [{ key: "power", value: `4${" "}636 W` }]);
  // An unavailable entity shows nothing, as its details
  assert.deepEqual(card.otherMeasures(linky, "fr", { "sensor.ecojoko_rt": { state: "unavailable" } }), []);
  // The unit of the entity wins: a temperature converted by Home Assistant
  const probe = { state: { temperature: 20.8 }, entities: { temperature: "sensor.t" } };
  assert.deepEqual(card.otherMeasures(probe, "fr", { "sensor.t": { state: "69.4", attributes: { unit_of_measurement: "°F" } } }),
    [{ key: "temperature", value: "69,4 °F" }]);
  const heater = { state: { voltage: 232.5 }, day: { energy: 0.97, cost: 0.14 }, entities: { energy: "sensor.e" } };
  const metrics = card.equipmentMetrics(TEXT, heater, "fr", { "sensor.e": { state: "1.2", attributes: { unit_of_measurement: "kWh" } } });
  // The spaces of the French numbers are not breaking
  assert.deepEqual(metrics.map((metric) => metric.value.replace(/\s/g, " ")), ["1,2 kWh", "0,14 €", "233 V"]);
});

test("a short period at the end of the day stays within the day", () => {
  const day = { date: "2026-11-18", switches: [
    { start: "2026-11-18T23:58:00+01:00", end: "2026-11-19T00:00:00+01:00", on: true, forced: true }] };
  const [segment] = card.dayTimeline(day).segments;
  assert.deepEqual([segment.x, segment.width], [1440 - 12, 12]);
});

test("an equipment that is not piloted shows its placement, batteries and signal", () => {
  const text = { battery: "Batterie {value}", signal: "Signal {value}", disconnected: "Déconnecté" };
  const meter = { install_state: "Bien placé", connected: true, battery: 80, battery_voltage: 5.09, signal: 33,
    entities: { battery: "sensor.b" } };
  assert.deepEqual(card.otherDetails(meter, text, "fr"), [
    { key: "install_state", value: "Bien placé" },
    { key: "battery", value: "Batterie 80 %" },
    { key: "battery_voltage", value: "5,09 V" },
    { key: "signal", value: "Signal 33 %" },
  ]);
  // The voltage alone, and a lost connection
  assert.deepEqual(card.otherDetails({ connected: false, status: "Déconnecté depuis 2 h", battery_voltage: 3.1 }, text, "fr"), [
    { key: "connection", value: "Déconnecté depuis 2 h", disconnected: true },
    { key: "battery_voltage", value: "Batterie 3,1 V" },
  ]);
  assert.deepEqual(card.otherDetails({ connected: true, battery: null, signal: null }, text, "fr"), []);
});

test("a field being typed is not drawn again by a reading, only by a touch", () => {
  const input = { tagName: "INPUT" };
  // A reading of ecojoko changed a value: the field keeps the focus
  assert.equal(card.keepsTyping(input, false), true);
  // The user touched a button: the card is drawn again
  assert.equal(card.keepsTyping(input, true), false);
  // No field has the focus
  assert.equal(card.keepsTyping({ tagName: "BUTTON" }, false), false);
  assert.equal(card.keepsTyping(null, false), false);
});

test("an entity of a device suggests the card on that device", () => {
  const sensor = (device, key) => ({
    entity_id: `sensor.${device}_${key}`, platform: "little_monkey", translation_key: key, device_id: device,
  });
  const hass = {
    entities: Object.fromEntries([
      sensor("home", "realtime_consumption"), sensor("barn", "realtime_consumption"), sensor("barn", "firmware"), sensor("shed", "firmware"),
    ].map((entity) => [entity.entity_id, entity])),
  };
  assert.deepEqual(card.entitySuggestion(hass, "sensor.barn_firmware", card.equipmentStubConfig), {
    config: { type: "custom:little-monkey-equipment-card", entity: "sensor.barn_realtime_consumption" },
  });
  // A device without the sensor needed, or an entity of another integration
  assert.equal(card.entitySuggestion(hass, "sensor.shed_firmware", card.equipmentStubConfig), null);
  assert.equal(card.entitySuggestion({ entities: { "light.lamp": { platform: "hue" } } }, "light.lamp", card.equipmentStubConfig), null);
});
