# Copyright (C) 2026 Michiel Cornelissen
# This file is part of ha-grimmory
# SPDX-License-Identifier: GPL-3.0-only
"""Grimmory API client."""

import asyncio
import logging
from typing import Any

import aiohttp
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_TOKEN, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed

from .const import CONF_REFRESH_TOKEN

_LOGGER = logging.getLogger(__name__)
_TOKEN_REFRESH_COOLDOWN = 60 * 15


class GrimmoryRateLimitedError(aiohttp.ClientError):
    """Raised when Grimmory rate limits token refreshes."""


class GrimmoryApiClient:
    """Grimmory API client."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        hass: HomeAssistant | None = None,
        entry: ConfigEntry | None = None,
        host: str | None = None,
        token: str | None = None,
    ) -> None:
        """Initialize the Grimmory API client."""
        self.hass = hass
        self.entry = entry
        self.session = session

        if entry is not None:
            self.host = entry.data[CONF_HOST]
            self.token = entry.data[CONF_TOKEN]
            self.refresh_token = entry.data[CONF_REFRESH_TOKEN]
        else:
            self.host = host
            self.token = token
            self.refresh_token = None

        self._refresh_lock = asyncio.Lock()
        self._refresh_failed = False
        self._refresh_retry_after = 0.0

    @staticmethod
    async def login(
        session: aiohttp.ClientSession, data: dict[str, Any]
    ) -> dict[str, Any]:
        """Login to the Grimmory API."""
        _LOGGER.debug("Logging in to Grimmory API at %s", data[CONF_HOST])

        async with session.post(
            f"{data[CONF_HOST]}/api/v1/auth/login",
            json={
                "username": data[CONF_USERNAME],
                "password": data[CONF_PASSWORD],
            },
        ) as response:
            response_json = await response.json()

        _LOGGER.debug("Login response status: %s", response.status)

        response.raise_for_status()

        return response_json

    def _start_reauth(self) -> None:
        """Start reauthentication once the API rejects the refreshed token."""
        if self._refresh_failed:
            return

        self._refresh_failed = True
        if self.entry is not None and self.hass is not None:
            self.entry.async_start_reauth(self.hass)

    async def _refresh_token(self, token_used: str | None) -> bool:
        """Refresh the access token."""

        if self.refresh_token is None:
            raise ConfigEntryAuthFailed("Grimmory refresh token is unavailable")

        async with self._refresh_lock:
            if self._refresh_failed:
                raise ConfigEntryAuthFailed("Grimmory authentication failed")

            if token_used != self.token:
                _LOGGER.debug("Access token already refreshed, stopping refresh")
                return True
            if asyncio.get_running_loop().time() < self._refresh_retry_after:
                _LOGGER.debug(
                    "Token refresh for Grimmory API at %s is rate limited; retrying later",
                    self.host,
                )
                raise GrimmoryRateLimitedError("Grimmory refresh is rate limited")

            _LOGGER.debug("Refreshing access token for Grimmory API at %s", self.host)
            async with self.session.post(
                f"{self.host}/api/v1/auth/refresh",
                json={"refreshToken": self.refresh_token},
            ) as response:
                if response.status == 429:
                    self._refresh_retry_after = (
                        asyncio.get_running_loop().time() + _TOKEN_REFRESH_COOLDOWN
                    )
                    _LOGGER.warning(
                        "Grimmory API at %s rate limited token refresh; retrying in %s minutes",
                        self.host,
                        _TOKEN_REFRESH_COOLDOWN // 60,
                    )
                    raise GrimmoryRateLimitedError("Grimmory refresh is rate limited")

                if response.status == 401:
                    self._start_reauth()
                    raise ConfigEntryAuthFailed("Grimmory refresh token is invalid")

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

    async def _get(
        self,
        url: str,
        params: dict | None,
        headers: dict[str, str],
        retry: bool = True,
        as_bytes: bool = False,
    ):
        """Make a GET request to the Grimmory API."""

        token_used = self.token

        async with self.session.get(url, params=params, headers=headers) as response:
            if response.status == 401 and retry:
                _LOGGER.debug("Unauthorized request to Grimmory API at %s", self.host)
                await self._refresh_token(token_used)
                return await self._get(
                    url,
                    params,
                    {
                        "Authorization": f"Bearer {self.token}",
                    },
                    retry=False,
                    as_bytes=as_bytes,
                )
            if response.status == 401:
                self._start_reauth()
                raise ConfigEntryAuthFailed("Grimmory access token is invalid")

            response.raise_for_status()
            if as_bytes:
                return await response.read()
            return await response.json()

    async def _put(
        self, url: str, params: dict | None, headers: dict[str, str], retry: bool = True
    ):
        """Make a PUT request to the Grimmory API."""

        token_used = self.token

        async with self.session.put(url, params=params, headers=headers) as response:
            if response.status == 401 and retry:
                _LOGGER.debug("Unauthorized request to Grimmory API at %s", self.host)
                await self._refresh_token(token_used)
                return await self._put(
                    url,
                    params,
                    {
                        "Authorization": f"Bearer {self.token}",
                    },
                    retry=False,
                )
            if response.status == 401:
                self._start_reauth()
                raise ConfigEntryAuthFailed("Grimmory access token is invalid")

            response.raise_for_status()

    async def _post(
        self, url: str, params: dict | None, headers: dict[str, str], retry: bool = True
    ):
        """Make a POST request to the Grimmory API."""

        token_used = self.token

        async with self.session.post(url, params=params, headers=headers) as response:
            if response.status == 401 and retry:
                _LOGGER.debug("Unauthorized request to Grimmory API at %s", self.host)
                await self._refresh_token(token_used)
                return await self._post(
                    url,
                    params,
                    {
                        "Authorization": f"Bearer {self.token}",
                    },
                    retry=False,
                )
            if response.status == 401:
                self._start_reauth()
                raise ConfigEntryAuthFailed("Grimmory access token is invalid")

            response.raise_for_status()

    async def get_book_count(self, library_id: int | None) -> int:
        """Get the number of books in Grimmory."""

        if self.host is None or self.token is None:
            raise RuntimeError("Client is not available")

        params = {"page": 0, "size": 1}
        if library_id is not None:
            params["libraryId"] = library_id

        books = await self._get(
            f"{self.host}/api/v1/app/books",
            params=params,
            headers={
                "Authorization": f"Bearer {self.token}",
            },
        )

        book_count = books["totalElements"]
        _LOGGER.debug("Retrieved %d books from Grimmory API", book_count)
        return book_count

    async def get_grimmory_version(self) -> dict[str, Any]:
        """Get the Grimmory version."""

        if self.host is None or self.token is None:
            raise RuntimeError("Client is not available")

        version_info = await self._get(
            f"{self.host}/api/v1/version",
            params=None,
            headers={
                "Authorization": f"Bearer {self.token}",
            },
        )

        _LOGGER.debug("Retrieved Grimmory version: %s", version_info)

        return version_info

    async def get_kobo_sync_status(self) -> bool:
        """Get the Kobo sync status."""

        if self.host is None or self.token is None:
            raise RuntimeError("Client is not available")

        kobo_settings = await self._get(
            f"{self.host}/api/v1/kobo-settings",
            params=None,
            headers={
                "Authorization": f"Bearer {self.token}",
            },
        )

        _LOGGER.debug("Retrieved Kobo settings: %s", kobo_settings["syncEnabled"])

        return kobo_settings["syncEnabled"]

    async def get_last_read_book(self, library_id: int | None) -> dict[str, Any] | None:
        """Get the last read book."""

        if self.host is None or self.token is None:
            raise RuntimeError("Client is not available")

        params = {
            "page": 1,
            "size": 1,
            "sort": "lastReadTime",
            "dir": "desc",
        }

        if library_id is not None:
            params["libraryId"] = library_id

        last_read = await self._get(
            f"{self.host}/api/v1/app/books",
            params=params,
            headers={
                "Authorization": f"Bearer {self.token}",
            },
        )

        books = last_read.get("content", [])

        return books[0] if books else None

    async def get_libraries(self) -> list[dict[str, Any]]:
        """Get the available libraries in Grimmory."""

        if self.host is None or self.token is None:
            raise RuntimeError("Client is not available")

        libraries = await self._get(
            f"{self.host}/api/v1/libraries",
            params={},
            headers={
                "Authorization": f"Bearer {self.token}",
            },
        )

        _LOGGER.debug("Retrieved %s libraries from Grimmory API", len(libraries))

        return libraries

    async def refresh_libraries(self, library_id: int | None) -> None:
        """Request a refresh of the selected library or all libraries."""

        if self.host is None or self.token is None:
            raise RuntimeError("Client is not available")

        if library_id is None:
            libraries = await self.get_libraries()
        else:
            libraries = [{"id": library_id}]

        for library in libraries:
            await self._put(
                url=f"{self.host}/api/v1/libraries/{library['id']}/refresh",
                params={},
                headers={
                    "Authorization": f"Bearer {self.token}",
                },
            )

    async def rescan_bookdrop_folder(self) -> None:
        """Request a rescan of the Grimmory bookdrop folder."""

        if self.host is None or self.token is None:
            raise RuntimeError("Client is not available")

        await self._post(
            url=f"{self.host}/api/v1/bookdrop/rescan",
            params={},
            headers={"Authorization": f"Bearer {self.token}"},
        )

    async def get_book(self, book_id: int) -> dict[str, Any]:
        """Get a book by ID."""

        if self.host is None or self.token is None:
            raise RuntimeError("Client is not available")

        return await self._get(
            f"{self.host}/api/v1/books/{book_id}",
            params={
                "withDescription": "false",
            },
            headers={"Authorization": f"Bearer {self.token}"},
        )

    async def get_bookdrop_files_by_status(
        self,
        status: str,
        page: int | None = None,
        size: int | None = None,
    ) -> dict[str, Any]:
        """Get bookdrop files filtered by status, optionally paginated."""

        if self.host is None or self.token is None:
            raise RuntimeError("Client is not available")

        params: dict[str, str | int] = {"status": status}
        if page is not None:
            params["page"] = page
        if size is not None:
            params["size"] = size

        return await self._get(
            f"{self.host}/api/v1/bookdrop/files",
            params=params,
            headers={"Authorization": f"Bearer {self.token}"},
        )

    async def get_reading_book_distributions(self):
        """Get reading status distribution"""

        if self.host is None or self.token is None:
            raise RuntimeError("Client is not available")

        return await self._get(
            f"{self.host}/api/v1/user-stats/reading/book-distributions",
            params=None,
            headers={"Authorization": f"Bearer {self.token}"},
        )

    async def get_book_cover(self, book_id: int) -> bytes:
        """Get the book cover image for a book by ID."""

        if self.host is None or self.token is None:
            raise RuntimeError("Client is not available")

        return await self._get(
            f"{self.host}/api/v1/media/book/{book_id}/cover",
            params=None,
            headers={"Authorization": f"Bearer {self.token}"},
            as_bytes=True,
        )
