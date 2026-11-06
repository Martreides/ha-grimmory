# Copyright (C) 2026 Michiel Cornelissen
# This file is part of ha-grimmory
# SPDX-License-Identifier: GPL-3.0-only
"""Sensor platform for Grimmory."""

import logging
from datetime import timedelta
from typing import Any

import aiohttp
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import ChildDeviceInfo, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from . import GrimmoryConfigEntry
from .api import GrimmoryApiClient
from .const import CONF_BOOKS, CONF_LIBRARY_ID, CONF_PROGRESS_SOURCE, DOMAIN
from .coordinator import GrimmoryCoordinator
from .helpers import _get_book_device_name

SCAN_INTERVAL = timedelta(minutes=5)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: GrimmoryConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Grimmory sensor platform."""

    api_client = entry.runtime_data.api_client
    coordinator = entry.runtime_data.coordinator

    library_id = entry.data.get(CONF_LIBRARY_ID)
    async_add_entities(
        [
            GrimmoryBookCountSensor(api_client, entry.entry_id, library_id),
            GrimmoryBookCountReadSensor(coordinator, entry.entry_id),
            GrimmoryBookCountReadingSensor(coordinator, entry.entry_id),
            GrimmoryBookdropPendingReviewSensor(api_client, entry.entry_id),
            GrimmoryLastReadSensor(api_client, entry.entry_id, library_id),
        ],
        update_before_add=True,
    )

    device_registry = dr.async_get(hass)
    parent_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, entry.entry_id),
        entry.entry_id,
    )

    if parent_device is None:
        raise RuntimeError("Grimmory parent device not found")

    progress_source = entry.data.get(CONF_PROGRESS_SOURCE)
    for book in entry.options.get(CONF_BOOKS, []):
        async_add_entities(
            [
                GrimmoryBookReadStatusSensor(
                    coordinator, book, parent_device.id, entry.entry_id
                ),
                GrimmoryBookProgressSensor(
                    coordinator, book, parent_device.id, progress_source, entry.entry_id
                ),
                GrimmoryBookLastReadSensor(
                    coordinator, book, parent_device.id, entry.entry_id
                ),
            ],
        )


class GrimmoryBookCountSensor(SensorEntity):
    """A sensor for the book count in Grimmory."""

    _attr_has_entity_name = True
    _attr_name = "Book count"
    _attr_icon = "mdi:bookshelf"

    def __init__(
        self,
        api_client: GrimmoryApiClient,
        entry_id: str,
        library_id: int | None,
    ) -> None:
        """Initialize the sensor."""
        self._api_client = api_client
        self._library_id = library_id
        self._attr_unique_id = f"{entry_id}_book_count"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
            name="Grimmory",
            manufacturer="Grimmory",
        )

    async def async_update(self) -> None:
        """Fetch number of books."""
        try:
            self._attr_native_value = await self._api_client.get_book_count(
                self._library_id
            )
        except (aiohttp.ClientError, TimeoutError, ConfigEntryAuthFailed):
            self._attr_available = False
            return
        self._attr_available = True


class GrimmoryBookCountReadSensor(CoordinatorEntity[GrimmoryCoordinator], SensorEntity):
    """A sensor for the read book count in Grimmory."""

    _attr_has_entity_name = True
    _attr_name = "Read book count"
    _attr_icon = "mdi:book-check-outline"

    def __init__(self, coordinator: GrimmoryCoordinator, entry_id: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry_id}_book_count_read"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
            name="Grimmory",
            manufacturer="Grimmory",
        )

    async def async_added_to_hass(self) -> None:
        """Register the listener and apply the coordinator's current data."""
        await super().async_added_to_hass()
        self._handle_coordinator_update()

    def _handle_coordinator_update(self) -> None:
        """Fetch number of read books."""
        distributions = self.coordinator.data["distributions"]

        stats = distributions.get("statusDistribution")
        count_read = None
        for stat in stats:
            if stat.get("status") == "READ":
                count_read = stat.get("count")
                break

        self._attr_native_value = count_read if count_read is not None else 0

        super()._handle_coordinator_update()


class GrimmoryBookCountReadingSensor(
    CoordinatorEntity[GrimmoryCoordinator], SensorEntity
):
    """A sensor for the reading book count in Grimmory."""

    _attr_has_entity_name = True
    _attr_name = "Reading book count"
    _attr_icon = "mdi:book-open-outline"

    def __init__(self, coordinator: GrimmoryCoordinator, entry_id: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry_id}_book_count_reading"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
            name="Grimmory",
            manufacturer="Grimmory",
        )

    async def async_added_to_hass(self) -> None:
        """Register the listener and apply the coordinator's current data."""
        await super().async_added_to_hass()
        self._handle_coordinator_update()

    def _handle_coordinator_update(self) -> None:
        """Fetch number of reading books."""
        distributions = self.coordinator.data["distributions"]

        stats = distributions.get("statusDistribution")
        count_read = None
        for stat in stats:
            if stat.get("status") == "READING":
                count_read = stat.get("count")
                break

        self._attr_native_value = count_read if count_read is not None else 0

        super()._handle_coordinator_update()


class GrimmoryBookdropPendingReviewSensor(SensorEntity):
    """Sensor for bookdrop files pending review."""

    _attr_has_entity_name = True
    _attr_name = "Bookdrop files pending review"
    _attr_icon = "mdi:book-alert-outline"

    def __init__(self, api_client: GrimmoryApiClient, entry_id: str) -> None:
        """Initialize the sensor."""
        self._api_client = api_client
        self._attr_unique_id = f"{entry_id}_bookdrop_pending_review"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
            name="Grimmory",
            manufacturer="Grimmory",
        )

    async def async_update(self) -> None:
        """Fetch the number of bookdrop files pending review."""
        try:
            files = await self._api_client.get_bookdrop_files_by_status("PENDING_REVIEW")
        except (aiohttp.ClientError, TimeoutError, ConfigEntryAuthFailed):
            self._attr_available = False
            return
        self._attr_available = True
        self._attr_native_value = files["page"]["totalElements"]


class GrimmoryLastReadSensor(SensorEntity):
    """A sensor for the last read book in Grimmory."""

    _attr_has_entity_name = True
    _attr_name = "Last read book"
    _attr_icon = "mdi:book-clock-outline"

    def __init__(
        self,
        api_client: GrimmoryApiClient,
        entry_id: str,
        library_id: int | None,
    ) -> None:
        """Initialize the sensor."""
        self._api_client = api_client
        self._library_id = library_id
        self._attr_unique_id = f"{entry_id}_last_read_book"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
            name="Grimmory",
            manufacturer="Grimmory",
        )

    async def async_update(self) -> None:
        """Fetch last read book."""
        try:
            book = await self._api_client.get_last_read_book(self._library_id)
        except (aiohttp.ClientError, TimeoutError, ConfigEntryAuthFailed):
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


class GrimmoryBookReadStatusSensor(
    CoordinatorEntity[GrimmoryCoordinator], SensorEntity
):
    """Sensor for the read status of a Grimmory book."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:book-check-outline"

    def __init__(
        self,
        coordinator: GrimmoryCoordinator,
        book: dict[str, Any],
        parent_device_id: str,
        entry_id: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._book_id = book["book_id"]
        self._parent_device_id = parent_device_id
        self._entry_id = entry_id
        self._attr_name = "Read Status"
        self._attr_unique_id = f"{self._entry_id}_book_{self._book_id}_read_status"
        self._attr_device_info = ChildDeviceInfo(
            identifiers={(DOMAIN, f"{self._entry_id}_book_{self._book_id}")},
            name=_get_book_device_name(book, self._book_id),
            parent_device_id=parent_device_id,
        )

    async def async_added_to_hass(self) -> None:
        """Register the listener and apply the coordinator's current data."""
        await super().async_added_to_hass()
        self._handle_coordinator_update()

    def _handle_coordinator_update(self) -> None:
        """Update the book's read status from coordinator data."""

        book = self.coordinator.data["books"].get(self._book_id)
        self._attr_available = book is not None

        if book is not None:
            self._attr_native_value = book.get("readStatus")

            name = _get_book_device_name(book, self._book_id)
            self._attr_device_info = ChildDeviceInfo(
                identifiers={(DOMAIN, f"{self._entry_id}_book_{self._book_id}")},
                name=name,
                parent_device_id=self._parent_device_id,
            )
            device = self.device_entry
            if device is not None and device.name != name:
                dr.async_get(self.hass).async_update_child_device(
                    device.id,
                    name=name,
                )

        super()._handle_coordinator_update()


class GrimmoryBookProgressSensor(CoordinatorEntity[GrimmoryCoordinator], SensorEntity):
    """Sensor for the Koreader progress of a Grimmory book."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:file-percent-outline"
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self,
        coordinator: GrimmoryCoordinator,
        book: dict[str, Any],
        parent_device_id: str,
        progress_source: str | None,
        entry_id: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._book_id = book["book_id"]
        self._parent_device_id = parent_device_id
        self._progress_source = progress_source
        self._entry_id = entry_id
        self._attr_name = "Read progress"
        self._attr_unique_id = f"{self._entry_id}_book_{self._book_id}_read_progress"
        self._attr_device_info = ChildDeviceInfo(
            identifiers={(DOMAIN, f"{self._entry_id}_book_{self._book_id}")},
            name=_get_book_device_name(book, self._book_id),
            parent_device_id=parent_device_id,
        )

    async def async_added_to_hass(self) -> None:
        """Register the listener and apply the coordinator's current data."""
        await super().async_added_to_hass()
        self._handle_coordinator_update()

    def _handle_coordinator_update(self) -> None:
        """Fetch the book's koreader pogress."""
        book = self.coordinator.data["books"].get(self._book_id)
        self._attr_available = book is not None

        if book is not None:
            name = _get_book_device_name(book, self._book_id)
            self._attr_device_info = ChildDeviceInfo(
                identifiers={(DOMAIN, f"{self._entry_id}_book_{self._book_id}")},
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

        super()._handle_coordinator_update()


class GrimmoryBookLastReadSensor(CoordinatorEntity[GrimmoryCoordinator], SensorEntity):
    """Sensor for when a Grimmory book was last read."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:book-clock-outline"

    def __init__(
        self,
        coordinator: GrimmoryCoordinator,
        book: dict[str, Any],
        parent_device_id: str,
        entry_id: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._book_id = book["book_id"]
        self._parent_device_id = parent_device_id
        self._entry_id = entry_id
        self._attr_name = "Last read"
        self._attr_unique_id = f"{self._entry_id}_book_{self._book_id}_last_read"
        self._attr_device_class = SensorDeviceClass.TIMESTAMP
        self._attr_device_info = ChildDeviceInfo(
            identifiers={(DOMAIN, f"{self._entry_id}_book_{self._book_id}")},
            name=_get_book_device_name(book, self._book_id),
            parent_device_id=parent_device_id,
        )

    async def async_added_to_hass(self) -> None:
        """Register the listener and apply the coordinator's current data."""
        await super().async_added_to_hass()
        self._handle_coordinator_update()

    def _handle_coordinator_update(self) -> None:
        """Fetch the book's last read time."""
        book = self.coordinator.data["books"].get(self._book_id)
        self._attr_available = book is not None

        if book is not None:
            name = _get_book_device_name(book, self._book_id)
            self._attr_device_info = ChildDeviceInfo(
                identifiers={(DOMAIN, f"{self._entry_id}_book_{self._book_id}")},
                name=name,
                parent_device_id=self._parent_device_id,
            )
            device = self.device_entry

            if device is not None and device.name != name:
                dr.async_get(self.hass).async_update_child_device(
                    device.id,
                    name=name,
                )

            # Datetime format "lastReadTime": "2026-11-04T21:59:05Z"
            last_read = book.get("lastReadTime")
            self._attr_native_value = (
                dt_util.parse_datetime(last_read) if last_read else None
            )

        super()._handle_coordinator_update()
