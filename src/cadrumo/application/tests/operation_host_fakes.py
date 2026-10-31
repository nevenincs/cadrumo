"""Recording stand-ins for the supervisor's per-execution event and cancellation seams."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import datetime

from pydantic import BaseModel

from ...core.operations import OperationEffect


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
