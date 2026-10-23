"""Sensor platform for Grimmory."""

import logging
from datetime import timedelta

from homeassistant.components.sensor import SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import GrimmoryConfigEntry
from .api import GrimmoryApiClient
from .const import DOMAIN

SCAN_INTERVAL = timedelta(minutes=5)

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
        GrimmoryLastReadSensor(client),
    ]
    _LOGGER.debug("Setting up Grimmory sensors: %s", sensors)

    async_add_entities(sensors, update_before_add=True)


class GrimmoryBookCountSensor(SensorEntity):
    """A sensor for the book count in Grimmory."""

    _attr_has_entity_name = True
    _attr_name = "Book count"
    _attr_unique_id = "book_count"
    _attr_icon = "mdi:bookshelf"
    _attr_device_info = DeviceInfo(
        identifiers={(DOMAIN, "grimmory")},
        name="Grimmory",
        manufacturer="Grimmory",
    )

    def __init__(self, client: GrimmoryApiClient) -> None:
        """Initialize the sensor."""
        self._client = client

    async def async_update(self) -> None:
        """Fetch number of books."""
        self._attr_native_value = await self._client.get_book_count()


class GrimmoryLastReadSensor(SensorEntity):
    """A sensor for the last read book in Grimmory."""

    _attr_has_entity_name = True
    _attr_name = "Last read book"
    _attr_unique_id = "last_read_book"
    _attr_icon = "mdi:book-clock-outline"
    _attr_device_info = DeviceInfo(
        identifiers={(DOMAIN, "grimmory")},
        name="Grimmory",
        manufacturer="Grimmory",
    )

    def __init__(self, client: GrimmoryApiClient) -> None:
        """Initialize the sensor."""
        self._client = client

    async def async_update(self) -> None:
        """Fetch last read book."""
        book = await self._client.get_last_read_book()

        if book is None:
            self._attr_native_value = None
            self._attr_extra_state_attributes = {}
            return

        self._attr_native_value = book.get("title")
        self._attr_extra_state_attributes = {
            "authors": book.get("authors"),
            "last_read": book.get("lastReadTime"),
            "read_progress": book.get("readProgress"),
            "series": book.get("seriesName"),
        }
