# Copyright (C) 2026 Michiel Cornelissen
# This file is part of ha-grimmory
# SPDX-License-Identifier: GPL-3.0-only
"""Button platform for Grimmory."""

import logging

import aiohttp
from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import GrimmoryConfigEntry
from .api import GrimmoryApiClient
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: GrimmoryConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Grimmory button platform."""

    client = entry.runtime_data

    buttons = [
        GrimmoryRefreshButton(client),
        GrimmoryBookdropRescanButton(client),
    ]

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
        try:
            await self._client.refresh_libraries()
        except (aiohttp.ClientError, TimeoutError, ConfigEntryAuthFailed):
            _LOGGER.warning("Unable to refresh Grimmory libraries")
            raise HomeAssistantError("Unable to refresh Grimmory libraries") from None


class GrimmoryBookdropRescanButton(ButtonEntity):
    """Button to rescan the Grimmory bookdrop folder."""

    _attr_has_entity_name = True
    _attr_name = "Rescan bookdrop folder"
    _attr_icon = "mdi:folder-sync-outline"
    _attr_device_info = DeviceInfo(
        identifiers={(DOMAIN, "grimmory")},
        name="Grimmory",
        manufacturer="Grimmory",
    )

    def __init__(self, client: GrimmoryApiClient) -> None:
        """Initialize the button."""
        self._client = client
        self._attr_unique_id = f"{client.entry.entry_id}_bookdrop_rescan"

    async def async_press(self) -> None:
        """Request a rescan of the Grimmory bookdrop folder."""
        try:
            await self._client.rescan_bookdrop_folder()
        except (aiohttp.ClientError, TimeoutError, ConfigEntryAuthFailed):
            _LOGGER.warning("Unable to rescan the Grimmory bookdrop folder")
            raise HomeAssistantError(
                "Unable to rescan the Grimmory bookdrop folder"
            ) from None
