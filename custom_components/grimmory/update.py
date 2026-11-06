# Copyright (C) 2026 Michiel Cornelissen
# This file is part of ha-grimmory
# SPDX-License-Identifier: GPL-3.0-only
"""Update platform for Grimmory."""

import aiohttp

from homeassistant.components.update import UpdateEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
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
    """Set up the Grimmory sensor platform."""

    api_client = entry.runtime_data.api_client

    async_add_entities(
        [
            GrimmoryUpdateEntity(api_client, entry.entry_id),
        ],
        update_before_add=True,
    )


class GrimmoryUpdateEntity(UpdateEntity):
    """Update entity for Grimmory."""

    _attr_has_entity_name = True
    _attr_name = "Grimmory"
    _attr_icon = "mdi:package-up"

    def __init__(self, api_client: GrimmoryApiClient, entry_id: str) -> None:
        """Initialize the update entity."""
        self._api_client = api_client
        self._attr_unique_id = f"{entry_id}_version"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
            name="Grimmory",
            manufacturer="Grimmory",
        )

    async def async_update(self) -> None:
        """Fetch the latest version information."""
        try:
            version_info = await self._api_client.get_grimmory_version()
        except (aiohttp.ClientError, TimeoutError, ConfigEntryAuthFailed):
            self._attr_available = False
            return

        self._attr_available = True
        self._attr_installed_version = version_info["current"]
        self._attr_latest_version = version_info["latest"]
