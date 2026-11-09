"""A profile worker host drops the calendar work its list reads kept when a session ends and when it closes.

The host holds real composed operation services over the real journal; the
capture memory is the one those services were composed with.
"""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path
from typing import Any, cast

import pytest

from cadrumo.adapters.persistence.operations.tests.supervisor_test_support import (
    SUPERVISOR_NOW,
    IdleExecutor,
    operation_repositories,
    supervisor_registry,
)
from cadrumo.adapters.persistence.storage.master_key.profile_worker_custody import ProfileWorkerCustody
from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from cadrumo.application.operations.composition import compose_operation_services
from cadrumo.application.operations.tests.authority_test_support import unread_authority_operation
from cadrumo.application.workbench_capture_memory import WorkbenchCaptureMemory, WorkbenchCaptureMemoryOwner
from cadrumo.domain.calculations.registry.tests.shared_authority_isolation import isolated_shared_authority

from ...adapters.worker_authorization_client import WorkerAuthorizationClient
from ..operation_host import ProfileWorkerOperationHost

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_PROFILE = "44444444-4444-4444-8444-444444444444"


def _kept(memory: WorkbenchCaptureMemory) -> bool:
    """Whether the memory still stores and serves work: a second reuse of one key builds nothing."""
    key = cast(Any, object())
    builds: list[int] = []

    def build() -> Any:
        builds.append(1)
        return cast(Any, object())

    memory.calendar.reuse(key, build)
    memory.calendar.reuse(key, build)
    return len(builds) == 1


@pytest.mark.asyncio
async def test_a_session_end_and_the_host_close_drop_the_kept_calendar_work(tmp_path: Path) -> None:
    with isolated_shared_authority(tmp_path), isolated_runtime_profile(tmp_path=tmp_path) as profile:
        journal, leases, operands = operation_repositories(
            storage_root=tmp_path / "durable-state", profile_objects=profile.repository
        )
        owner = WorkbenchCaptureMemoryOwner()
        host = ProfileWorkerOperationHost(
            cast(ProfileWorkerCustody, object()), authorization=cast(WorkerAuthorizationClient, object())
        )
        host.services = compose_operation_services(
            registry=supervisor_registry(executor_type=IdleExecutor, build=IdleExecutor),
            authority_operation=unread_authority_operation(),
            journal=journal,
            reader=journal,
            event_stream=journal,
            leases=leases,
            operands=operands,
            owner_id="1" * 64,
            lease_token_factory=lambda: "2" * 64,
            clock=lambda: SUPERVISOR_NOW,
            lease_duration=timedelta(minutes=10),
            execution_timeout=timedelta(minutes=1),
            cleanup_timeout=timedelta(minutes=1),
            session_reads_end=owner.close,
        )
        signed_in = owner.for_profile(_PROFILE)
        assert _kept(signed_in), "an open memory reuses its work"

        host.end_session_reads()

        assert not _kept(signed_in), "a lock, sign-out or lapsed lease ends the reuse"
        next_session = owner.for_profile(_PROFILE)
        assert next_session is not signed_in
        assert _kept(next_session), "the next session starts an empty memory"

        await host.close()

        assert not _kept(next_session), "a closed host keeps nothing a read computed"
