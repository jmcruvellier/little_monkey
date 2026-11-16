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

# Fields of a contract kept for the diagnostics: neither prices nor the
# internal ids of the subscription
CONTRACT_FIELDS = (
    "supplier_name",
    "offer_id",
    "offer_name",
    "offer_type",
    "is_hchp",
    "special_day",
)


def _iso_date(milliseconds):
    """Return a time in milliseconds as an ISO date (UTC), or None."""
    if isinstance(milliseconds, bool) or not isinstance(milliseconds, int | float):
        return None
    return dt.datetime.fromtimestamp(milliseconds / 1000, dt.UTC).date().isoformat()


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


def totals_by_category(subconsumption):
    """Return the energy of a day by category, and the unclassified labels.

    Every band of a category is added: a Tempo day has up to two off peak
    bands, a Zen Week-End Plus contract has three of each in a week. A
    category without any band in the day counts 0.
    """
    totals = {OFF_PEAK: 0.0, PEAK: 0.0}
    unclassified = []
    for item in subconsumption:
        label = item.get("label")
        category = category_of(label)
        if category is None:
            unclassified.append(label)
            continue
        kwh = item.get("kwh")
        totals[category] += float(kwh) if kwh is not None else 0
    return totals, unclassified
