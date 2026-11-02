"""Recording stand-ins for the event and operand ports an operation executor receives."""

from __future__ import annotations

from pydantic import BaseModel

from ....core.operations import OperationEffect


class RecordingEvents:
    """Collect the effects an executor declares; phases carry no state here."""

    def __init__(self) -> None:
        self.effects: list[OperationEffect] = []

    async def phase(self, _phase: str) -> None:
        return None

    async def effect(self, effect: OperationEffect) -> None:
        self.effects.append(effect)


class RecordingOperands:
    """Keep the last operand an executor sealed and answer with a fixed reference."""

    value: BaseModel | None = None

    async def put(self, operand: BaseModel, *, written_at: object) -> str:
        self.value = operand
        return "d" * 64
