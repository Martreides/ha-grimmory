# Copyright (C) 2026 Michiel Cornelissen
# This file is part of ha-grimmory
# SPDX-License-Identifier: GPL-3.0-only
"""Grimmory data update coordinator"""

import logging
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .api import GrimmoryApiClient
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class GrimmoryCoordinator(DataUpdateCoordinator[dict[int, dict[str, Any]]]):
    """Fetch data for selected Grimmory books."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        client: GrimmoryApiClient,
    ) -> None:
        """Initialize the coordinator."""
        self.client = client
        self.book_ids = [book["book_id"] for book in entry.options.get("books", [])]

        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(minutes=5),
        )

    async def _async_update_data(self) -> dict[int, dict[str, Any]]:
        """Fetch data for all selected books."""
        books = {}

        for book_id in self.book_ids:
            books[book_id] = await self.client.get_book(book_id)

        return books
