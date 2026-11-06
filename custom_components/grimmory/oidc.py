# Copyright (C) 2026 Michiel Cornelissen
# This file is part of ha-grimmory
# SPDX-License-Identifier: GPL-3.0-only

"""OIDC authentication for Grimmory."""

import logging
import secrets
from typing import Any, override

from aiohttp import web
from homeassistant.components.http import KEY_HASS, HomeAssistantView
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.config_entry_oauth2_flow import (
    AbstractOAuth2Implementation,
)
from homeassistant.helpers.network import get_url
from homeassistant.helpers.oauth2 import compute_code_challenge, generate_code_verifier
from yarl import URL

from .api import GrimmoryApiClient
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

CALLBACK_PATH = "/oauth2-callback"

DATA_PENDING_FLOWS = f"{DOMAIN}_oidc_pending"
DATA_CALLBACK_VIEW_REGISTERED = f"{DOMAIN}_oidc_callback_registered"


class GrimmoryOIDCCallbackView(HomeAssistantView):
    """Handle the OIDC callback from the identity provider."""

    url = CALLBACK_PATH
    name = "api:grimmory:oidc:callback"
    requires_auth = False

    async def get(self, request: web.Request) -> web.Response:
        """Receive the authorization code."""

        hass = request.app[KEY_HASS]
        state = request.query.get("state")

        if not state:
            return web.Response(text="Missing state", status=400)

        pending_flows = hass.data.get(DATA_PENDING_FLOWS, {})
        pending = pending_flows.pop(state, None)

        if pending is None:
            return web.Response(text="Invalid or expired state", status=400)

        if "error" in request.query:
            user_input = {
                "state": state,
                "error": request.query["error"],
            }
        elif "code" in request.query:
            user_input = {
                "state": state,
                "code": request.query["code"],
            }
        else:
            return web.Response(text="Missing code or error", status=400)

        await hass.config_entries.flow.async_configure(
            flow_id=pending["flow_id"],
            user_input=user_input,
        )

        return web.Response(
            text="<html><body><h3>Authentication completed. "
            "You can close this window.</h3></body></html>",
            content_type="text/html",
        )


class GrimmoryOAuth2Implementation(AbstractOAuth2Implementation):
    """Grimmory-specific OIDC implementation."""

    def __init__(
        self,
        hass: HomeAssistant,
        host: str,
        oidc_settings: dict[str, Any],
    ) -> None:
        """Initialize the OIDC implementation."""
        self.hass = hass
        self.host = host
        self.oidc_settings = oidc_settings

        self.redirect_uri = (
            f"{get_url(hass, prefer_external=False).rstrip('/')}{CALLBACK_PATH}"
        )
        self.origin = str(URL(self.redirect_uri).origin())
        self._pending: dict[str, dict[str, str]] = {}

        if not hass.data.get(DATA_CALLBACK_VIEW_REGISTERED):
            hass.http.register_view(GrimmoryOIDCCallbackView())
            hass.data[DATA_CALLBACK_VIEW_REGISTERED] = True

    @property
    @override
    def name(self) -> str:
        """Return the implementation name."""
        return self.oidc_settings.get("providerName") or "Grimmory OIDC"

    @property
    @override
    def domain(self) -> str:
        """Return the implementation domain."""
        return DOMAIN

    @override
    async def async_generate_authorize_url(self, flow_id: str) -> str:
        """Generate the OIDC authorization URL."""

        session = async_get_clientsession(self.hass)

        async with session.get(
            f"{self.oidc_settings['issuerUri'].rstrip('/')}/.well-known/openid-configuration"
        ) as response:
            response.raise_for_status()
            discovery = await response.json()

        state = await GrimmoryApiClient.get_oidc_state(session, self.host)

        nonce = secrets.token_urlsafe(32)
        verifier = generate_code_verifier(43)
        challenge = compute_code_challenge(verifier)

        scopes = " ".join(self.oidc_settings.get("scopes"))

        self._pending[state] = {
            "nonce": nonce,
            "verifier": verifier,
        }

        self.hass.data.setdefault(DATA_PENDING_FLOWS, {})[state] = {
            "flow_id": flow_id,
        }

        params = {
            "response_type": "code",
            "client_id": self.oidc_settings["clientId"],
            "redirect_uri": self.redirect_uri,
            "scope": scopes,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "state": state,
            "nonce": nonce,
        }

        return str(URL(discovery["authorization_endpoint"]).update_query(params))

    @override
    async def async_resolve_external_data(
        self,
        external_data: Any,
    ) -> dict[str, Any]:
        """Exchange the authorization code through Grimmory."""

        state = external_data.get("state")
        pending = self._pending.pop(state, None)

        if pending is None:
            raise ValueError("Unknown or expired OIDC state")

        code = external_data.get("code")
        if not code:
            raise ValueError("Authorization code missing")

        payload = {
            "code": code,
            "codeVerifier": pending["verifier"],
            "redirectUri": self.redirect_uri,
            "nonce": pending["nonce"],
            "state": state,
        }

        token_data = await GrimmoryApiClient.exchange_oidc_code(
            async_get_clientsession(self.hass), self.host, payload, self.origin
        )

        return {
            "access_token": token_data["accessToken"],
            "refresh_token": token_data["refreshToken"],
            "expires_in": int(token_data["expires"]),
        }

    @override
    async def _async_refresh_token(self, token: dict[str, Any]) -> dict[str, Any]:
        """Token refresh is currently handled by GrimmoryApiClient."""
        raise NotImplementedError("Token refresh is handled by GrimmoryApiClient")
