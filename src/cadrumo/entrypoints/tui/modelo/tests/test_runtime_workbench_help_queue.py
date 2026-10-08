"""Worker-thread help reads retain exclusive ownership after UI cancellation."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from threading import Event, Lock
from typing import cast
from uuid import UUID, uuid4

import pytest

from .....adapters.local_runtime.frontend_client import RuntimeFrontendClient
from .....application.modelo.casilla_help import ModeloCasillaHelpCardV1
from .....application.modelo.declarations_workspace_contracts import DeclarationsWorkspaceDeclarationRefV1
from .....application.modelo.workbench_operations import ModeloCasillaHelpProjectionV1, ModeloCasillaHelpRequest
from .....application.operations.registry import OperationFrontendProjection
from .....application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from .....core.casilla_id import validated_casilla_id
from .....core.external_constants import OutputLanguage
from .....core.period import Period
from .....domain.modelos.work_unit import WorkUnitState
from .. import runtime_workbench_reads as reads

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]
_WORK_UNIT = "a" * 64


@dataclass
class _ClientIdentity:
    profile_id: UUID = field(default_factory=uuid4)
    session_id: UUID = field(default_factory=uuid4)
    frontend: OperationFrontendProjection = OperationFrontendProjection.TUI


class _ObservedLock:
    """Expose entry to the real thread lock without changing its acquisition rules."""

    def __init__(self) -> None:
        self.lock = Lock()
        self.counter_lock = Lock()
        self.queued = Event()
        self.attempts = 0

    def acquire(self, *, timeout: float) -> bool:
        with self.counter_lock:
            self.attempts += 1
            if self.attempts == 2:
                self.queued.set()
        return self.lock.acquire(timeout=timeout)

    def release(self) -> None:
        self.lock.release()


@dataclass
class _Clock:
    instant: float = 1000.0

    def monotonic(self) -> float:
        return self.instant


class _TransportBoundary:
    def __init__(self, clock: _Clock) -> None:
        self.clock = clock
        self.entered = Event()
        self.release = Event()
        self.calls: list[tuple[str, float, float]] = []
        self.active = 0
        self.max_active = 0
        self.guard = Lock()

    async def read(self, _client: RuntimeFrontendClient, **kwargs: object) -> ModeloCasillaHelpProjectionV1:
        payload = kwargs["payload"]
        deadline = kwargs["deadline"]
        assert isinstance(payload, ModeloCasillaHelpRequest)
        assert isinstance(deadline, float)
        with self.guard:
            self.calls.append((str(payload.casilla_id), deadline, self.clock.monotonic()))
            first = len(self.calls) == 1
            self.active += 1
            self.max_active = max(self.active, self.max_active)
        try:
            if first:
                self.entered.set()
                assert await asyncio.to_thread(self.release.wait, 5), "test did not release transport"
            return ModeloCasillaHelpProjectionV1(
                result_version=1,
                profile_id=payload.profile_id,
                work_unit_id=payload.work_unit_id,
                card=ModeloCasillaHelpCardV1(
                    casilla_id=payload.casilla_id,
                    formula=None,
                    quotes=(),
                    legal_basis=(),
                    constraints=(),
                    origins=(),
                    feeds=(),
                ),
            )
        finally:
            with self.guard:
                self.active -= 1


def _source(monkeypatch: pytest.MonkeyPatch):
    client = _ClientIdentity()
    clock = _Clock()
    gate = _ObservedLock()
    transport = _TransportBoundary(clock)
    monkeypatch.setattr(reads, "Lock", lambda: gate)
    monkeypatch.setattr(reads, "time", clock)
    monkeypatch.setattr(reads, "read_runtime_workbench_operation", transport.read)
    source = reads.RuntimeModeloWorkbenchSource(
        cast(RuntimeFrontendClient, client),
        DeclarationsWorkspaceDeclarationRefV1(
            work_unit_id=_WORK_UNIT,
            modelo="303",
            filing_year=2024,
            period=Period.from_year_and_code(2024, "1T"),
            state=WorkUnitState.BORRADOR,
            has_current_calculation=True,
            has_current_filing=False,
        ),
    )
    return source, client, clock, gate, transport


def _help(source: reads.RuntimeModeloWorkbenchSource, casilla: str) -> ModeloCasillaHelpCardV1:
    return source.help_card(
        validated_casilla_id(casilla, surface="test"),
        registry_revision_id="2024",
        calculation_revision_id=None,
        language=OutputLanguage.EN,
    )


async def _reached(event: Event) -> None:
    assert await asyncio.to_thread(event.wait, 5), "worker did not reach controlled boundary"


def test_cancelled_observer_keeps_running_help_exclusive(monkeypatch: pytest.MonkeyPatch) -> None:
    source, _, _, gate, transport = _source(monkeypatch)

    async def scenario() -> None:
        first = asyncio.create_task(asyncio.to_thread(_help, source, "01"))
        await _reached(transport.entered)
        first.cancel()
        with pytest.raises(asyncio.CancelledError):
            await first
        second = asyncio.create_task(asyncio.to_thread(_help, source, "02"))
        try:
            await _reached(gate.queued)
            assert len(transport.calls) == 1
            transport.release.set()
            assert (await asyncio.wait_for(second, 5)).casilla_id == "02"
        finally:
            transport.release.set()
            await asyncio.gather(second, return_exceptions=True)

    asyncio.run(scenario())
    assert [row[0] for row in transport.calls] == ["01", "02"]
    assert transport.max_active == 1


@pytest.mark.parametrize("changed_identity", ["session_id", "profile_id"])
def test_queued_help_rechecks_bound_identity(monkeypatch: pytest.MonkeyPatch, changed_identity: str) -> None:
    source, client, _, gate, transport = _source(monkeypatch)

    async def scenario() -> None:
        first = asyncio.create_task(asyncio.to_thread(_help, source, "01"))
        await _reached(transport.entered)
        second = asyncio.create_task(asyncio.to_thread(_help, source, "02"))
        try:
            await _reached(gate.queued)
            setattr(client, changed_identity, uuid4())
        finally:
            transport.release.set()
        outcomes = await asyncio.gather(first, second, return_exceptions=True)
        assert all(
            isinstance(outcome, RuntimeRefusalError) and outcome.reason is RuntimeRefusalCode.CONNECTION_CLOSED
            for outcome in outcomes
        )

    asyncio.run(scenario())
    assert len(transport.calls) == 1


def test_queue_and_transport_share_one_deadline(monkeypatch: pytest.MonkeyPatch) -> None:
    source, _, clock, gate, transport = _source(monkeypatch)

    async def scenario() -> None:
        first = asyncio.create_task(asyncio.to_thread(_help, source, "01"))
        await _reached(transport.entered)
        second = asyncio.create_task(asyncio.to_thread(_help, source, "02"))
        try:
            await _reached(gate.queued)
            clock.instant += 100
        finally:
            transport.release.set()
        await asyncio.gather(first, second)

    asyncio.run(scenario())
    assert transport.calls[1] == ("02", 1120.0, 1100.0)


def test_queue_timeout_never_starts_a_second_operation(monkeypatch: pytest.MonkeyPatch) -> None:
    source, _, _, _, transport = _source(monkeypatch)
    monkeypatch.setattr(reads, "_READ_TIMEOUT_SECONDS", 0.02)

    async def scenario() -> None:
        first = asyncio.create_task(asyncio.to_thread(_help, source, "01"))
        await _reached(transport.entered)
        try:
            with pytest.raises(RuntimeRefusalError) as raised:
                await asyncio.to_thread(_help, source, "02")
            assert raised.value.reason is RuntimeRefusalCode.DEADLINE_EXCEEDED
            assert len(transport.calls) == 1
        finally:
            transport.release.set()
            await first
        assert (await asyncio.to_thread(_help, source, "03")).casilla_id == "03"

    asyncio.run(scenario())
    assert [row[0] for row in transport.calls] == ["01", "03"]
