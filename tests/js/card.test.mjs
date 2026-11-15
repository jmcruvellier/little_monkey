// Tests of the Little Monkey card, run with: node --test tests/js
import assert from "node:assert/strict";
import test from "node:test";

// The card module defines a custom element: a browser is not needed for the
// functions tested here
globalThis.HTMLElement = class {};
globalThis.customElements = { get: () => true };
const card = await import(
  "../../custom_components/little_monkey/frontend/little-monkey-card.js"
);

test("the graduations of the power arc are evenly spaced", () => {
  const angles = [0, 50, 100, 500, 1000, 5000, 10000, 12000].map((power) =>
    Math.round(card.powerAngle(power)),
  );
  assert.deepEqual(angles, [-100, -71, -43, -14, 14, 43, 71, 100]);
});

test("the power arc is logarithmic between graduations", () => {
  // Halfway between 100 and 500 on a logarithmic scale
  assert.equal(
    card.powerAngle(Math.sqrt(100 * 500)).toFixed(3),
    ((card.powerAngle(100) + card.powerAngle(500)) / 2).toFixed(3),
  );
});

test("the needle stays on the arc", () => {
  assert.equal(card.powerAngle(-300), -100);
  assert.equal(card.powerAngle(50000), 100);
  // A maximum below 10K cannot hide the 10K graduation
  assert.equal(Math.round(card.powerAngle(9000, 9000)), 67);
  assert.equal(card.powerAngle(10001, 9000), 100);
  assert.equal(Math.round(card.powerAngle(18000, 18000)), 100);
});

test("tariff periods are read in many forms", () => {
  const cases = [
    ["sensor.period", "HC", { period: "hc", color: null }],
    ["sensor.period", "Heures Pleines", { period: "hp", color: null }],
    ["sensor.period", "off-peak", { period: "hc", color: null }],
    ["sensor.period", "peak", { period: "hp", color: null }],
    ["sensor.period", "HC Bleu", { period: "hc", color: "blue" }],
    ["sensor.period", "hp_red", { period: "hp", color: "red" }],
    ["sensor.period", "HCJW", { period: "hc", color: "white" }],
    ["sensor.period", "HPJR", { period: "hp", color: "red" }],
    ["sensor.couleur", "Blanc", { period: null, color: "white" }],
    ["sensor.couleur", "Rouge", { period: null, color: "red" }],
    ["binary_sensor.hc", "on", { period: "hc", color: null }],
    ["binary_sensor.hc", "off", { period: "hp", color: null }],
    ["sensor.period", "unavailable", { period: null, color: null }],
    ["sensor.period", undefined, { period: null, color: null }],
  ];
  for (const [entityId, state, expected] of cases) {
    assert.deepEqual(card.parseTariff(entityId, state), expected, `${entityId} = ${state}`);
  }
});

test("the disc takes the color of the current period", () => {
  const blue = "#0b6aae";
  assert.equal(card.discColor(null, { period: "hc", color: "red" }), blue);
  assert.equal(card.discColor("hchp", { period: "hc", color: null }), "#00008B");
  assert.equal(card.discColor("hchp", { period: "hp", color: null }), "#0000FF");
  assert.equal(card.discColor("hchp", { period: null, color: null }), blue);
  assert.equal(card.discColor("tempo", { period: "hc", color: "white" }), "#D3D3D3");
  assert.equal(card.discColor("tempo", { period: "hp", color: "white" }), "#FFFFFF");
  assert.equal(card.discColor("tempo", { period: "hc", color: "red" }), "#8B0000");
  assert.equal(card.discColor("tempo", { period: "hp", color: "red" }), "#FF0000");
  assert.equal(card.discColor("tempo", { period: "hc", color: "blue" }), "#00008B");
  // Color known, period unknown: HP color; color unknown: ecojoko blue
  assert.equal(card.discColor("tempo", { period: null, color: "red" }), "#FF0000");
  assert.equal(card.discColor("tempo", { period: "hc", color: null }), blue);
});

// Entity registry of Home Assistant with two Little Monkey devices
function hassWith(...devices) {
  const entities = {};
  for (const [deviceId, keys] of devices) {
    for (const key of keys) {
      const entityId = `sensor.${deviceId}_${key}`;
      entities[entityId] = { entity_id: entityId, device_id: deviceId, platform: "little_monkey", translation_key: key };
    }
  }
  entities["sensor.other_power"] = { entity_id: "sensor.other_power", device_id: "other", platform: "shelly" };
  return { entities, states: {} };
}
const POWER = "realtime_consumption";
const APPARENT = "realtime_apparent_power";

test("a new card takes the sensors of the Little Monkey device", () => {
  assert.deepEqual(card.stubConfig(hassWith(["home", [POWER, APPARENT]])), {
    type: "custom:little-monkey-card",
    entity: "sensor.home_realtime_consumption",
    apparent_power_entity: "sensor.home_realtime_apparent_power",
  });
  assert.deepEqual(card.stubConfig(hassWith(["home", [POWER]])), {
    type: "custom:little-monkey-card",
    entity: "sensor.home_realtime_consumption",
  });
  assert.deepEqual(card.stubConfig({ entities: {} }), { type: "custom:little-monkey-card" });
});

test("choosing another device takes its apparent power sensor", () => {
  const hass = hassWith(["home", [POWER, APPARENT]], ["barn", [POWER, APPARENT]], ["shed", [POWER]]);
  const previous = { entity: "sensor.home_realtime_consumption", apparent_power_entity: "sensor.home_realtime_apparent_power" };
  assert.equal(
    card.editedConfig(hass, previous, { ...previous, entity: "sensor.barn_realtime_consumption" }).apparent_power_entity,
    "sensor.barn_realtime_apparent_power",
  );
  // The device has none: the option is removed
  assert.equal(
    "apparent_power_entity" in card.editedConfig(hass, previous, { ...previous, entity: "sensor.shed_realtime_consumption" }),
    false,
  );
  // A sensor chosen by hand is kept
  const chosen = { ...previous, apparent_power_entity: "sensor.linky_va" };
  assert.equal(
    card.editedConfig(hass, chosen, { ...chosen, entity: "sensor.barn_realtime_consumption" }).apparent_power_entity,
    "sensor.linky_va",
  );
});

test("empty options are removed", () => {
  const hass = hassWith(["home", [POWER]]);
  const previous = { entity: "sensor.home_realtime_consumption", tariff_entity: "sensor.tempo" };
  assert.deepEqual(card.editedConfig(hass, previous, { ...previous, tariff_entity: "", max_power: undefined }), {
    entity: "sensor.home_realtime_consumption",
  });
});

test("the editor asks for the tariff period only with the HC/HP or Tempo option", () => {
  const names = (hass) => card.editorSchema(hass, { entity: "sensor.home_realtime_consumption" }).map((field) => field.name);
  assert.deepEqual(names(hassWith(["home", [POWER]])), ["entity", "apparent_power_entity", "max_power", "trend_minutes"]);
  assert.deepEqual(names(hassWith(["home", [POWER, "hc_grid_consumption"]])), [
    "entity", "apparent_power_entity", "tariff_entity", "max_power", "trend_minutes",
  ]);
  assert.deepEqual(names(hassWith(["home", [POWER, "red_hp_grid_consumption"]])), [
    "entity", "apparent_power_entity", "tariff_entity", "tempo_color_entity", "max_power", "trend_minutes",
  ]);
});

test("the period sensor of the integration is chosen automatically", () => {
  const hass = hassWith(["home", [POWER, "current_tariff_period"]], ["barn", [POWER]]);
  assert.equal(card.stubConfig(hass).tariff_entity, "sensor.home_current_tariff_period");
  const previous = card.stubConfig(hass);
  assert.equal(
    "tariff_entity" in card.editedConfig(hass, previous, { ...previous, entity: "sensor.barn_realtime_consumption" }),
    false,
  );
  // An entity chosen by hand is kept
  const chosen = { ...previous, tariff_entity: "binary_sensor.heures_creuses" };
  assert.equal(
    card.editedConfig(hass, chosen, { ...chosen, entity: "sensor.barn_realtime_consumption" }).tariff_entity,
    "binary_sensor.heures_creuses",
  );
});

test("the trend covers ten minutes by default, one hour at most", () => {
  assert.equal(card.trendMinutes({}), 10);
  assert.equal(card.trendMinutes({ trend_minutes: 5 }), 5);
  assert.equal(card.trendMinutes({ trend_minutes: 600 }), 60);
  assert.equal(card.trendMinutes({ trend_minutes: 0 }), 10);
  assert.equal(card.trendMinutes({ trend_minutes: "x" }), 10);
});

test("the trend is drawn over the whole period, in its box", () => {
  const box = { left: 0, top: 0, width: 100, height: 10 };
  const now = 1_000_000;
  // A value received before the period lasts into it, then 300 W at mid-period
  const samples = [{ time: now - 2000, value: 100 }, { time: now - 500, value: 300 }];
  const path = card.trendPath(samples, now, 1000, box, 11);
  const numbers = path.match(/-?[\d.]+/g).map(Number);
  assert.ok(path.startsWith("M 0.00 10.00"), path);
  assert.ok(path.endsWith("100.00 0.00"), path);
  assert.ok(numbers.every((n) => n >= 0 && n <= 100), path);
});

test("a short spike does not flatten the trend", () => {
  const box = { left: 0, top: 0, width: 100, height: 10 };
  const now = 1_000_000;
  // 400 W then 500 W, with a 3000 W spike of one second
  const samples = [
    { time: now - 2000_000, value: 400 },
    { time: now - 300_000, value: 500 },
    { time: now - 100_000, value: 3000 },
    { time: now - 99_000, value: 500 },
  ];
  const path = card.trendPath(samples, now, 600_000, box, 40);
  const ys = [...path.matchAll(/ (-?[\d.]+) (-?[\d.]+)(?= C|$)/g)].map((m) => Number(m[2]));
  // The step from 400 to 500 W uses the whole height, the spike is clipped
  assert.equal(ys[0], 10);
  assert.equal(ys[ys.length - 1], 0);
  assert.ok(ys.every((y) => y >= 0 && y <= 10), path);
});

test("no trend without two known points", () => {
  assert.equal(card.trendPath([], 1000, 1000), "");
  assert.equal(card.trendPath([{ time: 2000, value: 5 }], 1000, 1000), "");
});
