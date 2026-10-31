# Copyright (C) 2026 Michiel Cornelissen
# This file is part of ha-grimmory
# SPDX-License-Identifier: GPL-3.0-only
"""The grimmory integration."""

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .api import GrimmoryApiClient
from .const import CONF_BOOKS, DOMAIN

_PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.UPDATE,
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
]

type GrimmoryConfigEntry = ConfigEntry[GrimmoryApiClient]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: GrimmoryConfigEntry) -> bool:
    """Set up grimmory from a config entry."""

    client = GrimmoryApiClient(hass, entry)

    entry.runtime_data = client
    _LOGGER.debug("Grimmory API client initialized")

    device_registry = dr.async_get(hass)

    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, "grimmory")},
        name="Grimmory",
        manufacturer="Grimmory",
    )

    await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)

    return True


async def async_migrate_entry(
    hass: HomeAssistant,
    entry: GrimmoryConfigEntry,
) -> bool:
    """Migrate Grimmory config entry."""

    if entry.version == 1:
        _LOGGER.info("Migrating Grimmory config entry to version 2")

        books = list(entry.options.get(CONF_BOOKS, []))
        book_ids = {book["book_id"] for book in books}  # Create a set
        subentries = entry.get_subentries_of_type("book")

        for subentry in subentries:
            book_id = subentry.data["book_id"]
            if book_id not in book_ids:
                books.append({"book_id": book_id})
                book_ids.add(book_id)

        # Save the new book configuration before removing subentries.
        hass.config_entries.async_update_entry(
            entry,
            options={
                **entry.options,
                CONF_BOOKS: books,
            },
        )

        # Remove the old book subentries.
        for subentry in subentries:
            hass.config_entries.async_remove_subentry(
                entry,
                subentry.subentry_id,
            )

        # Mark migration as complete.
        hass.config_entries.async_update_entry(entry, version=2)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: GrimmoryConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, _PLATFORMS)
