"""Event-recording execution authority and browser resources for capture operation tests."""

from __future__ import annotations

from collections.abc import AsyncGenerator, Generator
from contextlib import asynccontextmanager, contextmanager

from cadrumo_client.contracts.access_refusals import AccessDenialCode
from cadrumo_client.contracts.access_vocabulary import AccessAction

from ...application.user_profile.access_errors import ProfileAccessRefusedError


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


class FencedExecutionAuthority:
    """Admit every operation, number each commit guard, and optionally refuse one of them.

    Guard entry and exit are recorded in ``events`` with the guard's number,
    and ``guard_depth`` is the count of guards open now.
    """

    def __init__(self, events: list[str], *, refuse_guard: int | None = None) -> None:
        self.events = events
        self.refuse_guard = refuse_guard
        self.guard_calls = 0
        self.guard_depth = 0

    async def require(self, *, identity: object, request: object, action: AccessAction) -> None:
        assert identity is not None and request is not None
        self.events.append(f"require:{action.value}")

    @asynccontextmanager
    async def commit_guard(self, identity: object) -> AsyncGenerator[None]:
        assert identity is not None
        self.guard_calls += 1
        guard_number = self.guard_calls
        self.events.append(f"commit-guard-enter:{guard_number}")
        if guard_number == self.refuse_guard:
            self.events.append(f"commit-guard-refused:{guard_number}")
            raise ProfileAccessRefusedError(AccessDenialCode.GRANT_INACTIVE)
        self.guard_depth += 1
        try:
            yield
        finally:
            self.guard_depth -= 1
            self.events.append(f"commit-guard-exit:{guard_number}")


class ObservableBrowserResources:
    """Synthetic browser process whose single activation and cleanup are observable in ``events``."""

    def __init__(self, events: list[str]) -> None:
        self.events = events
        self.active = False
        self.closed = False
        self.close_calls = 0

    @contextmanager
    def activate(self) -> Generator[None]:
        assert not self.active
        self.active = True
        self.events.append("browser-activate")
        try:
            yield
        finally:
            self.active = False
            self.events.append("browser-deactivate")

    async def close(self) -> None:
        assert not self.active
        self.closed = True
        self.close_calls += 1
        self.events.append("browser-close")
