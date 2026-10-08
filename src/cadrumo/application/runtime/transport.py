"""Public transport observations, independent of profile admission and operations."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from .contracts import RuntimePeer


@dataclass(frozen=True)
class RuntimeConnectionContext:
    """Server-assigned connection identity and kernel-proven peer observations."""

    connection_id: UUID
    runtime_boot_id: UUID
    peer: RuntimePeer
    lifecycle_notices: bool = False
