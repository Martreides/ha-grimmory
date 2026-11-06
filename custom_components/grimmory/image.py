# Copyright (C) 2026 Michiel Cornelissen
# This file is part of ha-grimmory
# SPDX-License-Identifier: GPL-3.0-only
"""Image platform for Grimmory."""

import asyncio
from datetime import timedelta
from typing import Any

import aiohttp
from homeassistant.components.image import ImageEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import ChildDeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from . import GrimmoryConfigEntry
from .api import GrimmoryApiClient
from .const import CONF_BOOKS, DOMAIN
from .helpers import _get_book_device_name

_IMAGE_CACHE_TTL = timedelta(minutes=15)


async def async_setup_entry(
    hass: HomeAssistant | None,
    entry: GrimmoryConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Grimmory image platform."""

    api_client = entry.runtime_data.api_client

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
                GrimmoryImageEntity(
                    hass, api_client, book, parent_device.id, entry.entry_id
                ),
            ],
            update_before_add=True,
        )


class GrimmoryImageEntity(ImageEntity):
    """Image entity for Grimmory."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:image"

    def __init__(
        self,
        hass: HomeAssistant,
        api_client: GrimmoryApiClient,
        book: dict[str, Any],
        parent_device_id: str,
        entry_id: str,
    ) -> None:
        """Initialize the image entity."""
        super().__init__(hass)
        self._api_client = api_client
        self._image_bytes: bytes | None = None
        self._image_fetched_at: float | None = None
        self._book_id = book["book_id"]
        self._parent_device_id = parent_device_id
        self._entry_id = entry_id
        self._attr_name = "Book cover"
        self._attr_unique_id = f"{self._entry_id}_book_{self._book_id}_cover"
        self._attr_device_info = ChildDeviceInfo(
            identifiers={(DOMAIN, f"{self._entry_id}_book_{self._book_id}")},
            name=_get_book_device_name(book, self._book_id),
            parent_device_id=parent_device_id,
        )

    async def async_image(self) -> bytes | None:
        """Fetch the book cover as image."""
        now = asyncio.get_running_loop().time()
        if (
            self._image_bytes is not None
            and self._image_fetched_at is not None
            and now - self._image_fetched_at < _IMAGE_CACHE_TTL.total_seconds()
        ):
            return self._image_bytes

        try:
            image = await self._api_client.get_book_cover(self._book_id)
        except (aiohttp.ClientError, TimeoutError, ConfigEntryAuthFailed):
            if self._image_bytes is not None:
                return self._image_bytes
            self._attr_available = False
            self.async_write_ha_state()
            return None

        self._image_bytes = image
        self._image_fetched_at = asyncio.get_running_loop().time()
        self._attr_available = True
        self._attr_image_last_updated = dt_util.utcnow()
        self.async_write_ha_state()
        return image
