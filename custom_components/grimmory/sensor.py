# Copyright (C) 2026 Michiel Cornelissen
# This file is part of ha-grimmory
# SPDX-License-Identifier: GPL-3.0-only
"""Sensor platform for Grimmory."""

import logging
from datetime import timedelta

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.const import PERCENTAGE
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
        GrimmoryBookdropPendingReviewSensor(client),
        GrimmoryLastReadSensor(client),
    ]
    _LOGGER.debug("Setting up Grimmory sensors: %s", sensors)

    async_add_entities(sensors, update_before_add=True)

    for subentry in entry.get_subentries_of_type("book"):
        async_add_entities(
            [
                GrimmoryBookReadStatusSensor(client, subentry),
                GrimmoryBookKoreaderProgressSensor(client, subentry),
            ],
            update_before_add=True,
            config_subentry_id=subentry.subentry_id,
        )


class GrimmoryBookCountSensor(SensorEntity):
    """A sensor for the book count in Grimmory."""

    _attr_has_entity_name = True
    _attr_name = "Book count"
    _attr_icon = "mdi:bookshelf"
    _attr_device_info = DeviceInfo(
        identifiers={(DOMAIN, "grimmory")},
        name="Grimmory",
        manufacturer="Grimmory",
    )

    def __init__(self, client: GrimmoryApiClient) -> None:
        """Initialize the sensor."""
        self._client = client
        self._attr_unique_id = f"{client.entry.entry_id}_book_count"

    async def async_update(self) -> None:
        """Fetch number of books."""
        self._attr_native_value = await self._client.get_book_count()


class GrimmoryBookdropPendingReviewSensor(SensorEntity):
    """Sensor for bookdrop files pending review."""

    _attr_has_entity_name = True
    _attr_name = "Bookdrop files pending review"
    _attr_icon = "mdi:book-alert-outline"
    _attr_device_info = DeviceInfo(
        identifiers={(DOMAIN, "grimmory")},
        name="Grimmory",
        manufacturer="Grimmory",
    )

    def __init__(self, client: GrimmoryApiClient) -> None:
        """Initialize the sensor."""
        self._client = client
        self._attr_unique_id = f"{client.entry.entry_id}_bookdrop_pending_review"

    async def async_update(self) -> None:
        """Fetch the number of bookdrop files pending review."""
        files = await self._client.get_bookdrop_files_by_status("PENDING_REVIEW")
        self._attr_native_value = files["page"]["totalElements"]


class GrimmoryLastReadSensor(SensorEntity):
    """A sensor for the last read book in Grimmory."""

    _attr_has_entity_name = True
    _attr_name = "Last read book"
    _attr_icon = "mdi:book-clock-outline"
    _attr_device_info = DeviceInfo(
        identifiers={(DOMAIN, "grimmory")},
        name="Grimmory",
        manufacturer="Grimmory",
    )

    def __init__(self, client: GrimmoryApiClient) -> None:
        """Initialize the sensor."""
        self._client = client
        self._attr_unique_id = f"{client.entry.entry_id}_last_read_book"

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


class GrimmoryBookReadStatusSensor(SensorEntity):
    """Sensor for the read status of a Grimmory book."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:book-check-outline"

    def __init__(
        self,
        client: GrimmoryApiClient,
        subentry,
    ) -> None:
        """Initialize the sensor."""

        self._client = client
        self._book_id = subentry.data["book_id"]
        self._attr_name = f"{subentry.title} Read Status"
        self._attr_unique_id = f"book_{self._book_id}_read_status"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"book_{self._book_id}")},
            name=subentry.title,
            manufacturer="Grimmory",
            model="Book",
        )

    async def async_update(self) -> None:
        """Fetch the book's read status."""
        book = await self._client.get_book(self._book_id)
        _LOGGER.debug(book)
        self._attr_native_value = book.get("readStatus")


class GrimmoryBookKoreaderProgressSensor(SensorEntity):
    """Sensor for the Koreader progress of a Grimmory book."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:file-percent-outline"
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self,
        client: GrimmoryApiClient,
        subentry,
    ) -> None:
        """Initialize the sensor."""

        self._client = client
        self._book_id = subentry.data["book_id"]
        self._attr_name = f"{subentry.title} Koreader Progress"
        self._attr_unique_id = f"book_{self._book_id}_koreader_progress"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"book_{self._book_id}")},
            name=subentry.title,
            manufacturer="Grimmory",
            model="Book",
        )

    async def async_update(self) -> None:
        """Fetch the book's koreader pogress."""
        book = await self._client.get_book(self._book_id)
        _LOGGER.debug(book)
        progress = book.get("koreaderProgress")
        self._attr_native_value = progress.get("percentage") if progress else None
