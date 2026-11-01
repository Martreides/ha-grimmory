# Copyright (C) 2026 Michiel Cornelissen
# This file is part of ha-grimmory
# SPDX-License-Identifier: GPL-3.0-only

"""Config flow for the grimmory integration."""

import logging
from collections.abc import Mapping
from typing import Any, override

import aiohttp
import probatio
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlowWithReload,
)
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_TOKEN, CONF_USERNAME
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.selector import (
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .api import GrimmoryApiClient
from .const import (
    CONF_BOOKS,
    CONF_LIBRARY_ID,
    CONF_PROGRESS_SOURCE,
    CONF_REFRESH_TOKEN,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


STEP_USER_DATA_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_HOST): str,
        probatio.Required(CONF_USERNAME): str,
        probatio.Required(CONF_PASSWORD): str,
    }
)


async def validate_input(data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """

    try:
        response_json = await GrimmoryApiClient.login(data)
    except aiohttp.ClientResponseError as err:
        if err.status in (401, 403):
            _LOGGER.warning("Invalid credentials for Grimmory at %s", data[CONF_HOST])
            raise InvalidAuth from None
        _LOGGER.warning("Unable to connect to Grimmory at %s", data[CONF_HOST])
        raise CannotConnect from None
    except aiohttp.ClientError, TimeoutError:
        _LOGGER.warning("Unable to connect to Grimmory at %s", data[CONF_HOST])
        raise CannotConnect from None

    # Return info that you want to store in the config entry.
    return {
        CONF_HOST: data[CONF_HOST],
        CONF_USERNAME: data[CONF_USERNAME],
        CONF_TOKEN: response_json["accessToken"],
        CONF_REFRESH_TOKEN: response_json["refreshToken"],
    }


async def _get_additional_settings_schema(
    client: GrimmoryApiClient,
    current_library_id: int | None = None,
    current_progress_source: str | None = None,
) -> probatio.Schema:
    """Build the library and progress source selection schema."""

    libraries = await client.get_libraries()
    current_library = "all" if current_library_id is None else str(current_library_id)

    return probatio.Schema(
        {
            probatio.Required(CONF_LIBRARY_ID, default=current_library): SelectSelector(
                SelectSelectorConfig(
                    options=[
                        {"value": "all", "label": "All libraries"},
                        *[
                            {"value": str(library["id"]), "label": library["name"]}
                            for library in libraries
                        ],
                    ],
                    mode=SelectSelectorMode.DROPDOWN,
                )
            ),
            probatio.Required(
                CONF_PROGRESS_SOURCE,
                default=current_progress_source,
            ): SelectSelector(
                SelectSelectorConfig(
                    options=[
                        {"value": "grimmory", "label": "Grimmory"},
                        {"value": "koreader", "label": "KOReader"},
                        {"value": "kobo", "label": "Kobo"},
                    ],
                    mode=SelectSelectorMode.DROPDOWN,
                )
            ),
        }
    )


class GrimmoryConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for grimmory."""

    VERSION = 2

    def __init__(self) -> None:
        """Initialize the config flow."""
        super().__init__()
        self._login_data: dict[str, Any] = {}

    @override
    @staticmethod
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlowWithReload:
        """Get the options flow."""
        return GrimmoryOptionsFlow()

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            user_input[CONF_HOST] = user_input[CONF_HOST].strip().rstrip("/")

            await self.async_set_unique_id(user_input[CONF_HOST])
            self._abort_if_unique_id_configured()

            try:
                api_data = await validate_input(user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                self._login_data = api_data
                return await self.async_step_library()

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA,
                user_input or {},
            ),
            errors=errors,
        )

    async def async_step_library(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the library selection"""

        if user_input is not None:
            library_id = user_input[CONF_LIBRARY_ID]
            progress_source = user_input[CONF_PROGRESS_SOURCE]

            return self.async_create_entry(
                title=self._login_data[CONF_HOST],
                data={
                    **self._login_data,
                    CONF_LIBRARY_ID: (None if library_id == "all" else int(library_id)),
                    CONF_PROGRESS_SOURCE: progress_source,
                },
            )

        client = GrimmoryApiClient(
            host=self._login_data[CONF_HOST],
            token=self._login_data[CONF_TOKEN],
        )

        try:
            data_schema = await _get_additional_settings_schema(client)
        except (aiohttp.ClientError, TimeoutError):
            _LOGGER.warning(
                "Unable to retrieve Grimmory libraries from %s",
                self._login_data[CONF_HOST],
            )
            return self.async_abort(reason="cannot_connect")

        return self.async_show_form(step_id="library", data_schema=data_schema)

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Config flow to reconfigure the integration."""

        entry = self._get_reconfigure_entry()

        if user_input is not None:
            library_id = user_input[CONF_LIBRARY_ID]
            progress_source = user_input[CONF_PROGRESS_SOURCE]

            return self.async_update_reload_and_abort(
                entry=entry,
                data_updates={
                    CONF_LIBRARY_ID: (None if library_id == "all" else int(library_id)),
                    CONF_PROGRESS_SOURCE: progress_source,
                },
            )

        client = GrimmoryApiClient(hass=self.hass, entry=entry)
        current_progress_source = (
            "grimmory"
            if entry.data.get(CONF_PROGRESS_SOURCE) is None
            else entry.data.get(CONF_PROGRESS_SOURCE)
        )
        try:
            data_schema = await _get_additional_settings_schema(
                client,
                entry.data.get(CONF_LIBRARY_ID),
                current_progress_source,
            )
        except (aiohttp.ClientError, TimeoutError):
            _LOGGER.warning(
                "Unable to retrieve Grimmory libraries from %s", entry.data[CONF_HOST]
            )
            return self.async_abort(reason="cannot_connect")

        return self.async_show_form(step_id="reconfigure", data_schema=data_schema)

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle reauthentication."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask the user to reauthenticate."""

        # Using the protected method below is standard practice.
        reauth_entry = self._get_reauth_entry()  # pylint: disable=protected-access
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                api_data = await validate_input(
                    {
                        CONF_HOST: reauth_entry.data[CONF_HOST],
                        CONF_USERNAME: reauth_entry.data[CONF_USERNAME],
                        CONF_PASSWORD: user_input[CONF_PASSWORD],
                    }
                )
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:
                _LOGGER.exception("Unexpected error during reauthentication")
                errors["base"] = "unknown"
            else:
                return self.async_update_reload_and_abort(
                    reauth_entry,
                    data_updates=api_data,
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=probatio.Schema({probatio.Required(CONF_PASSWORD): str}),
            errors=errors,
        )


class GrimmoryOptionsFlow(OptionsFlowWithReload):
    """Handle Grimmory book child devices as options."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Choose how to manage books."""

        menu_options = ["add_book"]
        if self.config_entry.options.get(CONF_BOOKS):
            menu_options.append("remove_book")
        menu_options.append("additional_settings")

        return self.async_show_menu(step_id="init", menu_options=menu_options)

    async def async_step_add_book(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Add a book by ID."""

        errors: dict[str, str] = {}

        if user_input is not None:
            book_id = user_input["book_id"]
            entry = self.config_entry
            client = GrimmoryApiClient(
                hass=self.hass,
                entry=entry,
            )

            try:
                book = await client.get_book(book_id)
            except aiohttp.ClientResponseError as err:
                if err.status == 404:
                    errors["base"] = "book_not_found"
                else:
                    errors["base"] = "cannot_connect"
            except (aiohttp.ClientError, TimeoutError):
                errors["base"] = "cannot_connect"
            else:
                if (
                    entry.data.get(CONF_LIBRARY_ID) is not None
                    and book.get("libraryId") != entry.data[CONF_LIBRARY_ID]
                ):
                    errors["base"] = "book_not_in_library"
                else:
                    books = list(entry.options.get(CONF_BOOKS, []))
                    if any(item["book_id"] == book["id"] for item in books):
                        errors["base"] = "book_already_added"
                    else:
                        books.append(
                            {
                                "book_id": book["id"],
                                "metadata": book.get("metadata"),
                            }
                        )
                        return self.async_create_entry(
                            title="", data={CONF_BOOKS: books}
                        )

        return self.async_show_form(
            step_id="add_book",
            data_schema=probatio.Schema({probatio.Required("book_id"): int}),
            errors=errors,
        )

    async def async_step_remove_book(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Remove a tracked book."""

        entry = self.config_entry
        books = list(entry.options.get(CONF_BOOKS, []))

        if user_input is not None:
            book_id = int(user_input["book_id"])
            books = [book for book in books if book["book_id"] != book_id]

            device_registry = dr.async_get(self.hass)
            child_device = device_registry.async_get_child_device_by_identifier(
                (DOMAIN, f"book_{book_id}"), entry.entry_id
            )
            if child_device is not None:
                device_registry.async_remove_device(child_device.id)

            return self.async_create_entry(
                title="",
                data={**entry.options, CONF_BOOKS: books},
            )

        if not books:
            return await self.async_step_init()

        return self.async_show_form(
            step_id="remove_book",
            data_schema=probatio.Schema(
                {
                    probatio.Required("book_id"): SelectSelector(
                        SelectSelectorConfig(
                            options=[
                                {
                                    "value": str(book["book_id"]),
                                    "label": f"Book {book['book_id']}",
                                }
                                for book in books
                            ],
                            mode=SelectSelectorMode.DROPDOWN,
                        )
                    )
                }
            ),
        )

    async def async_step_additional_settings(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Change the selected library and progress source."""

        entry = self.config_entry
        client = GrimmoryApiClient(hass=self.hass, entry=entry)

        if user_input is not None:
            library_id = user_input[CONF_LIBRARY_ID]
            data = {
                **entry.data,
                CONF_LIBRARY_ID: None if library_id == "all" else int(library_id),
                CONF_PROGRESS_SOURCE: user_input[CONF_PROGRESS_SOURCE],
            }
            if data != entry.data:
                self.hass.config_entries.async_update_entry(entry, data=data)
                await self.hass.config_entries.async_reload(entry.entry_id)

            return self.async_create_entry(title="", data=entry.options)

        library_id = entry.data.get(CONF_LIBRARY_ID)
        progress_source = entry.data.get(CONF_PROGRESS_SOURCE) or "grimmory"

        try:
            data_schema = await _get_additional_settings_schema(
                client,
                library_id,
                progress_source,
            )
        except (aiohttp.ClientError, TimeoutError):
            _LOGGER.warning(
                "Unable to retrieve Grimmory libraries from %s", entry.data[CONF_HOST]
            )
            return self.async_abort(reason="cannot_connect")

        return self.async_show_form(
            step_id="additional_settings",
            data_schema=data_schema,
        )


class CannotConnect(Exception):
    """Error to indicate we cannot connect."""


class InvalidAuth(Exception):
    """Error to indicate there is invalid auth."""
