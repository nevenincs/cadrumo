"""Fresh scope reads yield to control without lending a task's held permit.

These pure tests use the real operation registry, resolver dispatch and worker
authority. The read and custody/client ports are explicit witnesses; they claim
no native permission or encrypted-storage integrity.
"""

from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncGenerator, Generator
from contextlib import asynccontextmanager, contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Event, RLock, get_ident
from typing import override
from uuid import UUID, uuid4

import pytest
from pydantic import BaseModel

from cadrumo.adapters.local_runtime.worker_authorization_client import WorkerAuthorizationClient
from cadrumo.adapters.local_runtime.worker_authorization_lease import WorkerAuthorizationLease
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
from cadrumo.application.runtime.profile_worker import ProfileWorkerIdentity
from cadrumo.application.runtime.worker_authorization import WorkerAuthorityRequest
from cadrumo.application.user_profile.access_contracts import (
    AccessAction,
    AccessDenialCode,
    AccessScope,
    AccessSession,
    Availability,
    ProfileAccessBinding,
    SessionKind,
    SessionState,
)
from cadrumo.application.user_profile.access_errors import ProfileAccessRefusedError
from cadrumo.application.user_profile.automation_custody_port import AutomationCustodyCode, AutomationCustodyError
from cadrumo.core.period import Period
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation
from cadrumo.domain.calculations.registry.governed_fact_scope import governed_facts_in_scope
from cadrumo.entrypoints.runtime.operation_authority import ProfileWorkerOperationAuthority, WorkerOperationBinding

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_DEFINITION = "test.scope-read"
_ACTIONS = frozenset({AccessAction.SUBMIT, AccessAction.START, AccessAction.COMMIT})
_CARRIED_CONTEXT: ContextVar[str] = ContextVar("scope_read_test_context", default="absent")


class _ScopeRequest(CredentialFreeOperationRequest):
    profile_id: UUID


class _UnusedExecutor:
    async def execute(self, request: OperationRequest[BaseModel], context: OperationExecutorContext) -> str:
        pytest.fail("Scope resolution must not execute an operation")


class _CustodyWitness(ProfileWorkerCustody):
    """Model a control retirement without installing or borrowing any key."""

    def __init__(self, identity: ProfileWorkerIdentity, root: Path, session: AccessSession) -> None:
        self.identity, self.root = identity, root
        self.session = session
        self.live = True
        self._witness_lock = RLock()
        self.section_tasks: list[asyncio.Task[object] | None] = []

    @override
    def require(self, session_id: UUID) -> AccessSession:
        with self._witness_lock:
            if not self.live or session_id != self.session.session_id:
                raise AutomationCustodyError(AutomationCustodyCode.CREDENTIAL_REJECTED)
            return self.session

    @override
    @contextmanager
    def section(self, session_id: UUID) -> Generator[None]:
        self.require(session_id)
        self.section_tasks.append(asyncio.current_task())
        yield

    @override
    def retire(self, session_id: UUID) -> None:
        with self._witness_lock:
            assert session_id == self.session.session_id
            self.live = False

    @override
    def live_sessions(self) -> tuple[UUID, ...]:
        with self._witness_lock:
            return (self.session.session_id,) if self.live else ()


class _PermitWitness(WorkerAuthorizationClient):
    """Record exact caller tasks without claiming native authorization."""

    def __init__(self, identity: ProfileWorkerIdentity, root: Path) -> None:
        super().__init__(identity=identity, root=root, parent_pid=os.getpid())
        self.requests: list[WorkerAuthorityRequest] = []
        self.tasks: list[asyncio.Task[object] | None] = []
        self.released = 0

    @override
    @asynccontextmanager
    async def guard(self, request: WorkerAuthorityRequest) -> AsyncGenerator[WorkerAuthorizationLease]:
        self.requests.append(request)
        self.tasks.append(asyncio.current_task())
        try:
            yield WorkerAuthorizationLease(
                identity=self.identity, root=self.root, parent_pid=self.parent_pid, request=request
            )
        finally:
            self.released += 1


class _ScopeRead:
    """Hold the registered resolver's read until a control task releases it."""

    def __init__(self, operation: PinnedAuthorityOperation) -> None:
        self.operation = operation
        self.period = Period.from_year_and_code(2026, "1T")
        self.calls: list[AccessAction] = []
        self.contexts: list[str] = []
        self.entered = asyncio.Event()
        self.release = Event()
        self.finished = Event()
        self.loop: asyncio.AbstractEventLoop | None = None
        self.loop_thread: int | None = None
        self.denied = False
        self.failure: ProfileAccessRefusedError | None = None

    def hold(self) -> None:
        self.loop, self.loop_thread = asyncio.get_running_loop(), get_ident()

    def resolve(self, request: OperationRequest[BaseModel], context: OperationAccessContext) -> ResolvedOperationAccess:
        assert isinstance(request.payload, _ScopeRequest)
        assert request.payload.profile_id == context.profile_id
        assert context.authority_operation is self.operation
        assert governed_facts_in_scope() is self.operation
        self.calls.append(context.action)
        self.contexts.append(_CARRIED_CONTEXT.get())
        if self.loop is not None:
            # Refuse a loop-blocking implementation immediately rather than
            # deadlocking the test on a control task it cannot schedule.
            self.loop.call_soon_threadsafe(self.entered.set)
            assert get_ident() != self.loop_thread
            try:
                self.release.wait()
                if self.failure is not None:
                    raise self.failure
            finally:
                self.finished.set()
        if self.denied:
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
        return bind_operation_access(
            context,
            profile_id=context.profile_id,
            definition_id=request.definition_id,
            actions=_ACTIONS,
            disclosures=frozenset(),
            periods=frozenset({self.period}),
            period_independent=False,
            requires_all_periods=False,
            requires_human=True,
            provider=Availability.NOT_REQUIRED,
        )


@dataclass(frozen=True)
class _Harness:
    authority: ProfileWorkerOperationAuthority
    custody: _CustodyWitness
    client: _PermitWitness
    reader: _ScopeRead
    identity: OperationIdentity
    request: OperationRequest[BaseModel]


@pytest.fixture
def harness(authority_operation: PinnedAuthorityOperation, tmp_path: Path) -> _Harness:
    """Compose a real registered scope resolver over explicit pure ports."""
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
    instant = datetime(2026, 10, 7, 12, tzinfo=UTC)
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
            operations=frozenset({_DEFINITION}),
            actions=_ACTIONS,
            disclosures=frozenset(),
            periods=None,
            allow_period_independent=False,
            allow_delegation=False,
        ),
        issued_at=instant,
        expires_at=instant + timedelta(minutes=2),
        issued_monotonic=0.0,
    )
    custody, client, reader = (
        _CustodyWitness(identity, tmp_path, session),
        _PermitWitness(identity, tmp_path),
        _ScopeRead(authority_operation),
    )
    definition = build_single_phase_definition(
        definition_id=_DEFINITION,
        request_type=_ScopeRequest,
        result_type=None,
        executor_type=_UnusedExecutor,
        build=_UnusedExecutor,
        capabilities=RECORDED_IDEMPOTENT_JOURNALED_READ_CAPABILITIES,
        permitted_frontends=frozenset({OperationFrontendProjection.CLI}),
    )
    registration = OperationPublicDefinitionRegistrationV1.compose_request_only(
        definition=definition, request_schema_id=_DEFINITION + ".request", access_resolver=reader.resolve
    )
    registry = OperationRegistry(definitions=(definition,), public_registrations=(registration,))
    authority = ProfileWorkerOperationAuthority(
        custody=custody, client=client, registry=registry, authority_operation=authority_operation
    )
    request = OperationRequest[BaseModel](
        definition_id=_DEFINITION,
        subject_ref="synthetic-work-unit",
        payload=_ScopeRequest(profile_id=identity.binding.profile_id),
    )
    operation_identity = OperationIdentity(
        operation_id=new_operation_id(), definition_id=_DEFINITION, subject_ref=request.subject_ref
    )
    authority.bind(
        operation_identity.operation_id,
        WorkerOperationBinding(session.session_id, OperationFrontendProjection.CLI, request),
    )
    return _Harness(authority, custody, client, reader, operation_identity, request)


async def _guard(harness: _Harness) -> None:
    async with harness.authority.guard(harness.identity, AccessAction.SUBMIT):
        pass


async def _require(harness: _Harness) -> None:
    await harness.authority.require(identity=harness.identity, request=harness.request, action=AccessAction.SUBMIT)


@pytest.mark.asyncio
async def test_control_progresses_while_registered_scope_read_is_held(harness: _Harness) -> None:
    harness.reader.hold()
    token = _CARRIED_CONTEXT.set("caller-context")
    pending = asyncio.create_task(_guard(harness))
    try:
        await harness.reader.entered.wait()
        assert not pending.done() and not harness.client.requests
        assert harness.custody.live_sessions() == (harness.custody.session.session_id,)
        harness.reader.release.set()
        await pending
    finally:
        harness.reader.release.set()
        await asyncio.gather(pending, return_exceptions=True)
        _CARRIED_CONTEXT.reset(token)
    assert harness.reader.contexts == ["caller-context"]
    assert harness.client.tasks == [pending]
    assert harness.custody.section_tasks == [pending]
    assert harness.client.released == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("require_only", [False, True])
async def test_retirement_during_scope_read_refuses_before_native_guard(harness: _Harness, require_only: bool) -> None:
    harness.reader.hold()
    pending = asyncio.create_task(_require(harness) if require_only else _guard(harness))
    try:
        await harness.reader.entered.wait()
        harness.custody.retire(harness.custody.session.session_id)
        assert not harness.custody.live_sessions()
        harness.reader.release.set()
        with pytest.raises(AutomationCustodyError) as refused:
            await pending
    finally:
        harness.reader.release.set()
        await asyncio.gather(pending, return_exceptions=True)
    assert refused.value.reason is AutomationCustodyCode.CREDENTIAL_REJECTED
    assert harness.reader.finished.is_set()
    assert not harness.client.requests and not harness.custody.section_tasks


@pytest.mark.asyncio
@pytest.mark.parametrize("read_fails", [False, True])
async def test_cancellation_waits_for_scope_read_and_retains_failure(harness: _Harness, read_fails: bool) -> None:
    harness.reader.hold()
    if read_fails:
        harness.reader.failure = ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
    pending = asyncio.create_task(_guard(harness))
    try:
        await harness.reader.entered.wait()
        pending.cancel()
        await asyncio.sleep(0)
        pending.cancel()
        await asyncio.sleep(0)
        assert not pending.done() and not harness.reader.finished.is_set()
        assert not harness.client.requests
        harness.reader.release.set()
        with pytest.raises(asyncio.CancelledError) as cancelled:
            await pending
    finally:
        harness.reader.release.set()
        await asyncio.gather(pending, return_exceptions=True)
    assert harness.reader.finished.is_set()
    if read_fails:
        assert cancelled.value.__dict__.get("cleanup_error") is harness.reader.failure
    assert not harness.client.requests and not harness.custody.section_tasks


@pytest.mark.asyncio
@pytest.mark.parametrize("action", [AccessAction.SUBMIT, AccessAction.START, AccessAction.COMMIT])
async def test_every_action_and_held_require_resolves_freshly_without_lending_permit(
    harness: _Harness, action: AccessAction
) -> None:
    async with harness.authority.guard(harness.identity, AccessAction.SUBMIT):
        harness.authority.capture_provenance(harness.identity)
    caller = asyncio.current_task()
    async with harness.authority.guard(harness.identity, action):
        await harness.authority.require(identity=harness.identity, request=harness.request, action=action)
        assert len(harness.client.requests) == 2
        child = asyncio.create_task(
            harness.authority.require(identity=harness.identity, request=harness.request, action=action)
        )
        await child
        assert harness.client.tasks == [caller, caller, child]
        harness.reader.denied = True
        with pytest.raises(ProfileAccessRefusedError) as refused:
            await harness.authority.require(identity=harness.identity, request=harness.request, action=action)
        assert refused.value.reason is AccessDenialCode.OPERATION_DENIED
        assert len(harness.client.requests) == 3
    assert harness.reader.calls == [AccessAction.SUBMIT, action, action, action, action]
    assert harness.custody.section_tasks == [caller, caller]
    assert harness.client.released == 3
