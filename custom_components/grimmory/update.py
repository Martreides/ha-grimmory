"""Update platform for Grimmory."""

import logging

from homeassistant.components.update import UpdateEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import GrimmoryConfigEntry
from .api import GrimmoryApiClient

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: GrimmoryConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Grimmory sensor platform."""

    client = entry.runtime_data

    _LOGGER.debug("Setting up Grimmory update entity")

    async_add_entities(
        [
            GrimmoryUpdateEntity(client),
        ],
        update_before_add=True,
    )


class GrimmoryUpdateEntity(UpdateEntity):
    """Update entity for Grimmory."""

    _attr_has_entity_name = True
    _attr_name = "Grimmory"
    _attr_unique_id = "version"

    def __init__(self, client: GrimmoryApiClient) -> None:
        """Initialize the update entity."""
        self._client = client

    async def async_update(self) -> None:
        """Fetch the latest version information."""
        version_info = await self._client.get_grimmory_version()

        self._attr_installed_version = version_info["current"]
        self._attr_latest_version = version_info["latest"]
