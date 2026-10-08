"""A profile worker host releases the shared registry authority when its lease closes, and only then.

The host takes its lifetime lease on the process-shared authority the first
time a governed capability needs it. An orderly close drops that lease and
then releases the owner; a close that leaves a local task needing containment
keeps the lease, so the owner stays open for that task; and a failure that
escapes the drain reaches the caller untouched and releases nothing. Every case
uses the real lease against a private copy of the published authority.
"""

from __future__ import annotations

import asyncio
from datetime import timedelta
from pathlib import Path
from typing import cast

import pytest

from cadrumo.adapters.local_runtime.worker_authorization_client import WorkerAuthorizationClient
from cadrumo.adapters.persistence.storage.master_key.profile_worker_custody import ProfileWorkerCustody
from cadrumo.application.operations.composition import OperationComposedServices
from cadrumo.application.operations.models import new_operation_id
from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority
from cadrumo.domain.calculations.registry.authority_store import AuthorityStoreError
from cadrumo.domain.calculations.registry.tests.shared_authority_isolation import isolated_shared_authority
from cadrumo.entrypoints.runtime.operation_host import ProfileWorkerOperationHost

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def _leased_host() -> ProfileWorkerOperationHost:
    # Only the authority lease is under test: no custody method or native
    # authorization may run on this path.
    host = ProfileWorkerOperationHost(
        cast(ProfileWorkerCustody, object()), authorization=cast(WorkerAuthorizationClient, object())
    )
    host.profile_decode_context()
    return host


@pytest.mark.asyncio
async def test_an_orderly_close_releases_the_shared_registry_authority(tmp_path: Path) -> None:
    with isolated_shared_authority(tmp_path) as database:
        served = bundled_indexed_authority()
        host = _leased_host()

        result = await host.close()

        assert not result.needs_containment
        with pytest.raises(AuthorityStoreError, match="closed"), served.operation():
            pass
        # Windows refuses to delete a file a live connection holds.
        database.unlink()


@pytest.mark.asyncio
async def test_a_close_that_needs_containment_keeps_the_shared_registry_authority(tmp_path: Path) -> None:
    with isolated_shared_authority(tmp_path):
        served = bundled_indexed_authority()
        host = _leased_host()
        projection = asyncio.create_task(asyncio.Event().wait())
        host._output_tasks[projection] = new_operation_id()
        try:
            result = await host.close()

            assert result.needs_containment
            with served.operation() as operation:
                assert operation.pin().logical_generation
        finally:
            projection.cancel()
            # The parent's containment ends the retained lease in production.
            host._lifetime.close()


class _FailingDrain:
    async def drain(self, timeout: timedelta) -> object:
        del timeout
        raise RuntimeError("operation drain failed")


@pytest.mark.asyncio
async def test_a_close_whose_drain_fails_leaves_the_shared_registry_authority_to_its_error(tmp_path: Path) -> None:
    with isolated_shared_authority(tmp_path):
        served = bundled_indexed_authority()
        host = _leased_host()
        # Only the drain's failure is under test; the services it would drain are not.
        host._services = cast(OperationComposedServices, _FailingDrain())
        try:
            with pytest.raises(RuntimeError, match="operation drain failed"):
                await host.close()

            with served.operation() as operation:
                assert operation.pin().logical_generation
        finally:
            host._lifetime.close()
