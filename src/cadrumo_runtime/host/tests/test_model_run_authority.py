"""A running operation's model runs go out under its own START authority, through the held lease.

The real worker authority, registry and resolver dispatch run here; custody
and the authorization client are explicit witnesses, as in the server-start
tests, so the held lease answers the model run it is asked for instead of
sending it over a native channel. The runtime and service side of the relay
are covered by the service's relay integration tests.
"""

from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import override
from uuid import UUID, uuid4

import pytest
from pydantic import BaseModel

from cadrumo.adapters.persistence.storage.master_key.profile_worker_custody import (
    ProfileWorkerCustody,
    ProfileWorkerCustodySection,
)
from cadrumo.application.operations.access_resolution import (
    OperationAccessContext,
    ResolvedOperationAccess,
    bind_operation_access,
)
from cadrumo.application.operations.capabilities import RECORDED_IDEMPOTENT_JOURNALED_READ_CAPABILITIES
from cadrumo.application.operations.model_runs import OperationModelRuns, operation_model_run_port
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
from cadrumo.core.model_roles import ModelRole
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation
from cadrumo_client.contracts.access_vocabulary import AccessAction, AccessScope, Availability
from cadrumo_client.contracts.model_runs import (
    ModelRunBody,
    ModelRunHeader,
    ModelRunLane,
    ModelRunOutcome,
    ModelRunOutput,
    ModelRunRefusal,
    ModelRunRefusalCode,
    ModelRunRoleSelection,
    ModelRunSelectedModel,
    ModelRunServed,
    decode_model_run_body,
)
from cadrumo_client.contracts.worker_identity import ProfileWorkerIdentity
from cadrumo_runtime.contracts.worker_authorization import WorkerAuthorityRequest

from ...adapters.worker_authorization_client import WorkerAuthorizationClient
from ...adapters.worker_authorization_connections import WorkerAuthorizationConnections
from ...adapters.worker_authorization_lease import WorkerAuthorizationLease
from ..operation_authority import ProfileWorkerOperationAuthority
from ..worker_operation_binding import WorkerOperationBinding

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_DEFINITION = "ledger.evidence.extract"
_LANE = ModelRunLane(
    provider_id="example",
    transport="cli",
    model="example-model-1",
    reads_off_host=True,
    licence=None,
    size_bytes=None,
    vision=None,
    context_length=None,
    installed=None,
)
_ACTIONS = frozenset({AccessAction.SUBMIT, AccessAction.START, AccessAction.COMMIT})


class _Request(CredentialFreeOperationRequest):
    profile_id: UUID


class _UnusedExecutor:
    async def execute(self, request: OperationRequest[BaseModel], context: OperationExecutorContext) -> str:
        pytest.fail("a model run executes no operation")


class _CustodyWitness(ProfileWorkerCustody):
    """One live session, entered without installing or borrowing any key."""

    def __init__(self, identity: ProfileWorkerIdentity, root: Path, session: AccessSession) -> None:
        self.identity, self.root, self.session = identity, root, session

    @override
    def require(self, session_id: UUID) -> AccessSession:
        assert session_id == self.session.session_id
        return self.session

    @override
    def section(self, session_id: UUID) -> ProfileWorkerCustodySection:
        self.require(session_id)
        return ProfileWorkerCustodySection(lambda: None)

    @override
    def live_sessions(self) -> tuple[UUID, ...]:
        return (self.session.session_id,)


class _AnsweringLease(WorkerAuthorizationLease):
    """The held lease, answering the model run it is asked for and recording the fence it came under."""

    def __init__(
        self,
        *,
        answers: list[tuple[WorkerAuthorityRequest, str | None, ModelRunHeader | None, bytes]],
        outcome: tuple[ModelRunOutcome, bytes],
        connections: WorkerAuthorizationConnections,
        request: WorkerAuthorityRequest,
    ) -> None:
        super().__init__(connections=connections, request=request)
        self._answers, self._outcome, self._fence = answers, outcome, request

    @override
    def model_run(
        self, role: str | None, header: ModelRunHeader | None, body: bytearray, *, answer_seconds: float
    ) -> tuple[ModelRunOutcome, bytearray]:
        self._answers.append((self._fence, role, header, bytes(body)))
        outcome, text = self._outcome
        return outcome, bytearray(text)


class _ClientWitness(WorkerAuthorizationClient):
    def __init__(self, identity: ProfileWorkerIdentity, root: Path) -> None:
        super().__init__(identity=identity, root=root, parent_pid=os.getpid())
        self.answers: list[tuple[WorkerAuthorityRequest, str | None, ModelRunHeader | None, bytes]] = []
        self.outcome: tuple[ModelRunOutcome, bytes] = (ModelRunOutcome(lane=_LANE), b"")

    @override
    async def check(self, request: WorkerAuthorityRequest) -> None:
        # This port's guard stands in for the runtime's admission; a check holds it for no body.
        async with self.guard(request):
            pass

    @override
    @asynccontextmanager
    async def guard(self, request: WorkerAuthorityRequest) -> AsyncGenerator[WorkerAuthorizationLease]:
        yield _AnsweringLease(
            answers=self.answers,
            outcome=self.outcome,
            connections=self.connections,
            request=request,
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
    asyncio.run(
        authority.bind(
            operation.operation_id, WorkerOperationBinding(session.session_id, OperationFrontendProjection.CLI, request)
        )
    )
    return _Harness(authority, client, operation)


async def _submitted(harness: _Harness) -> None:
    # The invocation's provenance is captured at submission, as the host does,
    # before its execution asks for any model run under START.
    async with harness.authority.guard(harness.identity, AccessAction.SUBMIT):
        await harness.authority.capture_provenance(harness.identity)


async def _lookup(harness: _Harness, role: str) -> ModelRunLane | ModelRunRefusal:
    await _submitted(harness)
    return await harness.authority.model_run_lookup(harness.identity, role)


async def _run(harness: _Harness, header: ModelRunHeader, body: ModelRunBody) -> ModelRunOutput | ModelRunRefusal:
    await _submitted(harness)
    return await harness.authority.model_run(harness.identity, header, body)


_SERVED = ModelRunServed(provider_id="example", transport="cli", model="example-model-1", agent_version="1")
_HEADER = ModelRunHeader(role=ModelRole.TEXT_EXTRACTION.value, deadline_seconds=30)


def test_the_execution_authority_is_a_model_run_door(
    authority_operation: PinnedAuthorityOperation, tmp_path: Path
) -> None:
    harness = _harness(_DEFINITION, authority_operation, tmp_path)
    assert isinstance(harness.authority, OperationModelRuns)


def test_a_lookup_goes_out_under_the_operations_own_start_fence(
    authority_operation: PinnedAuthorityOperation, tmp_path: Path
) -> None:
    harness = _harness(_DEFINITION, authority_operation, tmp_path)

    lane = asyncio.run(_lookup(harness, ModelRole.TEXT_EXTRACTION.value))

    assert lane == _LANE
    ((fence, role, header, body),) = harness.client.answers
    assert fence.request.action is AccessAction.START
    assert fence.request.definition_id == _DEFINITION
    assert (role, header, body) == (ModelRole.TEXT_EXTRACTION.value, None, b"")


def test_a_selections_read_goes_out_without_a_role_under_the_start_fence_and_returns_every_state(
    authority_operation: PinnedAuthorityOperation, tmp_path: Path
) -> None:
    harness = _harness(_DEFINITION, authority_operation, tmp_path)
    states = (
        ModelRunRoleSelection(
            role=ModelRole.TEXT_EXTRACTION.value,
            selected=ModelRunSelectedModel(lane_id="example_cli", model=_LANE.model),
            lane=_LANE,
        ),
        ModelRunRoleSelection(role=ModelRole.VISION_TRANSCRIPTION.value, refusal=ModelRunRefusalCode.NO_SELECTION),
    )
    harness.client.outcome = (ModelRunOutcome(selections=states), b"")

    async def read() -> tuple[ModelRunRoleSelection, ...] | ModelRunRefusal:
        await _submitted(harness)
        return await harness.authority.model_run_selections(harness.identity)

    assert asyncio.run(read()) == states
    ((fence, role, header, body),) = harness.client.answers
    assert fence.request.action is AccessAction.START
    assert (role, header, body) == (None, None, b"")


def test_a_selections_read_the_service_refuses_returns_that_refusal(
    authority_operation: PinnedAuthorityOperation, tmp_path: Path
) -> None:
    harness = _harness(_DEFINITION, authority_operation, tmp_path)
    harness.client.outcome = (ModelRunOutcome(refusal=ModelRunRefusalCode.NOT_SIGNED_IN), b"")

    async def read() -> tuple[ModelRunRoleSelection, ...] | ModelRunRefusal:
        await _submitted(harness)
        return await harness.authority.model_run_selections(harness.identity)

    assert asyncio.run(read()) == ModelRunRefusal(code=ModelRunRefusalCode.NOT_SIGNED_IN)


def test_a_run_sends_its_encoded_body_and_returns_the_served_reply(
    authority_operation: PinnedAuthorityOperation, tmp_path: Path
) -> None:
    harness = _harness(_DEFINITION, authority_operation, tmp_path)
    harness.client.outcome = (ModelRunOutcome(served=_SERVED, text_byte_count=2), b"{}")
    body = ModelRunBody(prompt="Read this invoice.", max_output_tokens=64)

    output = asyncio.run(_run(harness, _HEADER, body))

    assert output == ModelRunOutput(
        text="{}", provider_id="example", transport="cli", model="example-model-1", agent_version="1"
    )
    ((_, _, header, sent),) = harness.client.answers
    assert header == _HEADER
    assert decode_model_run_body(sent) == body


@pytest.mark.parametrize(
    ("outcome", "text", "expected"),
    [
        (ModelRunOutcome(refusal=ModelRunRefusalCode.CONSENT_MISSING), b"", ModelRunRefusalCode.CONSENT_MISSING),
        (ModelRunOutcome(lane=_LANE), b"", ModelRunRefusalCode.RUN_FAILED),
        (ModelRunOutcome(served=_SERVED, text_byte_count=2), b"\xff\xfe", ModelRunRefusalCode.OUTPUT_INVALID),
    ],
)
def test_a_run_answered_with_anything_but_a_served_reply_refuses(
    outcome: ModelRunOutcome,
    text: bytes,
    expected: ModelRunRefusalCode,
    authority_operation: PinnedAuthorityOperation,
    tmp_path: Path,
) -> None:
    harness = _harness(_DEFINITION, authority_operation, tmp_path)
    harness.client.outcome = (outcome, text)

    output = asyncio.run(_run(harness, _HEADER, ModelRunBody(prompt="x", max_output_tokens=8)))

    assert output == ModelRunRefusal(code=expected)


def test_the_bound_port_reaches_the_authority_from_inside_a_running_operation(
    authority_operation: PinnedAuthorityOperation, tmp_path: Path
) -> None:
    harness = _harness(_DEFINITION, authority_operation, tmp_path)

    async def scenario() -> ModelRunLane | ModelRunRefusal:
        await _submitted(harness)
        port = operation_model_run_port(harness.authority, harness.identity)
        assert port is not None
        return await port.lookup(ModelRole.SUPPLY_NATURE_PROPOSAL)

    assert asyncio.run(scenario()) == _LANE
    ((_, role, _, _),) = harness.client.answers
    assert role == ModelRole.SUPPLY_NATURE_PROPOSAL.value
