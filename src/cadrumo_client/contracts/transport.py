"""Public transport observations, independent of profile admission and operations."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from .contracts import Peer


@dataclass(frozen=True)
class ConnectionContext:
    """Server-assigned connection identity and kernel-proven peer observations."""

    connection_id: UUID
    runtime_boot_id: UUID
    peer: Peer
    lifecycle_notices: bool = False
