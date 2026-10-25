# Copyright (C) 2026 Michiel Cornelissen
# This file is part of ha-grimmory
# SPDX-License-Identifier: GPL-3.0-only
"""Button platform for Grimmory."""

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import GrimmoryConfigEntry
from .api import GrimmoryApiClient
from .const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    entry: GrimmoryConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Grimmory button platform."""

    client = entry.runtime_data

    buttons = [GrimmoryRefreshButton(client)]

    async_add_entities(buttons)


class GrimmoryRefreshButton(ButtonEntity):
    """Button to refresh Grimmory libraries."""

    _attr_has_entity_name = True
    _attr_name = "Refresh libraries"
    _attr_icon = "mdi:archive-refresh-outline"
    _attr_device_info = DeviceInfo(
        identifiers={(DOMAIN, "grimmory")},
        name="Grimmory",
        manufacturer="Grimmory",
    )

    def __init__(self, client: GrimmoryApiClient) -> None:
        """Initialize the button."""
        self._client = client
        self._attr_unique_id = f"{client.entry.entry_id}_refresh_libraries"

    async def async_press(self) -> None:
        """Refresh the configured Grimmory library or libraries."""
        await self._client.refresh_libraries()
