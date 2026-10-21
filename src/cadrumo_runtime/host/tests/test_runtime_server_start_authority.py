"""Which operations' COMMIT fence may ask the runtime to start the model program's server.

The real worker authority, registry and resolver dispatch run here; custody
and the authorization client are explicit witnesses, as in the scope-resolution
tests, so the held lease records the start it is asked for instead of sending
it over a native channel. The native channel and the runtime side are covered
by the Windows containment tests of the owner-started server.
"""

from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncGenerator, Generator
from contextlib import asynccontextmanager, contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import override
from uuid import UUID, uuid4

import pytest
from pydantic import BaseModel

from cadrumo.adapters.persistence.storage.master_key.profile_worker_custody import ProfileWorkerCustody
from cadrumo.application.operations.access_resolution import (
    OperationAccessContext,
    ResolvedOperationAccess,
    bind_operation_access,
)
from cadrumo.application.operations.capabilities import RECORDED_IDEMPOTENT_JOURNALED_READ_CAPABILITIES
from cadrumo.application.operations.models import (
    CredentialFreeOperationRequest,
    OperationIdentity,
    OperationRequest,
    new_operation_id,
)
from cadrumo.application.operations.operation_definition import build_single_phase_definition
from cadrumo.application.operations.owner import OperationExecutorContext
from cadrumo.application.operations.registry import (
    OperationFrontendProjection,
    OperationPublicDefinitionRegistrationV1,
    OperationRegistry,
)
from cadrumo.application.operations.subject_reference import OperationSubjectReferenceV1
from cadrumo.application.user_profile.access_contracts import (
    AccessSession,
    ProfileAccessBinding,
    SessionKind,
    SessionState,
)
from cadrumo.application.user_profile.access_errors import ProfileAccessRefusedError
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation
from cadrumo_client.contracts.access_refusals import AccessDenialCode
from cadrumo_client.contracts.access_vocabulary import AccessAction, AccessScope, Availability
from cadrumo_client.contracts.operation_ids import (
    DEPENDENCIES_SETUP_OPERATION_DEFINITION_ID,
    LOCAL_READER_OPERATION_DEFINITION_ID,
)
from cadrumo_client.contracts.worker_identity import ProfileWorkerIdentity
from cadrumo_runtime.contracts.worker_authorization import WorkerAuthorityRequest

from ...adapters.worker_authorization import runtime_server_start_definitions
from ...adapters.worker_authorization_client import WorkerAuthorizationClient
from ...adapters.worker_authorization_lease import WorkerAuthorizationLease
from ..operation_authority import ProfileWorkerOperationAuthority, WorkerOperationBinding

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_UNRELATED = "ledger.list"
_ACTIONS = frozenset({AccessAction.SUBMIT, AccessAction.START, AccessAction.COMMIT})
_SERVER_PROCESS_ID = 4242


class _Request(CredentialFreeOperationRequest):
    profile_id: UUID


class _UnusedExecutor:
    async def execute(self, request: OperationRequest[BaseModel], context: OperationExecutorContext) -> str:
        pytest.fail("the server-start fence executes no operation")


class _CustodyWitness(ProfileWorkerCustody):
    """One live session, entered without installing or borrowing any key."""

    def __init__(self, identity: ProfileWorkerIdentity, root: Path, session: AccessSession) -> None:
        self.identity, self.root, self.session = identity, root, session

    @override
    def require(self, session_id: UUID) -> AccessSession:
        assert session_id == self.session.session_id
        return self.session

    @override
    @contextmanager
    def section(self, session_id: UUID) -> Generator[None]:
        self.require(session_id)
        yield

    @override
    def live_sessions(self) -> tuple[UUID, ...]:
        return (self.session.session_id,)


class _StartingLease(WorkerAuthorizationLease):
    """The held lease, recording the start it is asked for and the fence it was asked under."""

    def __init__(
        self,
        *,
        starts: list[WorkerAuthorityRequest],
        identity: ProfileWorkerIdentity,
        root: Path,
        parent_pid: int,
        request: WorkerAuthorityRequest,
    ) -> None:
        super().__init__(identity=identity, root=root, parent_pid=parent_pid, request=request)
        self._starts = starts
        self._fence = request

    @override
    def start_runtime_server(self) -> int | None:
        self._starts.append(self._fence)
        return _SERVER_PROCESS_ID


class _ClientWitness(WorkerAuthorizationClient):
    def __init__(self, identity: ProfileWorkerIdentity, root: Path) -> None:
        super().__init__(identity=identity, root=root, parent_pid=os.getpid())
        self.guards: list[WorkerAuthorityRequest] = []
        self.starts: list[WorkerAuthorityRequest] = []

    @override
    @asynccontextmanager
    async def guard(self, request: WorkerAuthorityRequest) -> AsyncGenerator[WorkerAuthorizationLease]:
        self.guards.append(request)
        yield _StartingLease(
            starts=self.starts, identity=self.identity, root=self.root, parent_pid=self.parent_pid, request=request
        )


@dataclass(frozen=True)
class _Harness:
    authority: ProfileWorkerOperationAuthority
    client: _ClientWitness
    identity: OperationIdentity


def _resolve(request: OperationRequest[BaseModel], context: OperationAccessContext) -> ResolvedOperationAccess:
    return bind_operation_access(
        context,
        profile_id=context.profile_id,
        definition_id=request.definition_id,
        actions=_ACTIONS,
        disclosures=frozenset(),
        periods=frozenset(),
        period_independent=True,
        requires_all_periods=False,
        requires_human=True,
        provider=Availability.NOT_REQUIRED,
    )


def _harness(definition_id: str, authority_operation: PinnedAuthorityOperation, root: Path) -> _Harness:
    identity = ProfileWorkerIdentity(
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
    instant = datetime(2026, 10, 18, 12, tzinfo=UTC)
    session = AccessSession(
        session_id=uuid4(),
        binding=identity.binding,
        profile_lock_generation=0,
        runtime_boot_id=identity.runtime_boot_id,
        connection_id=uuid4(),
        client_id=uuid4(),
        kind=SessionKind.HUMAN,
        originating_login_id="synthetic-login",
        state=SessionState.ACTIVE,
        scope=AccessScope(
            operations=frozenset({definition_id}),
            actions=_ACTIONS,
            disclosures=frozenset(),
            periods=None,
            allow_period_independent=True,
            allow_delegation=False,
        ),
        issued_at=instant,
        expires_at=instant + timedelta(minutes=2),
        issued_monotonic=0.0,
    )
    definition = build_single_phase_definition(
        definition_id=definition_id,
        request_type=_Request,
        subject_reference=OperationSubjectReferenceV1.profile(),
        result_type=None,
        executor_type=_UnusedExecutor,
        build=_UnusedExecutor,
        capabilities=RECORDED_IDEMPOTENT_JOURNALED_READ_CAPABILITIES,
    )
    registration = OperationPublicDefinitionRegistrationV1.compose_request_only(
        definition=definition, request_schema_id=definition_id + ".request", access_resolver=_resolve
    )
    client = _ClientWitness(identity, root)
    authority = ProfileWorkerOperationAuthority(
        custody=_CustodyWitness(identity, root, session),
        client=client,
        registry=OperationRegistry(definitions=(definition,), public_registrations=(registration,)),
        authority_operation=authority_operation,
    )
    request = OperationRequest[BaseModel](
        definition_id=definition_id,
        subject_ref="local-model-program",
        payload=_Request(profile_id=identity.binding.profile_id),
    )
    operation = OperationIdentity(
        operation_id=new_operation_id(), definition_id=definition_id, subject_ref=request.subject_ref
    )
    authority.bind(
        operation.operation_id, WorkerOperationBinding(session.session_id, OperationFrontendProjection.CLI, request)
    )
    return _Harness(authority, client, operation)


async def _submitted_then_started(harness: _Harness) -> int | None:
    # The invocation's provenance is captured at submission, as the host does,
    # before its execution asks for the server under COMMIT.
    async with harness.authority.guard(harness.identity, AccessAction.SUBMIT):
        harness.authority.capture_provenance(harness.identity)
    return await harness.authority.start_runtime_server(harness.identity)


def test_the_admitted_set_is_the_local_reader_provisioning_and_the_dependency_setup() -> None:
    assert runtime_server_start_definitions() == frozenset(
        {LOCAL_READER_OPERATION_DEFINITION_ID, DEPENDENCIES_SETUP_OPERATION_DEFINITION_ID}
    )


@pytest.mark.parametrize(
    "definition_id", [DEPENDENCIES_SETUP_OPERATION_DEFINITION_ID, LOCAL_READER_OPERATION_DEFINITION_ID]
)
def test_an_admitted_operation_starts_the_server_under_its_own_commit_fence(
    definition_id: str, authority_operation: PinnedAuthorityOperation, tmp_path: Path
) -> None:
    harness = _harness(definition_id, authority_operation, tmp_path)
    started = asyncio.run(_submitted_then_started(harness))
    assert started == _SERVER_PROCESS_ID
    submitted, fence = harness.client.guards
    assert submitted.request.action is AccessAction.SUBMIT
    assert harness.client.starts == [fence]
    assert fence.request.definition_id == definition_id
    assert fence.request.action is AccessAction.COMMIT


def test_an_unrelated_operation_is_refused_before_any_fence_is_taken(
    authority_operation: PinnedAuthorityOperation, tmp_path: Path
) -> None:
    harness = _harness(_UNRELATED, authority_operation, tmp_path)
    with pytest.raises(ProfileAccessRefusedError) as refused:
        asyncio.run(harness.authority.start_runtime_server(harness.identity))
    assert refused.value.reason is AccessDenialCode.OPERATION_DENIED
    assert harness.client.guards == []
    assert harness.client.starts == []
