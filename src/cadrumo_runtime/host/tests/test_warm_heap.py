"""A profile worker freezes its warm heap after the grounding walk and releases it with the session.

The real walk runs under the real lease against a private copy of the
published authority. The collector's permanent generation is process wide, so
each case restores the test session's own freeze afterwards.
"""

from __future__ import annotations

import gc
from collections.abc import Generator
from pathlib import Path
from typing import cast

import pytest

from cadrumo.adapters.persistence.storage.master_key.profile_worker_custody import ProfileWorkerCustody
from cadrumo.domain.calculations.registry import profile_grounding
from cadrumo.domain.calculations.registry.tests.shared_authority_isolation import isolated_shared_authority

from ...adapters.worker_authorization_client import WorkerAuthorizationClient
from ..operation_host import ProfileWorkerOperationHost
from ..warm_heap import WarmHeapFreeze

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


@pytest.fixture(autouse=True)
def unfrozen_collector(monkeypatch: pytest.MonkeyPatch) -> Generator[None]:
    monkeypatch.setattr(profile_grounding, "_grounding_index_cache", {})
    monkeypatch.setattr(profile_grounding, "_grounding_index_flights", {})
    gc.unfreeze()
    try:
        yield
    finally:
        gc.collect()
        gc.freeze()


def _host(warm_heap: WarmHeapFreeze | None) -> ProfileWorkerOperationHost:
    return ProfileWorkerOperationHost(
        cast(ProfileWorkerCustody, object()),
        authorization=cast(WorkerAuthorizationClient, object()),
        warm_heap=warm_heap,
    )


def test_a_freeze_collects_first_and_a_release_returns_every_object() -> None:
    warm_heap = WarmHeapFreeze()
    cycle: list[object] = []
    cycle.append(cycle)
    del cycle
    epoch = warm_heap.epoch
    warm_heap.freeze(epoch)
    frozen = gc.get_freeze_count()
    assert warm_heap.frozen and frozen > 0
    warm_heap.freeze(epoch)
    assert gc.get_freeze_count() == frozen
    warm_heap.release()
    assert not warm_heap.frozen and gc.get_freeze_count() == 0
    warm_heap.release()
    assert gc.get_freeze_count() == 0


def test_a_freeze_for_an_ended_epoch_freezes_nothing() -> None:
    warm_heap = WarmHeapFreeze()
    admitted = warm_heap.epoch
    warm_heap.release()
    warm_heap.freeze(admitted)
    assert not warm_heap.frozen and gc.get_freeze_count() == 0
    warm_heap.freeze(warm_heap.epoch)
    assert warm_heap.frozen
    warm_heap.release()


@pytest.mark.asyncio
async def test_the_walk_freezes_the_heap_until_the_session_ends_and_each_admission_freezes_again(
    tmp_path: Path,
) -> None:
    with isolated_shared_authority(tmp_path) as database:
        warm_heap = WarmHeapFreeze()
        host = _host(warm_heap)

        host.start_profile_grounding_warmup()
        first = host._grounding_warmup
        assert first is not None
        await first
        assert warm_heap.frozen and gc.get_freeze_count() > 0

        host.end_session_reads()
        assert not warm_heap.frozen and gc.get_freeze_count() == 0

        host.start_profile_grounding_warmup()
        second = host._grounding_warmup
        assert second is not None and second is not first
        await second
        assert warm_heap.frozen

        result = await host.close()
        assert not result.needs_containment
        assert not warm_heap.frozen and gc.get_freeze_count() == 0
        database.unlink()


@pytest.mark.asyncio
async def test_a_session_ended_during_the_walk_leaves_nothing_frozen_after_it(tmp_path: Path) -> None:
    with isolated_shared_authority(tmp_path) as database:
        warm_heap = WarmHeapFreeze()
        host = _host(warm_heap)

        host.start_profile_grounding_warmup()
        warmup = host._grounding_warmup
        assert warmup is not None and not warmup.done()
        host.end_session_reads()
        await warmup
        assert not warm_heap.frozen and gc.get_freeze_count() == 0

        await host.close()
        database.unlink()


@pytest.mark.asyncio
async def test_without_a_freeze_owner_nothing_is_frozen_and_the_walk_runs_once(tmp_path: Path) -> None:
    with isolated_shared_authority(tmp_path) as database:
        host = _host(None)

        host.start_profile_grounding_warmup()
        warmup = host._grounding_warmup
        assert warmup is not None
        await warmup
        host.start_profile_grounding_warmup()
        assert host._grounding_warmup is warmup
        assert gc.get_freeze_count() == 0

        await host.close()
        database.unlink()
