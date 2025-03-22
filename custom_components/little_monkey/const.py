"""Constants for little_monkey."""
from logging import Logger, getLogger

LOGGER: Logger = getLogger(__package__)

NAME = "Little Monkey"
DOMAIN = "little_monkey"
MANUFACTURER = "Jean-Marc Cruvellier"
MODEL = "Ecojoko"
VERSION = "1.2.1"
ATTRIBUTION = "Data provided by https://service.ecojoko.com//"
POLL_INTERVAL = "poll_interval"
DEFAULT_POLL_INTERVAL = "5"

PLATFORMS = ['sensor']
CONF_USE_HCHP_FEATURE = "use_hchp_feature"
CONF_USE_TEMPO_FEATURE = "use_tempo_feature"
CONF_USE_TEMPHUM_FEATURE = "use_temphum_feature"
CONF_USE_PROD_FEATURE = "use_prod_feature"
CONF_LANG = 'lang'
DEFAULT_LANG = 'fr-FR'
# Language Supported Codes
LANG_CODES = ['fr-FR', 'en-US']

# APIs
CONF_API_TIMEOUT = 3
CONF_API_STAT_REFRESH = 30

# URLs
ECOJOKO_LOGIN_URL = "https://service.ecojoko.com/login"
ECOJOKO_GATEWAYS_URL = "https://service.ecojoko.com/gateways"
ECOJOKO_GATEWAY_URL = "https://service.ecojoko.com/gateway"
