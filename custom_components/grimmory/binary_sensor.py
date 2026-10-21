"""Binary sensor platform for Grimmory."""

import logging

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import GrimmoryConfigEntry
from .api import GrimmoryApiClient

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant | None,
    entry: GrimmoryConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Grimmory binary sensor platform."""

    client = entry.runtime_data

    sensors = [
        GrimmoryKoboSyncEnabledSensor(client),
    ]
    _LOGGER.debug("Setting up Grimmory sensors: %s", sensors)

    async_add_entities(sensors, update_before_add=True)


class GrimmoryKoboSyncEnabledSensor(BinarySensorEntity):
    """A sensor for the Kobo sync status in Grimmory."""

    _attr_has_entity_name = True
    _attr_name = "Kobo Sync Enabled"
    _attr_unique_id = "kobo_sync_enabled"

    def __init__(self, client: GrimmoryApiClient) -> None:
        """Initialize the sensor."""
        self._client = client

    async def async_update(self) -> None:
        """Fetch Kobo sync status."""
        self._attr_is_on = await self._client.get_kobo_sync_status()
