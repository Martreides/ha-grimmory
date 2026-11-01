# Copyright (C) 2026 Michiel Cornelissen
# This file is part of ha-grimmory
# SPDX-License-Identifier: GPL-3.0-only
"""Sensor platform for Grimmory."""

import logging
from datetime import timedelta
from typing import Any

import aiohttp
from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import ChildDeviceInfo, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import GrimmoryConfigEntry
from .api import GrimmoryApiClient, GrimmoryRateLimitedError
from .const import CONF_BOOKS, CONF_PROGRESS_SOURCE, DOMAIN

SCAN_INTERVAL = timedelta(minutes=5)

_LOGGER = logging.getLogger(__name__)


def _get_book_device_name(book: dict[str, Any], book_id: int) -> str:
    """Build a device name from book metadata."""

    metadata = book.get("metadata")
    if metadata is None:
        return f"Book {book_id}"

    return f"{', '.join(metadata['authors'])} - {metadata['title']}"


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

    device_registry = dr.async_get(hass)
    parent_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, "grimmory"),
        entry.entry_id,
    )

    if parent_device is None:
        raise RuntimeError("Grimmory parent device not found")

    progress_source = entry.data.get(CONF_PROGRESS_SOURCE)
    for book in entry.options.get(CONF_BOOKS, []):
        async_add_entities(
            [
                GrimmoryBookReadStatusSensor(client, book, parent_device.id),
                GrimmoryBookProgressSensor(
                    client, book, parent_device.id, progress_source
                ),
            ],
            update_before_add=True,
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
        try:
            self._attr_native_value = await self._client.get_book_count()
        except (GrimmoryRateLimitedError, ConfigEntryAuthFailed):
            self._attr_available = False
            return
        self._attr_available = True


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
        try:
            files = await self._client.get_bookdrop_files_by_status("PENDING_REVIEW")
        except (GrimmoryRateLimitedError, ConfigEntryAuthFailed):
            self._attr_available = False
            return
        self._attr_available = True
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
        try:
            book = await self._client.get_last_read_book()
        except (GrimmoryRateLimitedError, ConfigEntryAuthFailed):
            self._attr_available = False
            return
        self._attr_available = True

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
        book: dict[str, Any],
        parent_device_id: str,
    ) -> None:
        """Initialize the sensor."""

        self._client = client
        self._book_id = book["book_id"]
        self._parent_device_id = parent_device_id
        self._attr_name = "Read Status"
        self._attr_unique_id = f"book_{self._book_id}_read_status"
        self._attr_device_info = ChildDeviceInfo(
            identifiers={(DOMAIN, f"book_{self._book_id}")},
            name=_get_book_device_name(book, self._book_id),
            parent_device_id=parent_device_id,
        )

    async def async_update(self) -> None:
        """Fetch the book's read status."""
        try:
            book = await self._client.get_book(self._book_id)
        except (aiohttp.ClientError, ConfigEntryAuthFailed, TimeoutError):
            self._attr_available = False
            return

        self._attr_available = True
        self._attr_native_value = book.get("readStatus")

        name = _get_book_device_name(book, self._book_id)
        self._attr_device_info = ChildDeviceInfo(
            identifiers={(DOMAIN, f"book_{self._book_id}")},
            name=name,
            parent_device_id=self._parent_device_id,
        )
        device = self.device_entry
        if device is not None and device.name != name:
            dr.async_get(self.hass).async_update_child_device(
                device.id,
                name=name,
            )


class GrimmoryBookProgressSensor(SensorEntity):
    """Sensor for the Koreader progress of a Grimmory book."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:file-percent-outline"
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self,
        client: GrimmoryApiClient,
        book: dict[str, Any],
        parent_device_id: str,
        progress_source: str | None,
    ) -> None:
        """Initialize the sensor."""

        self._client = client
        self._book_id = book["book_id"]
        self._parent_device_id = parent_device_id
        self._progress_source = progress_source
        self._attr_name = "Read progress"
        self._attr_unique_id = f"book_{self._book_id}_read_progress"
        self._attr_device_info = ChildDeviceInfo(
            identifiers={(DOMAIN, f"book_{self._book_id}")},
            name=_get_book_device_name(book, self._book_id),
            parent_device_id=parent_device_id,
        )

    async def async_update(self) -> None:
        """Fetch the book's koreader pogress."""
        try:
            book = await self._client.get_book(self._book_id)
        except (aiohttp.ClientError, ConfigEntryAuthFailed, TimeoutError):
            self._attr_available = False
            return

        self._attr_available = True

        name = _get_book_device_name(book, self._book_id)
        self._attr_device_info = ChildDeviceInfo(
            identifiers={(DOMAIN, f"book_{self._book_id}")},
            name=name,
            parent_device_id=self._parent_device_id,
        )
        device = self.device_entry

        if device is not None and device.name != name:
            dr.async_get(self.hass).async_update_child_device(
                device.id,
                name=name,
            )

        if self._progress_source == "koreader":
            progress = book.get("koreaderProgress")
        elif self._progress_source == "kobo":
            progress = book.get("koboProgress")
        else:
            progress = book.get("epubProgress")

        self._attr_native_value = progress.get("percentage") if progress else None
