"""Authenticated client for an undocumented Nourish web endpoint.

Credentials are never logged. Token refresh rotation is persisted immediately
using the caller-supplied callback before the subsequent goals request.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
import time
from typing import Any

from aiohttp import ClientError, ClientSession

from .const import (
    CONF_CLIENT_ID,
    CONF_DEVICE_TIME_ZONE,
    CONF_PATIENT_ID,
    CONF_REFRESH_TOKEN,
    GOALS_URL,
    TOKEN_URL,
)


class NourishAuthError(Exception):
    """Reauthentication is necessary."""


class NourishConnectionError(Exception):
    """Temporary server, protocol or network failure."""


class NourishClient:
    """Small read-only client using user-provided OAuth refresh credentials."""

    def __init__(
        self,
        session: ClientSession,
        details: dict[str, str],
        on_token_rotation: Callable[[str], Awaitable[None]] | None = None,
    ) -> None:
        self._session = session
        self._details = dict(details)
        self._on_token_rotation = on_token_rotation
        self._access_token: str | None = None
        self._expires_at = 0.0
        self._refresh_lock = asyncio.Lock()

    @property
    def refresh_token(self) -> str:
        """Latest refresh token, including any rotation."""
        return self._details[CONF_REFRESH_TOKEN]

    async def _refresh(self, *, force: bool = False) -> None:
        """Get an access token, refreshing only when necessary."""
        async with self._refresh_lock:
            if not force and self._access_token and time.monotonic() < self._expires_at - 60:
                return

            payload = {
                "grant_type": "refresh_token",
                "client_id": self._details[CONF_CLIENT_ID],
                "refresh_token": self._details[CONF_REFRESH_TOKEN],
            }
            try:
                async with asyncio.timeout(20):
                    async with self._session.post(
                        TOKEN_URL, json=payload, headers={"Accept": "application/json"}
                    ) as response:
                        if response.status in (400, 401, 403):
                            raise NourishAuthError("Nourish could not refresh this session")
                        if response.status >= 400:
                            raise NourishConnectionError("Nourish authentication is temporarily unavailable")
                        body = await response.json()
            except (TimeoutError, ClientError) as err:
                raise NourishConnectionError("Could not contact Nourish authentication") from err
            except ValueError as err:
                raise NourishConnectionError("Nourish authentication returned invalid JSON") from err

            if not isinstance(body, dict) or not isinstance(body.get("access_token"), str):
                raise NourishConnectionError("Nourish authentication response was incomplete")
            access_token = body["access_token"]
            if not access_token:
                raise NourishConnectionError("Nourish returned an empty access token")

            rotated = body.get("refresh_token")
            if isinstance(rotated, str) and rotated and rotated != self.refresh_token:
                self._details[CONF_REFRESH_TOKEN] = rotated
                if self._on_token_rotation is not None:
                    await self._on_token_rotation(rotated)

            expires_in = body.get("expires_in", 600)
            if isinstance(expires_in, bool) or not isinstance(expires_in, (int, float)):
                expires_in = 600
            self._access_token = access_token
            self._expires_at = time.monotonic() + max(0, float(expires_in))

    async def _request_goals(self) -> Any:
        """Request the web app's current-day goals using the active token."""
        if not self._access_token:
            raise NourishAuthError("Nourish is not authenticated")
        try:
            async with asyncio.timeout(20):
                async with self._session.get(
                    GOALS_URL.format(patient_id=self._details[CONF_PATIENT_ID]),
                    params={"deviceTimeZone": self._details[CONF_DEVICE_TIME_ZONE]},
                    headers={
                        "Authorization": f"Bearer {self._access_token}",
                        "Accept": "application/json",
                    },
                ) as response:
                    if response.status in (401, 403):
                        raise NourishAuthError("Nourish rejected the access token")
                    if response.status >= 400:
                        raise NourishConnectionError("Nourish could not return today's goals")
                    return await response.json()
        except (TimeoutError, ClientError) as err:
            raise NourishConnectionError("Could not contact Nourish goals endpoint") from err
        except ValueError as err:
            raise NourishConnectionError("Nourish goals endpoint returned invalid JSON") from err

    async def async_fetch_goals(self) -> Any:
        """Fetch today's goals, retrying one access-token authorization failure."""
        await self._refresh()
        try:
            return await self._request_goals()
        except NourishAuthError:
            await self._refresh(force=True)
            return await self._request_goals()
