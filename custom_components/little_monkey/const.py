"""Constants for little_monkey."""
from logging import Logger, getLogger

LOGGER: Logger = getLogger(__package__)

DOMAIN = "little_monkey"
MANUFACTURER = "Jean-Marc Cruvellier"
MODEL = "Ecojoko"
VERSION = "2.0.0b2"
ATTRIBUTION = "Data provided by https://service.ecojoko.com/"
POLL_INTERVAL = "poll_interval"
# ecojoko refreshes the realtime of the integration every 30 s: a shorter
# interval reads the same value again and loads its servers
DEFAULT_POLL_INTERVAL = 30
# Shortest interval allowed in the options: ecojoko changes the realtime
# value every 5 to 10 s at best, a third of the readings at 5 s are the same
MIN_POLL_INTERVAL = 5

PLATFORMS = ['sensor', 'select', 'binary_sensor']
CONF_USE_HCHP_FEATURE = "use_hchp_feature"
# Replaced by the tariff bands in version 3 of the config entries
CONF_USE_TEMPO_FEATURE = "use_tempo_feature"
CONF_USE_TEMPHUM_FEATURE = "use_temphum_feature"
CONF_USE_PROD_FEATURE = "use_prod_feature"
# Groups of sensors added in 2.0.0, off by default: their sensors are
# created, and their data read from ecojoko, only when they are on
CONF_USE_ACTIVITY_FEATURE = "use_activity_feature"
CONF_USE_SAVINGS_FEATURE = "use_savings_feature"
CONF_USE_CONTRACT_FEATURE = "use_contract_feature"
CONF_USE_EQUIPMENT_FEATURE = "use_equipment_feature"
# Cards without sensors, read on demand with services: their services
# answer only when their option is on, as the other groups
CONF_USE_ANALYSIS_FEATURE = "use_analysis_feature"
CONF_USE_MEASURES_FEATURE = "use_measures_feature"
SENSOR_GROUP_OPTIONS = (
    CONF_USE_ACTIVITY_FEATURE,
    CONF_USE_SAVINGS_FEATURE,
    CONF_USE_CONTRACT_FEATURE,
    CONF_USE_EQUIPMENT_FEATURE,
    CONF_USE_ANALYSIS_FEATURE,
    CONF_USE_MEASURES_FEATURE,
)


def option_enabled(entry, option) -> bool:
    """Tell whether an option of a config entry is on."""
    return entry.data.get(option) is True


# Tariff bands of the contract and their settings (see tariff.py)
CONF_TARIFF_BANDS = "tariff_bands"
# Ids of the bands removed by the user while ecojoko still gives them: they
# are neither proposed again nor reported as missing (previous contract...)
CONF_REMOVED_BANDS = "removed_bands"

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
# Seconds between two readings of each statistic, apart from the poll
# interval. Measured over an hour on two installations (11/2026): ecojoko
# updates the energies of the day about every minute, the temperature and
# the humidity about every two minutes
CONF_API_STAT_REFRESH = {"powerstat": 60, "tempstat": 120, "humstat": 120}
# A statistic is read at the first poll that comes this close to its delay,
# at most half the poll interval: the polls do not fall exactly on it
CONF_API_STAT_MARGIN = 5
# With a short poll interval, the statistics due together are spread over
# this many seconds, one per poll; with a longer one, they are read together
CONF_API_STAT_SPREAD = 30
# Timeout of the statistics APIs, read in the background: ecojoko often
# takes more than CONF_API_TIMEOUT to answer them with a short poll
# interval. Shorter than CONF_API_STAT_REFRESH, so that a statistic is not
# asked for again while it is read
CONF_API_STAT_TIMEOUT = 15
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
# slowly, and its web application waits 30 seconds for it. It changes a few
# times an hour and at midnight: it is read every half hour. Its last values
# are kept during an hour of failures
CONF_API_ACTIVITY_TIMEOUT = 30
CONF_API_ACTIVITY_REFRESH = 1800
CONF_API_ACTIVITY_GRACE = 3600
# Savings of the account (12 months, current week, month and year): read
# like the activity, with its timeout and its grace, every half hour
CONF_API_SAVINGS_REFRESH = 1800
# Piloted equipments (water heater...): their state is read every two
# minutes, with the timeout and grace of the activity. Their power curve of
# the day is read every third time, their changes of state of the day every
# fifth time: they never changed in an hour (11/2026). Both are read again
# after a command and at the end of a forced mode or of an absence
CONF_API_EQUIPMENT_REFRESH = 120
CONF_API_EQUIPMENT_POWER_REFRESH = 360
CONF_API_EQUIPMENT_SWITCHES_REFRESH = 600

# URLs
ECOJOKO_LOGIN_URL = "https://service.ecojoko.com/login"
ECOJOKO_GATEWAYS_URL = "https://service.ecojoko.com/gateways"
ECOJOKO_GATEWAY_URL = "https://service.ecojoko.com/gateway"
ECOJOKO_ACTIVITY_URL = "https://service.ecojoko.com/user/activity"
