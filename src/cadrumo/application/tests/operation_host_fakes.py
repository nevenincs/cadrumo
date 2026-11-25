"""Recording stand-ins for the supervisor's per-execution event and cancellation seams."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import datetime
from types import SimpleNamespace
from typing import cast
from uuid import UUID

from pydantic import BaseModel

from ...core.operations import OperationEffect, profile_operation_subject
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ..operations.models import OperationRequest
from ..operations.owner import OperationExecutorContext


class RecordingEvents:
    """Keep the fixed phase and effect facts an operation reports."""

    def __init__(self) -> None:
        self.phases: list[str] = []
        self.effects: list[OperationEffect] = []

    async def phase(self, value: str) -> None:
        self.phases.append(value)

    async def effect(self, value: OperationEffect) -> None:
        self.effects.append(value)


class IrreversibleSectionGrant:
    """Grant the irreversible section without a supervisor."""

    @asynccontextmanager
    async def irreversible_section(self) -> AsyncGenerator[None]:
        yield


class RecordingOperands:
    """Keep every operand an operation stores and answer with one fixed reference."""

    def __init__(self, reference: str) -> None:
        self.reference = reference
        self.stored: list[BaseModel] = []

    async def put(self, operand: BaseModel, *, written_at: datetime) -> str:
        assert written_at.tzinfo is not None
        self.stored.append(operand)
        return self.reference


def executor_context(
    definition_id: str,
    *,
    profile_id: str,
    operation: PinnedAuthorityOperation,
    cancellation: object,
    events: object,
    operands: object,
) -> OperationExecutorContext:
    """Bind the recording seams to one profile-subject execution."""
    return cast(
        OperationExecutorContext,
        SimpleNamespace(
            identity=SimpleNamespace(definition_id=definition_id, subject_ref=profile_operation_subject(profile_id)),
            authority_operation=operation,
            cancellation=cancellation,
            events=events,
            operands=operands,
        ),
    )


def profile_operation_request(
    payload: BaseModel, definition_id: str, profile_id: UUID | str
) -> OperationRequest[BaseModel]:
    return OperationRequest[BaseModel](
        definition_id=definition_id, subject_ref=profile_operation_subject(str(profile_id)), payload=payload
    )
