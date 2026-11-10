"""A profile worker walks its grounding index in the background under its own lease.

A person's admission starts the walk; the first read then finds the index cached
for the worker's pinned generation. The walk defers to the worker requests being
served and resumes once they have been quiet for a moment. Shutdown abandons a walk under way and
waits for it before the lease closes. A walk that fails leaves only a value-free
diagnostic record, and the index is walked again on demand. Every case runs the
real walk and the real lease against a private copy of the published authority.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import cast

import pytest

from cadrumo.adapters.persistence.storage.master_key.profile_worker_custody import ProfileWorkerCustody
from cadrumo.core.diagnostic_log import diagnostic_process
from cadrumo.domain.calculations.registry import profile_grounding
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation
from cadrumo.domain.calculations.registry.schema import ModeloRevision
from cadrumo.domain.calculations.registry.tests.shared_authority_isolation import isolated_shared_authority
from cadrumo.tests.log_records import delivered_records

from ...adapters.worker_authorization_client import WorkerAuthorizationClient
from .. import operation_host
from ..operation_host import ProfileWorkerOperationHost, worker_request_served

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


@pytest.fixture(autouse=True)
def cold_grounding_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(profile_grounding, "_grounding_index_cache", {})
    monkeypatch.setattr(profile_grounding, "_grounding_index_flights", {})


def _host() -> ProfileWorkerOperationHost:
    # The walk reads only the pinned authority: no custody method or native
    # authorization may run on this path.
    return ProfileWorkerOperationHost(
        cast(ProfileWorkerCustody, object()), authorization=cast(WorkerAuthorizationClient, object())
    )


@pytest.mark.asyncio
async def test_admission_warm_up_caches_the_index_of_the_workers_own_generation(tmp_path: Path) -> None:
    with isolated_shared_authority(tmp_path) as database:
        host = _host()

        host.start_profile_grounding_warmup()
        warmup = host._grounding_warmup
        host.start_profile_grounding_warmup()
        assert warmup is not None and host._grounding_warmup is warmup
        await warmup

        generation = host.pinned().generation.logical_generation
        assert list(profile_grounding._grounding_index_cache) == [generation]
        with host.governed():
            index = profile_grounding.build_profile_grounding_index(host.pinned())
        assert index is profile_grounding._grounding_index_cache[generation]
        assert "censo.status" in index

        result = await host.close()
        assert not result.needs_containment
        # Windows refuses to delete a file a live connection holds.
        database.unlink()


@pytest.mark.asyncio
async def test_shutdown_abandons_a_walk_under_way_before_releasing_the_lease(tmp_path: Path) -> None:
    with isolated_shared_authority(tmp_path) as database:
        host = _host()
        host.start_profile_grounding_warmup()
        # Let the walk lease the authority and begin.
        async with asyncio.timeout(60):
            while not profile_grounding._grounding_index_flights:
                await asyncio.sleep(0.01)

        result = await host.close()

        assert not result.needs_containment
        assert host._grounding_warmup is not None and host._grounding_warmup.done()
        assert profile_grounding._grounding_index_cache == {}
        assert profile_grounding._grounding_index_flights == {}
        database.unlink()


@pytest.mark.asyncio
async def test_a_failed_walk_leaves_one_value_free_record_and_the_host_closes(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    with isolated_shared_authority(tmp_path) as database:
        canary = "synthetic-private-canary"
        # An unreadable publication: the lease the walk needs cannot be taken.
        database.write_bytes(canary.encode())
        host = _host()

        with diagnostic_process("profile_worker"), caplog.at_level(logging.DEBUG, logger=operation_host.__name__):
            host.start_profile_grounding_warmup()
            warmup = host._grounding_warmup
            assert warmup is not None
            await warmup

        records = [
            record
            for record in delivered_records(caplog, operation_host.__name__)
            if record.getMessage() == "profile_grounding_warmup_failed"
        ]
        assert len(records) == 1
        assert records[0].levelno == logging.ERROR
        assert records[0].exc_info is None
        rendered = "".join(str(value) for value in vars(records[0]).values())
        assert canary not in rendered
        assert str(tmp_path) not in rendered
        assert profile_grounding._grounding_index_cache == {}
        assert not (await host.close()).needs_containment


@pytest.mark.asyncio
async def test_the_warm_up_defers_to_a_served_request_and_completes_once_requests_are_quiet(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(operation_host, "_GROUNDING_WARMUP_QUIET_SECONDS", 0.2)
    decodes: list[str] = []
    decode = PinnedAuthorityOperation.revision

    def counted(operation: PinnedAuthorityOperation, modelo_id: str, revision_id: str) -> ModeloRevision:
        decodes.append(revision_id)
        return decode(operation, modelo_id, revision_id)

    # Observed, not replaced: every decode still runs the real component read.
    monkeypatch.setattr(PinnedAuthorityOperation, "revision", counted)
    with isolated_shared_authority(tmp_path) as database:
        host = _host()
        with worker_request_served():
            host.start_profile_grounding_warmup()
            warmup = host._grounding_warmup
            assert warmup is not None
            await asyncio.sleep(0.5)
            # Held before its first revision while the request is served: under way, nothing decoded or cached.
            assert not warmup.done()
            assert decodes == []
            assert list(profile_grounding._grounding_index_flights) == [host.pinned().generation.logical_generation]
            assert profile_grounding._grounding_index_cache == {}
        # Still quiet for less than the window: the walk keeps deferring.
        assert operation_host._grounding_deferred()
        async with asyncio.timeout(120):
            await warmup
        assert not operation_host._grounding_deferred()
        assert len(decodes) == len(host.pinned().revision_ids())
        assert list(profile_grounding._grounding_index_cache) == [host.pinned().generation.logical_generation]

        assert not (await host.close()).needs_containment
        database.unlink()
