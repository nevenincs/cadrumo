"""A profile worker host drops the calendar work its list reads kept when the profile session ends."""

from __future__ import annotations

from typing import Any, cast

import pytest

from cadrumo.adapters.persistence.storage.master_key.profile_worker_custody import ProfileWorkerCustody
from cadrumo.domain.calculations.registry.tests.shared_authority_isolation import isolated_shared_authority
from cadrumo.entrypoints.workbench_generation_composition import _declaration_list_capture_memory

from ...adapters.worker_authorization_client import WorkerAuthorizationClient
from ..operation_host import ProfileWorkerOperationHost

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_PROFILE = "44444444-4444-4444-8444-444444444444"


@pytest.mark.asyncio
async def test_closing_the_host_drops_the_kept_calendar_work_and_a_fresh_read_recomputes(tmp_path) -> None:
    with isolated_shared_authority(tmp_path):
        host = ProfileWorkerOperationHost(
            cast(ProfileWorkerCustody, object()), authorization=cast(WorkerAuthorizationClient, object())
        )
        memory = _declaration_list_capture_memory(_PROFILE)
        key = cast(Any, object())
        built: list[int] = []

        def build() -> Any:
            built.append(1)
            return object()

        memory.calendar.reuse(key, build)
        memory.calendar.reuse(key, build)
        assert len(built) == 1, "an open memory reuses its work"

        await host.close()

        memory.calendar.reuse(key, build)
        memory.calendar.reuse(key, build)
        assert len(built) == 3, "the closed memory kept and stores nothing"
        fresh = _declaration_list_capture_memory(_PROFILE)
        assert fresh is not memory
        fresh.calendar.reuse(key, build)
        assert len(built) == 4, "a fresh read recomputes"
