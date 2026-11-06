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
from .const import CONF_LIBRARY_ID, DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: GrimmoryConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Grimmory button platform."""

    api_client = entry.runtime_data.api_client

    buttons = [
        GrimmoryRefreshButton(
            api_client, entry.entry_id, entry.data.get(CONF_LIBRARY_ID)
        ),
        GrimmoryBookdropRescanButton(api_client, entry.entry_id),
    ]

    async_add_entities(buttons)


class GrimmoryRefreshButton(ButtonEntity):
    """Button to refresh Grimmory libraries."""

    _attr_has_entity_name = True
    _attr_name = "Refresh libraries"
    _attr_icon = "mdi:archive-refresh-outline"

    def __init__(
        self,
        api_client: GrimmoryApiClient,
        entry_id: str,
        library_id: int | None,
    ) -> None:
        """Initialize the button."""
        self._api_client = api_client
        self._library_id = library_id
        self._attr_unique_id = f"{entry_id}_refresh_libraries"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
            name="Grimmory",
            manufacturer="Grimmory",
        )

    async def async_press(self) -> None:
        """Refresh the configured Grimmory library or libraries."""
        try:
            await self._api_client.refresh_libraries(self._library_id)
        except (aiohttp.ClientError, TimeoutError, ConfigEntryAuthFailed):
            _LOGGER.warning("Unable to refresh Grimmory libraries")
            raise HomeAssistantError("Unable to refresh Grimmory libraries") from None


class GrimmoryBookdropRescanButton(ButtonEntity):
    """Button to rescan the Grimmory bookdrop folder."""

    _attr_has_entity_name = True
    _attr_name = "Rescan bookdrop folder"
    _attr_icon = "mdi:folder-sync-outline"

    def __init__(self, api_client: GrimmoryApiClient, entry_id: str) -> None:
        """Initialize the button."""
        self._api_client = api_client
        self._attr_unique_id = f"{entry_id}_bookdrop_rescan"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
            name="Grimmory",
            manufacturer="Grimmory",
        )

    async def async_press(self) -> None:
        """Request a rescan of the Grimmory bookdrop folder."""
        try:
            await self._api_client.rescan_bookdrop_folder()
        except (aiohttp.ClientError, TimeoutError, ConfigEntryAuthFailed):
            _LOGGER.warning("Unable to rescan the Grimmory bookdrop folder")
            raise HomeAssistantError(
                "Unable to rescan the Grimmory bookdrop folder"
            ) from None
