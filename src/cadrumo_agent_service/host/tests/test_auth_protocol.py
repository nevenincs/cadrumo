"""Untrusted helper frames cannot cross attempts or disclose arbitrary content."""

from __future__ import annotations

import json
from uuid import uuid4

import pytest

from ..auth_protocol import MAX_AUTH_LINE, AuthProtocol

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _event(attempt: str, event: str, **fields: object) -> bytes:
    return (
        json.dumps({"version": 1, "attempt_id": attempt, "provider": "example", "event": event, **fields}) + "\n"
    ).encode()


def test_valid_browser_and_device_actions_follow_correlated_handshake() -> None:
    attempt = str(uuid4())
    protocol = AuthProtocol("example")
    for event in ("ready", "started"):
        assert protocol.read(_event(attempt, event)).event == event
    action = protocol.read(
        _event(attempt, "browser_action", url="https://example.org/login?state=opaque", user_code="ABCD-EFGH")
    )
    assert action.user_code == "ABCD-EFGH"
    assert "ABCD-EFGH" not in repr(action)
    assert "state=opaque" not in repr(action)
    assert protocol.read(_event(attempt, "succeeded")).event == "succeeded"
    with pytest.raises(ValueError, match=r"^invalid_auth_event$"):
        protocol.read(_event(attempt, "started"))


@pytest.mark.parametrize(
    "fields",
    [
        {"url": "http://example.org/login"},
        {"url": "https://user:secret@example.org/login"},
        {"url": "https://example.org/login#credential"},
        {"url": "https://example.org:444/login"},
        {"url": "https://example.org/\nlogin"},
        {"url": "file:///secret"},
        {"url": "https://example.org/login?access_token=secret"},
        {"url": "https://example.org/login?code=secret"},
        {"url": "https://example.org", "user_code": "sensitive arbitrary text"},
        {"url": "https://example.org", "provider": "other"},
        {"url": "https://example.org", "attempt_id": str(uuid4())},
        {"url": "https://example.org", "access_token": "secret"},
        {"url": "https://example.org", "version": True},
    ],
)
def test_invalid_actions_are_content_free(fields: dict[str, object]) -> None:
    attempt = str(uuid4())
    protocol = AuthProtocol("example")
    protocol.read(_event(attempt, "ready"))
    protocol.read(_event(attempt, "started"))
    with pytest.raises(ValueError, match=r"^invalid_auth_event$"):
        protocol.read(_event(attempt, "browser_action", **fields))


@pytest.mark.parametrize("event", ["started", "browser_action", "succeeded", "failed"])
def test_stream_requires_ready_first(event: str) -> None:
    with pytest.raises(ValueError, match=r"^invalid_auth_event$"):
        AuthProtocol("example").read(_event(str(uuid4()), event))


@pytest.mark.parametrize("raw", [b"private invalid output\n", b"x" * (MAX_AUTH_LINE + 1), b"{}"])
def test_malformed_frames_never_echo_contents(raw: bytes) -> None:
    with pytest.raises(ValueError, match=r"^invalid_auth_event$"):
        AuthProtocol("example").read(raw)
