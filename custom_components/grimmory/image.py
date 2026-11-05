# Copyright (C) 2026 Michiel Cornelissen
# This file is part of ha-grimmory
# SPDX-License-Identifier: GPL-3.0-only
"""Image platform for Grimmory."""

from typing import Any

import aiohttp
from homeassistant.components.image import ImageEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import GrimmoryConfigEntry
from .api import GrimmoryApiClient
from .const import CONF_BOOKS, DOMAIN


async def async_setup_entry(
    hass: HomeAssistant | None,
    entry: GrimmoryConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Grimmory image platform."""

    client = entry.runtime_data.client

    device_registry = dr.async_get(hass)
    parent_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, entry.entry_id),
        entry.entry_id,
    )

    if parent_device is None:
        raise RuntimeError("Grimmory parent device not found")

    for book in entry.options.get(CONF_BOOKS, []):
        async_add_entities(
            [
                GrimmoryImageEntity(client, book, parent_device.id, entry.entry_id),
            ],
            update_before_add=True,
        )


class GrimmoryImageEntity(ImageEntity):
    """Image entity for Grimmory."""

    _attr_has_entity_name = True
    _attr_name = "Book cover"
    _attr_icon = "mdi:image"

    def __init__(
        self,
        client: GrimmoryApiClient,
        book: dict[str, Any],
        parent_device_id: str,
        entry_id: str,
    ) -> None:
        """Initialize the image entity."""
        self._client = client
        self._book_id = book["book_id"]
        self._parent_device_id = parent_device_id
        self._entry_id = entry_id
        self._attr_unique_id = f"{entry_id}_image"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry_id)},
            "name": "Grimmory",
            "manufacturer": "Grimmory",
        }

    async def async_image(self) -> None:
        """Fetch the latest image information."""
        try:
            image_info = await self._client.get_book_cover(self._book_id)
            self._attr_image_url = image_info["url"]
        except (aiohttp.ClientError, TimeoutError, ConfigEntryAuthFailed):
            self._attr_available = False
            return
        self._attr_available = True
