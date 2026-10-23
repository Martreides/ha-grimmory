"""The grimmory integration."""

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .api import GrimmoryApiClient

_PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.UPDATE,
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
]

type GrimmoryConfigEntry = ConfigEntry[GrimmoryApiClient]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: GrimmoryConfigEntry) -> bool:
    """Set up grimmory from a config entry."""

    client = GrimmoryApiClient(hass, entry)

    entry.runtime_data = client
    _LOGGER.debug("Grimmory API client initialized")
    await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: GrimmoryConfigEntry) -> None:
    """Unload a config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, _PLATFORMS)
