"""Serve the Little Monkey Lovelace card.

The cards are JavaScript modules shipped in the frontend folder of the
integration. They are loaded on every page of the frontend, like the cards
of the core: nobody has to add a Lovelace resource, and the cards always
have the version of the integration.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import StaticPathConfig
from homeassistant.core import HomeAssistant

from .const import LOGGER, VERSION

# URL of the folder holding the files of the card
CARD_URL_BASE = "/little_monkey_card"
CARD_FILENAME = "little-monkey-card.js"
# Every module loaded by the frontend: the dial, savings, analysis, contract,
# equipment and measures cards
CARD_FILENAMES = (
    CARD_FILENAME, "little-monkey-savings-cards.js", "little-monkey-analysis-cards.js",
    "little-monkey-contract-card.js", "little-monkey-equipment-card.js",
    "little-monkey-measures-card.js")
CARD_DIR = Path(__file__).parent / "frontend"


def file_digest(filename: str) -> str:
    """Return a short digest of the content of a file of the cards."""
    return hashlib.sha256((CARD_DIR / filename).read_bytes()).hexdigest()[:8]


def card_url(filename: str = CARD_FILENAME, digest: str | None = None) -> str:
    """Return the URL loaded by the frontend.

    The version and the digest of the file in the query string make the
    browsers load the new card after an update of the integration, and after
    any change of the file under the same version: the browsers keep the
    modules they loaded, a reload of the page included.
    """
    version = VERSION if digest is None else f"{VERSION}-{digest}"
    return f"{CARD_URL_BASE}/{filename}?v={version}"


async def async_register_card(hass: HomeAssistant) -> None:
    """Serve the cards and load them in the frontend."""
    # The http and frontend components are after dependencies: they are set
    # up first when they are configured, which default_config does
    if hass.http is None or "frontend" not in hass.config.components:
        LOGGER.debug("Frontend not loaded: the Little Monkey card is not served")
        return
    await hass.http.async_register_static_paths(
        # Not cached: browsers check that the file did not change
        [StaticPathConfig(CARD_URL_BASE, str(CARD_DIR), False)]
    )
    # Read from the disk, out of the event loop
    digests = await hass.async_add_executor_job(
        lambda: {filename: file_digest(filename) for filename in CARD_FILENAMES})
    for filename in CARD_FILENAMES:
        add_extra_js_url(hass, card_url(filename, digests[filename]))
