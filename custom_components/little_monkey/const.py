"""Constants for little_monkey."""
from logging import Logger, getLogger

LOGGER: Logger = getLogger(__package__)

DOMAIN = "little_monkey"
MANUFACTURER = "Jean-Marc Cruvellier"
MODEL = "Ecojoko"
VERSION = "1.3.0"
ATTRIBUTION = "Data provided by https://service.ecojoko.com/"
POLL_INTERVAL = "poll_interval"
DEFAULT_POLL_INTERVAL = 5

PLATFORMS = ['sensor']
CONF_USE_HCHP_FEATURE = "use_hchp_feature"
# Replaced by the tariff bands in version 3 of the config entries
CONF_USE_TEMPO_FEATURE = "use_tempo_feature"
CONF_USE_TEMPHUM_FEATURE = "use_temphum_feature"
CONF_USE_PROD_FEATURE = "use_prod_feature"
# Tariff bands of the contract and their settings (see tariff.py)
CONF_TARIFF_BANDS = "tariff_bands"

# Values of the current tariff period sensor, by tariff option
HCHP_PERIODS = ["hc", "hp"]
TEMPO_PERIODS = ["hc_blue", "hp_blue", "hc_white", "hp_white", "hc_red", "hp_red"]


# Tempo tariff bands, by id, and their period (see tariff.py)
TEMPO_BAND_PERIODS = {
    18: "hp_blue", 19: "hc_blue",
    20: "hp_white", 21: "hc_white",
    22: "hp_red", 23: "hc_red",
}


def tariff_periods(data):
    """Return the periods of the tariff option of a config entry, or None.

    The Tempo periods come with the bands of a Tempo contract, the HC/HP
    periods with the HC/HP totals.
    """
    bands = data.get(CONF_TARIFF_BANDS) or []
    if data.get(CONF_USE_TEMPO_FEATURE) is True or any(
        band.get("id") in TEMPO_BAND_PERIODS for band in bands
    ):
        return TEMPO_PERIODS
    if data.get(CONF_USE_HCHP_FEATURE) is True:
        return HCHP_PERIODS
    return None


# APIs
CONF_API_TIMEOUT = 3
CONF_API_STAT_REFRESH = 30
# A communication failure shorter than this many seconds keeps the last
# values instead of making the sensors unavailable
CONF_API_FAILURE_GRACE = 120
# ecojoko feeds its APIs with live data during ten minutes after the list
# of the gateways is read, then serves outdated data without any error.
# The list is read again after this many seconds, to keep the data live
CONF_API_KEEP_LIVE = 300
# and after this many seconds when this reading failed
CONF_API_KEEP_LIVE_RETRY = 30
# The contract of the installation is read again after this many seconds,
# and after this many seconds when its reading failed
CONF_API_CONTRACT_REFRESH = 6 * 3600
CONF_API_CONTRACT_RETRY = 600

# Activity of the account (savings over 7 days...): ecojoko computes it
# slowly, its web application waits 30 seconds for it and asks for it at most
# every ten minutes. Its last values are kept during an hour of failures
CONF_API_ACTIVITY_TIMEOUT = 30
CONF_API_ACTIVITY_REFRESH = 600
CONF_API_ACTIVITY_GRACE = 3600

# URLs
ECOJOKO_LOGIN_URL = "https://service.ecojoko.com/login"
ECOJOKO_GATEWAYS_URL = "https://service.ecojoko.com/gateways"
ECOJOKO_GATEWAY_URL = "https://service.ecojoko.com/gateway"
ECOJOKO_ACTIVITY_URL = "https://service.ecojoko.com/user/activity"
