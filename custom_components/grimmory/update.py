# Copyright (C) 2026 Michiel Cornelissen
# This file is part of ha-grimmory
# SPDX-License-Identifier: GPL-3.0-only
"""Update platform for Grimmory."""

import logging

from homeassistant.components.update import UpdateEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import GrimmoryConfigEntry
from .api import GrimmoryApiClient, GrimmoryRateLimitedError
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: GrimmoryConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Grimmory sensor platform."""

    client = entry.runtime_data.client

    _LOGGER.debug("Setting up Grimmory update entity")

    async_add_entities(
        [
            GrimmoryUpdateEntity(client),
        ],
        update_before_add=True,
    )


class GrimmoryUpdateEntity(UpdateEntity):
    """Update entity for Grimmory."""

    _attr_has_entity_name = True
    _attr_name = "Grimmory"
    _attr_icon = "mdi:package-up"
    _attr_device_info = DeviceInfo(
        identifiers={(DOMAIN, "grimmory")},
        name="Grimmory",
        manufacturer="Grimmory",
    )

    def __init__(self, client: GrimmoryApiClient) -> None:
        """Initialize the update entity."""
        self._client = client
        self._attr_unique_id = f"{client.entry.entry_id}_version"

    async def async_update(self) -> None:
        """Fetch the latest version information."""
        try:
            version_info = await self._client.get_grimmory_version()
        except (GrimmoryRateLimitedError, ConfigEntryAuthFailed):
            self._attr_available = False
            return

        self._attr_available = True
        self._attr_installed_version = version_info["current"]
        self._attr_latest_version = version_info["latest"]
