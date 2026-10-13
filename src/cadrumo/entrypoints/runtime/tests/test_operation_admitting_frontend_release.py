"""A session reads what an execution stored on every frontend alike, whichever frontend admitted it.

The production worker host and its authority run over one stored synthetic
profile: the real journal, leases and encrypted operand store hold every
invocation and the admission the worker recorded for it. The host registers the
one operation these cases submit, which stores a host path. Custody and the
native permit are explicit witnesses: the permit applies each reader's own
scope ceiling and claims no native authorization.
"""

from __future__ import annotations

import asyncio
import os
import secrets
from collections.abc import AsyncGenerator, Awaitable, Callable, Generator
from contextlib import asynccontextmanager, contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import override
from uuid import UUID, uuid4

import pytest
from pydantic import BaseModel, JsonValue

from cadrumo.adapters.local_runtime.worker_authorization_client import WorkerAuthorizationClient
from cadrumo.adapters.local_runtime.worker_authorization_lease import WorkerAuthorizationLease
from cadrumo.adapters.persistence.operations.journal import OperationJournalRepository
from cadrumo.adapters.persistence.operations.lease import OperationLeaseFilesystemRepository
from cadrumo.adapters.persistence.operations.secure_references import operation_secure_reference_repository
from cadrumo.adapters.persistence.storage.master_key.profile_worker_custody import ProfileWorkerCustody
from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from cadrumo.application.aggregation.errors import AggregationUnsupportedModeloError
from cadrumo.application.operations.access_resolution import (
    LIFECYCLE_PERIOD_INDEPENDENT_REGISTERED_RESULT_PROFILE_VALUES_ACCESS,
    OperationAccessContext,
    ResolvedOperationAccess,
    bind_replayed_period_independent_access,
    require_declared_action,
)
from cadrumo.application.operations.capabilities import RECORDED_IDEMPOTENT_SECURE_STORED_READ_CAPABILITIES
from cadrumo.application.operations.composition import OperationComposedServices, compose_operation_services
from cadrumo.application.operations.error_detail import operation_error_detail_schema
from cadrumo.application.operations.frontend_projection import (
    OperationPublicProjectionV1,
    OperationReviewProjectionReferenceV1,
)
from cadrumo.application.operations.frontend_requests import (
    OPERATION_OBSERVATION_PROJECTION_ID,
    OperationObservationRequestV1,
    OperationObservationSuccessV1,
    OperationResultProjectionRequestV1,
    OperationReviewProjectionRequestV1,
)
from cadrumo.application.operations.models import OperationId, OperationRequest, new_operation_id
from cadrumo.application.operations.operation_definition import build_single_phase_definition
from cadrumo.application.operations.owner import OperationExecutorContext
from cadrumo.application.operations.persistence.journal import OperationSecureReferenceStore
from cadrumo.application.operations.registry import (
    OperationFrontendProjection,
    OperationPublicDefinitionRegistrationV1,
    OperationRegistry,
    OperationSchemaBindingV1,
)
from cadrumo.application.operations.schema_identity import OperationSchemaIdentityV1
from cadrumo.application.operations.subject_reference import OperationSubjectReferenceV1
from cadrumo.application.runtime.profile_worker import ProfileWorkerIdentity
from cadrumo.application.runtime.projection_pages import ProjectionPageRequest, project_document_page
from cadrumo.application.runtime.worker_authorization import WorkerAuthorityRequest
from cadrumo.application.user_profile.access_contracts import (
    AccessAction,
    AccessDenialCode,
    AccessScope,
    AccessSession,
    DisclosureCategory,
    DisclosurePermission,
    ProfileAccessBinding,
    SessionKind,
    SessionState,
)
from cadrumo.application.user_profile.access_errors import ProfileAccessRefusedError
from cadrumo.application.user_profile.automation_custody_port import AutomationCustodyCode, AutomationCustodyError
from cadrumo.application.user_profile.operation_access_policy import operation_scope_refusal
from cadrumo.core.i18n.translatable import Translatable as tr
from cadrumo.core.models import STRICT_FROZEN_CONFIG
from cadrumo.core.operations import (
    OperationEffect,
    OperationLifecycle,
    OperationTerminalCondition,
    profile_operation_subject,
)
from cadrumo.core.time.clock import now
from cadrumo.entrypoints.runtime import operation_host
from cadrumo.entrypoints.runtime.operation_authority import WorkerOperationBinding
from cadrumo.entrypoints.runtime.operation_host import ProfileWorkerOperationHost

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint, pytest.mark.usefixtures("authority_operation")]

_CLI = OperationFrontendProjection.CLI
_TUI = OperationFrontendProjection.TUI
_MCP = OperationFrontendProjection.MCP
_DEFINITION = "test.sealed-document"
_RESULT_SCHEMA = _DEFINITION + ".result"
_DIRECTORY = "C:\\synthetic\\evidence"
_FILE = "invoice-0001.pdf"
_LOCATION = f"{_DIRECTORY}\\{_FILE}"
_FRONTENDS = (_CLI, _TUI, _MCP)
_REFUSAL_MESSAGE_KEY = "aggregation.grouping.errors.unsupported_modelo"
_REPLAY_KEY = "sealed-document-once"
_LEASE_DURATION = timedelta(minutes=10)


class _DocumentRequest(BaseModel):
    model_config = STRICT_FROZEN_CONFIG

    profile_id: UUID
    refuse: bool = False


class _DocumentResult(BaseModel):
    model_config = STRICT_FROZEN_CONFIG

    profile_id: UUID
    location: str


class _DocumentExecutor:
    """Store where the document lies, or refuse with a public detail that names it."""

    async def execute(self, request: OperationRequest[_DocumentRequest], context: OperationExecutorContext) -> str:
        if request.payload.refuse:
            raise AggregationUnsupportedModeloError(tr(_REFUSAL_MESSAGE_KEY), context={"location": _LOCATION})
        result = _DocumentResult(profile_id=request.payload.profile_id, location=_LOCATION)
        reference = await context.operands.put(result, written_at=now())
        await context.events.effect(OperationEffect.NONE)
        return reference


def _resolve_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    payload = request.payload
    if not isinstance(payload, _DocumentRequest) or payload.profile_id != context.profile_id:
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    access = LIFECYCLE_PERIOD_INDEPENDENT_REGISTERED_RESULT_PROFILE_VALUES_ACCESS
    require_declared_action(context, actions=access.actions)
    return bind_replayed_period_independent_access(context, access, definition_id=request.definition_id)


def _registry() -> OperationRegistry:
    definition = build_single_phase_definition(
        definition_id=_DEFINITION,
        request_type=_DocumentRequest,
        subject_reference=OperationSubjectReferenceV1.profile(),
        result_type=_DocumentResult,
        executor_type=_DocumentExecutor,
        build=_DocumentExecutor,
        capabilities=RECORDED_IDEMPOTENT_SECURE_STORED_READ_CAPABILITIES,
        public_error_detail=True,
    )
    registration = OperationPublicDefinitionRegistrationV1.compose(
        definition=definition,
        request_schema=OperationSchemaBindingV1.bind(
            schema_id=_DEFINITION + ".request", schema_version=1, model_type=_DocumentRequest
        ),
        result_schema=OperationSchemaBindingV1.bind(
            schema_id=_RESULT_SCHEMA, schema_version=1, model_type=_DocumentResult
        ),
        access_resolver=_resolve_access,
    )
    return OperationRegistry(definitions=(definition,), public_registrations=(registration,))


class _SessionsWitness(ProfileWorkerCustody):
    """Hold the live leases of one profile without installing or borrowing a key."""

    def __init__(self, identity: ProfileWorkerIdentity, root: Path, sessions: tuple[AccessSession, ...]) -> None:
        self.identity, self.root = identity, root
        self._sessions = {session.session_id: session for session in sessions}

    @override
    def require(self, session_id: UUID) -> AccessSession:
        session = self._sessions.get(session_id)
        if session is None:
            raise AutomationCustodyError(AutomationCustodyCode.CREDENTIAL_REJECTED)
        return session

    @override
    @contextmanager
    def section(self, session_id: UUID) -> Generator[None]:
        self.require(session_id)
        yield

    @override
    def retire(self, session_id: UUID) -> frozenset[UUID]:
        retired = self._sessions.pop(session_id, None)
        return frozenset({session_id}) if retired is not None else frozenset[UUID]()


class _ScopeCeilingPermit(WorkerAuthorizationClient):
    """Hold each reader to its own lease's scope ceiling; no native authorization is claimed."""

    def __init__(self, custody: _SessionsWitness) -> None:
        super().__init__(identity=custody.identity, root=custody.root, parent_pid=os.getpid())
        self._custody = custody

    @override
    @asynccontextmanager
    async def guard(self, request: WorkerAuthorityRequest) -> AsyncGenerator[WorkerAuthorizationLease]:
        refusal = operation_scope_refusal(
            request=request.request, policy=request.policy, scope=self._custody.require(request.session_id).scope
        )
        if refusal is not None:
            raise ProfileAccessRefusedError(refusal.code)
        yield WorkerAuthorizationLease(
            identity=self.identity, root=self.root, parent_pid=self.parent_pid, request=request
        )


class _SealedDocumentHost(ProfileWorkerOperationHost):
    """The production host over a registry of the one operation these cases submit."""

    def __init__(
        self,
        custody: _SessionsWitness,
        *,
        authorization: _ScopeCeilingPermit,
        operands: OperationSecureReferenceStore,
    ) -> None:
        super().__init__(custody, authorization=authorization)
        self._operands = operands
        self.elapsed = timedelta()

    def clock(self) -> datetime:
        """The supervisor's time: real time moved on by :attr:`elapsed`."""
        return now() + self.elapsed

    @override
    def _composed(self) -> OperationComposedServices:
        if self._services is None:
            registry = _registry()
            journal = OperationJournalRepository(storage_root=self.custody.root)
            self._services = compose_operation_services(
                registry=registry,
                authority_operation=self._pinned(),
                journal=journal,
                reader=journal,
                event_stream=journal,
                leases=OperationLeaseFilesystemRepository(storage_root=self.custody.root),
                operands=self._operands,
                owner_id=self.custody.identity.operation_owner_id,
                lease_token_factory=lambda: secrets.token_hex(32),
                clock=self.clock,
                lease_duration=_LEASE_DURATION,
                execution_timeout=timedelta(minutes=5),
                cleanup_timeout=timedelta(minutes=2),
                execution_authority=self._bind_execution(registry),
            )
        return super()._composed()


def _session(identity: ProfileWorkerIdentity, kind: SessionKind) -> AccessSession:
    """One live lease of the profile whose scope discloses this operation to its own client alone."""
    client_id = uuid4()
    instant = now()
    disclosures = frozenset(
        {
            DisclosurePermission(
                destination_id=client_id,
                projection_id=OPERATION_OBSERVATION_PROJECTION_ID,
                category=DisclosureCategory.OPERATION_METADATA,
            ),
            DisclosurePermission(
                destination_id=client_id, projection_id=_RESULT_SCHEMA, category=DisclosureCategory.PROFILE_VALUES
            ),
        }
    )
    delegated = kind is SessionKind.API_KEY
    return AccessSession(
        session_id=uuid4(),
        binding=identity.binding,
        profile_lock_generation=0,
        runtime_boot_id=identity.runtime_boot_id,
        connection_id=uuid4(),
        client_id=client_id,
        kind=kind,
        originating_login_id=None if delegated else "synthetic-login",
        state=SessionState.ACTIVE,
        scope=AccessScope(
            operations=frozenset({_DEFINITION}),
            actions=frozenset(AccessAction),
            disclosures=disclosures,
            periods=None,
            allow_period_independent=True,
            allow_delegation=False,
        ),
        grant_id=uuid4() if delegated else None,
        grant_generation=1 if delegated else None,
        key_id=uuid4() if delegated else None,
        key_generation=1 if delegated else None,
        issued_at=instant,
        expires_at=instant + timedelta(minutes=2),
        issued_monotonic=0.0,
    )


@dataclass(frozen=True)
class _Worker:
    """One profile worker with a person's session and a key session of the same profile."""

    host: _SealedDocumentHost
    person: AccessSession
    key: AccessSession
    profile_id: UUID

    def request(self, *, refuse: bool = False, idempotency_key: str | None = None) -> OperationRequest[BaseModel]:
        return OperationRequest[BaseModel](
            definition_id=_DEFINITION,
            subject_ref=profile_operation_subject(str(self.profile_id)),
            payload=_DocumentRequest(profile_id=self.profile_id, refuse=refuse),
            idempotency_key=idempotency_key,
        )

    async def submit(
        self, session: AccessSession, frontend: OperationFrontendProjection, request: OperationRequest[BaseModel]
    ) -> OperationId:
        submitted = await self.host.submit(session_id=session.session_id, frontend=frontend, request=request)
        return submitted.receipt.operation_id

    async def settled(self, operation_id: OperationId) -> None:
        await self.host._composed().submission.settled(operation_id)

    async def run(
        self,
        session: AccessSession,
        frontend: OperationFrontendProjection,
        *,
        refuse: bool = False,
        idempotency_key: str | None = None,
    ) -> OperationId:
        """Submit, start and settle one invocation on ``session``'s frontend."""
        request = self.request(refuse=refuse, idempotency_key=idempotency_key)
        operation_id = await self.submit(session, frontend, request)
        await self.host.start(operation_id, session.session_id)
        await self.settled(operation_id)
        return operation_id

    async def observed(
        self, session: AccessSession, frontend: OperationFrontendProjection, operation_id: OperationId
    ) -> OperationPublicProjectionV1:
        request = OperationObservationRequestV1(operation_id=operation_id, after_cursor=0, page_limit=32)
        async with self.host.observe(session.session_id, request, frontend=frontend) as (observation, _release):
            assert isinstance(observation, OperationObservationSuccessV1), observation
            return observation.projection

    async def _result_request(
        self, operation_id: OperationId, schema: OperationSchemaIdentityV1 | None
    ) -> OperationResultProjectionRequestV1:
        # Every read names the true coordinates, taken from the person's own observation.
        terminal = await self.observed(self.person, _CLI, operation_id)
        registered = terminal.definition_contract.result_schema
        assert registered is not None
        return OperationResultProjectionRequestV1(
            operation_id=operation_id,
            terminal_revision=terminal.revision,
            definition_contract_digest=terminal.definition_contract.definition_contract_digest,
            result_schema=registered if schema is None else schema,
        )

    async def result(
        self,
        session: AccessSession,
        frontend: OperationFrontendProjection,
        operation_id: OperationId,
        *,
        schema: OperationSchemaIdentityV1 | None = None,
    ) -> dict[str, JsonValue]:
        request = await self._result_request(operation_id, schema)
        async with self.host.project(session.session_id, request, frontend=frontend) as (document, release):
            assert release.request.frontend is frontend
            assert release.request.destination_id == session.client_id
            return document

    async def result_page(
        self, session: AccessSession, frontend: OperationFrontendProjection, operation_id: OperationId
    ) -> bytes:
        """Cut the first page as the worker does, inside the same released projection."""
        request = await self._result_request(operation_id, None)
        async with self.host.project(session.session_id, request, frontend=frontend) as (document, _release):
            return project_document_page(document, ProjectionPageRequest()).decode()

    async def review(
        self, session: AccessSession, frontend: OperationFrontendProjection, operation_id: OperationId
    ) -> dict[str, JsonValue]:
        terminal = await self.observed(self.person, _CLI, operation_id)
        schema = terminal.definition_contract.result_schema
        assert schema is not None
        request = OperationReviewProjectionRequestV1(
            reference=OperationReviewProjectionReferenceV1(
                operation_id=operation_id,
                interaction_id="f" * 64,
                revision=terminal.revision,
                review_projection_schema=schema,
                definition_contract_digest=terminal.definition_contract.definition_contract_digest,
                expires_at=None,
            )
        )
        async with self.host.project(session.session_id, request, frontend=frontend) as (document, _release):
            return document

    async def admitting_frontend(self, operation_id: OperationId) -> OperationFrontendProjection | None:
        """Read the frontend the worker stored with the invocation's admission."""
        invocation = await self.host._composed().submission.stored_invocation(operation_id)
        return None if invocation.provenance is None else invocation.provenance.admitting_frontend


async def _refusal(read: Awaitable[object]) -> AccessDenialCode:
    with pytest.raises(ProfileAccessRefusedError) as refused:
        await read
    return refused.value.reason


def _location(document: dict[str, JsonValue]) -> JsonValue:
    assert document["outcome"] == "success", document
    projection = document["projection"]
    assert isinstance(projection, dict)
    return projection["location"]


@contextmanager
def _worker(tmp_path: Path) -> Generator[_Worker]:
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        identity = ProfileWorkerIdentity(
            worker_id=uuid4(),
            runtime_boot_id=uuid4(),
            binding=ProfileAccessBinding(
                profile_id=UUID(profile.bucket_id),
                installation_id=uuid4(),
                os_owner_id="synthetic-owner",
                custody_generation=1,
                dek_epoch=uuid4(),
            ),
        )
        person, key = _session(identity, SessionKind.HUMAN), _session(identity, SessionKind.API_KEY)
        custody = _SessionsWitness(identity, profile.storage_root, (person, key))
        host = _SealedDocumentHost(
            custody,
            authorization=_ScopeCeilingPermit(custody),
            operands=operation_secure_reference_repository(objects=profile.repository),
        )
        yield _Worker(host, person, key, identity.binding.profile_id)


def _exercise(tmp_path: Path, scenario: Callable[[_Worker], Awaitable[None]]) -> None:
    """Run ``scenario`` on one event loop and drain the host on that loop."""

    async def body(worker: _Worker) -> None:
        try:
            await scenario(worker)
        finally:
            await worker.host.close()

    with _worker(tmp_path) as worker:
        asyncio.run(body(worker))


@pytest.mark.parametrize("admitting", _FRONTENDS, ids=["cli", "tui", "mcp"])
def test_every_frontend_reads_the_same_result_and_page_whichever_frontend_admitted_the_operation(
    tmp_path: Path, admitting: OperationFrontendProjection
) -> None:
    """Either kind of session reads the stored result whole, on the frontend it happens to use."""

    async def scenario(worker: _Worker) -> None:
        operation_id = await worker.run(worker.person, admitting)
        assert await worker.admitting_frontend(operation_id) is admitting

        pages = set[bytes]()
        for session in (worker.person, worker.key):
            for frontend in _FRONTENDS:
                assert _location(await worker.result(session, frontend, operation_id)) == _LOCATION
                pages.add(await worker.result_page(session, frontend, operation_id))
        assert len(pages) == 1
        assert _FILE.encode() in next(iter(pages))

    _exercise(tmp_path, scenario)


def test_a_review_read_and_a_stopped_operations_detail_answer_alike_on_every_frontend(tmp_path: Path) -> None:
    """A review read and a refused operation's public detail follow the result's rule."""

    async def scenario(worker: _Worker) -> None:
        settled = await worker.run(worker.person, _CLI)
        # The operation declares no review, so its own policy refuses the read to every reader.
        for session in (worker.person, worker.key):
            for frontend in _FRONTENDS:
                refusal = await _refusal(worker.review(session, frontend, settled))
                assert refusal is AccessDenialCode.OPERATION_DENIED

        refused = await worker.run(worker.person, _CLI, refuse=True)
        terminal = await worker.observed(worker.person, _CLI, refused)
        assert terminal.terminal_condition is OperationTerminalCondition.REFUSED
        detail = await worker.result(worker.person, _CLI, refused, schema=operation_error_detail_schema())
        assert detail["outcome"] == "success", detail
        for session in (worker.person, worker.key):
            for frontend in _FRONTENDS:
                read = await worker.result(session, frontend, refused, schema=operation_error_detail_schema())
                assert read == detail

    _exercise(tmp_path, scenario)


def test_every_frontend_observes_the_same_settled_state_and_none_of_the_result(tmp_path: Path) -> None:
    """Observation carries the settled state and effect, not what the execution stored."""

    async def scenario(worker: _Worker) -> None:
        operation_id = await worker.run(worker.person, _CLI)

        observed = await worker.observed(worker.person, _CLI, operation_id)

        for session in (worker.person, worker.key):
            for frontend in _FRONTENDS:
                assert await worker.observed(session, frontend, operation_id) == observed
        assert observed.lifecycle is OperationLifecycle.TERMINAL
        assert observed.terminal_condition is OperationTerminalCondition.SUCCEEDED
        assert observed.effect is OperationEffect.NONE
        document = observed.model_dump_json()
        assert _FILE not in document
        assert "synthetic" not in document

    _exercise(tmp_path, scenario)


def test_an_unknown_operation_is_refused_alike_on_every_frontend(tmp_path: Path) -> None:
    async def scenario(worker: _Worker) -> None:
        for frontend in _FRONTENDS:
            for action in (AccessAction.OBSERVE, AccessAction.RESULT, AccessAction.REVIEW):
                with pytest.raises(ProfileAccessRefusedError) as refused:
                    async with worker.host.release(worker.key.session_id, new_operation_id(), frontend, action):
                        pytest.fail("an unknown operation must release nothing")
                assert refused.value.reason is AccessDenialCode.OPERATION_UNAVAILABLE

    _exercise(tmp_path, scenario)


def test_a_replay_on_another_frontend_names_the_first_operation_and_reads_its_result(tmp_path: Path) -> None:
    """The same key resolves to the first invocation, and the replaying session reads what it stored."""

    async def scenario(worker: _Worker) -> None:
        operation_id = await worker.run(worker.person, _CLI, idempotency_key=_REPLAY_KEY)

        replayed = await worker.submit(worker.key, _MCP, worker.request(idempotency_key=_REPLAY_KEY))

        assert replayed == operation_id
        # The admission the worker stored still names the frontend that first submitted it.
        assert await worker.admitting_frontend(operation_id) is _CLI
        async with worker.host.release(worker.key.session_id, operation_id, _MCP, AccessAction.SUBMIT) as receipt:
            assert receipt.request.frontend is _MCP
        observed = await worker.observed(worker.key, _MCP, operation_id)
        assert observed.terminal_condition is OperationTerminalCondition.SUCCEEDED
        assert _location(await worker.result(worker.key, _MCP, operation_id)) == _LOCATION
        assert _FILE.encode() in await worker.result_page(worker.key, _MCP, operation_id)
        assert _location(await worker.result(worker.person, _CLI, operation_id)) == _LOCATION

    _exercise(tmp_path, scenario)


def test_an_operation_stored_without_an_admission_releases_nothing_on_any_frontend(tmp_path: Path) -> None:
    """A read needs the admission the worker recorded, whoever reads and wherever."""

    async def scenario(worker: _Worker) -> None:
        services = worker.host._composed()
        execution = worker.host._execution
        assert execution is not None
        request = worker.request()
        operation_id = new_operation_id()
        execution.bind(operation_id, WorkerOperationBinding(worker.key.session_id, _MCP, request))
        submitted = await services.submission.submit(
            request, actor_ref=f"session:{worker.key.session_id}", operation_id=operation_id
        )
        assert submitted.receipt.operation_id == operation_id
        assert await worker.admitting_frontend(operation_id) is None

        for session in (worker.person, worker.key):
            for frontend in _FRONTENDS:
                for action in (AccessAction.RESULT, AccessAction.REVIEW):
                    with pytest.raises(ProfileAccessRefusedError) as refused:
                        async with worker.host.release(session.session_id, operation_id, frontend, action):
                            pytest.fail("an invocation without an admission must release nothing")
                    assert refused.value.reason is AccessDenialCode.OPERATION_UNAVAILABLE

    _exercise(tmp_path, scenario)


@pytest.mark.parametrize(("admitting", "resuming"), [(_MCP, _CLI), (_CLI, _MCP)], ids=["mcp-then-cli", "cli-then-mcp"])
def test_an_invocation_re_entered_on_another_frontend_is_read_whole_on_both(
    tmp_path: Path, admitting: OperationFrontendProjection, resuming: OperationFrontendProjection
) -> None:
    """Whichever session carries the execution to its end, each session reads the stored result."""

    async def scenario(worker: _Worker) -> None:
        first, second = (worker.key, worker.person) if admitting is _MCP else (worker.person, worker.key)
        operation_id = await worker.submit(first, admitting, worker.request())

        await worker.host.resume(operation_id, second.session_id, frontend=resuming)
        await worker.settled(operation_id)

        # Attribution keeps the frontend that first submitted the invocation.
        assert await worker.admitting_frontend(operation_id) is admitting
        assert _location(await worker.result(first, admitting, operation_id)) == _LOCATION
        assert _location(await worker.result(second, resuming, operation_id)) == _LOCATION

    _exercise(tmp_path, scenario)


def test_an_admission_whose_receipt_is_refused_settles_and_frees_its_subject(tmp_path: Path) -> None:
    """A submitter that loses its session before its receipt leaves no unstarted operation holding the subject."""

    async def scenario(worker: _Worker) -> None:
        operation_id = await worker.submit(worker.key, _MCP, worker.request())
        worker.host.custody.retire(worker.key.session_id)

        with pytest.raises(AutomationCustodyError):
            async with worker.host.release_submission(worker.key.session_id, operation_id, _MCP):
                pytest.fail("a refused submitter must not receive its receipt")

        settled = await worker.host._composed().submission.supervisor.inspect(operation_id)
        assert settled.lifecycle is OperationLifecycle.TERMINAL
        assert settled.terminal_condition is OperationTerminalCondition.REFUSED
        assert settled.effect is OperationEffect.NONE
        assert await worker.run(worker.person, _CLI) != operation_id

    _exercise(tmp_path, scenario)


def test_a_subject_held_by_an_unsettled_operation_is_refused_as_busy(tmp_path: Path) -> None:
    """The refusal names the busy subject, not an unavailable operation or a sign-in problem."""

    async def scenario(worker: _Worker) -> None:
        held = await worker.submit(worker.person, _CLI, worker.request())

        with pytest.raises(ProfileAccessRefusedError) as refused:
            await worker.submit(worker.key, _MCP, worker.request())

        assert refused.value.reason is AccessDenialCode.SUBJECT_BUSY
        # The refused frontend is told which operation holds the subject, so the person can follow it.
        assert refused.value.holder_operation_id == held
        # A receipt the holder's own session takes is released as before.
        async with worker.host.release_submission(worker.person.session_id, held, _CLI) as receipt:
            assert receipt.request.frontend is _CLI

    _exercise(tmp_path, scenario)


def test_an_admission_nobody_starts_settles_once_its_owner_has_lapsed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A submitter that vanishes after its receipt leaves no operation unsettled and no subject held for good."""
    monkeypatch.setattr(operation_host, "_LAPSE_CHECK_SECONDS", 0.0)

    async def scenario(worker: _Worker) -> None:
        supervisor = worker.host._composed().submission.supervisor
        abandoned = await worker.submit(worker.key, _MCP, worker.request())

        # The lease has run out, but its submitter still has the grace to start it.
        worker.host.elapsed = _LEASE_DURATION + timedelta(seconds=1)
        await worker.observed(worker.person, _CLI, abandoned)
        assert (await supervisor.inspect(abandoned)).lifecycle is OperationLifecycle.CREATED

        worker.host.elapsed = 2 * _LEASE_DURATION + timedelta(seconds=1)
        await worker.observed(worker.person, _CLI, abandoned)

        settled = await supervisor.inspect(abandoned)
        assert settled.lifecycle is OperationLifecycle.TERMINAL
        assert settled.terminal_condition is OperationTerminalCondition.INTERRUPTED
        assert settled.effect is OperationEffect.NONE
        assert await worker.run(worker.person, _CLI) != abandoned

    _exercise(tmp_path, scenario)


def test_a_new_submission_interrupts_an_admission_nobody_started_within_its_lease(tmp_path: Path) -> None:
    """The same runtime that admitted the abandoned operation gives its subject to the next submitter."""

    async def scenario(worker: _Worker) -> None:
        supervisor = worker.host._composed().submission.supervisor
        abandoned = await worker.submit(worker.key, _MCP, worker.request())
        assert await _refusal(worker.submit(worker.person, _CLI, worker.request())) is AccessDenialCode.SUBJECT_BUSY

        worker.host.elapsed = _LEASE_DURATION + timedelta(seconds=1)
        admitted = await worker.submit(worker.person, _CLI, worker.request())

        assert admitted != abandoned
        settled = await supervisor.inspect(abandoned)
        assert settled.terminal_condition is OperationTerminalCondition.INTERRUPTED
        assert settled.effect is OperationEffect.NONE
        await worker.host.start(admitted, worker.person.session_id)
        await worker.settled(admitted)

    _exercise(tmp_path, scenario)
