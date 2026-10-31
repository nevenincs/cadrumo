"""Human review, exact receipt binding and uncertain-effect publication tests."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import cast
from uuid import uuid4

import pytest
from pydantic import BaseModel

from cadrumo_client.contracts.access_vocabulary import AccessAction, Availability, DisclosureCategory

from ....core.operations import (
    OperationEffect,
    OperationTerminalCondition,
)
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ...operations import profile_guard
from ...operations.access_resolution import OperationAccessContext, resolve_operation_access
from ...operations.interactions import (
    OperationApplyResponse,
    OperationRejectResponse,
)
from ...operations.models import OperationRequest, OperationTerminalReceipt
from ...operations.registry import OperationFrontendProjection, OperationRegistry
from ...tests.review_operation_fakes import profile_operation_request, review_execution_context
from ...user_profile import capabilities
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


def _request(payload: BaseModel, definition_id: str) -> OperationRequest[BaseModel]:
    return profile_operation_request(payload, definition_id, PROFILE_ID)


def _context(request: OperationRequest[BaseModel], operation: PinnedAuthorityOperation):
    return review_execution_context(
        request, operation, phase_prefix="export.google-review", proposal_type=GoogleReviewProposal
    )


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
    access = resolve_operation_access(registry=registry, request=request, context=context)
    assert access.policy.requires_human and access.policy.requires_all_periods
    assert {item.category for item in access.policy.disclosures} == {
        DisclosureCategory.PROFILE_VALUES,
        DisclosureCategory.TAX_VALUES,
    }
    assert AccessAction.COMMIT in access.policy.actions


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


class _ReviewPublisher:
    """The publish port, failing at the step the named scenario selects."""

    def __init__(
        self,
        *,
        failure: str | None,
        snapshot,
        publication,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        self.failure = failure
        self.snapshot = snapshot
        self.publication = publication
        self.root = publication.root
        self.monkeypatch = monkeypatch
        self.calls: list = []
        self.retained = None

    def __call__(self, selected, receipt, authorization, *, commit, before_handoff, acknowledged):
        failure = self.failure
        self.calls.append(selected)
        assert selected == self.snapshot
        assert authorization.snapshot_digest == self.snapshot.snapshot_digest
        assert authorization.root_folder_id == self.publication.root.artifact_id
        if failure == "revoked_handoff":
            self.monkeypatch.setattr(
                capabilities, "resolve_active_capability", lambda _: SimpleNamespace(enabled=False)
            )
        if failure != "retained":
            before_handoff("drive.files.create", writes=True)
        if failure == "unknown":
            raise TimeoutError("lost acknowledgement")
        if failure != "retained":
            acknowledged("drive.files.create", writes=True)
        artifact = ArtifactCreationReceipt(
            profile_id=PROFILE_ID,
            root_folder_id=self.root.artifact_id,
            artifact_id="native-sheet",
            parent_id=self.root.artifact_id,
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
            self.monkeypatch.setattr(
                capabilities, "resolve_active_capability", lambda _: SimpleNamespace(enabled=False)
            )
        if failure == "retained":
            self.retained = receipt
            return receipt
        result = commit(lambda: receipt, changed=lambda _: True)
        if failure != "missing_custody":
            self.retained = result
        return result


def _assert_foreign_operation_response_refused(executor, request, pending, context, events, publisher) -> None:
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
    assert publisher.calls == []


def _consume_review_response(pending, context, *, reject: bool):
    if reject:
        return pending.consume(
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
    return pending.consume(
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


def _corrupt_stored_proposal(operands, raw) -> None:
    assert operands.proposal is not None
    operands.proposal = operands.proposal.model_copy(update={"revision": raw.revision + 1})

    # Simulate corrupted returned bytes to test the executor's own digest check.
    async def altered(reference, model_type):
        return operands.proposal

    operands.resolve = altered


# Scenarios whose resume raises: (exception, message pattern, effect left behind).
_RESUME_RAISES: dict[str, tuple[type[BaseException], str | None, OperationEffect]] = {
    "revoked_handoff": (GoogleSheetsExportCapabilityDisabledError, None, OperationEffect.NONE),
    "revoked_commit": (GoogleSheetsExportCapabilityDisabledError, None, OperationEffect.PARTIAL),
    "missing_custody": (ValueError, "durable receipt custody", OperationEffect.PARTIAL),
    "wrong_receipt": (ValueError, "approved verified receipt", OperationEffect.PARTIAL),
    "unknown": (TimeoutError, None, OperationEffect.UNKNOWN),
}


def _assert_published_result(executor, request, applied, context, events, operands, failure) -> None:
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
    publisher = _ReviewPublisher(failure=failure, snapshot=snapshot, publication=publication, monkeypatch=monkeypatch)

    def factory(*, profile_id, operation):
        return GoogleReviewOperationPorts(
            profile_id,
            operation,
            lambda _: snapshot,
            lambda: publisher.root,
            cast(GoogleReviewPublish, publisher),
            lambda _: publisher.retained,
        )

    executor = GoogleReviewExecutor(factory)
    assert asyncio.run(executor.execute(request, context)) is None
    assert publisher.calls == [] and events.effects == [OperationEffect.NONE]
    pending = interactions.pending
    assert pending is not None
    raw.revision = pending.request.revision
    if failure is None:
        _assert_foreign_operation_response_refused(executor, request, pending, context, events, publisher)
    with pytest.raises(ProfileAccessRefusedError) as lost_owner:
        asyncio.run(executor.resume(request, pending, context))
    assert lost_owner.value.reason.value == "response_authority_required"
    assert publisher.calls == [] and events.effects[-1] is OperationEffect.NONE
    applied = _consume_review_response(pending, context, reject=failure == "rejected")
    if failure == "wrong_root":
        publisher.root = publisher.root.model_copy(update={"artifact_id": "other-root", "root_folder_id": "other-root"})
    elif failure == "foreign_profile":
        monkeypatch.setattr(profile_guard, "require_active_bucket_id", lambda: str(uuid4()))
    elif failure == "changed_proposal":
        _corrupt_stored_proposal(operands, raw)
    if failure in {"wrong_root", "foreign_profile", "changed_proposal", "rejected"}:
        with pytest.raises(ProfileAccessRefusedError):
            asyncio.run(executor.resume(request, applied, context))
        assert publisher.calls == []
    elif failure in _RESUME_RAISES:
        error_type, message, expected_effect = _RESUME_RAISES[failure]
        with pytest.raises(error_type, match=message):
            asyncio.run(executor.resume(request, applied, context))
        assert events.effects[-1] is expected_effect
    else:
        _assert_published_result(executor, request, applied, context, events, operands, failure)
