"""Recording stand-ins for the supervisor's per-execution event and cancellation seams."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

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
