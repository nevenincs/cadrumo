"""The operation host composes its registry once, on its first operation.

A person's sign-in never composes the registry. The first operation does, off
the service loop; every concurrent caller joins that one composition, and
shutdown waits for it, so one worker never holds two supervisors or releases
its authority lease under a composition still using it.

The composition itself is replaced here: these cases isolate the host's own
once-only and shutdown bookkeeping, which is independent of what is composed.
"""

from __future__ import annotations

import asyncio
import threading
from datetime import timedelta
from typing import TYPE_CHECKING, cast, override

import pytest

from cadrumo.application.operations.composition import OperationComposedServices
from cadrumo.application.operations.drain import OperationDrainResult
from cadrumo.application.user_profile.automation_custody_port import AutomationCustodyError

from ..operation_host import ProfileWorkerOperationHost

if TYPE_CHECKING:
    from cadrumo.adapters.persistence.storage.master_key.profile_worker_custody import ProfileWorkerCustody

    from ...adapters.worker_authorization_client import WorkerAuthorizationClient

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


class _Supervisor:
    def in_flight_operation_count(self) -> int:
        return 0


class _Submission:
    supervisor = _Supervisor()


class _Services:
    """The two members the host reads from a composed graph outside an operation."""

    submission = _Submission()

    def __init__(self) -> None:
        self.drained: list[timedelta] = []

    async def drain(self, timeout: timedelta) -> OperationDrainResult:
        self.drained.append(timeout)
        return OperationDrainResult(unresolved=(), recovery_required=())


class _GatedHost(ProfileWorkerOperationHost):
    """Count compositions and hold each one until the case releases it."""

    def __init__(self, *, failures: int = 0) -> None:
        # Neither is read: composition bookkeeping and shutdown never touch custody or the runtime.
        super().__init__(
            cast("ProfileWorkerCustody", object()), authorization=cast("WorkerAuthorizationClient", object())
        )
        self.started = threading.Event()
        self.unblock = threading.Event()
        self.compositions = 0
        self._failures = failures

    @override
    def _compose(self) -> OperationComposedServices:
        self.compositions += 1
        self.started.set()
        self.unblock.wait(timeout=30)
        if self.compositions <= self._failures:
            raise RuntimeError("composition failed")
        return cast("OperationComposedServices", _Services())


def test_concurrent_first_operations_share_one_composition_off_the_loop() -> None:
    host = _GatedHost()

    async def two_first_operations() -> tuple[OperationComposedServices, OperationComposedServices]:
        first = asyncio.create_task(host._composed_off_loop())
        second = asyncio.create_task(host._composed_off_loop())
        assert await asyncio.to_thread(host.started.wait, 30)
        # The loop still runs other work while both callers wait.
        await asyncio.sleep(0)
        assert not first.done() and not second.done()
        host.unblock.set()
        return await first, await second

    first, second = asyncio.run(two_first_operations())

    assert host.compositions == 1
    assert first is second is host._composed()
    assert host.in_flight_operation_count() == 0


def test_a_host_without_operations_never_composes() -> None:
    host = _GatedHost()

    result = asyncio.run(host.close())

    assert host.compositions == 0
    assert not result.needs_containment


def test_shutdown_waits_for_a_composition_under_way_and_drains_it() -> None:
    host = _GatedHost()
    composing = threading.Thread(target=host._composed)
    composing.start()
    assert host.started.wait(timeout=30)

    async def close_while_composing() -> OperationDrainResult:
        closing = asyncio.create_task(host.close())
        await asyncio.sleep(0.05)
        assert not closing.done(), "shutdown released the host while its composition still ran"
        host.unblock.set()
        return await closing

    result = asyncio.run(close_while_composing())
    composing.join(timeout=30)

    assert not result.needs_containment
    services = cast("_Services", host._services)
    assert services.drained == [timedelta(seconds=5)]
    with pytest.raises(AutomationCustodyError):
        host._composed()


def test_a_failed_composition_is_raised_and_the_next_caller_composes_again() -> None:
    host = _GatedHost(failures=1)
    host.unblock.set()

    with pytest.raises(RuntimeError, match="composition failed"):
        host._composed()
    assert host._composed() is host._services
    assert host.compositions == 2
