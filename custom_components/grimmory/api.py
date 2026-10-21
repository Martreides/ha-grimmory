"""Minimal Grimmory API client."""

import asyncio
import logging
from typing import Any

import aiohttp

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_TOKEN, CONF_USERNAME
from homeassistant.core import HomeAssistant

from .const import CONF_REFRESH_TOKEN

_LOGGER = logging.getLogger(__name__)


class GrimmoryApiClient:
    """Minimal Grimmory API client."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the Grimmory API client."""
        self.hass = hass
        self.entry = entry
        self.host = entry.data[CONF_HOST]
        self.token = entry.data[CONF_TOKEN]
        self.refresh_token = entry.data[CONF_REFRESH_TOKEN]
        self._refresh_lock = asyncio.Lock()

    @staticmethod
    async def login(data: dict[str, Any]) -> dict[str, Any]:
        """Login to the Grimmory API."""
        _LOGGER.debug(
            "Logging in to Grimmory API at %s as %s",
            data[CONF_HOST],
            data[CONF_USERNAME],
        )

        async with (
            aiohttp.ClientSession() as session,
            session.post(
                f"{data[CONF_HOST]}/api/v1/auth/login",
                json={
                    "username": data[CONF_USERNAME],
                    "password": data[CONF_PASSWORD],
                },
            ) as response,
        ):
            response_json = await response.json()

        _LOGGER.debug("Login response status: %s", response.status)

        # This only passes if there are no exceptions so it is safe to assume the login was successful after this line.
        response.raise_for_status()

        _LOGGER.debug("Login successful!")

        return response_json

    async def _refresh_token(self, token_used: str | None) -> bool:
        """Refresh the access token."""

        _LOGGER.debug("Refreshing access token for Grimmory API at %s", self.host)
        async with self._refresh_lock:
            if token_used != self.token:
                _LOGGER.debug("Access token already refreshed, stopping refresh")
                return True

            async with (
                aiohttp.ClientSession() as session,
                session.post(
                    f"{self.host}/api/v1/auth/refresh",
                    json={"refreshToken": self.refresh_token},
                ) as response,
            ):
                if response.status != 200:
                    error_text = await response.text()
                    _LOGGER.error(
                        "Grimmory token refresh failed: HTTP %s — %s",
                        response.status,
                        error_text,
                    )
                    response.raise_for_status()

                data = await response.json()

            self.hass.config_entries.async_update_entry(
                self.entry,
                data={
                    **self.entry.data,
                    CONF_TOKEN: data["accessToken"],
                    CONF_REFRESH_TOKEN: data["refreshToken"],
                },
            )

            self.token = data["accessToken"]
            self.refresh_token = data["refreshToken"]

        _LOGGER.debug("Successfully refreshed Grimmory access token")
        return True

    async def _request(self, url, params, headers, retry=True):
        """Make a request to the Grimmory API."""

        token_used = self.token

        async with (
            aiohttp.ClientSession() as session,
            session.get(url, params=params, headers=headers) as response,
        ):
            if response.status == 401 and retry:
                _LOGGER.debug("Unauthorized request to Grimmory API at %s", self.host)
                await self._refresh_token(token_used)
                return await self._request(
                    url,
                    params,
                    {
                        "Authorization": f"Bearer {self.token}",
                    },
                    retry=False,
                )

            response.raise_for_status()
            return await response.json()

    async def get_book_count(self):
        """Get the number of books in Grimmory."""

        _LOGGER.debug("Getting book count from Grimmory API at %s", self.host)

        if self.host is None or self.token is None:
            raise RuntimeError("Client is not available")

        books = await self._request(
            f"{self.host}/api/v1/books",
            params={
                "withDescription": "false",
                "stripForListView": "true",
            },
            headers={
                "Authorization": f"Bearer {self.token}",
            },
        )

        _LOGGER.debug("Retrieved %d books from Grimmory API", len(books))

        return len(books)

    async def get_grimmory_version(self):
        """Get the Grimmory version."""

        _LOGGER.debug("Getting Grimmory version from API at %s", self.host)

        if self.host is None or self.token is None:
            raise RuntimeError("Client is not available")

        version_info = await self._request(
            f"{self.host}/api/v1/version",
            params=None,
            headers={
                "Authorization": f"Bearer {self.token}",
            },
        )

        _LOGGER.debug("Retrieved Grimmory version: %s", version_info)

        return version_info

    async def get_kobo_sync_status(self):
        """Get the Kobo sync status."""

        _LOGGER.debug("Getting Kobo Sync status from API at %s", self.host)

        if self.host is None or self.token is None:
            raise RuntimeError("Client is not available")

        kobo_settings = await self._request(
            f"{self.host}/api/v1/kobo-settings",
            params=None,
            headers={
                "Authorization": f"Bearer {self.token}",
            },
        )

        _LOGGER.debug("Retrieved Kobo settings: %s", kobo_settings)

        return kobo_settings["syncEnabled"]

    async def get_last_read_book(self):
        """Get the last read book."""

        _LOGGER.debug("Getting last read book from API at %s", self.host)

        if self.host is None or self.token is None:
            raise RuntimeError("Client is not available")

        last_read = await self._request(
            f"{self.host}/api/v1/app/books",
            params={
                "page": 1,
                "size": 1,
                "sort": "lastReadTime",
                "dir": "desc",
            },
            headers={
                "Authorization": f"Bearer {self.token}",
            },
        )

        _LOGGER.debug("Retrieved last read book: %s", last_read)

        books = last_read.get("content", [])
        return books[0] if books else None
