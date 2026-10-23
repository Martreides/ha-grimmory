"""Config flow for the grimmory integration."""

import logging
from typing import Any, override

import aiohttp
import probatio

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_TOKEN, CONF_USERNAME

from .api import GrimmoryApiClient
from .const import CONF_REFRESH_TOKEN, DOMAIN

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
                info = await validate_input(user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(title=user_input[CONF_HOST], data=info)

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA,
                user_input or {},
            ),
            errors=errors,
        )


class CannotConnect(Exception):
    """Error to indicate we cannot connect."""


class InvalidAuth(Exception):
    """Error to indicate there is invalid auth."""
