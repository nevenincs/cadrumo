"""The one standard-input frame that carries a profile's provider credentials to the agent.

The frame is a single JSON object on one line::

    {"version":1,"credentials":{"<provider>":{"secret":"<value>","base_url":"<url>"}},"gateway_bearer":"<value>"}

``gateway_bearer`` is present only when the host was handed one: the bearer a
client of the agent's gateway presents. It is a secret under the same rules as
the provider credentials. The frame is assembled byte by byte into one mutable buffer so the caller can wipe it
after the write. Secrets are never decoded into ``str`` here; values that would
need JSON escaping are refused rather than escaped.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Final, override

CREDENTIAL_FRAME_VERSION: Final = 1
CREDENTIAL_FRAME_MAX_BYTES: Final = 64 * 1024

_PROVIDER_ID = re.compile(r"[a-z][a-z0-9_-]{0,63}")
# Printable ASCII without the two characters JSON would have to escape.
_PLAIN_BYTES: Final = frozenset(range(0x20, 0x7F)) - {ord('"'), ord("\\")}


class CredentialFrameRefusal(StrEnum):
    """Why a set of credentials cannot be carried in a frame."""

    PROVIDER_ID_INVALID = "provider_id_invalid"
    VALUE_INVALID = "value_invalid"
    BEARER_INVALID = "bearer_invalid"
    BASE_URL_INVALID = "base_url_invalid"
    TOO_LARGE = "too_large"


class CredentialFrameError(ValueError):
    """A typed refusal to build a frame; it never carries credential bytes."""

    def __init__(self, reason: CredentialFrameRefusal) -> None:
        """Keep only the closed reason."""
        super().__init__(reason.value)
        self.reason = reason


@dataclass(frozen=True, slots=True)
class AgentCredential:
    """One provider's resolved credential, held in a buffer its owner wipes."""

    secret: bytearray
    base_url: str | None = None

    @override
    def __repr__(self) -> str:
        """Never show the secret."""
        return f"AgentCredential(secret=<{len(self.secret)} bytes>, base_url={self.base_url!r})"


def build_credential_frame(
    credentials: Mapping[str, AgentCredential], *, gateway_bearer: bytearray | None = None
) -> bytearray:
    """Return the newline-terminated frame for these credentials, and any gateway bearer, in a fresh buffer.

    On refusal no partial buffer survives: it is wiped before the error leaves.
    """
    frame = bytearray(b'{"version":%d,"credentials":{' % CREDENTIAL_FRAME_VERSION)
    try:
        for index, provider in enumerate(sorted(credentials)):
            credential = credentials[provider]
            if not _PROVIDER_ID.fullmatch(provider):
                raise CredentialFrameError(CredentialFrameRefusal.PROVIDER_ID_INVALID)
            if not credential.secret or any(byte not in _PLAIN_BYTES for byte in credential.secret):
                raise CredentialFrameError(CredentialFrameRefusal.VALUE_INVALID)
            if index:
                frame += b","
            frame += b'"' + provider.encode("ascii") + b'":{"secret":"'
            frame += credential.secret
            frame += b'"'
            if credential.base_url is not None:
                encoded_url = _plain_ascii(credential.base_url)
                if encoded_url is None or not credential.base_url.startswith("https://"):
                    raise CredentialFrameError(CredentialFrameRefusal.BASE_URL_INVALID)
                frame += b',"base_url":"' + encoded_url + b'"'
            frame += b"}"
            if len(frame) > CREDENTIAL_FRAME_MAX_BYTES:
                raise CredentialFrameError(CredentialFrameRefusal.TOO_LARGE)
        frame += b"}"
        if gateway_bearer is not None:
            if not gateway_bearer or any(byte not in _PLAIN_BYTES for byte in gateway_bearer):
                raise CredentialFrameError(CredentialFrameRefusal.BEARER_INVALID)
            frame += b',"gateway_bearer":"'
            frame += gateway_bearer
            frame += b'"'
        frame += b"}\n"
        if len(frame) > CREDENTIAL_FRAME_MAX_BYTES:
            raise CredentialFrameError(CredentialFrameRefusal.TOO_LARGE)
    except BaseException:
        wipe(frame)
        raise
    return frame


def wipe(buffer: bytearray) -> None:
    """Overwrite a mutable buffer in place, then empty it."""
    buffer[:] = bytes(len(buffer))
    buffer.clear()


def _plain_ascii(value: str) -> bytes | None:
    try:
        encoded = value.encode("ascii")
    except UnicodeEncodeError:
        return None
    return encoded if all(byte in _PLAIN_BYTES for byte in encoded) else None
