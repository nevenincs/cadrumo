"""The operation host composes its registry once, on its first operation.

A person's sign-in never composes the registry. The first operation does, off
the service loop; every concurrent caller joins that one composition, and
shutdown waits for it, so one worker never holds two supervisors or releases
its authority lease under a composition still using it. An idle worker imports
the composition's graph beforehand: a composition waits for that import, a
sign-in does not.

The composition itself is replaced here: these cases isolate the host's own
once-only and shutdown bookkeeping, which is independent of what is composed.
"""

from __future__ import annotations

import asyncio
import threading
from datetime import timedelta
from pathlib import Path
from typing import TYPE_CHECKING, cast, override

import pytest

from cadrumo.application.operations.composition import OperationComposedServices
from cadrumo.application.operations.drain import OperationDrainResult
from cadrumo.domain.calculations.registry.tests.shared_authority_isolation import isolated_shared_authority
from cadrumo_client.contracts.automation_codes import AutomationCustodyError

from .. import operation_host
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
        first = asyncio.create_task(host.composed_off_loop())
        second = asyncio.create_task(host.composed_off_loop())
        assert await asyncio.to_thread(host.started.wait, 30)
        # The loop still runs other work while both callers wait.
        await asyncio.sleep(0)
        assert not first.done() and not second.done()
        host.unblock.set()
        return await first, await second

    first, second = asyncio.run(two_first_operations())

    assert host.compositions == 1
    assert first is second is host.composed()
    assert host.in_flight_operation_count() == 0


def test_a_host_without_operations_never_composes() -> None:
    host = _GatedHost()

    result = asyncio.run(host.close())

    assert host.compositions == 0
    assert not result.needs_containment


def test_shutdown_waits_for_a_composition_under_way_and_drains_it() -> None:
    host = _GatedHost()
    composing = threading.Thread(target=host.composed)
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
    services = cast("_Services", host.services)
    assert services.drained == [timedelta(seconds=5)]
    with pytest.raises(AutomationCustodyError):
        host.composed()


def test_a_failed_composition_is_raised_and_the_next_caller_composes_again() -> None:
    host = _GatedHost(failures=1)
    host.unblock.set()

    with pytest.raises(RuntimeError, match="composition failed"):
        host.composed()
    assert host.composed() is host.services
    assert host.compositions == 2


class _GatedImports:
    """Stand in for the idle import of the composition graph and hold it until the case releases it."""

    def __init__(self) -> None:
        self.started = threading.Event()
        self.unblock = threading.Event()
        self.imported: list[str] = []

    def __call__(self, name: str) -> object:
        self.started.set()
        self.unblock.wait(timeout=30)
        self.imported.append(name)
        return object()


def test_a_composition_waits_for_the_idle_imports_under_way(monkeypatch: pytest.MonkeyPatch) -> None:
    imports = _GatedImports()
    monkeypatch.setattr(operation_host, "import_module", imports)
    host = _GatedHost()
    host.unblock.set()
    warming = threading.Thread(target=host.warm_imports)
    warming.start()
    assert imports.started.wait(timeout=30)
    composing = threading.Thread(target=host.composed)
    composing.start()

    composing.join(timeout=0.2)
    assert composing.is_alive() and host.compositions == 0, "a composition raced the idle imports"
    imports.unblock.set()
    warming.join(timeout=30)
    composing.join(timeout=30)

    assert host.compositions == 1
    assert imports.imported, "the idle warm-up imported nothing"


def test_a_sign_in_reads_the_authority_while_the_idle_imports_run(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    imports = _GatedImports()
    monkeypatch.setattr(operation_host, "import_module", imports)
    with isolated_shared_authority(tmp_path):
        host = _GatedHost()
        warming = threading.Thread(target=host.warm_imports)
        warming.start()
        assert imports.started.wait(timeout=30)
        decoded: list[object] = []
        signing_in = threading.Thread(target=lambda: decoded.append(host.profile_decode_context()))
        signing_in.start()

        signing_in.join(timeout=30)
        try:
            assert decoded, "a sign-in's profile decode waited for the idle imports"
        finally:
            imports.unblock.set()
            warming.join(timeout=30)
            asyncio.run(host.close())


def test_a_composed_host_warms_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    imports = _GatedImports()
    imports.unblock.set()
    monkeypatch.setattr(operation_host, "import_module", imports)
    host = _GatedHost()
    host.unblock.set()
    host.composed()

    host.warm_imports()

    assert imports.imported == []
