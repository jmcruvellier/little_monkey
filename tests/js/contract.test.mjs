// Tests of the contract card of Little Monkey, run with: node --test tests/js
import assert from "node:assert/strict";
import test from "node:test";

// The module defines custom elements: a browser is not needed for the
// functions tested here
globalThis.HTMLElement = class {};
globalThis.customElements = { get: () => true };
const card = await import(
  "../../custom_components/little_monkey/frontend/little-monkey-contract-card.js"
);

const SLOTS = card.offPeakSlots([
  { start: "01:30", stop: "07:00" },
  { start: "14:00", stop: "16:30" },
]);
const NIGHT = card.offPeakSlots([{ start: "22:00", stop: "06:00" }]);

test("the off-peak slots are read in minutes", () => {
  assert.deepEqual(SLOTS, [[90, 420], [840, 990]]);
  assert.deepEqual(card.offPeakSlots([{ start: "x", stop: "07:00" }, { start: "08:00", stop: "08:00" }]), []);
  assert.deepEqual(card.offPeakSlots(undefined), []);
  assert.equal(card.timeOf(1530), "01:30");
});

test("a time is in the off-peak hours or not, across midnight too", () => {
  assert.equal(card.isOffPeak(SLOTS, 5 * 60), true);
  assert.equal(card.isOffPeak(SLOTS, 7 * 60), false);
  assert.equal(card.isOffPeak(SLOTS, 15 * 60), true);
  assert.equal(card.isOffPeak(NIGHT, 23 * 60), true);
  assert.equal(card.isOffPeak(NIGHT, 3 * 60), true);
  assert.equal(card.isOffPeak(NIGHT, 12 * 60), false);
});

test("the next change of period", () => {
  assert.deepEqual(card.nextChange(SLOTS, 5 * 60 + 15), { minutes: 420, offPeak: false, wait: 105 });
  assert.deepEqual(card.nextChange(SLOTS, 17 * 60), { minutes: 90, offPeak: true, wait: 510 });
  assert.deepEqual(card.nextChange(NIGHT, 21 * 60 + 40), { minutes: 1320, offPeak: true, wait: 20 });
  assert.equal(card.nextChange([], 600), null);
  const text = { hours: "{h} h {m}", minutes: "{m} min" };
  assert.equal(card.durationLabel(text, 105), "1 h 45");
  assert.equal(card.durationLabel(text, 20), "20 min");
});

test("the dial draws an arc between two times", () => {
  // 0 h at the top, 6 h on the right
  assert.equal(card.dialArc(0, 360, 60), "M 80.00 20.00 A 60 60 0 0 1 140.00 80.00");
  // Across midnight: 22 h to 6 h is a third of the day
  assert.match(card.dialArc(1320, 360, 60), / 0 0 1 140\.00 80\.00$/);
});

test("the Tempo color of the day and the badge of the supplier", () => {
  assert.equal(card.tempoDay("hp_white"), "white");
  assert.equal(card.tempoDay("hc_red"), "red");
  assert.equal(card.tempoDay("hc"), null);
  assert.equal(card.supplierBadge("EDF"), "EDF");
  assert.equal(card.supplierBadge("TotalEnergies"), "TOTA");
  assert.equal(card.supplierBadge("Ekwateur Énergie Verte"), "EÉV");
  assert.equal(card.supplierBadge(""), "?");
});

function fakeHass(period) {
  const entities = {};
  for (const [entityId, key] of [
    ["sensor.eco_contract", "contract"],
    ["sensor.eco_period", "current_tariff_period"],
    ["sensor.eco_hc", "hc_grid_consumption"],
  ]) {
    entities[entityId] = { entity_id: entityId, platform: "little_monkey", translation_key: key, device_id: "eco" };
  }
  return {
    entities,
    states: {
      "sensor.eco_contract": {
        state: "Zen Fixe - Option HP/HC",
        attributes: {
          supplier: "EDF", power: 9, subscription_price: 24.77, start_date: "2026-08-05",
          off_peak_timeslots: [{ start: "01:30", stop: "07:00" }, { start: "14:00", stop: "16:30" }],
          bands: [
            { key: "hc_grid_consumption", name: "Heures Creuses", category: "hc" },
            { key: "band_99", name: "Inconnue", category: "hp" },
          ],
        },
      },
      "sensor.eco_period": { state: period, attributes: {} },
      "sensor.eco_hc": { state: "4.63", attributes: {} },
    },
  };
}

test("the card shows the contract, the period and the bands", () => {
  const view = card.contractView(fakeHass("hp"), "sensor.eco_contract", new Date("2026-11-17T05:15:00+01:00"));
  assert.equal(view.offer, "Zen Fixe - Option HP/HC");
  assert.equal(view.power, 9);
  // The off-peak hours of the contract win over the period of the integration
  assert.equal(view.offPeak, true);
  assert.equal(view.minutes, 315);
  assert.deepEqual(view.next, { minutes: 420, offPeak: false, wait: 105 });
  assert.deepEqual(view.bands.map((band) => [band.name, band.energy, band.entity]), [
    ["Heures Creuses", 4.63, "sensor.eco_hc"],
    ["Inconnue", null, undefined],
  ]);
  const tempo = card.contractView(fakeHass("hc_blue"), "sensor.eco_contract", new Date("2026-11-17T12:00:00+01:00"));
  assert.equal(tempo.tempo, "blue");
  assert.equal(tempo.offPeak, false);
  // Without off-peak hours in the contract, the period of the integration decides
  const hass = fakeHass("hc");
  hass.states["sensor.eco_contract"].attributes.off_peak_timeslots = [];
  assert.equal(card.contractView(hass, "sensor.eco_contract", new Date("2026-11-17T12:00:00+01:00")).offPeak, true);
});

test("an unknown contract gives nothing to show", () => {
  const hass = fakeHass("hc");
  hass.states["sensor.eco_contract"].state = "unknown";
  assert.equal(card.contractView(hass, "sensor.eco_contract"), null);
  assert.equal(card.contractView(hass, "sensor.missing"), null);
});

test("a new contract card takes the contract sensor of the first device", () => {
  assert.deepEqual(card.contractStubConfig(fakeHass("hc")), {
    type: "custom:little-monkey-contract-card", entity: "sensor.eco_contract",
  });
  assert.deepEqual(card.contractSchema().map((field) => field.name), ["entity", "title"]);
});

const PRICE_TEXT = { per_kwh: "{price} / kWh" };
// The spaces of the French numbers are not breaking
const plain = (value) => value?.replace(/\s/g, " ");

test("the price of a kWh: as ecojoko gives it, or estimated to the tenth of a cent", () => {
  assert.equal(plain(card.bandPrice(PRICE_TEXT, "fr", { price: 0.2016, price_exact: true })), "0,2016 € / kWh");
  assert.equal(plain(card.bandPrice(PRICE_TEXT, "fr", { price: 0.18, price_exact: true })), "0,18 € / kWh");
  assert.equal(plain(card.bandPrice(PRICE_TEXT, "fr", { price: 0.18, price_exact: false })), "≈ 0,180 € / kWh");
  assert.equal(card.bandPrice(PRICE_TEXT, "fr", { price: null }), null);
  assert.equal(card.bandPrice(PRICE_TEXT, "fr", {}), null);
});

test("the current band: named by the period sensor, or the only one of the period", () => {
  const hass = fakeHass("hp");
  hass.states["sensor.eco_contract"].attributes.bands = [
    { key: "hp_grid_consumption", name: "Heures Pleines", category: "hp" },
    { key: "hc_grid_consumption", name: "Heures Creuses", category: "hc" },
  ];
  // 05:15 is in the off-peak hours of the contract
  let view = card.contractView(hass, "sensor.eco_contract", new Date("2026-11-17T05:15:00+01:00"));
  assert.deepEqual(view.bands.map((band) => band.current), [false, true]);
  // The period sensor names it
  hass.states["sensor.eco_period"].attributes = { tariff_band: "Heures Pleines" };
  view = card.contractView(hass, "sensor.eco_contract", new Date("2026-11-17T05:15:00+01:00"));
  assert.deepEqual(view.bands.map((band) => band.current), [true, false]);
});

test("without its name, no current band for Tempo: it depends on the day", () => {
  const hass = fakeHass("hc_white");
  hass.states["sensor.eco_contract"].attributes.bands = [
    { key: "band_19", name: "HC Bleu", category: "hc" },
    { key: "band_18", name: "HP Bleu", category: "hp" },
    { key: "band_20", name: "HP Blanc", category: "hp" },
  ];
  const view = card.contractView(hass, "sensor.eco_contract", new Date("2026-11-17T05:15:00+01:00"));
  assert.deepEqual(view.bands.map((band) => band.current), [false, false, false]);
});

test("the time of the dial is the one of Paris, whatever the browser", () => {
  // 05:15 in Paris in winter, 04:15 UTC
  assert.equal(card.parisMinutes(new Date("2026-11-17T04:15:00Z")), 315);
  // In summer, two hours after UTC
  assert.equal(card.parisMinutes(new Date("2026-07-01T22:30:00Z")), 30);
});

test("a contract without off-peak hours nor a known period shows no period", () => {
  const hass = fakeHass("unknown");
  hass.states["sensor.eco_contract"].attributes.off_peak_timeslots = [];
  const view = card.contractView(hass, "sensor.eco_contract", new Date("2026-11-17T12:00:00+01:00"));
  assert.equal(view.known, false);
  assert.equal(view.next, null);
  // With off-peak hours, or with the period of the integration, it is known
  assert.equal(card.contractView(fakeHass("unknown"), "sensor.eco_contract").known, true);
  const period = fakeHass("hp");
  period.states["sensor.eco_contract"].attributes.off_peak_timeslots = [];
  assert.equal(card.contractView(period, "sensor.eco_contract").known, true);
});
