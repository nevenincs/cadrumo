"""Validate transient helper events without including their contents in failures."""

from __future__ import annotations

import contextlib
from queue import Empty, Full, Queue
from typing import BinaryIO, Literal
from urllib.parse import SplitResult, parse_qsl, urlsplit
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, JsonValue, field_validator

from ..providers.application.contracts import HelperCause, ServiceCause
from ..providers.application.next_steps import next_step_for

MAX_AUTH_LINE = 16 * 1024
TERMINAL_EVENTS = frozenset({"succeeded", "cancelled", "failed"})


class AuthEvent(BaseModel):
    """The agent's closed version-one login event; never a log record."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True, hide_input_in_errors=True)
    version: Literal[1]
    attempt_id: UUID
    provider: str
    event: Literal[
        "ready", "started", "browser_action", "authorization_code_required", "succeeded", "cancelled", "failed"
    ]
    reason: (
        Literal[
            "invalid_request",
            "host_disconnected",
            "timeout",
            "busy",
            "provider_unavailable",
            "provider_error",
            "unsupported_flow",
            "cleanup_failed",
            "profile_required",
        ]
        | None
    ) = None
    cause: HelperCause | None = None
    """The helper's closed word for why a terminal event is not a success."""
    url: str | None = Field(default=None, max_length=8192, repr=False)
    user_code: str | None = Field(default=None, pattern=r"^[A-Za-z0-9-]{4,32}$", repr=False)

    @field_validator("version", mode="before")
    @classmethod
    def integer_version(cls, value: object) -> object:
        """JSON true is not protocol version one."""
        if type(value) is not int:
            raise ValueError("invalid_version")
        return value


class AuthProtocol:
    """Correlate one bounded attempt and reject out-of-order or unsafe actions."""

    def __init__(self, provider: str) -> None:
        """Bind the stream to the requested canonical provider."""
        self.provider = provider
        self.attempt_id: UUID | None = None
        self.previous: str | None = None
        self.code_submitted = False

    def read(self, raw: bytes) -> AuthEvent:
        """Accept one framed event or raise a content-free protocol failure."""
        try:
            if len(raw) > MAX_AUTH_LINE or not raw.endswith(b"\n"):
                raise ValueError
            event = AuthEvent.model_validate_json(raw)
            self._correlate(event)
            self._validate_transition_state(event)
            if event.event == "browser_action":
                _validate_authorization_url(event.url)
            elif event.url is not None or event.user_code is not None:
                raise ValueError
            self.previous = event.event
            return event
        except (ValueError, RecursionError):
            raise ValueError("invalid_auth_event") from None

    def _validate_transition_state(self, event: AuthEvent) -> None:
        if self.previous in TERMINAL_EVENTS:
            raise ValueError
        if (event.reason is not None or event.cause is not None) and event.event not in {"failed", "cancelled"}:
            raise ValueError
        _validate_predecessor(event, self.previous)
        if event.event == "succeeded" and self.previous == "authorization_code_required" and not self.code_submitted:
            raise ValueError

    def _correlate(self, event: AuthEvent) -> None:
        if event.provider != self.provider:
            raise ValueError
        if self.previous is None:
            if event.event != "ready":
                raise ValueError
            self.attempt_id = event.attempt_id
        elif event.attempt_id != self.attempt_id or event.event == "ready":
            raise ValueError


def snapshot(
    attempt_id: str,
    provider: str,
    event: str,
    *,
    reason: str | None = None,
    cause: HelperCause | ServiceCause | None = None,
    status_cause: str | None = None,
) -> dict[str, JsonValue]:
    """Build a secret-free outcome; browser data is added only while awaiting login.

    ``cause`` and ``status_cause`` are closed words, and the next step is the
    one declared for the cause.
    """
    result: dict[str, JsonValue] = {"attempt_id": attempt_id, "provider": provider, "event": event}
    if reason is not None:
        result["reason"] = reason
    if cause is not None:
        result["cause"] = cause
        step = next_step_for(cause)
        if step is not None:
            result["next_step"] = step.value
    if status_cause is not None:
        result["status_cause"] = status_cause
    return result


_PREDECESSORS = {
    "started": frozenset({"ready"}),
    "browser_action": frozenset({"started", "browser_action"}),
    "authorization_code_required": frozenset({"browser_action"}),
    "succeeded": frozenset({"started", "browser_action", "authorization_code_required"}),
}


def _validate_predecessor(event: AuthEvent, previous: str | None) -> None:
    allowed = _PREDECESSORS.get(event.event)
    if allowed is not None and previous not in allowed:
        raise ValueError


def _validate_authorization_url(value: str | None) -> None:
    if value is None or any(ord(c) < 33 or ord(c) == 127 for c in value):
        raise ValueError
    url = urlsplit(value)
    _validate_authorization_origin(url)
    _validate_authorization_query(url.query)


def _validate_authorization_origin(url: SplitResult) -> None:
    if (
        url.scheme != "https"
        or url.hostname in (None, "")
        or url.username is not None
        or url.password is not None
        or url.fragment
    ):
        raise ValueError
    if url.port not in (None, 443):
        raise ValueError


def _validate_authorization_query(raw_query: str) -> None:
    query = [(key.lower(), value) for key, value in parse_qsl(raw_query, keep_blank_values=True)]
    if any(key in {"access_token", "refresh_token", "id_token"} for key, _ in query):
        raise ValueError
    codes = [value for key, value in query if key == "code"]
    # Some authorization pages use a boolean flow flag, never a returned code.
    if codes and codes != ["true"]:
        raise ValueError


def read_event_lines(stream: BinaryIO, queue: Queue[bytes | None]) -> None:
    """Queue the helper's output lines; an end, overlong or unterminated line ends the read with ``None``."""
    try:
        while True:
            line = stream.readline(MAX_AUTH_LINE + 1)
            queue.put_nowait(line or None)
            if not line or len(line) > MAX_AUTH_LINE or not line.endswith(b"\n"):
                return
    except (OSError, ValueError, Full):
        with contextlib.suppress(Empty):
            queue.get_nowait()
        with contextlib.suppress(Full):
            queue.put_nowait(None)
    finally:
        with contextlib.suppress(OSError, ValueError):
            stream.close()


def append_auth_code(line: bytearray, code: bytearray) -> None:
    """Escape the code into the action line in place, so no copy of it outlives the caller's wipe."""
    for byte in code:
        if byte in (34, 92):
            line.append(92)
        line.append(byte)
    line.extend(b'"}\n')
    if len(line) > 4096:
        raise ValueError("invalid_request")
