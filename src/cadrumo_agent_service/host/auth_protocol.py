"""Validate transient helper events without including their contents in failures."""

from __future__ import annotations

from typing import Literal
from urllib.parse import parse_qsl, urlsplit
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, JsonValue, field_validator

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
            if event.provider != self.provider:
                raise ValueError
            if self.previous is None:
                if event.event != "ready":
                    raise ValueError
                self.attempt_id = event.attempt_id
            elif event.attempt_id != self.attempt_id or event.event == "ready":
                raise ValueError
            if self.previous in TERMINAL_EVENTS:
                raise ValueError
            if event.reason is not None and event.event not in {"failed", "cancelled"}:
                raise ValueError
            if event.event == "started" and self.previous != "ready":
                raise ValueError
            if event.event == "browser_action" and self.previous not in {"started", "browser_action"}:
                raise ValueError
            if event.event == "authorization_code_required" and self.previous != "browser_action":
                raise ValueError
            if event.event == "succeeded" and self.previous not in {
                "started",
                "browser_action",
                "authorization_code_required",
            }:
                raise ValueError
            if (
                event.event == "succeeded"
                and self.previous == "authorization_code_required"
                and not self.code_submitted
            ):
                raise ValueError
            if event.event == "browser_action":
                if event.url is None or any(ord(c) < 33 or ord(c) == 127 for c in event.url):
                    raise ValueError
                url = urlsplit(event.url)
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
                query = [(key.lower(), value) for key, value in parse_qsl(url.query, keep_blank_values=True)]
                if any(key in {"access_token", "refresh_token", "id_token"} for key, _ in query):
                    raise ValueError
                codes = [value for key, value in query if key == "code"]
                # Some authorization pages use a boolean flow flag, never a returned code.
                if codes and codes != ["true"]:
                    raise ValueError
            elif event.url is not None or event.user_code is not None:
                raise ValueError
            self.previous = event.event
            return event
        except (ValueError, RecursionError):
            raise ValueError("invalid_auth_event") from None


def snapshot(attempt_id: str, provider: str, event: str, *, reason: str | None = None) -> dict[str, JsonValue]:
    """Build a secret-free outcome; browser data is added only while awaiting login."""
    result: dict[str, JsonValue] = {"attempt_id": attempt_id, "provider": provider, "event": event}
    if reason is not None:
        result["reason"] = reason
    return result
