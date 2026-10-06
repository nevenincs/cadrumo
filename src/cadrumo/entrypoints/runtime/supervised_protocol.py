"""Closed line grammar between a supervised runtime and the process that launched it.

Each message is one JSON object on one line, at most :data:`MAX_LINE_BYTES`
including its newline, discriminated by a closed ``type`` set. The launching
supervisor sends commands; the runtime sends announcements. No message carries
diagnostic text: refusals, busy replies and stops name bounded codes only.

A ``ready`` announcement is the launched process's own assertion. Client
readiness remains the authenticated transport handshake.
"""

from __future__ import annotations

import json
from enum import StrEnum
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, Field, TypeAdapter, ValidationError

from ...adapters.local_runtime.login_policy import RuntimeAdmissionPolicy
from ...application.runtime.contracts import RuntimeExitReason
from ...core.errors.hierarchy import CadrumoError
from ...core.hashing import reject_duplicate_json_members, reject_json_constant
from ...core.identity.digest import ContentDigest
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG

MAX_LINE_BYTES = 512
"""Upper bound of one protocol line in either direction, including the newline."""

_MAX_SEQUENCE = 2**53 - 1

type ProtocolSequence = Annotated[int, Field(ge=0, le=_MAX_SEQUENCE)]
type ProtocolCount = Annotated[int, Field(ge=0, le=_MAX_SEQUENCE)]


class SupervisorPing(BaseModel):
    """Ask for one heartbeat that echoes ``seq``."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    type: Literal["ping"] = "ping"
    seq: ProtocolSequence


class SupervisorStop(BaseModel):
    """Ask for the normal drain."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    type: Literal["stop"] = "stop"


class SupervisorStopIfIdle(BaseModel):
    """Ask for the normal drain only when no profile worker can hold work."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    type: Literal["stop-if-idle"] = "stop-if-idle"


class SupervisorSessionEnd(BaseModel):
    """Report that the desktop session is ending."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    type: Literal["session-end"] = "session-end"


type SupervisorCommand = Annotated[
    SupervisorPing | SupervisorStop | SupervisorStopIfIdle | SupervisorSessionEnd, Field(discriminator="type")
]


class RuntimeReady(BaseModel):
    """The runtime owns its endpoint and is accepting verified connections."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    type: Literal["ready"] = "ready"
    boot_id: UUID
    pid: Annotated[int, Field(gt=0, le=_MAX_SEQUENCE)]
    version: Annotated[str, Field(min_length=1, max_length=64)]
    storage_identity: ContentDigest
    admission: RuntimeAdmissionPolicy


class RuntimeHeartbeat(BaseModel):
    """Liveness evidence in reply to one ping.

    ``tick_age_ms`` is the time since the accept loop last turned, absent
    before the runtime serves. ``frontends`` counts open verified transport
    connections. ``hosted_profiles`` counts profile hosts, each owning the
    worker in which that profile's operations run. It is not an operation
    count or an idle decision: bootstrap custody may run without a worker.
    The runtime's stop-if-idle admission fence owns the final decision.
    """

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    type: Literal["heartbeat"] = "heartbeat"
    seq: ProtocolSequence
    tick_age_ms: ProtocolCount | None
    frontends: ProtocolCount
    hosted_profiles: ProtocolCount


class RuntimeStopping(BaseModel):
    """The runtime is ending for ``reason``; the exit code remains authoritative."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    type: Literal["stopping"] = "stopping"
    reason: RuntimeExitReason


class RuntimeBusy(BaseModel):
    """A ``stop-if-idle`` found possible work; admissions stay open."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    type: Literal["busy"] = "busy"


class SupervisorLineRefusal(StrEnum):
    """Why one supervisor line was refused; the line itself is never echoed."""

    MALFORMED = "malformed"
    OVERSIZED = "oversized"


class RuntimeRefused(BaseModel):
    """One supervisor line was refused; the channel stays open."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    type: Literal["refused"] = "refused"
    code: SupervisorLineRefusal


type RuntimeAnnouncement = Annotated[
    RuntimeReady | RuntimeHeartbeat | RuntimeStopping | RuntimeBusy | RuntimeRefused, Field(discriminator="type")
]

_COMMANDS: TypeAdapter[SupervisorCommand] = TypeAdapter(SupervisorCommand)


class SupervisorLineError(CadrumoError):
    """A supervisor line outside the closed grammar."""

    def __init__(self, code: SupervisorLineRefusal) -> None:
        """Keep only the bounded refusal code."""
        super().__init__(code.value)
        self.reason = code


def decode_supervisor_command(line: bytes) -> SupervisorCommand:
    """Parse one supervisor line without its newline, refusing anything outside the grammar."""
    if len(line) >= MAX_LINE_BYTES:
        raise SupervisorLineError(SupervisorLineRefusal.OVERSIZED)
    try:
        text = line.decode("ascii")
        parsed: object = json.loads(
            text, object_pairs_hook=reject_duplicate_json_members, parse_constant=reject_json_constant
        )
        return _COMMANDS.validate_python(parsed, strict=True)
    except (UnicodeDecodeError, ValueError, ValidationError):
        raise SupervisorLineError(SupervisorLineRefusal.MALFORMED) from None


def encode_runtime_announcement(message: RuntimeAnnouncement) -> bytes:
    """Return one bounded ASCII protocol line, newline included."""
    line = message.model_dump_json().encode("ascii") + b"\n"
    if len(line) > MAX_LINE_BYTES:
        raise ValueError("runtime announcement exceeds the protocol line bound")
    return line


class SupervisorLineFraming:
    """Split supervisor bytes into lines while holding at most one bounded line.

    A line longer than the bound is discarded through its newline and reported
    once as oversized, so memory stays bounded whatever the supervisor writes.
    """

    def __init__(self) -> None:
        """Start between lines."""
        self._buffer = bytearray()
        self._discarding = False

    def feed(self, chunk: bytes) -> list[bytes | SupervisorLineRefusal]:
        """Return each complete line, or a refusal in its place, in arrival order."""
        framed: list[bytes | SupervisorLineRefusal] = []
        self._buffer += chunk
        while (end := self._buffer.find(b"\n")) >= 0:
            line = bytes(self._buffer[:end])
            del self._buffer[: end + 1]
            if self._discarding or end + 1 > MAX_LINE_BYTES:
                self._discarding = False
                framed.append(SupervisorLineRefusal.OVERSIZED)
            else:
                framed.append(line)
        if len(self._buffer) >= MAX_LINE_BYTES:
            self._buffer.clear()
            self._discarding = True
        return framed
