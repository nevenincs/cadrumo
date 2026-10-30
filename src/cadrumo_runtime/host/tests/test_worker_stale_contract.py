"""A stale operation contract refuses that operation and leaves the profile worker serving.

The operation channel, its request loop, the registry that checks the shipped
manifest and the refusal frame are real. The registry's group builder composes
nothing, which is how a group that drifted from the manifest presents.
"""

from __future__ import annotations

import asyncio
import sys
import time
from collections.abc import Generator
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from typing import cast, override
from uuid import UUID, uuid4

import pytest

from cadrumo.adapters.persistence.storage.master_key.profile_worker_custody import ProfileWorkerCustody
from cadrumo.application.operations.contract_manifest import (
    ManifestOperationRegistry,
    OperationGroupBuild,
    load_operation_contract_manifest,
)
from cadrumo.application.operations.registry import OperationPublicDefinitionDescriptionV1
from cadrumo.application.user_profile.access_contracts import ProfileAccessBinding
from cadrumo_client.contracts.access_refusals import AccessDenialCode
from cadrumo_client.contracts.worker_identity import ProfileWorkerIdentity
from cadrumo_client.transport.frame_io import read_document, write_document
from cadrumo_client.transport.windows import WindowsEndpoint
from cadrumo_client.transport.windows_channel import WindowsChannel
from cadrumo_runtime.contracts.profile_worker import (
    ProfileWorkerContractRequest,
    ProfileWorkerRefusal,
    ProfileWorkerReply,
    ProfileWorkerRequest,
    ProfileWorkerSubmissionAbortRequest,
    ProfileWorkerUploadAccepted,
)

from .. import worker_operation_requests
from ..operation_host import ProfileWorkerOperationHost
from ..worker_submission_staging import WorkerSubmissionStaging

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires the native Windows transport"),
]

_IDENTITY = ProfileWorkerIdentity(
    worker_id=uuid4(),
    runtime_boot_id=uuid4(),
    binding=ProfileAccessBinding(
        profile_id=uuid4(),
        installation_id=uuid4(),
        os_owner_id="synthetic-owner",
        custody_generation=1,
        dek_epoch=uuid4(),
    ),
)


class _StaleHost(ProfileWorkerOperationHost):
    """Describe through a registry whose composed group drifted from the shipped manifest."""

    def __init__(self) -> None:
        self.custody = cast("ProfileWorkerCustody", SimpleNamespace(identity=_IDENTITY))
        self.registry = ManifestOperationRegistry.from_manifest(
            load_operation_contract_manifest(), lambda _group: OperationGroupBuild((), ())
        )

    @override
    def describe(self, session_id: UUID, definition_id: str) -> OperationPublicDefinitionDescriptionV1:
        return self.registry.describe_public_definition(definition_id)


@contextmanager
def _pair(tmp_path: Path) -> Generator[tuple[WindowsChannel, WindowsChannel]]:
    root = tmp_path / "cadrumo-storage"
    root.mkdir(parents=True)
    endpoint = WindowsEndpoint(storage_root=root)
    endpoint.listen()
    try:
        with ThreadPoolExecutor(max_workers=1) as pool:
            accepted = pool.submit(endpoint.accept, timeout=5)
            worker = endpoint.connect(timeout=5)
            runtime = accepted.result(timeout=5)
        try:
            yield worker, runtime
        finally:
            worker.close()
            runtime.close()
    finally:
        endpoint.close()


def test_a_stale_contract_is_refused_as_unavailable_and_the_worker_keeps_serving(tmp_path: Path) -> None:
    definition_id = load_operation_contract_manifest().operations[0].contract.definition_id

    def reply(runtime: WindowsChannel) -> object:
        return read_document(runtime, ProfileWorkerReply, deadline=time.monotonic() + 10).root

    async def scenario(worker: WindowsChannel, runtime: WindowsChannel) -> None:
        failed, changed = asyncio.Event(), asyncio.Event()
        uploads = WorkerSubmissionStaging()
        with ThreadPoolExecutor(max_workers=2, thread_name_prefix="profile-worker-input") as input_executor:
            serving = asyncio.create_task(
                worker_operation_requests.operate(worker, _StaleHost(), failed, uploads, changed, input_executor)
            )
            try:
                for _ in range(2):
                    stale = ProfileWorkerContractRequest(
                        request_id=uuid4(), session_id=uuid4(), definition_id=definition_id
                    )
                    write_document(runtime, ProfileWorkerRequest(stale), deadline=time.monotonic() + 5)
                    refusal = await asyncio.to_thread(reply, runtime)
                    assert isinstance(refusal, ProfileWorkerRefusal)
                    assert refusal.request_id == stale.request_id
                    assert refusal.reason is AccessDenialCode.OPERATION_UNAVAILABLE
                    assert not failed.is_set() and not serving.done()
                other = ProfileWorkerSubmissionAbortRequest(
                    request_id=uuid4(), upload_id=uuid4(), connection_id=uuid4(), session_id=uuid4()
                )
                write_document(runtime, ProfileWorkerRequest(other), deadline=time.monotonic() + 5)
                accepted = await asyncio.to_thread(reply, runtime)
                assert isinstance(accepted, ProfileWorkerUploadAccepted)
                assert accepted.request_id == other.request_id
                assert not failed.is_set() and not serving.done()
            finally:
                serving.cancel()
                await asyncio.gather(serving, return_exceptions=True)
                uploads.close()

    with _pair(tmp_path) as (worker, runtime):
        asyncio.run(scenario(worker, runtime))
