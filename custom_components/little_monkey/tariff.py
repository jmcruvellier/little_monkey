"""Contract and tariff bands of an ecojoko account.

ecojoko has no public documentation. What follows was observed in its
responses:

- GET /gateway/{id}/suppliers lists the electricity contracts of the
  installation, the active one first with "is_active": 1, the previous ones
  with a "stop_date". "offer_type" is the family of the offer ("HP/HC",
  "TEMPO", "HC SEM WE LUNDI"...).
- The daily statistics split the energy of a day into tariff bands:
  "subconsumption" items {id, label, kwh, price}, and "pricing_details"
  items {id, label, color} for the bands met in the period. The id of a band
  is shared by every offer using it (2 is "Heures Pleines" for EDF, Gaz de
  Bordeaux...), while its label is only meant to be displayed.
"""
from __future__ import annotations

import datetime as dt
from zoneinfo import ZoneInfo

# Fields of a contract kept for the diagnostics: neither prices nor the
# internal ids of the subscription
CONTRACT_FIELDS = (
    "supplier_name",
    "offer_id",
    "offer_name",
    "offer_type",
    "is_hchp",
    "special_day",
    # Subscribed power in kVA, and price of the subscription
    "power",
    "subscription_price",
)


PARIS = ZoneInfo("Europe/Paris")


def local_date(milliseconds):
    """Return the day in Paris of a time in milliseconds, or None.

    ecojoko gives its days and contract dates as the time of midnight in
    Paris.
    """
    if isinstance(milliseconds, bool) or not isinstance(milliseconds, int | float):
        return None
    return dt.datetime.fromtimestamp(milliseconds / 1000, PARIS).date()


def _iso_date(milliseconds):
    """Return a time in milliseconds as an ISO date in Paris, or None."""
    day = local_date(milliseconds)
    return None if day is None else day.isoformat()


def active_contract(payload):
    """Return the active contract of a suppliers response, or None.

    The contract flagged active is taken, otherwise the one without an end
    date, otherwise the first one (the most recent).
    """
    suppliers = payload.get("suppliers") if isinstance(payload, dict) else None
    if not isinstance(suppliers, list):
        raise TypeError("No list of suppliers in the response")
    suppliers = [item for item in suppliers if isinstance(item, dict)]
    if not suppliers:
        return None
    current = next(
        (item for item in suppliers if item.get("is_active") == 1),
        next((item for item in suppliers if "stop_date" not in item), suppliers[0]),
    )
    contract = {key: current.get(key) for key in CONTRACT_FIELDS}
    timeslot = current.get("off_peak_timeslot")
    slots = timeslot.get("timeslots") if isinstance(timeslot, dict) else None
    contract["off_peak_timeslots"] = [
        {"start": slot.get("start"), "stop": slot.get("stop")}
        for slot in slots or []
        if isinstance(slot, dict)
    ]
    contract["start_date"] = _iso_date(current.get("start_date"))
    return contract


def bands_of(stat, day=None):
    """Return the tariff bands {id: label} of a statistics response.

    stat: the "stat" object of the response; day: the item of the day in its
    "data", whose "subconsumption" holds the bands of that day.
    """
    bands = {}
    items = list(stat.get("pricing_details") or [])
    if isinstance(day, dict):
        items += day.get("subconsumption") or []
    for item in items:
        if not isinstance(item, dict):
            continue
        band_id = item.get("id")
        label = item.get("label")
        if isinstance(band_id, bool) or not isinstance(band_id, int):
            continue
        if isinstance(label, str):
            bands[band_id] = label
    return bands


# Categories of the HC/HP totals
OFF_PEAK = "hc"
PEAK = "hp"


def category_of(label):
    """Return the category deduced from the label of a band, or None.

    "Heures Creuses", "HC Bleu", "HC Semaine", "HC Jour Spécial"... are off
    peak, "Heures Pleines", "HP Rouge", "HP Weekend"... are peak. A band such
    as "Heures Weekend" belongs to neither.
    """
    if not isinstance(label, str):
        return None
    words = label.strip().upper().split()
    if not words:
        return None
    if words[0] == "HC" or words[:2] == ["HEURES", "CREUSES"]:
        return OFF_PEAK
    if words[0] == "HP" or words[:2] == ["HEURES", "PLEINES"]:
        return PEAK
    return None


# --- Tariff bands configured in a config entry
#
# The entry keeps a list of bands: {"id", "label", "key", "name",
# "category"}. "id" identifies the band at ecojoko and never changes, while
# its label may; "key" is the key of its sensor, which builds the unique id
# of the entity; "name" is the name chosen by the user (None: the translated
# name of a known sensor, or the label); "category" counts the band in the
# HC or the HP total, or in neither (None).

NO_CATEGORY = "none"

# Bands having a sensor since the first versions: they keep its key, and so
# the entity id, the history and the statistics of the installations
KNOWN_BANDS = {
    2: ("hp_grid_consumption", PEAK),
    3: ("hc_grid_consumption", OFF_PEAK),
    18: ("blue_hp_grid_consumption", PEAK),
    19: ("blue_hc_grid_consumption", OFF_PEAK),
    20: ("white_hp_grid_consumption", PEAK),
    21: ("white_hc_grid_consumption", OFF_PEAK),
    22: ("red_hp_grid_consumption", PEAK),
    23: ("red_hc_grid_consumption", OFF_PEAK),
}
# Heures Pleines and Heures Creuses are the HP and HC totals themselves:
# they have no sensor of their own
TOTAL_BANDS = {2, 3}
TEMPO_BANDS = (18, 19, 20, 21, 22, 23)

# Bands of an offer, by offer type, as observed. The statistics only give
# the bands met in a period (no red Tempo day in summer): the offer type
# completes them
OFFER_BANDS = {
    "HP/HC": {2: "Heures Pleines", 3: "Heures Creuses"},
    "TEMPO": {
        18: "HP Bleu", 19: "HC Bleu",
        20: "HP Blanc", 21: "HC Blanc",
        22: "HP Rouge", 23: "HC Rouge",
    },
    "HC SEM WE LUNDI": {
        8: "HP Semaine", 9: "HC Semaine",
        10: "HP Jour Spécial", 11: "HC Jour Spécial",
        6: "HP Weekend", 7: "HC Weekend",
    },
}


def band_key(band_id):
    """Return the key of the sensor of a band."""
    known = KNOWN_BANDS.get(band_id)
    return known[0] if known else f"band_{band_id}"


def new_band(band_id, label):
    """Return the configuration of a band with its default settings."""
    known = KNOWN_BANDS.get(band_id)
    return {
        "id": band_id,
        "label": label,
        "key": band_key(band_id),
        "name": None,
        "category": known[1] if known else category_of(label),
    }


def bands_of_offer(offer_type, observed):
    """Return the bands {id: label} of an offer: its type and what was seen.

    observed: bands {id: label} met in the statistics of the contract.
    """
    bands = dict(OFFER_BANDS.get(offer_type, {}))
    bands.update(observed)
    return dict(sorted(bands.items()))


def legacy_bands(use_hchp, use_tempo):
    """Return the bands of an entry created before the bands were configured.

    Such an entry only knew the HC/HP and the Tempo options. Other bands of
    its contract are counted by their label until the user configures them.
    """
    labels = {**OFFER_BANDS["HP/HC"], **OFFER_BANDS["TEMPO"]}
    ids = []
    if use_hchp:
        ids += [2, 3]
    if use_tempo:
        ids += TEMPO_BANDS
    return [new_band(band_id, labels[band_id]) for band_id in ids]


def has_sensor(band):
    """Tell whether a configured band has a sensor of its own."""
    return band["id"] not in TOTAL_BANDS


def is_band_key(key):
    """Tell whether a sensor key is the one of a band having a sensor.

    The keys of the HC and HP totals are the ones of Heures Creuses and
    Heures Pleines, which have no sensor of their own: they are not.
    """
    if key.startswith("band_"):
        return key[len("band_"):].isdigit()
    return any(
        known_key == key and band_id not in TOTAL_BANDS
        for band_id, (known_key, _category) in KNOWN_BANDS.items())


def day_values(subconsumption, bands):
    """Return the energy of a day by band and by category.

    bands: the configured bands. Returns the energy by sensor key of the
    configured bands, the HC/HP totals and the labels of the bands counted
    in neither. A configured band absent from the day counts 0; a band not
    configured is classified by its label.
    """
    by_id = {band["id"]: band for band in bands}
    values = {band["key"]: 0.0 for band in bands}
    totals = {OFF_PEAK: 0.0, PEAK: 0.0}
    unclassified = []
    for item in subconsumption:
        kwh = item.get("kwh")
        kwh = float(kwh) if kwh is not None else 0.0
        band = by_id.get(item.get("id"))
        if band is not None:
            values[band["key"]] += kwh
            category = band.get("category")
        else:
            category = category_of(item.get("label"))
        if category in totals:
            totals[category] += kwh
        elif band is None:
            unclassified.append(item.get("label"))
    return values, totals, unclassified


# --- Price of a kWh of each tariff band
#
# ecojoko gives the exact prices only with a water heater it pilots, and not
# for every offer: its device may have "device_external_settings.pricing_data
# .prices", items {label, price} in euros per kWh, shown in its web
# application. For some offers its pricing data has the supplier and the
# offer only (Primeo Energie, Offre Fixe -20%, November 2026). Otherwise they are
# estimated from the daily statistics: the cost of a band on a day is its
# energy at the price of a kWh, plus a share of the subscription that does
# not depend on the energy. The slope of the costs against the energies
# over a few days is the price of a kWh.

# Days of statistics kept for the estimation, and what it needs for a band:
# days, and kWh between the smallest and the largest day of the band
PRICE_DAYS = 15
PRICE_MIN_DAYS = 3
PRICE_MIN_SPREAD = 1.0


def _number(value):
    """Return a number given as a number or as a text such as "0,2016", or None."""
    if isinstance(value, bool):
        return None
    if isinstance(value, str):
        try:
            value = float(value.strip().replace(",", "."))
        except ValueError:
            return None
    if not isinstance(value, int | float) or value != value:
        return None
    return float(value)


def day_costs(stat):
    """Return the energy and cost of each band, each day of a statistics response.

    {iso date: {band id: (kWh, euros)}}, the days without bands left out.
    """
    days = {}
    for item in stat.get("data") or []:
        if not isinstance(item, dict):
            continue
        day = local_date(item.get("time"))
        bands = {}
        for band in item.get("subconsumption") or []:
            if not isinstance(band, dict):
                continue
            band_id = band.get("id")
            kwh = _number(band.get("kwh"))
            price = _number(band.get("price"))
            if isinstance(band_id, int) and not isinstance(band_id, bool) \
                    and kwh is not None and price is not None and kwh > 0:
                bands[band_id] = (kwh, price)
        if day is not None and bands:
            days[day.isoformat()] = bands
    return days


def estimate_prices(days):
    """Return the estimated price of a kWh of each band {band id: euros}.

    The slope of the least squares line of the costs against the energies of
    the days of a band, rounded to the tenth of a cent: ecojoko rounds its
    costs to the cent. A band without enough days, or whose days are too
    alike, has no price.
    """
    points = {}
    for bands in days.values():
        for band_id, point in bands.items():
            points.setdefault(band_id, []).append(point)
    prices = {}
    for band_id, values in points.items():
        energies = [kwh for kwh, _price in values]
        if len(values) < PRICE_MIN_DAYS or max(energies) - min(energies) < PRICE_MIN_SPREAD:
            continue
        mean_kwh = sum(energies) / len(values)
        mean_price = sum(price for _kwh, price in values) / len(values)
        spread = sum((kwh - mean_kwh) ** 2 for kwh in energies)
        slope = sum((kwh - mean_kwh) * (price - mean_price) for kwh, price in values) / spread
        if 0 < slope < 5:
            prices[band_id] = round(slope, 3)
    return prices


def entered_prices(entered, day):
    """Return the prices entered by the user that apply on a day, or None.

    entered: the prices of the options (CONF_CONTRACT_PRICES). They apply
    from their start to their end, both included, each optional. Returns
    {"prices": {band id: euros}, "subscription": euros or None, "start",
    "end"}: outside their dates, or without any price, ecojoko's apply.
    """
    if not isinstance(entered, dict):
        return None
    start, end = entered.get("start"), entered.get("end")
    if (start and day.isoformat() < start) or (end and day.isoformat() > end):
        return None
    prices = {}
    for band_id, price in (entered.get("prices") or {}).items():
        price = _number(price)
        try:
            band_id = int(band_id)
        except (TypeError, ValueError):
            continue
        if price is not None and price > 0:
            prices[band_id] = price
    subscription = _number(entered.get("subscription"))
    if not prices and subscription is None:
        return None
    return {"prices": prices, "subscription": subscription, "start": start, "end": end}


def price_gap(energies, base_prices, prices):
    """Return the euros to add to a cost computed by ecojoko, or None.

    energies: kWh by band id; base_prices: ecojoko's price of a kWh by band
    (exact or estimated); prices: the prices entered by band. The energy of
    each band costs the price entered instead of ecojoko's; the rest of
    ecojoko's cost, as its share of the subscription, is kept. None when no
    band has both prices.
    """
    gap, corrected = 0.0, False
    for band_id, kwh in energies.items():
        if kwh is None or band_id not in prices or band_id not in base_prices:
            continue
        gap += kwh * (prices[band_id] - base_prices[band_id])
        corrected = True
    return gap if corrected else None


def subscription_gap(subscription, base_subscription, days):
    """Return the euros to add for a subscription entered over some days, else 0."""
    if subscription is None or base_subscription is None:
        return 0.0
    return (subscription - base_subscription) * 12 / 365 * days


def energies_of_points(points):
    """Return the kWh of each band of a day of power, from its points.

    Each point holds its power until the next one; the last one holds it for
    the median interval of the day.
    """
    times = []
    for point in points:
        try:
            times.append(dt.datetime.fromisoformat(point["time"]))
        except (KeyError, TypeError, ValueError):
            times.append(None)
    gaps = sorted(
        (later - earlier).total_seconds() for earlier, later in zip(times, times[1:])
        if earlier is not None and later is not None and later > earlier)
    usual = gaps[len(gaps) // 2] if gaps else 0
    energies = {}
    for index, point in enumerate(points):
        power, band = point.get("power"), point.get("band")
        if power is None or band is None or times[index] is None:
            continue
        following = times[index + 1] if index + 1 < len(times) else None
        seconds = (following - times[index]).total_seconds() if following else usual
        energies[band] = energies.get(band, 0.0) + max(power, 0) * seconds / 3_600_000
    return energies


def exact_prices(prices, labels):
    """Return the prices given by ecojoko {band id: euros}.

    prices: the "prices" items of its pricing data; labels: the labels of
    the bands {band id: label}. An item is matched by its id when it has
    one, by its label otherwise.
    """
    by_label = {
        str(label).strip().casefold(): band_id for band_id, label in labels.items()}
    result = {}
    for item in prices or []:
        if not isinstance(item, dict):
            continue
        price = _number(item.get("price"))
        band_id = item.get("id")
        if not isinstance(band_id, int) or isinstance(band_id, bool) or band_id not in labels:
            band_id = by_label.get(str(item.get("label", "")).strip().casefold())
        if price is not None and price > 0 and band_id is not None:
            result[band_id] = price
    return result


def _slot_minutes(text):
    """Return a time "HH:MM" of an off-peak slot in minutes, None if not one."""
    try:
        hours, minutes = str(text).split(":")[:2]
        value = int(hours) * 60 + int(minutes)
    except (TypeError, ValueError):
        return None
    return value if 0 <= value <= 1440 else None


def off_peak_at(slots, moment):
    """Tell whether a time is in the off-peak hours of a contract, None without them.

    slots: the off_peak_timeslots of the contract, French times
    [{"start": "22:00", "stop": "06:00"}]; moment: a time in Paris.
    """
    ranges = []
    for slot in slots or []:
        if not isinstance(slot, dict):
            continue
        start, stop = _slot_minutes(slot.get("start")), _slot_minutes(slot.get("stop"))
        if start is not None and stop is not None and start != stop:
            ranges.append((start, stop))
    if not ranges:
        return None
    minutes = moment.hour * 60 + moment.minute
    return any(
        start <= minutes < stop if start < stop else minutes >= start or minutes < stop
        for start, stop in ranges)
