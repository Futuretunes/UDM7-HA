"""Tests for WebSocket message handling.

The ``UniFiWebSocket`` class manages a persistent WebSocket connection and
dispatches incoming messages to registered subscribers.  We test the
subscription, unsubscription, message parsing, dispatch, and state-change
logic directly without an active WebSocket connection.

Since ``__init__`` requires an aiohttp session, we pass a mock.
"""

import json
from unittest.mock import MagicMock

import aiohttp
import pytest

from custom_components.unifi_network_ha.api.websocket import (
    UniFiWebSocket,
    WebSocketMessageType,
    WebSocketState,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_session():
    """Provide a mock aiohttp ClientSession."""
    return MagicMock(spec=aiohttp.ClientSession)


@pytest.fixture
def ws(mock_session):
    """Provide a UniFiWebSocket instance (not connected)."""
    return UniFiWebSocket(
        host="192.168.1.1",
        port=443,
        site="default",
        session=mock_session,
        is_unifi_os=True,
        verify_ssl=False,
    )


# ---------------------------------------------------------------------------
# Helper to build a raw WebSocket message string
# ---------------------------------------------------------------------------


def _make_ws_message(msg_type: str, data: list[dict]) -> str:
    """Build a JSON string matching the UniFi WS message format."""
    return json.dumps({"meta": {"rc": "ok", "message": msg_type}, "data": data})


# ---------------------------------------------------------------------------
# Tests — message dispatch
# ---------------------------------------------------------------------------


class TestProcessMessageDispatch:
    """Verify _process_message routing to subscribers."""

    def test_dispatches_to_typed_subscriber(self, ws):
        """Subscribe to DEVICE_SYNC, process a device:sync message."""
        received = []

        def callback(msg_type, data):
            received.append((msg_type, data))

        ws.subscribe(callback, message_types=[WebSocketMessageType.DEVICE_SYNC])

        raw = _make_ws_message(
            "device:sync",
            [{"mac": "aa:bb:cc:dd:ee:01", "cpu": 50}],
        )
        ws._process_message(raw)

        assert len(received) == 1
        assert received[0][0] == "device:sync"
        assert received[0][1] == [{"mac": "aa:bb:cc:dd:ee:01", "cpu": 50}]

    def test_global_subscriber_receives_all(self, ws):
        """Subscribe with no filter; receives all message types."""
        received = []

        def callback(msg_type, data):
            received.append(msg_type)

        ws.subscribe(callback, message_types=None)

        ws._process_message(
            _make_ws_message("device:sync", [{"mac": "aa:bb:cc:dd:ee:01"}])
        )
        ws._process_message(
            _make_ws_message("sta:sync", [{"mac": "11:22:33:44:55:66"}])
        )
        ws._process_message(
            _make_ws_message("events", [{"key": "EVT_AP_Lost"}])
        )

        assert len(received) == 3
        assert received[0] == "device:sync"
        assert received[1] == "sta:sync"
        assert received[2] == "events"

    def test_ignores_wrong_message_type(self, ws):
        """Subscribe to STA_SYNC; device:sync message does NOT trigger it."""
        received = []

        def callback(msg_type, data):
            received.append(msg_type)

        ws.subscribe(callback, message_types=[WebSocketMessageType.STA_SYNC])

        ws._process_message(
            _make_ws_message("device:sync", [{"mac": "aa:bb:cc:dd:ee:01"}])
        )

        assert len(received) == 0

    def test_multiple_types_subscription(self, ws):
        """Subscribe to multiple types; receives only those types."""
        received = []

        def callback(msg_type, data):
            received.append(msg_type)

        ws.subscribe(
            callback,
            message_types=[
                WebSocketMessageType.DEVICE_SYNC,
                WebSocketMessageType.ALARM_ADD,
            ],
        )

        ws._process_message(
            _make_ws_message("device:sync", [{"mac": "aa"}])
        )
        ws._process_message(
            _make_ws_message("sta:sync", [{"mac": "bb"}])
        )
        ws._process_message(
            _make_ws_message("alarm:add", [{"_id": "a1"}])
        )

        assert len(received) == 2
        assert "device:sync" in received
        assert "alarm:add" in received
        assert "sta:sync" not in received


# ---------------------------------------------------------------------------
# Tests — invalid / edge-case messages
# ---------------------------------------------------------------------------


class TestProcessMessageEdgeCases:
    """Verify robustness against invalid or empty messages."""

    def test_invalid_json_no_crash(self, ws):
        """Process garbage string; no crash, no callback."""
        received = []

        def callback(msg_type, data):
            received.append(msg_type)

        ws.subscribe(callback, message_types=None)
        ws._process_message("this is not json {{{")

        assert len(received) == 0

    def test_empty_data_no_callback(self, ws):
        """Process message with empty data list; no callback."""
        received = []

        def callback(msg_type, data):
            received.append(msg_type)

        ws.subscribe(callback, message_types=None)

        raw = json.dumps(
            {"meta": {"rc": "ok", "message": "device:sync"}, "data": []}
        )
        ws._process_message(raw)

        assert len(received) == 0

    def test_missing_meta_no_callback(self, ws):
        """Process message without meta field; no callback."""
        received = []

        def callback(msg_type, data):
            received.append(msg_type)

        ws.subscribe(callback, message_types=None)
        ws._process_message(json.dumps({"data": [{"foo": 1}]}))

        assert len(received) == 0

    def test_missing_message_type_no_callback(self, ws):
        """Process message with empty message type; no callback."""
        received = []

        def callback(msg_type, data):
            received.append(msg_type)

        ws.subscribe(callback, message_types=None)

        raw = json.dumps(
            {"meta": {"rc": "ok", "message": ""}, "data": [{"foo": 1}]}
        )
        ws._process_message(raw)

        assert len(received) == 0

    def test_callback_exception_does_not_crash(self, ws):
        """If a callback raises, other subscribers still receive the message."""
        received = []

        def bad_callback(msg_type, data):
            raise RuntimeError("boom")

        def good_callback(msg_type, data):
            received.append(msg_type)

        ws.subscribe(bad_callback, message_types=[WebSocketMessageType.DEVICE_SYNC])
        ws.subscribe(good_callback, message_types=[WebSocketMessageType.DEVICE_SYNC])

        ws._process_message(
            _make_ws_message("device:sync", [{"mac": "aa"}])
        )

        # The good callback should still have fired
        assert len(received) == 1


# ---------------------------------------------------------------------------
# Tests — subscribe / unsubscribe
# ---------------------------------------------------------------------------


class TestSubscribeUnsubscribe:
    """Verify subscription management."""

    def test_subscribe_returns_unsubscribe_typed(self, ws):
        """Subscribe, call unsubscribe, process message; callback NOT called."""
        received = []

        def callback(msg_type, data):
            received.append(msg_type)

        unsub = ws.subscribe(
            callback, message_types=[WebSocketMessageType.DEVICE_SYNC]
        )

        # Process a message -- callback fires
        ws._process_message(
            _make_ws_message("device:sync", [{"mac": "aa"}])
        )
        assert len(received) == 1

        # Unsubscribe
        unsub()

        # Process another message -- callback should NOT fire
        ws._process_message(
            _make_ws_message("device:sync", [{"mac": "bb"}])
        )
        assert len(received) == 1  # still 1

    def test_subscribe_returns_unsubscribe_global(self, ws):
        """Global subscriber can be unsubscribed."""
        received = []

        def callback(msg_type, data):
            received.append(msg_type)

        unsub = ws.subscribe(callback, message_types=None)

        ws._process_message(
            _make_ws_message("device:sync", [{"mac": "aa"}])
        )
        assert len(received) == 1

        unsub()

        ws._process_message(
            _make_ws_message("sta:sync", [{"mac": "bb"}])
        )
        assert len(received) == 1  # still 1

    def test_double_unsubscribe_no_error(self, ws):
        """Calling unsubscribe twice does not raise."""
        def callback(msg_type, data):
            pass

        unsub = ws.subscribe(
            callback, message_types=[WebSocketMessageType.DEVICE_SYNC]
        )
        unsub()
        unsub()  # Should not raise


# ---------------------------------------------------------------------------
# Tests — state changes
# ---------------------------------------------------------------------------


class TestStateChanges:
    """Verify state change callback mechanism."""

    def test_state_change_callback(self, ws):
        """Register state change callback; changing state triggers it."""
        states = []

        def on_state(state):
            states.append(state)

        ws.on_state_change(on_state)

        # Initial state is DISCONNECTED
        assert ws.state == WebSocketState.DISCONNECTED

        # Transition to CONNECTING
        ws._set_state(WebSocketState.CONNECTING)
        assert ws.state == WebSocketState.CONNECTING
        assert len(states) == 1
        assert states[0] == WebSocketState.CONNECTING

        # Transition to CONNECTED
        ws._set_state(WebSocketState.CONNECTED)
        assert ws.state == WebSocketState.CONNECTED
        assert len(states) == 2
        assert states[1] == WebSocketState.CONNECTED

    def test_state_change_same_state_no_callback(self, ws):
        """Setting the same state again does NOT trigger the callback."""
        states = []

        def on_state(state):
            states.append(state)

        ws.on_state_change(on_state)

        # Already DISCONNECTED; setting it again should not trigger
        ws._set_state(WebSocketState.DISCONNECTED)
        assert len(states) == 0

    def test_state_change_unsubscribe(self, ws):
        """State change callback can be unsubscribed."""
        states = []

        def on_state(state):
            states.append(state)

        unsub = ws.on_state_change(on_state)

        ws._set_state(WebSocketState.CONNECTING)
        assert len(states) == 1

        unsub()

        ws._set_state(WebSocketState.CONNECTED)
        assert len(states) == 1  # still 1

    def test_is_connected_property(self, ws):
        """is_connected reflects the CONNECTED state."""
        assert ws.is_connected is False

        ws._set_state(WebSocketState.CONNECTING)
        assert ws.is_connected is False

        ws._set_state(WebSocketState.CONNECTED)
        assert ws.is_connected is True

        ws._set_state(WebSocketState.DISCONNECTED)
        assert ws.is_connected is False

    def test_state_callback_exception_does_not_crash(self, ws):
        """If a state callback raises, other listeners still fire."""
        states = []

        def bad_callback(state):
            raise RuntimeError("boom")

        def good_callback(state):
            states.append(state)

        ws.on_state_change(bad_callback)
        ws.on_state_change(good_callback)

        ws._set_state(WebSocketState.CONNECTING)

        assert len(states) == 1
        assert states[0] == WebSocketState.CONNECTING


# ---------------------------------------------------------------------------
# Tests — WebSocket URL construction
# ---------------------------------------------------------------------------


class TestWebSocketUrl:
    """Verify WebSocket URL construction for UniFi OS vs standalone."""

    def test_unifi_os_url(self, mock_session):
        """UniFi OS WebSocket URL includes /proxy/network prefix."""
        ws = UniFiWebSocket(
            host="192.168.1.1",
            port=443,
            site="default",
            session=mock_session,
            is_unifi_os=True,
        )
        # The URL is constructed in _connect; we verify the instance state
        assert ws._is_unifi_os is True
        assert ws._host == "192.168.1.1"
        assert ws._port == 443
        assert ws._site == "default"

    def test_standalone_url(self, mock_session):
        """Standalone controller WebSocket does NOT use /proxy/network."""
        ws = UniFiWebSocket(
            host="192.168.1.1",
            port=8443,
            site="default",
            session=mock_session,
            is_unifi_os=False,
        )
        assert ws._is_unifi_os is False
        assert ws._port == 8443


# ---------------------------------------------------------------------------
# Tests — WebSocketMessageType enum
# ---------------------------------------------------------------------------


class TestWebSocketMessageType:
    """Verify the message type enum values."""

    def test_known_types(self):
        assert WebSocketMessageType.DEVICE_SYNC == "device:sync"
        assert WebSocketMessageType.STA_SYNC == "sta:sync"
        assert WebSocketMessageType.USER_DELETE == "user:delete"
        assert WebSocketMessageType.EVENTS == "events"
        assert WebSocketMessageType.ALARM_ADD == "alarm:add"
        assert WebSocketMessageType.SPEED_TEST_UPDATE == "speed-test:update"

    def test_string_comparison(self):
        """Message type enum values compare equal to their string values."""
        assert WebSocketMessageType.DEVICE_SYNC == "device:sync"
        assert "device:sync" == WebSocketMessageType.DEVICE_SYNC
