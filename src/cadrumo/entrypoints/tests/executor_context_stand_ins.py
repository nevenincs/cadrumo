"""Recording stand-ins for the pieces of the supervisor context an executor reads."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime

from pydantic import BaseModel

from ...core.hashing import content_hash_hex
from ...core.operations import OperationEffect


@dataclass(slots=True)
class RecordedEvents:
    """Phases and effects an executor reported."""

    phases: list[str] = field(default_factory=list)
    effects: list[OperationEffect] = field(default_factory=list)

    async def phase(self, phase_code: str) -> None:
        self.phases.append(phase_code)

    async def effect(self, effect: OperationEffect) -> None:
        self.effects.append(effect)


class UninterruptedCancellation:
    """A cancellation scope whose irreversible section never interrupts."""

    @asynccontextmanager
    async def irreversible_section(self) -> AsyncGenerator[None]:
        yield


@dataclass(slots=True)
class RecordedOperands:
    """Operand store that keeps every result an executor wrote."""

    results: list[BaseModel] = field(default_factory=list)

    async def put(self, operand: BaseModel, *, written_at: datetime) -> str:
        del written_at
        self.results.append(operand)
        return content_hash_hex({"operand": len(self.results)})
