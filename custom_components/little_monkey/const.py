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
CONF_USE_TEMPO_FEATURE = "use_tempo_feature"
CONF_USE_TEMPHUM_FEATURE = "use_temphum_feature"
CONF_USE_PROD_FEATURE = "use_prod_feature"

# Values of the current tariff period sensor, by tariff option
HCHP_PERIODS = ["hc", "hp"]
TEMPO_PERIODS = ["hc_blue", "hp_blue", "hc_white", "hp_white", "hc_red", "hp_red"]


def tariff_periods(data):
    """Return the periods of the tariff option of a config entry, or None."""
    if data.get(CONF_USE_TEMPO_FEATURE) is True:
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

# URLs
ECOJOKO_LOGIN_URL = "https://service.ecojoko.com/login"
ECOJOKO_GATEWAYS_URL = "https://service.ecojoko.com/gateways"
ECOJOKO_GATEWAY_URL = "https://service.ecojoko.com/gateway"
