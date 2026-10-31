"""Event-recording execution authority and browser resources for capture operation tests."""

from __future__ import annotations

from collections.abc import AsyncGenerator, Generator
from contextlib import asynccontextmanager, contextmanager

from cadrumo_client.contracts.access_vocabulary import AccessAction


class RecordingExecutionAuthority:
    """Admit every operation and record each requirement and commit guard in ``events``."""

    def __init__(self, events: list[str]) -> None:
        self.events = events

    async def require(self, *, identity: object, request: object, action: AccessAction) -> None:
        assert identity is not None and request is not None
        self.events.append(f"require:{action.value}")

    @asynccontextmanager
    async def commit_guard(self, identity: object) -> AsyncGenerator[None]:
        assert identity is not None
        self.events.append("guard-enter")
        try:
            yield
        finally:
            self.events.append("guard-exit")


class RecordingResources:
    """Browser resources that record activation and closure without launching anything."""

    def __init__(self, events: list[str]) -> None:
        self.events = events
        self.closed = False
        self.close_calls = 0

    @contextmanager
    def activate(self) -> Generator[None]:
        self.events.append("resources-activate")
        try:
            yield
        finally:
            self.events.append("resources-deactivate")

    async def close(self) -> None:
        self.closed = True
        self.close_calls += 1
        self.events.append("resources-close")
