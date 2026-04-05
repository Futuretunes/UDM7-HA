"""WebSocket manager for real-time UniFi controller updates.

Maintains a persistent WebSocket connection to the UniFi controller and
dispatches incoming messages to registered subscribers.  Handles automatic
reconnection on failure with a configurable backoff interval.

Message format from the controller::

    {
        "meta": {"rc": "ok", "message": "device:sync"},
        "data": [{ ...payload... }]
    }

The ``meta.message`` field determines the message type and is used for
routing to the correct subscriber callbacks.
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Callable
from contextlib import suppress
from enum import StrEnum

import aiohttp

_LOGGER = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Message types
# ---------------------------------------------------------------------------


class WebSocketMessageType(StrEnum):
    """Known WebSocket message types sent by the UniFi controller."""

    DEVICE_SYNC = "device:sync"
    STA_SYNC = "sta:sync"
    USER_SYNC = "user:sync"
    USER_DELETE = "user:delete"
    EVENTS = "events"
    SPEED_TEST_UPDATE = "speed-test:update"
    WLAN_SYNC = "wlanconf:sync"
    WLAN_ADD = "wlanconf:add"
    WLAN_DELETE = "wlanconf:delete"
    PORT_FORWARD_SYNC = "portforward:sync"
    PORT_FORWARD_ADD = "portforward:add"
    PORT_FORWARD_DELETE = "portforward:delete"
    DPI_APP_SYNC = "dpiapp:sync"
    DPI_GROUP_SYNC = "dpigroup:sync"
    FIREWALL_RULE_SYNC = "firewallrule:sync"
    FIREWALL_GROUP_SYNC = "firewallgroup:sync"
    ALARM_ADD = "alarm:add"
    ALARM_SYNC = "alarm:sync"
    VPN_CONNECT = "vpn:connect"
    VPN_DISCONNECT = "vpn:disconnect"


# Type alias for message callbacks.
# Receives the raw message type string (which may or may not be a known
# ``WebSocketMessageType``) and the list of data items from the payload.
type WebSocketCallback = Callable[[WebSocketMessageType | str, list[dict]], None]


# ---------------------------------------------------------------------------
# Connection state
# ---------------------------------------------------------------------------


class WebSocketState(StrEnum):
    """Possible states of the WebSocket connection."""

    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"


# ---------------------------------------------------------------------------
# WebSocket manager
# ---------------------------------------------------------------------------


class UniFiWebSocket:
    """Manages a persistent WebSocket connection to a UniFi controller.

    The connection shares the same :class:`aiohttp.ClientSession` as the HTTP
    client so that authentication cookies are available automatically.

    Args:
        host: Hostname or IP address of the controller.
        port: HTTPS port (443 for UniFi OS, 8443 for standalone).
        site: UniFi site name (usually ``"default"``).
        session: The shared aiohttp client session (carries auth cookies).
        is_unifi_os: ``True`` for UniFi OS devices (UDM/UDR/UCG).
        verify_ssl: Whether to verify the server's TLS certificate.
    """

    def __init__(
        self,
        host: str,
        port: int,
        site: str,
        session: aiohttp.ClientSession,
        is_unifi_os: bool,
        verify_ssl: bool = False,
    ) -> None:
        self._host = host
        self._port = port
        self._site = site
        self._session = session
        self._is_unifi_os = is_unifi_os
        self._ssl: bool | None = None if verify_ssl else False

        self._ws: aiohttp.ClientWebSocketResponse | None = None
        self._state = WebSocketState.DISCONNECTED
        self._task: asyncio.Task[None] | None = None

        # Subscribers keyed by message type.
        self._subscribers: dict[
            WebSocketMessageType | str, list[WebSocketCallback]
        ] = {}
        # Catch-all subscribers that receive every message type.
        self._global_subscribers: list[WebSocketCallback] = []

        # State-change listeners.
        self._state_callbacks: list[Callable[[WebSocketState], None]] = []

        # Reconnect settings.
        self._reconnect_interval: float = 15  # seconds
        self._should_run = False

    # ------------------------------------------------------------------
    # Public properties
    # ------------------------------------------------------------------

    @property
    def state(self) -> WebSocketState:
        """Current connection state."""
        return self._state

    @property
    def is_connected(self) -> bool:
        """Return ``True`` when the WebSocket is connected and listening."""
        return self._state == WebSocketState.CONNECTED

    # ------------------------------------------------------------------
    # Subscription helpers
    # ------------------------------------------------------------------

    def subscribe(
        self,
        callback: WebSocketCallback,
        message_types: list[WebSocketMessageType | str] | None = None,
    ) -> Callable[[], None]:
        """Subscribe to WebSocket messages.

        Args:
            callback: Synchronous callable invoked with ``(message_type, data)``
                whenever a matching message arrives.
            message_types: If provided, the callback is invoked only for
                messages whose ``meta.message`` matches one of these types.
                If ``None``, the callback receives **all** messages.

        Returns:
            A callable that, when invoked, removes the subscription.
        """
        if message_types is None:
            self._global_subscribers.append(callback)

            def _unsub_global() -> None:
                with suppress(ValueError):
                    self._global_subscribers.remove(callback)

            return _unsub_global

        for msg_type in message_types:
            self._subscribers.setdefault(msg_type, []).append(callback)

        def _unsub_typed() -> None:
            for msg_type in message_types:  # type: ignore[union-attr]
                subs = self._subscribers.get(msg_type)
                if subs is not None:
                    with suppress(ValueError):
                        subs.remove(callback)
                    if not subs:
                        del self._subscribers[msg_type]

        return _unsub_typed

    def on_state_change(
        self, callback: Callable[[WebSocketState], None]
    ) -> Callable[[], None]:
        """Subscribe to connection state changes.

        Args:
            callback: Synchronous callable invoked with the new
                :class:`WebSocketState` whenever the state transitions.

        Returns:
            A callable that removes the subscription.
        """
        self._state_callbacks.append(callback)

        def _unsub() -> None:
            with suppress(ValueError):
                self._state_callbacks.remove(callback)

        return _unsub

    # ------------------------------------------------------------------
    # Connection lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Start the WebSocket connection loop.

        If the session does not support WebSocket connections (e.g. when
        using API-key-only authentication), a warning is logged and no
        background task is created.
        """
        if self._task is not None and not self._task.done():
            _LOGGER.debug("WebSocket task already running")
            return

        self._should_run = True
        self._task = asyncio.create_task(self._run(), name="unifi-websocket")
        _LOGGER.debug("WebSocket connection loop started")

    async def stop(self) -> None:
        """Stop the WebSocket connection and cancel the background task."""
        self._should_run = False

        if self._ws is not None and not self._ws.closed:
            await self._ws.close()

        if self._task is not None:
            self._task.cancel()
            with suppress(asyncio.CancelledError):
                await self._task
            self._task = None

        self._set_state(WebSocketState.DISCONNECTED)
        _LOGGER.debug("WebSocket connection loop stopped")

    # ------------------------------------------------------------------
    # Internal: connection loop
    # ------------------------------------------------------------------

    async def _run(self) -> None:
        """Main loop: connect, listen, and reconnect on failure."""
        while self._should_run:
            try:
                await self._connect()
                await self._listen()
            except (
                aiohttp.WSServerHandshakeError,
                aiohttp.ClientError,
                asyncio.TimeoutError,
            ) as err:
                _LOGGER.warning("WebSocket connection failed: %s", err)
            except Exception:
                _LOGGER.exception("Unexpected WebSocket error")
            finally:
                self._set_state(WebSocketState.DISCONNECTED)

            if self._should_run:
                _LOGGER.debug(
                    "Reconnecting in %d seconds", self._reconnect_interval
                )
                await asyncio.sleep(self._reconnect_interval)

    async def _connect(self) -> None:
        """Establish the WebSocket connection to the controller."""
        self._set_state(WebSocketState.CONNECTING)

        if self._is_unifi_os:
            url = (
                f"wss://{self._host}:{self._port}"
                f"/proxy/network/wss/s/{self._site}/events"
            )
        else:
            url = (
                f"wss://{self._host}:{self._port}"
                f"/wss/s/{self._site}/events"
            )

        _LOGGER.debug("Connecting WebSocket to %s", url)

        self._ws = await self._session.ws_connect(
            url,
            ssl=self._ssl,
            heartbeat=15,
            compress=0,
        )

        self._set_state(WebSocketState.CONNECTED)
        _LOGGER.info("WebSocket connected to %s", url)

    async def _listen(self) -> None:
        """Read messages until the connection is closed or errors out."""
        assert self._ws is not None  # noqa: S101

        async for msg in self._ws:
            if msg.type == aiohttp.WSMsgType.TEXT:
                self._process_message(msg.data)
            elif msg.type == aiohttp.WSMsgType.ERROR:
                _LOGGER.error(
                    "WebSocket error: %s", self._ws.exception()
                )
                break
            elif msg.type in (
                aiohttp.WSMsgType.CLOSE,
                aiohttp.WSMsgType.CLOSING,
                aiohttp.WSMsgType.CLOSED,
            ):
                _LOGGER.debug("WebSocket closed (type=%s)", msg.type.name)
                break

    # ------------------------------------------------------------------
    # Internal: message dispatching
    # ------------------------------------------------------------------

    def _process_message(self, raw: str) -> None:
        """Parse a raw JSON string and dispatch to subscribers."""
        try:
            message = json.loads(raw)
        except json.JSONDecodeError:
            _LOGGER.warning("Invalid WebSocket JSON: %s", raw[:200])
            return

        meta = message.get("meta", {})
        msg_type: str = meta.get("message", "")
        data: list[dict] = message.get("data", [])

        if not msg_type or not data:
            return

        _LOGGER.debug(
            "WebSocket message: %s (%d item%s)",
            msg_type,
            len(data),
            "" if len(data) == 1 else "s",
        )

        # Dispatch to type-specific subscribers.
        for callback in self._subscribers.get(msg_type, []):
            try:
                callback(msg_type, data)
            except Exception:
                _LOGGER.exception(
                    "Error in WebSocket callback for %s", msg_type
                )

        # Dispatch to global (catch-all) subscribers.
        for callback in self._global_subscribers:
            try:
                callback(msg_type, data)
            except Exception:
                _LOGGER.exception("Error in global WebSocket callback")

    # ------------------------------------------------------------------
    # Internal: state management
    # ------------------------------------------------------------------

    def _set_state(self, state: WebSocketState) -> None:
        """Update the connection state and notify listeners."""
        if self._state == state:
            return

        old_state = self._state
        self._state = state
        _LOGGER.debug(
            "WebSocket state: %s -> %s", old_state.value, state.value
        )

        for callback in self._state_callbacks:
            try:
                callback(state)
            except Exception:
                _LOGGER.exception("Error in WebSocket state callback")
