"""Exact ephemeral admission binding for a profile worker operation."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from pydantic import BaseModel

from cadrumo.application.operations.models import OperationRequest
from cadrumo.application.operations.provenance import OperationAdmissionProvenance
from cadrumo.application.operations.registry import OperationFrontendProjection


@dataclass(frozen=True, slots=True)
class WorkerOperationBinding:
    """Ephemeral admission identity; it is never reconstructed from a journal ID."""

    session_id: UUID
    frontend: OperationFrontendProjection
    request: OperationRequest[BaseModel]
    provenance: OperationAdmissionProvenance | None = None
