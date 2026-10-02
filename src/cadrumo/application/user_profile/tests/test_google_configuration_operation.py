"""Closed Google contracts and truthful application handoffs without live providers."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Event
from types import SimpleNamespace
from typing import cast
from uuid import UUID, uuid4

import pytest
from pydantic import BaseModel

from ....core.hashing import sha256_hex
from ....core.operations import (
    OperationEffect,
    OperationInteractionKind,
    OperationTerminalCondition,
    profile_operation_subject,
)
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ...operations.access_resolution import OperationAccessContext, resolve_operation_access
from ...operations.interactions import OperationApplyResponse, OperationInteractionRequest, OperationPendingInteraction
from ...operations.models import OperationIdentity, OperationRequest, OperationTerminalReceipt
from ...operations.owner import OperationExecutorContext
from ...operations.refusal_evidence import OperationRefusalEvidence
from ...operations.registry import OperationFrontendProjection, OperationRegistry
from ...operations.secret_submission import (
    BoundEphemeralSecretAccess,
    EphemeralSecretBroker,
    OperationSecretRequirement,
)
from .. import google_configuration_operation as worker
from .. import google_configuration_operation_contracts as contracts
from ..access_contracts import AccessAction, Availability, DisclosureCategory
from ..access_errors import ProfileAccessRefusedError
from ..google_configuration_operation_ports import (
    GoogleConfigurationAcknowledgement,
    GoogleConfigurationCommit,
    GoogleConfigurationHandoff,
    GoogleConfigurationOperationPorts,
    GoogleConfigurationOperationPortsFactory,
    GoogleConfigurationRun,
)
from ..google_configuration_operation_refusal import (
    GOOGLE_CONFIGURATION_REFUSAL_CODE,
    GoogleConfigurationPresentationFacts,
    GoogleConfigurationRefusalProjection,
    GoogleConfigurationRefusedError,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]
_PROFILE = UUID("38383838-3838-4383-8383-383838383838")
_NOW = datetime.now(UTC)


class _Events:
    def __init__(self) -> None:
        self.effects: list[OperationEffect] = []

    async def phase(self, phase: str) -> None:
        assert phase.startswith("config.google.")

    async def effect(self, effect: OperationEffect) -> None:
        self.effects.append(effect)


class _Fence:
    def __init__(self) -> None:
        self.inside = False

    @asynccontextmanager
    async def irreversible_section(self) -> AsyncIterator[None]:
        assert not self.inside
        self.inside = True
        try:
            yield
        finally:
            self.inside = False


class _Operands:
    def __init__(self) -> None:
        self.value: BaseModel | None = None
        self.proposal: contracts.GoogleConsentProposal | None = None

    async def put(self, value: BaseModel, *, written_at: datetime) -> str:
        assert written_at.tzinfo is not None
        self.value = value
        return "d" * 64

    async def resolve(self, reference: str, model_type: type[BaseModel]) -> BaseModel:
        assert self.proposal is not None and reference == self.proposal.digest
        assert model_type is contracts.GoogleConsentProposal
        return self.proposal


class _Interactions:
    def __init__(self, operands: _Operands) -> None:
        self.operands = operands
        self.pending: OperationPendingInteraction | None = None

    async def publish_review(
        self,
        *,
        interaction_id: str,
        identity: OperationIdentity,
        revision: int,
        presentation_code: str,
        response_schema_ref: str,
        continuation_digest: str,
        expires_at: datetime | None,
        reviewed_operand: BaseModel,
        baseline_digest: str | None = None,
        proposed_effect_digest: str | None = None,
    ) -> None:
        assert isinstance(reviewed_operand, contracts.GoogleConsentProposal)
        self.operands.proposal = reviewed_operand
        self.pending = OperationPendingInteraction.bind(
            request=OperationInteractionRequest(
                interaction_id=interaction_id,
                identity=identity,
                revision=revision,
                kind=OperationInteractionKind.REVIEW,
                presentation_code=presentation_code,
                response_schema_ref=response_schema_ref,
                continuation_digest=continuation_digest,
                expires_at=expires_at,
            ),
            response_token="e" * 64,
            reviewed_proposal_digest=reviewed_operand.digest,
            baseline_digest=baseline_digest,
            proposed_effect_digest=proposed_effect_digest,
        )


def _request(payload: BaseModel, definition_id: str) -> OperationRequest[BaseModel]:
    return OperationRequest[BaseModel](
        definition_id=definition_id, subject_ref=profile_operation_subject(str(_PROFILE)), payload=payload
    )


def _context(request: OperationRequest[BaseModel], operation: PinnedAuthorityOperation):
    events, operands, fence = _Events(), _Operands(), _Fence()
    interactions = _Interactions(operands)
    value = SimpleNamespace(
        identity=OperationIdentity(
            operation_id="a" * 64, definition_id=request.definition_id, subject_ref=request.subject_ref
        ),
        revision=0,
        authority_operation=operation,
        events=events,
        operands=operands,
        cancellation=fence,
        interactions=interactions,
    )
    return value, cast(OperationExecutorContext, cast(object, value)), events, operands, fence, interactions


def _factory(
    run: GoogleConfigurationRun,
    *,
    prepare_consent: Callable[[], None] = lambda: None,
) -> GoogleConfigurationOperationPortsFactory:
    def factory(*, profile_id: UUID, operation: PinnedAuthorityOperation) -> GoogleConfigurationOperationPorts:
        return GoogleConfigurationOperationPorts(profile_id, operation, run, prepare_consent)

    return factory


def _refusal() -> GoogleConfigurationRefusalProjection:
    return GoogleConfigurationRefusalProjection(
        profile_id=_PROFILE,
        provider_code="AUTH_GOOGLE_EXPIRED",
        message_key="cli.config.google.detail.no_metadata_for_refresh",
        facts=GoogleConfigurationPresentationFacts(profile=_PROFILE),
    )


def test_all_nine_public_contracts_compile_and_require_human_dual_whole_profile_access(
    authority_operation: PinnedAuthorityOperation,
    tmp_path: Path,
) -> None:
    def unused(*, profile_id: UUID, operation: PinnedAuthorityOperation) -> GoogleConfigurationOperationPorts:
        pytest.fail("compiling Google contracts constructed credential capabilities")

    payloads: tuple[contracts.GoogleConfigurationRequest, ...] = (
        contracts.GoogleCredentialSourceSetRequest(
            profile_id=_PROFILE, kind=contracts.GoogleCredentialSourceKind.OAUTH_DESKTOP
        ),
        contracts.GoogleCredentialSourceViewRequest(profile_id=_PROFILE),
        contracts.GoogleFolderSetRequest(profile_id=_PROFILE, folder_id="folder"),
        contracts.GoogleFolderViewRequest(profile_id=_PROFILE),
        contracts.GoogleLoginRequest(profile_id=_PROFILE),
        contracts.GoogleLogoutRequest(profile_id=_PROFILE),
        contracts.GoogleProbeRequest(profile_id=_PROFILE),
        contracts.GoogleRegisterRequest(
            profile_id=_PROFILE, client_json_path=str(tmp_path / "client.json"), client_json_sha256="f" * 64
        ),
        contracts.GoogleStatusRequest(profile_id=_PROFILE),
    )
    definitions = worker.build_google_configuration_definitions(unused)
    assert len(definitions) == 9
    for definition, payload in zip(definitions, payloads, strict=True):
        registration = worker.build_google_configuration_registration(definition)
        registry = OperationRegistry(definitions=(definition,), public_registrations=(registration,))
        request = _request(payload, definition.definition_id)
        access_context = OperationAccessContext(
            profile_id=_PROFILE,
            destination_id=uuid4(),
            action=AccessAction.RESULT,
            frontend=OperationFrontendProjection.CLI,
            contract=registration.contract,
            published_authority=Availability.AVAILABLE,
            authority_operation=authority_operation,
        )
        access = resolve_operation_access(registry=registry, request=request, context=access_context)
        assert access.policy.requires_human and access.policy.requires_all_periods
        assert {item.category for item in access.policy.disclosures} == {
            DisclosureCategory.PROFILE_VALUES,
            DisclosureCategory.TAX_VALUES,
        }
        assert definition.permitted_frontends == frozenset({OperationFrontendProjection.CLI})
        assert definition.refusal_detail_codes == frozenset({GOOGLE_CONFIGURATION_REFUSAL_CODE})
        assert (definition.ephemeral_secret is not None) is isinstance(payload, contracts.GoogleRegisterRequest)
        assert (registration.contract.review_projection_schema is not None) is isinstance(
            payload, contracts.GoogleLoginRequest
        )
        with pytest.raises(ProfileAccessRefusedError):
            resolve_operation_access(
                registry=registry, request=request, context=replace(access_context, profile_id=uuid4())
            )


@pytest.mark.parametrize("removed", [False, True])
def test_local_commit_reports_actual_deletion_and_projector_rejects_wrong_receipt(
    removed: bool,
    authority_operation: PinnedAuthorityOperation,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(worker, "require_active_bucket_id", lambda: str(_PROFILE))
    request = _request(
        contracts.GoogleLogoutRequest(profile_id=_PROFILE), contracts.GOOGLE_LOGOUT_OPERATION_DEFINITION_ID
    )
    _, context, events, operands, fence, _ = _context(request, authority_operation)

    def run(
        request: contracts.GoogleConfigurationRequest,
        *,
        secret: memoryview | None,
        commit: GoogleConfigurationCommit,
        before_handoff: GoogleConfigurationHandoff,
        acknowledged: GoogleConfigurationAcknowledgement,
        terminal_admission: Callable[[], None] | None,
    ) -> contracts.GoogleConfigurationProjection:
        assert request.profile_id == _PROFILE and secret is None

        def save():
            assert fence.inside
            return (removed, removed)

        flags = commit(save, changed=lambda value: any(value))
        assert not fence.inside
        return contracts.GoogleLogoutProjection(profile_id=_PROFILE, token_removed=flags[0], metadata_removed=flags[1])

    assert asyncio.run(worker.GoogleConfigurationExecutor(_factory(run)).execute(request, context)) == "d" * 64
    assert isinstance(operands.value, worker.GoogleConfigurationExecutionResult)
    effect = OperationEffect.UPDATED if removed else OperationEffect.NONE
    assert events.effects[-1] is effect
    receipt = OperationTerminalReceipt(
        identity=context.identity,
        revision=1,
        condition=OperationTerminalCondition.SUCCEEDED,
        effect=effect,
        settled_at=_NOW,
        result_ref="d" * 64,
    )
    assert worker.project_google_configuration_result(operands.value, receipt) == operands.value.projection
    with pytest.raises(ValueError, match="receipt"):
        worker.project_google_configuration_result(
            operands.value,
            receipt.model_copy(update={"identity": context.identity.model_copy(update={"operation_id": "b" * 64})}),
        )


@pytest.mark.parametrize(
    "mode,expected",
    [
        ("prewrite", OperationEffect.NONE),
        ("partial", OperationEffect.PARTIAL),
        ("uncertain", OperationEffect.UNKNOWN),
        ("acknowledged", OperationEffect.UPDATED),
    ],
)
def test_provider_boundaries_leave_no_commit_held_and_settle_honest_effects(
    mode: str,
    expected: OperationEffect,
    authority_operation: PinnedAuthorityOperation,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(worker, "require_active_bucket_id", lambda: str(_PROFILE))
    request = _request(
        contracts.GoogleProbeRequest(profile_id=_PROFILE), contracts.GOOGLE_PROBE_OPERATION_DEFINITION_ID
    )
    _, context, events, operands, fence, _ = _context(request, authority_operation)

    def run(
        request: contracts.GoogleConfigurationRequest,
        *,
        secret: memoryview | None,
        commit: GoogleConfigurationCommit,
        before_handoff: GoogleConfigurationHandoff,
        acknowledged: GoogleConfigurationAcknowledgement,
        terminal_admission: Callable[[], None] | None,
    ) -> contracts.GoogleConfigurationProjection:
        if mode == "partial":
            commit(lambda: True, changed=lambda value: value)
        if mode in {"uncertain", "acknowledged"}:
            before_handoff("files.create", writes=True)
            assert not fence.inside  # actual provider call belongs here
            if mode == "acknowledged":
                acknowledged("files.create", writes=True)
        if mode != "acknowledged":
            raise GoogleConfigurationRefusedError(_refusal())
        return contracts.GoogleProbeProjection(
            profile_id=_PROFILE, reachable=True, writable=True, read_only=False, root_folder_id="root"
        )

    result = asyncio.run(worker.GoogleConfigurationExecutor(_factory(run)).execute(request, context))
    assert events.effects[-1] is expected
    assert isinstance(operands.value, worker.GoogleConfigurationExecutionResult)
    if mode == "acknowledged":
        assert result == "d" * 64
    else:
        assert isinstance(result, OperationRefusalEvidence) and result.refusal_code == GOOGLE_CONFIGURATION_REFUSAL_CODE
        receipt = OperationTerminalReceipt(
            identity=context.identity,
            revision=1,
            condition=OperationTerminalCondition.REFUSED,
            effect=expected,
            settled_at=_NOW,
            refusal_ref=result.refusal_code,
            refusal_detail_ref=result.detail_ref,
        )
        projected = worker.project_google_configuration_result(operands.value, receipt)
        assert isinstance(projected, contracts.GoogleConfigurationOutcome) and projected.refusal == _refusal()
        with pytest.raises(ValueError, match="receipt"):
            worker.project_google_configuration_result(
                operands.value, receipt.model_copy(update={"refusal_ref": "REFUSED_GOOGLE_NON_INTERACTIVE"})
            )


def test_owner_loss_after_first_save_refuses_second_physical_write_and_private_release(
    authority_operation: PinnedAuthorityOperation,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    active = [_PROFILE]
    monkeypatch.setattr(worker, "require_active_bucket_id", lambda: str(active[0]))
    request = _request(
        contracts.GoogleLogoutRequest(profile_id=_PROFILE), contracts.GOOGLE_LOGOUT_OPERATION_DEFINITION_ID
    )
    _, context, events, operands, fence, _ = _context(request, authority_operation)
    writes: list[int] = []

    def run(
        request: contracts.GoogleConfigurationRequest,
        *,
        secret: memoryview | None,
        commit: GoogleConfigurationCommit,
        before_handoff: GoogleConfigurationHandoff,
        acknowledged: GoogleConfigurationAcknowledgement,
        terminal_admission: Callable[[], None] | None,
    ) -> contracts.GoogleConfigurationProjection:
        def first():
            assert fence.inside
            writes.append(1)
            active[0] = uuid4()
            return True

        commit(first, changed=lambda value: value)
        commit(lambda: writes.append(2), changed=lambda _value: True)
        pytest.fail("second write crossed lost profile authority")

    with pytest.raises(ProfileAccessRefusedError):
        asyncio.run(worker.GoogleConfigurationExecutor(_factory(run)).execute(request, context))
    assert writes == [1] and operands.value is None and events.effects[-1] is OperationEffect.PARTIAL


def test_registration_consumes_exact_secret_once_and_excludes_secret_from_private_projection(
    authority_operation: PinnedAuthorityOperation,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(worker, "require_active_bucket_id", lambda: str(_PROFILE))
    secret = bytearray(b"synthetic-secret-client-json")
    request = _request(
        contracts.GoogleRegisterRequest(
            profile_id=_PROFILE,
            client_json_path=str(tmp_path / "client.json"),
            client_json_sha256=sha256_hex(bytes(secret)),
        ),
        contracts.GOOGLE_REGISTER_OPERATION_DEFINITION_ID,
    )
    raw, context, _, operands, _, _ = _context(request, authority_operation)
    requirement = OperationSecretRequirement(
        identity=context.identity,
        interaction_id="f" * 64,
        revision=1,
        secret_kind=contracts.GOOGLE_REGISTER_INPUT_KIND,
        expires_at=_NOW + timedelta(minutes=5),
    )
    broker = EphemeralSecretBroker()
    broker.submit(requirement, secret, observed_at=_NOW)
    assert secret == bytearray(len(secret))
    raw.ephemeral_secret = BoundEphemeralSecretAccess(requirement=requirement, broker=broker, clock=lambda: _NOW)

    def run(
        request: contracts.GoogleConfigurationRequest,
        *,
        secret: memoryview | None,
        commit: GoogleConfigurationCommit,
        before_handoff: GoogleConfigurationHandoff,
        acknowledged: GoogleConfigurationAcknowledgement,
        terminal_admission: Callable[[], None] | None,
    ) -> contracts.GoogleConfigurationProjection:
        assert secret is not None and bytes(secret) == b"synthetic-secret-client-json"
        commit(lambda: None, changed=lambda _value: True)
        return contracts.GoogleRegisterProjection(
            profile_id=_PROFILE, client_id="synthetic-client", project_id="synthetic-project"
        )

    executor = worker.GoogleConfigurationExecutor(_factory(run))
    assert asyncio.run(executor.execute(request, context)) == "d" * 64
    assert operands.value is not None and "synthetic-secret-client-json" not in operands.value.model_dump_json()
    with pytest.raises(ValueError, match="already consumed"):
        asyncio.run(executor.execute(request, context))
    broker.close()


def test_consent_requires_actual_consumed_exact_revision_proposal_before_canonical_flow(
    authority_operation: PinnedAuthorityOperation,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(worker, "require_active_bucket_id", lambda: str(_PROFILE))
    request = _request(
        contracts.GoogleLoginRequest(profile_id=_PROFILE), contracts.GOOGLE_LOGIN_OPERATION_DEFINITION_ID
    )
    raw, context, _, operands, fence, interactions = _context(request, authority_operation)
    flows: list[str] = []

    def run(
        request: contracts.GoogleConfigurationRequest,
        *,
        secret: memoryview | None,
        commit: GoogleConfigurationCommit,
        before_handoff: GoogleConfigurationHandoff,
        acknowledged: GoogleConfigurationAcknowledgement,
        terminal_admission: Callable[[], None] | None,
    ) -> contracts.GoogleConfigurationProjection:
        assert terminal_admission is not None
        terminal_admission()
        before_handoff("oauth.browser-consent")
        assert not fence.inside
        flows.append("consent")
        acknowledged("oauth.browser-consent")
        return contracts.GoogleLoginProjection(
            profile_id=_PROFILE, mode="consent", account_email="synthetic@example.invalid"
        )

    executor = worker.GoogleConfigurationExecutor(_factory(run))
    assert asyncio.run(executor.execute(request, context)) is None
    pending = interactions.pending
    assert pending is not None and pending.baseline_digest is not None and pending.proposed_effect_digest is not None
    assert not flows and operands.value is None
    raw.revision = pending.request.revision
    assert asyncio.run(executor.resume(request, pending, context)) is None
    applied = pending.consume(
        OperationApplyResponse(
            interaction_id=pending.request.interaction_id,
            operation_id=context.identity.operation_id,
            revision=pending.request.revision,
            response_token="e" * 64,
            continuation_digest=pending.request.continuation_digest,
            reviewed_proposal_digest=pending.reviewed_proposal_digest,
            baseline_digest=pending.baseline_digest,
            proposed_effect_digest=pending.proposed_effect_digest,
            actor_ref="session:" + str(uuid4()),
            responded_at=_NOW,
        )
    )
    assert asyncio.run(executor.resume(request, applied, context)) == "d" * 64
    assert flows == ["consent"]
    raw.identity = context.identity.model_copy(update={"operation_id": "b" * 64})
    with pytest.raises(ProfileAccessRefusedError):
        asyncio.run(executor.resume(request, applied, context))
    assert flows == ["consent"]


def test_caller_cancellation_waits_for_owned_provider_work_and_acknowledgement(
    authority_operation: PinnedAuthorityOperation,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(worker, "require_active_bucket_id", lambda: str(_PROFILE))
    request = _request(
        contracts.GoogleProbeRequest(profile_id=_PROFILE), contracts.GOOGLE_PROBE_OPERATION_DEFINITION_ID
    )
    _, context, events, operands, fence, _ = _context(request, authority_operation)
    release = Event()

    async def scenario() -> None:
        entered = asyncio.Event()
        loop = asyncio.get_running_loop()

        def run(
            request: contracts.GoogleConfigurationRequest,
            *,
            secret: memoryview | None,
            commit: GoogleConfigurationCommit,
            before_handoff: GoogleConfigurationHandoff,
            acknowledged: GoogleConfigurationAcknowledgement,
            terminal_admission: Callable[[], None] | None,
        ) -> contracts.GoogleConfigurationProjection:
            before_handoff("files.create", writes=True)
            assert not fence.inside
            loop.call_soon_threadsafe(entered.set)
            assert release.wait(timeout=5)
            acknowledged("files.create", writes=True)
            return contracts.GoogleProbeProjection(
                profile_id=_PROFILE, reachable=True, writable=True, read_only=False, root_folder_id="root"
            )

        task = asyncio.create_task(worker.GoogleConfigurationExecutor(_factory(run)).execute(request, context))
        try:
            await asyncio.wait_for(entered.wait(), timeout=5)
            task.cancel()
            await asyncio.sleep(0)
            assert not task.done() and operands.value is None
            release.set()
            with pytest.raises(asyncio.CancelledError):
                await task
        finally:
            release.set()
        assert events.effects[-1] is OperationEffect.UPDATED
        assert isinstance(operands.value, worker.GoogleConfigurationExecutionResult)

    asyncio.run(scenario())
