"""Tests of the service of the Lovelace card by the integration."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from custom_components.little_monkey import card, const


def test_card_files_are_shipped():
    """The served folder holds the cards."""
    for filename in card.CARD_FILENAMES:
        assert (card.CARD_DIR / filename).is_file(), filename


def test_card_url_changes_with_the_version():
    """Browsers load the card again after an update of the integration."""
    assert card.card_url() == (
        f"/little_monkey_card/little-monkey-card.js?v={const.VERSION}"
    )


async def test_card_is_served_and_loaded(hass):
    """The card folder is served, and the card loaded on every page."""
    hass.http = MagicMock(async_register_static_paths=AsyncMock())
    hass.config.components.add("frontend")
    with patch.object(card, "add_extra_js_url") as add_extra_js_url:
        await card.async_register_card(hass)

    (paths,), _ = hass.http.async_register_static_paths.call_args
    assert [(path.url_path, path.path, path.cache_headers) for path in paths] == [
        ("/little_monkey_card", str(card.CARD_DIR), False)
    ]
    assert [call.args for call in add_extra_js_url.call_args_list] == [
        (hass, card.card_url()),
        (hass, f"/little_monkey_card/little-monkey-savings-cards.js?v={const.VERSION}"),
        (hass, f"/little_monkey_card/little-monkey-analysis-cards.js?v={const.VERSION}"),
    ]


async def test_card_is_not_served_without_frontend(hass):
    """Without frontend, as in these tests, the setup goes on without card."""
    hass.http = MagicMock(async_register_static_paths=AsyncMock())
    with patch.object(card, "add_extra_js_url") as add_extra_js_url:
        await card.async_register_card(hass)

    hass.http.async_register_static_paths.assert_not_called()
    add_extra_js_url.assert_not_called()
