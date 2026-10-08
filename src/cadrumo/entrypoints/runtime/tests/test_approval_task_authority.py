"""A held approval publication permit belongs to its actual async task."""

from __future__ import annotations

import asyncio
import os
import sys
from collections.abc import AsyncGenerator, Iterator
from contextlib import asynccontextmanager, contextmanager
from pathlib import Path
from threading import Event
from typing import override
from uuid import uuid4

import pytest

from cadrumo.adapters.local_runtime.tests.profile_worker_support import changed, lease, worker_profiles
from cadrumo.adapters.local_runtime.worker_authorization_client import WorkerAuthorizationClient
from cadrumo.adapters.local_runtime.worker_authorization_lease import WorkerAuthorizationLease
from cadrumo.adapters.persistence.storage.master_key.profile_worker_custody import ProfileWorkerCustody
from cadrumo.application.operations.models import OperationIdentity, OperationRequest, new_operation_id
from cadrumo.application.operations.registry import OperationFrontendProjection, OperationRegistry
from cadrumo.application.runtime.approval_binding import RuntimeApprovalBinding
from cadrumo.application.runtime.profile_worker import ProfileWorkerIdentity
from cadrumo.application.runtime.worker_authorization import WorkerAuthorityRequest
from cadrumo.application.runtime.worker_enrollment import WorkerApprovalPublicationPhase
from cadrumo.application.user_profile.access_contracts import AccessAction, AccessScope, SessionKind
from cadrumo.application.user_profile.access_errors import ProfileAccessRefusedError
from cadrumo.application.user_profile.automation_enrollment import EnrollmentTransition
from cadrumo.application.user_profile.automation_operations import (
    AUTOMATION_APPROVE_OPERATION_DEFINITION_ID,
    AutomationOperationRequest,
    build_automation_operation_definitions,
    build_automation_operation_registrations,
)
from cadrumo.core.config import override_settings
from cadrumo.core.operations import profile_operation_subject
from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority
from cadrumo.entrypoints.adapter_composition import profile_adapter_composition
from cadrumo.entrypoints.runtime.operation_authority import ProfileWorkerOperationAuthority, WorkerOperationBinding
from cadrumo.tests.audited_process import run_audited_process

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


class HeldApprovalLease(WorkerAuthorizationLease):
    """Explicit permit boundary with publication paused at the native call site."""

    def __init__(
        self,
        *,
        identity: ProfileWorkerIdentity,
        root: Path,
        parent_pid: int,
        request: WorkerAuthorityRequest,
        entered: Event,
        release_publication: Event,
    ) -> None:
        super().__init__(identity=identity, root=root, parent_pid=parent_pid, request=request)
        self.entered = entered
        self.release_publication = release_publication
        self.active = True
        self.calls = 0

    @override
    def publish_approval(
        self, binding: RuntimeApprovalBinding, phase: WorkerApprovalPublicationPhase
    ) -> EnrollmentTransition | None:
        assert self.active and binding.operation_id == self.request.operation_id and phase == "commit_review"
        assert self.calls == 0
        self.calls += 1
        self.entered.set()
        assert self.release_publication.wait()
        assert self.active
        return None


class HeldAuthorizationClient(WorkerAuthorizationClient):
    """Guard test port: the production authority still owns task and custody checks."""

    def __init__(self, *, identity: ProfileWorkerIdentity, root: Path) -> None:
        super().__init__(identity=identity, root=root, parent_pid=os.getpid())
        self.entered = Event()
        self.release_publication = Event()
        self.release_publication.set()
        self.released = Event()
        self.leases: list[HeldApprovalLease] = []

    @override
    @asynccontextmanager
    async def guard(self, request: WorkerAuthorityRequest) -> AsyncGenerator[HeldApprovalLease]:
        held = HeldApprovalLease(
            identity=self.identity,
            root=self.root,
            parent_pid=self.parent_pid,
            request=request,
            entered=self.entered,
            release_publication=self.release_publication,
        )
        self.leases.append(held)
        try:
            yield held
        finally:
            held.active = False
            self.released.set()


def _registry() -> OperationRegistry:
    definitions = build_automation_operation_definitions()
    registrations = build_automation_operation_registrations(definitions)
    return OperationRegistry(
        definitions=tuple(sorted(definitions, key=lambda item: item.definition_id)),
        public_registrations=tuple(sorted(registrations, key=lambda item: item.contract.definition_id)),
    )


@contextmanager
def _authority(
    tmp_path: Path,
) -> Iterator[
    tuple[
        ProfileWorkerOperationAuthority,
        HeldAuthorizationClient,
        OperationIdentity,
        RuntimeApprovalBinding,
        ProfileWorkerCustody,
    ]
]:
    with profile_adapter_composition(), worker_profiles(tmp_path) as profiles:
        root, ((worker, key), _) = profiles
        with override_settings(cadrumo_local_storage_root=root, cadrumo_active_profile=str(worker.binding.profile_id)):
            custody = ProfileWorkerCustody(worker, storage_root=root)
            original = lease(worker)
            session = changed(
                original,
                kind=SessionKind.HUMAN,
                originating_login_id="synthetic-login",
                grant_id=None,
                grant_generation=None,
                key_id=None,
                key_generation=None,
                scope=AccessScope(
                    operations=frozenset({AUTOMATION_APPROVE_OPERATION_DEFINITION_ID}),
                    actions=frozenset(AccessAction),
                    disclosures=frozenset(),
                    periods=None,
                    allow_period_independent=True,
                    allow_delegation=False,
                ),
            )
            custody.install(session, bytearray(key))
            client = HeldAuthorizationClient(identity=worker, root=root)
            with bundled_indexed_authority().lease_operation() as pinned:
                authority = ProfileWorkerOperationAuthority(
                    custody=custody, client=client, registry=_registry(), authority_operation=pinned
                )
                request_id = uuid4()
                request = OperationRequest(
                    definition_id=AUTOMATION_APPROVE_OPERATION_DEFINITION_ID,
                    subject_ref=profile_operation_subject(str(worker.binding.profile_id)),
                    payload=AutomationOperationRequest(
                        profile_id=worker.binding.profile_id, request_id=request_id, review_digest="a" * 64
                    ),
                )
                identity = OperationIdentity(
                    operation_id=new_operation_id(),
                    definition_id=request.definition_id,
                    subject_ref=request.subject_ref,
                )
                authority.bind(
                    identity.operation_id,
                    WorkerOperationBinding(
                        session_id=session.session_id, frontend=OperationFrontendProjection.CLI, request=request
                    ),
                )
                binding = RuntimeApprovalBinding(
                    worker_id=worker.worker_id,
                    runtime_boot_id=worker.runtime_boot_id,
                    profile_binding=worker.binding,
                    connection_id=session.connection_id,
                    session_id=session.session_id,
                    operation_id=identity.operation_id,
                    enrollment_request_id=request_id,
                    review_digest="a" * 64,
                )
                try:
                    yield authority, client, identity, binding, custody
                finally:
                    custody.close()


async def _establish_provenance(authority: ProfileWorkerOperationAuthority, identity: OperationIdentity) -> None:
    async with authority.guard(identity, AccessAction.SUBMIT):
        provenance = authority.capture_provenance(identity)
        assert provenance.identity == identity


async def _exercise(tmp_path: Path) -> None:
    with _authority(tmp_path) as (authority, client, identity, binding, custody):
        await _establish_provenance(authority, identity)
        with pytest.raises(ProfileAccessRefusedError, match="operation_denied"):
            await authority.publish_approval(identity, binding, "commit_review")
        async with authority.commit_guard(identity):
            with pytest.raises(ProfileAccessRefusedError, match="operation_denied"):
                await authority.publish_approval(identity, binding, "decline")
            child = asyncio.create_task(authority.publish_approval(identity, binding, "commit_review"))
            with pytest.raises(ProfileAccessRefusedError, match="operation_denied"):
                await child
            other = identity.model_copy(update={"operation_id": new_operation_id()})
            with pytest.raises(ProfileAccessRefusedError, match="operation_denied"):
                await authority.publish_approval(other, binding, "commit_review")
            assert await authority.publish_approval(identity, binding, "commit_review") is None
        async with authority.guard(identity, AccessAction.START):
            with pytest.raises(ProfileAccessRefusedError, match="operation_denied"):
                await authority.publish_approval(identity, binding, "commit_review")
        with pytest.raises(ProfileAccessRefusedError, match="operation_denied"):
            await authority.publish_approval(identity, binding, "commit_review")
        assert sum(item.calls for item in client.leases) == 1
        client.entered.clear()
        client.released.clear()
        client.release_publication.clear()

        async def publish() -> None:
            async with authority.commit_guard(identity):
                await authority.publish_approval(identity, binding, "commit_review")

        task = asyncio.create_task(publish())
        try:
            while not client.entered.is_set():
                if task.done():
                    await task
                    pytest.fail("publication completed before entering its held boundary")
                await asyncio.sleep(0.01)
            task.cancel()
            await asyncio.sleep(0.02)
            assert not task.done() and not client.released.is_set()
            assert custody.require(binding.session_id).session_id == binding.session_id
        finally:
            client.release_publication.set()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert client.released.is_set()
        assert client.leases[-1].calls == 1 and not client.leases[-1].active


def test_exact_task_permit_and_cancellation_complete_publication(tmp_path: Path) -> None:
    """Keep the immutable worker binding inside its own process lifetime."""
    result = run_audited_process(
        [sys.executable, "-m", "cadrumo.entrypoints.runtime.tests.test_approval_task_authority", str(tmp_path)],
        capture_output=True,
        text=True,
        timeout=None,
        check=False,
    )
    assert result.returncode == 0, result.stderr


if __name__ == "__main__":
    asyncio.run(_exercise(Path(sys.argv[1])))
