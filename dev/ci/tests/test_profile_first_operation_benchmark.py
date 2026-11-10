"""Scale benchmark: a person's first operation after sign-in beside the grounding warm-up.

A person's admission starts a background walk of the profile grounding index:
every published revision is decoded, several seconds of interpreter-bound work.
The first operations a frontend sends right after sign-in do not need that
index, but ran beside it: the startup journal inventory of a long-used profile
took about three times as long, and the first profile view 15 s of worker time
on a synthetic large-journal profile. The warm-up now defers to worker
requests and decodes only once they have been quiet for a moment.

Each scenario reads the startup inventory of a REAL synthetic journal through
the composed operation services, and walks the REAL registry of a private copy
of the published authority. ``alone`` has no walk; ``undeferred`` runs the walk
as it ran before, beside the inventory; ``deferred`` starts it through the real
worker host and serves the inventory as a worker request. Revision decodes are
only observed, never replaced.

The gates: the deferred walk begins no revision decode while the request is
served, and the request's process CPU-time stays near the inventory's own,
while the undeferred walk decodes during the same window. Wall-clock is printed
as an advisory.
"""

from __future__ import annotations

import asyncio
import statistics
import tempfile
import threading
import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import cast

import pytest

from cadrumo.adapters.persistence.storage.master_key.profile_worker_custody import ProfileWorkerCustody
from cadrumo.domain.calculations.registry import profile_grounding
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from cadrumo.domain.calculations.registry.schema import ModeloRevision
from cadrumo.domain.calculations.registry.tests.shared_authority_isolation import isolated_shared_authority
from cadrumo_runtime.adapters.worker_authorization_client import WorkerAuthorizationClient
from cadrumo_runtime.host.operation_host import ProfileWorkerOperationHost, worker_request_served

from ..perf_measurement import wall_advisory_message
from .test_operation_journal_inventory_benchmark import inventory_services, seed_settled_journal

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

#: About the 2,942 records of the synthetic large-journal profile APP-QA measured.
_RECORDS = 3_000
_SAMPLES = 3
#: The measured co-residency inflation of CPU-time on the workstation (see
#: ``perf_measurement``) plus a fixed allowance for the deferred walk's polling
#: and scheduling. The undeferred walk adds its decode CPU on top of the inventory's.
_CPU_INFLATION = 1.64
_CPU_ALLOWANCE_SECONDS = 0.25
_WALL_ADVISORY_SECONDS = 4.0
_WEDGE_WALL_TO_CPU_RATIO = 4.0
_WAIT_SECONDS = 120


@dataclass
class _ObservedDecodes:
    """Record when each real revision decode begins."""

    started: list[float] = field(default_factory=list)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def wrap(
        self, decode: Callable[[PinnedAuthorityOperation, str, str], ModeloRevision]
    ) -> Callable[[PinnedAuthorityOperation, str, str], ModeloRevision]:
        def observed(operation: PinnedAuthorityOperation, modelo_id: str, revision_id: str) -> ModeloRevision:
            with self._lock:
                self.started.append(time.monotonic())
            return decode(operation, modelo_id, revision_id)

        return observed

    def begun_within(self, start: float, end: float) -> int:
        with self._lock:
            return sum(1 for instant in self.started if start <= instant <= end)


@dataclass(frozen=True)
class _Window:
    cpu_seconds: float
    wall_seconds: float
    decodes_begun: int


@pytest.fixture(scope="module")
def scale_journal() -> Iterator[Path]:
    with tempfile.TemporaryDirectory(prefix="cadrumo-first-operation-") as directory:
        root = Path(directory)
        seed_settled_journal(root, _RECORDS)
        yield root


@pytest.fixture
def decodes(monkeypatch: pytest.MonkeyPatch) -> _ObservedDecodes:
    observed = _ObservedDecodes()
    monkeypatch.setattr(PinnedAuthorityOperation, "revision", observed.wrap(PinnedAuthorityOperation.revision))
    return observed


def _cold_grounding_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(profile_grounding, "_grounding_index_cache", {})
    monkeypatch.setattr(profile_grounding, "_grounding_index_flights", {})


async def _inventory_window(journal: Path, decodes: _ObservedDecodes) -> _Window:
    services = inventory_services(journal)
    cpu_started, wall_started = time.process_time(), time.monotonic()
    inventory = await services.recovery_inventory()
    cpu, wall_ended = time.process_time() - cpu_started, time.monotonic()
    assert len(inventory.entries) == _RECORDS
    return _Window(cpu, wall_ended - wall_started, decodes.begun_within(wall_started, wall_ended))


async def _alone(journal: Path, decodes: _ObservedDecodes) -> _Window:
    return await _inventory_window(journal, decodes)


async def _undeferred(journal: Path, decodes: _ObservedDecodes) -> _Window:
    """The walk as it ran before: beside the request, deferring to nothing."""
    stop = threading.Event()
    with bundled_indexed_authority().lease_operation() as operation:
        walk = asyncio.create_task(
            asyncio.to_thread(profile_grounding.warm_profile_grounding_index, operation, abandoned=stop.is_set)
        )
        async with asyncio.timeout(_WAIT_SECONDS):
            while not decodes.started:
                await asyncio.sleep(0.005)
        try:
            return await _inventory_window(journal, decodes)
        finally:
            stop.set()
            await walk


async def _deferred(journal: Path, decodes: _ObservedDecodes) -> _Window:
    """The walk a person's admission starts, beside the same request served by the real host."""
    # The walk reads only the pinned authority; no custody or authorization runs on this path.
    host = ProfileWorkerOperationHost(
        cast(ProfileWorkerCustody, object()), authorization=cast(WorkerAuthorizationClient, object())
    )
    try:
        host.start_profile_grounding_warmup()
        with worker_request_served():
            window = await _inventory_window(journal, decodes)
        warmup = host._grounding_warmup
        assert warmup is not None
        async with asyncio.timeout(_WAIT_SECONDS):
            await warmup
        # Deferring never costs the index: once requests are quiet the walk completes and caches it.
        assert list(profile_grounding._grounding_index_cache) == [host.pinned().generation.logical_generation]
        return window
    finally:
        assert not (await host.close()).needs_containment


def _median(windows: list[_Window], measure: Callable[[_Window], float]) -> float:
    return statistics.median(measure(window) for window in windows)


@pytest.mark.perf
@pytest.mark.serial
def test_first_operation_after_sign_in_is_not_slowed_by_the_grounding_warm_up(
    scale_journal: Path, decodes: _ObservedDecodes, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The deferred walk leaves a long-used profile's first request near its own cost."""
    measured: dict[str, list[_Window]] = {"alone": [], "undeferred": [], "deferred": []}
    with isolated_shared_authority(tmp_path) as database:
        for _ in range(_SAMPLES):
            for name, scenario in (("alone", _alone), ("undeferred", _undeferred), ("deferred", _deferred)):
                _cold_grounding_cache(monkeypatch)
                measured[name].append(asyncio.run(scenario(scale_journal, decodes)))
        # Windows refuses to delete a file a live connection holds.
        database.unlink()

    cpu = {name: _median(windows, lambda window: window.cpu_seconds) for name, windows in measured.items()}
    wall = {name: _median(windows, lambda window: window.wall_seconds) for name, windows in measured.items()}
    ceiling = cpu["alone"] * _CPU_INFLATION + _CPU_ALLOWANCE_SECONDS
    print(
        f"\n[bench] profile_first_operation: records={_RECORDS} "
        + " ".join(f"{name}_cpu={cpu[name]:.3f}s {name}_wall={wall[name]:.3f}s" for name in measured)
        + f" gate=deferred_cpu<{ceiling:.3f}s (wall advisory)"
    )
    wall_advisory_message(
        "profile_first_operation deferred median",
        wall_seconds=wall["deferred"],
        cpu_seconds=cpu["deferred"],
        wall_advisory_seconds=_WALL_ADVISORY_SECONDS,
        hang_wall_to_cpu_ratio=_WEDGE_WALL_TO_CPU_RATIO,
    )
    # The scenario reproduces the defect: undeferred, the walk decodes while the request is served.
    assert all(window.decodes_begun > 0 for window in measured["undeferred"]), measured["undeferred"]
    assert all(window.decodes_begun == 0 for window in measured["deferred"]), measured["deferred"]
    assert cpu["deferred"] < ceiling, (
        f"first request beside the deferred warm-up took {cpu['deferred']:.3f} CPU-s, over {ceiling:.3f} CPU-s "
        f"(the inventory alone {cpu['alone']:.3f} CPU-s; samples={measured!r})"
    )
