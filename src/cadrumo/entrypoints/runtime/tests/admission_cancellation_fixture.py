"""Isolated profile-worker proof that cancelled admission finishes its real journal write."""

from __future__ import annotations

import asyncio
import os
import sys
from collections.abc import AsyncGenerator
from contextlib import ExitStack, asynccontextmanager
from pathlib import Path
from threading import Event
from typing import override

from cadrumo.adapters.local_runtime.tests.profile_worker_support import lease, worker_profiles
from cadrumo.adapters.local_runtime.worker_authorization_client import WorkerAuthorizationClient
from cadrumo.adapters.local_runtime.worker_authorization_lease import WorkerAuthorizationLease
from cadrumo.adapters.persistence.operations.journal import OperationJournalRepository
from cadrumo.adapters.persistence.storage.master_key.profile_worker_custody import ProfileWorkerCustody
from cadrumo.application.operations.composition import OperationComposedServices
from cadrumo.application.operations.models import OperationRequest
from cadrumo.application.operations.persistence.journal import OperationPersistedSnapshot
from cadrumo.application.operations.persistence.leases import OperationOwnerLease
from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.runtime.profile_worker import ProfileWorkerIdentity
from cadrumo.application.runtime.worker_authorization import (
    WorkerAuthorityRequest,
    WorkerAutomationInventoryRequest,
    WorkerResponseScopeRequest,
)
from cadrumo.application.user_profile.access_contracts import AccessAction, AccessDenialCode
from cadrumo.application.user_profile.access_errors import ProfileAccessRefusedError
from cadrumo.application.user_profile.automation_enrollment import AutomationInventory
from cadrumo.application.user_profile.profile_operation_contracts import ProfileFieldMutationOperationRequest
from cadrumo.application.user_profile.profile_record_repository import ProfileRecordRepository
from cadrumo.application.user_profile.projections import record_to_path_values
from cadrumo.core.config import override_settings
from cadrumo.core.operations import OperationLifecycle, OperationTerminalCondition
from cadrumo.domain.user_profile.setup_answers import PROFILE_OUTPUT_LANGUAGE_PATH
from cadrumo.entrypoints.adapter_composition import profile_adapter_composition
from cadrumo.entrypoints.operation_composition import compose_operation_dependencies
from cadrumo.entrypoints.runtime.operation_host import ProfileWorkerOperationHost


class PausedJournal(OperationJournalRepository):
    """Pause after the real encrypted journal create has persisted its snapshot."""

    def __init__(self, *, storage_root: Path) -> None:
        super().__init__(storage_root=storage_root)
        self.persisted = Event()
        self.release = Event()
        self.created: list[str] = []

    @override
    async def create(self, snapshot: OperationPersistedSnapshot, *, lease: OperationOwnerLease) -> str:
        operation_id = await super().create(snapshot, lease=lease)
        self.created.append(operation_id)
        self.persisted.set()
        if not await asyncio.to_thread(self.release.wait, 10):
            raise TimeoutError("paused journal was not released")
        return operation_id


class FaultAuthorizationClient(WorkerAuthorizationClient):
    """Grant explicit test authority while recording the held admission fence."""

    def __init__(self, *, identity: ProfileWorkerIdentity, root: Path) -> None:
        super().__init__(identity=identity, root=root, parent_pid=os.getpid())
        self.held: set[AccessAction] = set()

    @override
    @asynccontextmanager
    async def guard(self, request: WorkerAuthorityRequest) -> AsyncGenerator[WorkerAuthorizationLease]:
        if isinstance(request, WorkerResponseScopeRequest):
            raise ProfileAccessRefusedError(AccessDenialCode.RESPONSE_AUTHORITY_REQUIRED)
        action = request.request.action
        self.held.add(action)
        try:
            yield WorkerAuthorizationLease(
                identity=self.identity, root=self.root, parent_pid=self.parent_pid, request=request
            )
        finally:
            self.held.remove(action)

    @override
    async def inventory(self, request: WorkerAutomationInventoryRequest) -> AutomationInventory:
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)


class PausedHost(ProfileWorkerOperationHost):
    """Use the production graph with one instance-local journal fault port."""

    def __init__(self, custody: ProfileWorkerCustody, *, authorization: FaultAuthorizationClient) -> None:
        super().__init__(custody, authorization=authorization)
        self.paused_journal = PausedJournal(storage_root=custody.root)

    @override
    def _composed(self) -> OperationComposedServices:
        if self._services is None:
            services = compose_operation_dependencies(
                authority_operation=self._pinned(), execution_authority_factory=self._bind_execution
            )
            services.submission.supervisor._journal = self.paused_journal
            self._services = services
        return super()._composed()


async def _exercise_composed(tmp_path: Path) -> None:
    with worker_profiles(tmp_path) as profiles:
        root, ((identity, key), _) = profiles
        route = ExitStack()
        route.enter_context(
            override_settings(cadrumo_local_storage_root=root, cadrumo_active_profile=str(identity.binding.profile_id))
        )
        custody = ProfileWorkerCustody(identity, storage_root=root)
        session = lease(identity)
        custody.install(session, bytearray(key))
        client = FaultAuthorizationClient(identity=identity, root=root)
        host = PausedHost(custody, authorization=client)
        try:
            baseline = ProfileRecordRepository.for_current_session(
                identity.binding.profile_id, profile_decode_context=host.profile_decode_context()
            ).load(identity.binding.profile_id)
            request = OperationRequest(
                definition_id="user-profile.field-mutation",
                subject_ref=f"profile:{identity.binding.profile_id}",
                payload=ProfileFieldMutationOperationRequest(
                    profile_id=identity.binding.profile_id,
                    expected_revision=baseline.record_revision,
                    expected_content_digest=baseline.content_digest,
                    path=PROFILE_OUTPUT_LANGUAGE_PATH,
                    value="es",
                ),
                idempotency_key="cancelled-admission",
            )
            # Finish fixture startup before timing the journal cancellation
            # boundary; lazy registry composition can outlast its pause budget.
            host._composed()
            submitting = asyncio.create_task(
                host.submit(session_id=session.session_id, frontend=OperationFrontendProjection.MCP, request=request)
            )
            try:
                if not await asyncio.to_thread(host.paused_journal.persisted.wait, 10):
                    await submitting
                    raise AssertionError("journal create did not persist within the bound")
                operation_id = host.paused_journal.created[0]
                submitting.cancel()
                await asyncio.sleep(0.02)
                submitting.cancel()
                await asyncio.sleep(0.02)
                assert not submitting.done()
                assert AccessAction.SUBMIT in client.held
                assert custody.require(session.session_id) == session
                snapshot = await OperationJournalRepository(storage_root=root).load(operation_id)
                assert snapshot.identity.operation_id == operation_id
                assert snapshot.lifecycle is OperationLifecycle.CREATED
            finally:
                host.paused_journal.release.set()
            try:
                await asyncio.wait_for(submitting, 10)
            except asyncio.CancelledError:
                pass
            else:
                raise AssertionError("cancelled caller unexpectedly received an admission receipt")

            assert AccessAction.SUBMIT not in client.held
            assert await host.start(operation_id, session.session_id) == operation_id
            await asyncio.wait_for(host._composed().submission.settled(operation_id), 20)
            settled = await OperationJournalRepository(storage_root=root).load(operation_id)
            record = ProfileRecordRepository.for_current_session(
                identity.binding.profile_id, profile_decode_context=host.profile_decode_context()
            ).load(identity.binding.profile_id)
            assert settled.terminal_condition is OperationTerminalCondition.SUCCEEDED, settled.terminal_receipt
            assert record_to_path_values(record)[PROFILE_OUTPUT_LANGUAGE_PATH] == "es"

            replay = await host.submit(
                session_id=session.session_id, frontend=OperationFrontendProjection.MCP, request=request
            )
            assert replay.receipt.operation_id == operation_id
            assert replay.response_capability is None
            assert host.paused_journal.created == [operation_id]
        finally:
            host.paused_journal.release.set()
            await host.close()
            custody.close()
            route.close()


async def exercise(tmp_path: Path) -> None:
    with profile_adapter_composition():
        await _exercise_composed(tmp_path)


async def exercise_lazy_close(tmp_path: Path) -> None:
    """Open the publication during submit, then close it from the owning caller."""
    with profile_adapter_composition(), worker_profiles(tmp_path) as profiles:
        root, ((identity, key), _) = profiles
        with override_settings(
            cadrumo_local_storage_root=root, cadrumo_active_profile=str(identity.binding.profile_id)
        ):
            custody = ProfileWorkerCustody(identity, storage_root=root)
            session = lease(identity)
            custody.install(session, bytearray(key))
            host = ProfileWorkerOperationHost(
                custody, authorization=FaultAuthorizationClient(identity=identity, root=root)
            )
            try:
                baseline = ProfileRecordRepository.for_current_session(
                    identity.binding.profile_id, profile_decode_context=host.profile_decode_context()
                ).load(identity.binding.profile_id)
                request = OperationRequest(
                    definition_id="user-profile.field-mutation",
                    subject_ref=f"profile:{identity.binding.profile_id}",
                    payload=ProfileFieldMutationOperationRequest(
                        profile_id=identity.binding.profile_id,
                        expected_revision=baseline.record_revision,
                        expected_content_digest=baseline.content_digest,
                        path=PROFILE_OUTPUT_LANGUAGE_PATH,
                        value="es",
                    ),
                )
                submitted = await asyncio.create_task(
                    host.submit(
                        session_id=session.session_id, frontend=OperationFrontendProjection.MCP, request=request
                    )
                )
                assert submitted.receipt.operation_id
                snapshot = await OperationJournalRepository(storage_root=root).load(submitted.receipt.operation_id)
                assert snapshot.lifecycle is OperationLifecycle.CREATED
            finally:
                await host.close()
                custody.close()


if __name__ == "__main__":
    if sys.argv[2] == "lazy-close":
        asyncio.run(exercise_lazy_close(Path(sys.argv[1])))
    else:
        asyncio.run(exercise(Path(sys.argv[1])))
