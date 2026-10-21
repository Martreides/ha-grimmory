"""Sensor platform for Grimmory."""

import logging

from homeassistant.components.sensor import SensorEntity
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
    """Set up the Grimmory sensor platform."""

    client = entry.runtime_data

    sensors = [
        GrimmoryBookCountSensor(client),
    ]
    _LOGGER.debug("Setting up Grimmory sensors: %s", sensors)

    async_add_entities(sensors, update_before_add=True)


class GrimmoryBookCountSensor(SensorEntity):
    """A sensor for the book count in Grimmory."""

    _attr_has_entity_name = True
    _attr_name = "Book count"
    _attr_unique_id = "book_count"

    def __init__(self, client: GrimmoryApiClient) -> None:
        """Initialize the sensor."""
        self._client = client

    async def async_update(self) -> None:
        """Fetch number of books."""
        self._attr_native_value = await self._client.get_book_count()
