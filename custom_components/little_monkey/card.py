"""Serve the Little Monkey Lovelace card.

The card is a JavaScript module shipped in the frontend folder of the
integration. It is loaded on every page of the frontend, like the cards of
the core: nobody has to add a Lovelace resource, and the card always has the
version of the integration.
"""
from __future__ import annotations

from pathlib import Path

from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import StaticPathConfig
from homeassistant.core import HomeAssistant

from .const import LOGGER, VERSION

# URL of the folder holding the files of the card
CARD_URL_BASE = "/little_monkey_card"
CARD_FILENAME = "little-monkey-card.js"
CARD_DIR = Path(__file__).parent / "frontend"


def card_url() -> str:
    """Return the URL loaded by the frontend.

    The version in the query string makes the browsers load the new card
    after an update of the integration.
    """
    return f"{CARD_URL_BASE}/{CARD_FILENAME}?v={VERSION}"


async def async_register_card(hass: HomeAssistant) -> None:
    """Serve the card and load it in the frontend."""
    # The http and frontend components are after dependencies: they are set
    # up first when they are configured, which default_config does
    if hass.http is None or "frontend" not in hass.config.components:
        LOGGER.debug("Frontend not loaded: the Little Monkey card is not served")
        return
    await hass.http.async_register_static_paths(
        # Not cached: browsers check that the file did not change
        [StaticPathConfig(CARD_URL_BASE, str(CARD_DIR), False)]
    )
    add_extra_js_url(hass, card_url())
