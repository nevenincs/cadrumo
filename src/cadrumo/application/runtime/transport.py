"""Public transport observations, independent of profile admission and operations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal
from uuid import UUID

from pydantic import BaseModel

from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from .contracts import RuntimePeer


@dataclass(frozen=True)
class RuntimeConnectionContext:
    """Server-assigned connection identity and kernel-proven peer observations."""

    connection_id: UUID
    runtime_boot_id: UUID
    peer: RuntimePeer


class RuntimeStatusRequest(BaseModel):
    """Request only public runtime transport facts; carry no credential or profile."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    action: Literal["runtime_status"] = "runtime_status"
    request_id: UUID


class RuntimeTransportStatus(BaseModel):
    """Transport readiness does not authenticate a profile or grant execution."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    kind: Literal["runtime_status"] = "runtime_status"
    request_id: UUID
    runtime_boot_id: UUID
    connection_id: UUID
    accepting_connections: bool
