"""Thin async client for the Sentinel Command Center integration API.

Wraps the ``/api/integration/*`` endpoints (camera discovery, snapshot,
recording toggle, status, and the motion SSE) behind a small typed client.
Uses the Home Assistant-managed aiohttp session passed in by the caller.
"""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator

import aiohttp

_LOGGER = logging.getLogger(__name__)


class SentinelApiError(Exception):
    """A non-auth API failure (connection, 5xx, unexpected status)."""


class SentinelAuthError(SentinelApiError):
    """The integration key was rejected (HTTP 401)."""


class SentinelClient:
    """Talks to one Command Center org via a single integration key."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        base_url: str,
        api_key: str,
    ) -> None:
        self._session = session
        self._base = base_url.rstrip("/")
        self._headers = {"Authorization": f"Bearer {api_key}"}

    async def _get_json(self, path: str) -> dict:
        url = f"{self._base}{path}"
        try:
            async with self._session.get(url, headers=self._headers) as resp:
                if resp.status == 401:
                    raise SentinelAuthError("Integration key invalid or revoked")
                if resp.status != 200:
                    raise SentinelApiError(f"GET {path} returned HTTP {resp.status}")
                return await resp.json()
        except (aiohttp.ClientError, ValueError) as err:
            # ValueError covers json.JSONDecodeError: a 200 response with a
            # malformed/truncated body (e.g. a proxy error page served with a
            # JSON content-type) would otherwise propagate raw and crash the
            # coordinator's update instead of degrading to a clean UpdateFailed.
            # The deliberate SentinelAuthError/SentinelApiError raised above are
            # neither ClientError nor ValueError, so they pass through untouched.
            raise SentinelApiError(f"GET {path} failed: {err}") from err

    async def async_get_status(self) -> dict:
        """Org rollup — also the config-flow validation target."""
        return await self._get_json("/api/integration/status")

    async def async_get_cameras(self) -> list[dict]:
        """Every camera across every node, with stream URLs + recording state."""
        data = await self._get_json("/api/integration/cameras")
        return data.get("cameras", [])

    async def async_get_snapshot(self, camera_id: str) -> bytes:
        """Live JPEG for one camera."""
        url = f"{self._base}/api/integration/cameras/{camera_id}/snapshot"
        try:
            async with self._session.get(url, headers=self._headers) as resp:
                if resp.status == 401:
                    raise SentinelAuthError("Integration key invalid or revoked")
                if resp.status != 200:
                    raise SentinelApiError(
                        f"Snapshot for {camera_id} returned HTTP {resp.status}"
                    )
                return await resp.read()
        except aiohttp.ClientError as err:
            raise SentinelApiError(f"Snapshot for {camera_id} failed: {err}") from err

    async def async_set_recording(self, camera_id: str, recording: bool) -> None:
        """Toggle continuous recording for a camera."""
        url = f"{self._base}/api/integration/cameras/{camera_id}/recording"
        try:
            async with self._session.post(
                url, headers=self._headers, json={"recording": recording}
            ) as resp:
                if resp.status == 401:
                    raise SentinelAuthError("Integration key invalid or revoked")
                if resp.status != 200:
                    raise SentinelApiError(
                        f"Recording toggle for {camera_id} returned HTTP {resp.status}"
                    )
        except aiohttp.ClientError as err:
            raise SentinelApiError(
                f"Recording toggle for {camera_id} failed: {err}"
            ) from err

    async def async_iter_motion(self) -> AsyncIterator[dict]:
        """Yield motion events from the SSE feed.

        One long-lived GET; each ``data:`` line is a JSON motion event
        ``{type, camera_id, node_id, score, timestamp}``. ``: keepalive``
        comments are ignored. Caller owns reconnect — when the server or
        network drops the stream this generator simply ends.
        """
        url = f"{self._base}/api/integration/motion/stream"
        # No total timeout (the stream is meant to stay open); a sock_read
        # timeout longer than the server's 25s keepalive lets us notice a
        # truly dead connection without tearing down a healthy idle one.
        timeout = aiohttp.ClientTimeout(total=None, sock_read=60)
        async with self._session.get(
            url, headers=self._headers, timeout=timeout
        ) as resp:
            if resp.status == 401:
                raise SentinelAuthError("Integration key invalid or revoked")
            if resp.status != 200:
                raise SentinelApiError(f"Motion stream returned HTTP {resp.status}")
            async for raw in resp.content:
                line = raw.decode("utf-8", "ignore").strip()
                if not line.startswith("data:"):
                    continue
                payload = line[len("data:"):].strip()
                if not payload:
                    continue
                try:
                    event = json.loads(payload)
                except ValueError:
                    continue
                if isinstance(event, dict) and event.get("type") == "motion":
                    yield event
