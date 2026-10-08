"""Human review, exact receipt binding and uncertain-effect publication tests."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import cast
from uuid import uuid4

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
from ...operations import profile_guard
from ...operations.access_resolution import OperationAccessContext, resolve_operation_access
from ...operations.interactions import (
    OperationApplyResponse,
    OperationInteractionRequest,
    OperationPendingInteraction,
    OperationRejectResponse,
)
from ...operations.models import OperationIdentity, OperationRequest, OperationTerminalReceipt
from ...operations.owner import OperationExecutorContext
from ...operations.persistence.journal import serialize_operation_operand
from ...operations.registry import OperationFrontendProjection, OperationRegistry
from ...user_profile import capabilities
from ...user_profile.access_contracts import AccessAction, Availability, DisclosureCategory
from ...user_profile.access_errors import ProfileAccessRefusedError
from ..google_operation import GoogleSheetsExportCapabilityDisabledError
from ..google_review_operation import (
    build_google_review_operation_definition,
    build_google_review_operation_registration,
    project_google_review_result,
)
from ..google_review_operation_contracts import (
    GOOGLE_REVIEW_OPERATION_DEFINITION_ID,
    GoogleReviewOperationPorts,
    GoogleReviewProposal,
    GoogleReviewPublish,
    GoogleReviewRequest,
)
from ..google_review_operation_executor import GoogleReviewExecutor
from ..managed_artifact_ports import ArtifactCreationReceipt, ManagedArtifactKind
from ..publication_receipt import PublicationState
from .review_publication_fixture import PROFILE_ID, acceptance_publication, acceptance_snapshot

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]
_NOW = datetime.now(UTC)


class _Events:
    def __init__(self) -> None:
        self.effects: list[OperationEffect] = []

    async def phase(self, phase: str) -> None:
        assert phase.startswith("export.google-review")

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
        self.proposal: GoogleReviewProposal | None = None
        self.snapshot = None

    async def put(self, value: BaseModel, *, written_at: datetime) -> str:
        assert written_at.tzinfo is not None
        if type(value).__name__ == "ReviewSnapshot":
            self.snapshot = value
        self.value = value
        return "d" * 64

    async def resolve(self, reference: str, model_type: type[BaseModel]) -> BaseModel:
        if model_type.__name__ == "ReviewSnapshot":
            assert self.snapshot is not None
            return self.snapshot
        assert self.proposal is not None and reference == sha256_hex(serialize_operation_operand(self.proposal))
        assert model_type is GoogleReviewProposal
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
        assert isinstance(reviewed_operand, GoogleReviewProposal)
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
            reviewed_proposal_digest=sha256_hex(serialize_operation_operand(reviewed_operand)),
            baseline_digest=baseline_digest,
            proposed_effect_digest=proposed_effect_digest,
        )


def _request(payload: BaseModel, definition_id: str) -> OperationRequest[BaseModel]:
    return OperationRequest[BaseModel](
        definition_id=definition_id, subject_ref=profile_operation_subject(str(PROFILE_ID)), payload=payload
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


@pytest.mark.parametrize("frontend", tuple(OperationFrontendProjection))
def test_registration_requires_human_and_exact_profile(
    authority_operation: PinnedAuthorityOperation, frontend: OperationFrontendProjection
) -> None:
    def unused(**kwargs):
        pytest.fail("registration must not acquire credentials")

    definition = build_google_review_operation_definition(unused)
    registration = build_google_review_operation_registration(definition)
    registry = OperationRegistry(definitions=(definition,), public_registrations=(registration,))
    request = _request(
        GoogleReviewRequest(profile_id=PROFILE_ID, calculation_revision_id="c" * 64, publication_id=uuid4()),
        definition.definition_id,
    )
    context = OperationAccessContext(
        profile_id=PROFILE_ID,
        destination_id=uuid4(),
        action=AccessAction.REVIEW,
        frontend=frontend,
        contract=registration.contract,
        published_authority=Availability.AVAILABLE,
        authority_operation=authority_operation,
    )
    if frontend is OperationFrontendProjection.MCP:
        # The native contract door enforces frontend admission before invoking
        # this policy resolver; automation must remain excluded there.
        assert frontend not in registration.contract.permitted_frontends
        return
    access = resolve_operation_access(registry=registry, request=request, context=context)
    assert access.policy.requires_human and access.policy.requires_all_periods
    assert {item.category for item in access.policy.disclosures} == {
        DisclosureCategory.PROFILE_VALUES,
        DisclosureCategory.TAX_VALUES,
    }
    assert AccessAction.COMMIT in access.policy.actions
    assert definition.permitted_frontends == frozenset(
        {OperationFrontendProjection.CLI, OperationFrontendProjection.TUI}
    )


def test_optional_filing_selection_preserves_older_request_wire() -> None:
    request = GoogleReviewRequest(profile_id=PROFILE_ID, calculation_revision_id="c" * 64, publication_id=uuid4())
    assert "filing_record_id" not in request.model_dump(mode="json")
    assert GoogleReviewRequest.model_validate_json(request.model_dump_json()) == request


@pytest.mark.parametrize("loader_present", [False, True])
def test_exact_filing_selection_cannot_publish_unrelated_calculation_baseline(
    authority_operation: PinnedAuthorityOperation, monkeypatch: pytest.MonkeyPatch, loader_present: bool
) -> None:
    monkeypatch.setattr(profile_guard, "require_active_bucket_id", lambda: str(PROFILE_ID))
    monkeypatch.setattr(capabilities, "resolve_active_capability", lambda _: SimpleNamespace(enabled=True))
    snapshot = acceptance_snapshot()
    publication = acceptance_publication(snapshot)
    request = _request(
        GoogleReviewRequest(
            profile_id=PROFILE_ID,
            calculation_revision_id="c" * 64,
            publication_id=publication.publication_id,
            filing_record_id="d" * 64,
        ),
        GOOGLE_REVIEW_OPERATION_DEFINITION_ID,
    )
    _, context, events, _, _, _ = _context(request, authority_operation)

    def unused(*args, **kwargs):
        pytest.fail("exact filing refusal must precede publication and ordinary calculation selection")

    def factory(*, profile_id, operation):
        return GoogleReviewOperationPorts(
            profile_id=profile_id,
            operation=operation,
            load_snapshot=unused,
            load_root=lambda: publication.root,
            publish=unused,
            load_publication=lambda _: None,
            load_filing_snapshot=(lambda revision_id, filing_record_id: snapshot) if loader_present else None,
        )

    with pytest.raises(ProfileAccessRefusedError):
        asyncio.run(GoogleReviewExecutor(factory).execute(request, context))
    assert events.effects == [OperationEffect.NONE]


@pytest.mark.parametrize(
    "failure",
    [
        None,
        "unknown",
        "wrong_root",
        "foreign_profile",
        "changed_proposal",
        "rejected",
        "wrong_receipt",
        "revoked_handoff",
        "revoked_commit",
        "retained",
        "missing_custody",
    ],
)
def test_publication_requires_exact_review_and_preserves_effect_truth(
    authority_operation: PinnedAuthorityOperation, monkeypatch: pytest.MonkeyPatch, failure: str | None
) -> None:
    monkeypatch.setattr(profile_guard, "require_active_bucket_id", lambda: str(PROFILE_ID))
    monkeypatch.setattr(capabilities, "resolve_active_capability", lambda _: SimpleNamespace(enabled=True))
    snapshot = acceptance_snapshot()
    publication = acceptance_publication(snapshot)
    payload = GoogleReviewRequest(
        profile_id=PROFILE_ID, calculation_revision_id="c" * 64, publication_id=publication.publication_id
    )
    request = _request(payload, GOOGLE_REVIEW_OPERATION_DEFINITION_ID)
    raw, context, events, operands, _fence, interactions = _context(request, authority_operation)
    calls = []
    root = publication.root
    retained = None

    def publish(selected, receipt, authorization, *, commit, before_handoff, acknowledged):
        nonlocal retained
        calls.append(selected)
        assert selected == snapshot
        assert authorization.snapshot_digest == snapshot.snapshot_digest
        assert authorization.root_folder_id == publication.root.artifact_id
        if failure == "revoked_handoff":
            monkeypatch.setattr(capabilities, "resolve_active_capability", lambda _: SimpleNamespace(enabled=False))
        if failure != "retained":
            before_handoff("drive.files.create", writes=True)
        if failure == "unknown":
            raise TimeoutError("lost acknowledgement")
        if failure != "retained":
            acknowledged("drive.files.create", writes=True)
        artifact = ArtifactCreationReceipt(
            profile_id=PROFILE_ID,
            root_folder_id=root.artifact_id,
            artifact_id="native-sheet",
            parent_id=root.artifact_id,
            creation_id=uuid4(),
            kind=ManagedArtifactKind.REVIEW_SHEET,
            publication_id=receipt.publication_id,
        )
        for state in (
            PublicationState.REMOTE_CREATED,
            PublicationState.POPULATED,
            PublicationState.VERIFIED,
            PublicationState.PUBLISHED,
        ):
            receipt = receipt.advance(state, artifacts=(artifact,))
        if failure == "wrong_receipt":
            receipt = receipt.model_copy(update={"snapshot_digest": "0" * 64})
        if failure == "revoked_commit":
            monkeypatch.setattr(capabilities, "resolve_active_capability", lambda _: SimpleNamespace(enabled=False))
        if failure == "retained":
            retained = receipt
            return retained
        result = commit(lambda: receipt, changed=lambda _: True)
        if failure != "missing_custody":
            retained = result
        return result

    def factory(*, profile_id, operation):
        return GoogleReviewOperationPorts(
            profile_id,
            operation,
            lambda _: snapshot,
            lambda: root,
            cast(GoogleReviewPublish, publish),
            lambda _: retained,
        )

    executor = GoogleReviewExecutor(factory)
    assert asyncio.run(executor.execute(request, context)) is None
    assert calls == [] and events.effects == [OperationEffect.NONE]
    pending = interactions.pending
    assert pending is not None
    raw.revision = pending.request.revision
    if failure is None:
        foreign = pending.model_copy(
            update={
                "request": pending.request.model_copy(
                    update={"identity": pending.request.identity.model_copy(update={"operation_id": "9" * 64})}
                )
            }
        )
        events.effects.append(OperationEffect.UNKNOWN)
        with pytest.raises(ProfileAccessRefusedError):
            asyncio.run(executor.resume(request, foreign, context))
        assert events.effects.pop() is OperationEffect.UNKNOWN
        assert calls == []
    with pytest.raises(ProfileAccessRefusedError) as lost_owner:
        asyncio.run(executor.resume(request, pending, context))
    assert lost_owner.value.reason.value == "response_authority_required"
    assert calls == [] and events.effects[-1] is OperationEffect.NONE
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
    if failure == "rejected":
        applied = pending.consume(
            OperationRejectResponse(
                interaction_id=pending.request.interaction_id,
                operation_id=context.identity.operation_id,
                revision=pending.request.revision,
                response_token="e" * 64,
                continuation_digest=pending.request.continuation_digest,
                reviewed_proposal_digest=pending.reviewed_proposal_digest,
                actor_ref="session:" + str(uuid4()),
                responded_at=_NOW,
            )
        )
    if failure == "wrong_root":
        root = root.model_copy(update={"artifact_id": "other-root", "root_folder_id": "other-root"})
    elif failure == "foreign_profile":
        monkeypatch.setattr(profile_guard, "require_active_bucket_id", lambda: str(uuid4()))
    elif failure == "changed_proposal":
        assert operands.proposal is not None
        operands.proposal = operands.proposal.model_copy(update={"revision": raw.revision + 1})

        # Simulate corrupted returned bytes to test the executor's own digest check.
        async def altered(reference, model_type):
            return operands.proposal

        operands.resolve = altered
    if failure in {"wrong_root", "foreign_profile", "changed_proposal", "rejected"}:
        with pytest.raises(ProfileAccessRefusedError):
            asyncio.run(executor.resume(request, applied, context))
        assert calls == []
    elif failure in {"revoked_handoff", "revoked_commit"}:
        with pytest.raises(GoogleSheetsExportCapabilityDisabledError):
            asyncio.run(executor.resume(request, applied, context))
        expected = OperationEffect.NONE if failure == "revoked_handoff" else OperationEffect.PARTIAL
        assert events.effects[-1] is expected
    elif failure == "missing_custody":
        with pytest.raises(ValueError, match="durable receipt custody"):
            asyncio.run(executor.resume(request, applied, context))
        assert events.effects[-1] is OperationEffect.PARTIAL
    elif failure == "wrong_receipt":
        with pytest.raises(ValueError, match="approved verified receipt"):
            asyncio.run(executor.resume(request, applied, context))
        assert events.effects[-1] is OperationEffect.PARTIAL
    elif failure == "unknown":
        with pytest.raises(TimeoutError):
            asyncio.run(executor.resume(request, applied, context))
        assert events.effects[-1] is OperationEffect.UNKNOWN
    else:
        assert asyncio.run(executor.resume(request, applied, context)) == "d" * 64
        expected = OperationEffect.NONE if failure == "retained" else OperationEffect.UPDATED
        assert events.effects[-1] is expected
        assert operands.value.effect == expected.value
        assert operands.value.result.spreadsheet_url == "https://docs.google.com/spreadsheets/d/native-sheet/edit"
        terminal = OperationTerminalReceipt(
            identity=context.identity,
            revision=context.revision,
            condition=OperationTerminalCondition.SUCCEEDED,
            effect=expected,
            settled_at=_NOW,
            result_ref="d" * 64,
        )
        assert project_google_review_result(operands.value, terminal) == operands.value.result
        wrong_effect = OperationEffect.UPDATED if expected is OperationEffect.NONE else OperationEffect.NONE
        with pytest.raises(ValueError, match="terminal receipt"):
            project_google_review_result(operands.value, terminal.model_copy(update={"effect": wrong_effect}))
