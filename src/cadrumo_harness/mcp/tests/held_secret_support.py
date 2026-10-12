"""The secrets of one tool call over a held-secret source that records every read it is asked for."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from cadrumo_harness.mcp.session_acts import SessionSecrets


@dataclass
class HeldReads:
    """What a call asked of the credential store, in order."""

    verified: list[UUID] = field(default_factory=list[UUID])
    taken: list[UUID] = field(default_factory=list[UUID])


def call_secrets(arguments: dict[str, Any], held: dict[UUID, str] | None = None) -> tuple[SessionSecrets, HeldReads]:
    """Take the secrets out of one call's arguments, with ``held`` standing for the references the store holds."""
    store = held or {}
    reads = HeldReads()

    def verify(reference: UUID) -> None:
        if reference not in store:
            raise ValueError("no secret is held under that reference")
        reads.verified.append(reference)

    def take(reference: UUID) -> bytearray:
        if reference not in store:
            raise ValueError("no secret is held under that reference")
        reads.taken.append(reference)
        return bytearray(store[reference], "utf-8")

    return SessionSecrets(arguments, take=take, verify=verify), reads
