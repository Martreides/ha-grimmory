# Copyright (C) 2026 Michiel Cornelissen
# This file is part of ha-grimmory
# SPDX-License-Identifier: GPL-3.0-only

"""Config flow for the grimmory integration."""

import logging
from typing import Any, override

import aiohttp
import probatio
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_TOKEN, CONF_USERNAME
from homeassistant.helpers.selector import (
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .api import GrimmoryApiClient
from .const import CONF_LIBRARY_ID, CONF_REFRESH_TOKEN, DOMAIN

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


class GrimmoryConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for grimmory."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        super().__init__()
        self._login_data: dict[str, Any] = {}

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

            return self.async_create_entry(
                title=self._login_data[CONF_HOST],
                data={
                    **self._login_data,
                    CONF_LIBRARY_ID: (None if library_id == "all" else int(library_id)),
                },
            )

        client = GrimmoryApiClient(
            host=self._login_data[CONF_HOST],
            token=self._login_data[CONF_TOKEN],
        )

        data_schema = await self._get_library_schema(client)

        return self.async_show_form(step_id="library", data_schema=data_schema)

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Config flow to reconfigure the integration."""

        entry = self._get_reconfigure_entry()

        if user_input is not None:
            library_id = user_input[CONF_LIBRARY_ID]

            return self.async_update_reload_and_abort(
                entry=entry,
                data_updates={
                    CONF_LIBRARY_ID: (None if library_id == "all" else int(library_id)),
                },
            )

        client = GrimmoryApiClient(
            host=entry.data[CONF_HOST], token=entry.data[CONF_TOKEN]
        )

        data_schema = await self._get_library_schema(
            client, entry.data.get(CONF_LIBRARY_ID)
        )

        return self.async_show_form(step_id="reconfigure", data_schema=data_schema)

    async def _get_library_schema(
        self,
        client: GrimmoryApiClient,
        current_library_id: int | None = None,
    ) -> probatio.Schema:
        """Build the library selection schema."""

        libraries = await client.get_libraries()
        current_value = "all" if current_library_id is None else str(current_library_id)

        return probatio.Schema(
            {
                probatio.Required(
                    CONF_LIBRARY_ID, default=current_value
                ): SelectSelector(
                    SelectSelectorConfig(
                        options=[
                            {"value": "all", "label": "All libraries"},
                            *[
                                {
                                    "value": str(library["id"]),
                                    "label": library["name"],
                                }
                                for library in libraries
                            ],
                        ],
                        mode=SelectSelectorMode.DROPDOWN,
                    )
                )
            }
        )


class CannotConnect(Exception):
    """Error to indicate we cannot connect."""


class InvalidAuth(Exception):
    """Error to indicate there is invalid auth."""
