# Copyright (C) 2026 Michiel Cornelissen
# This file is part of ha-grimmory
# SPDX-License-Identifier: GPL-3.0-only
"""Binary sensor platform for Grimmory."""

from datetime import timedelta

import aiohttp

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import GrimmoryConfigEntry
from .api import GrimmoryApiClient
from .const import DOMAIN

SCAN_INTERVAL = timedelta(minutes=5)


async def async_setup_entry(
    hass: HomeAssistant | None,
    entry: GrimmoryConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Grimmory binary sensor platform."""

    client = entry.runtime_data.client

    sensors = [
        GrimmoryKoboSyncEnabledSensor(client, entry.entry_id),
    ]
    async_add_entities(sensors, update_before_add=True)


class GrimmoryKoboSyncEnabledSensor(BinarySensorEntity):
    """A sensor for the Kobo sync status in Grimmory."""

    _attr_has_entity_name = True
    _attr_name = "Kobo Sync Enabled"
    _attr_icon = "mdi:book-sync-outline"

    def __init__(self, client: GrimmoryApiClient, entry_id: str) -> None:
        """Initialize the sensor."""
        self._client = client
        self._attr_unique_id = f"{entry_id}_kobo_sync_enabled"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
            name="Grimmory",
            manufacturer="Grimmory",
        )

    async def async_update(self) -> None:
        """Fetch Kobo sync status."""
        try:
            self._attr_is_on = await self._client.get_kobo_sync_status()
        except (aiohttp.ClientError, TimeoutError, ConfigEntryAuthFailed):
            self._attr_available = False
            return
        self._attr_available = True
