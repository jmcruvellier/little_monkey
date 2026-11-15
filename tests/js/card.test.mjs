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
