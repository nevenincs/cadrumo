"""All-period access and receipt-bound public contracts for evidence follow-up reads."""

from __future__ import annotations

from collections.abc import Callable
from typing import cast
from uuid import UUID, uuid4

import pytest
from pydantic import BaseModel

from ....application.ledger.attachment_review import AttachmentReviewItem
from ....application.ledger.consent_withdrawal import ConsentedDispatch
from ....application.ledger.evidence_followup_contracts import (
    LEDGER_EVIDENCE_ATTACHMENT_QUEUE_OPERATION_DEFINITION_ID,
    LEDGER_EVIDENCE_ATTACHMENT_VIEW_OPERATION_DEFINITION_ID,
    LEDGER_EVIDENCE_CONSENT_LIST_OPERATION_DEFINITION_ID,
    LEDGER_EVIDENCE_REVIEW_LIST_OPERATION_DEFINITION_ID,
    LEDGER_EVIDENCE_REVIEW_VIEW_OPERATION_DEFINITION_ID,
    AttachmentStoreFactory,
    ConsentWithdrawalSurveyProjection,
    EvidenceConsentEntriesFactory,
    LedgerEvidenceAttachmentQueueExecutionResult,
    LedgerEvidenceAttachmentQueueProjection,
    LedgerEvidenceAttachmentQueueRequest,
    LedgerEvidenceAttachmentViewExecutionResult,
    LedgerEvidenceAttachmentViewProjection,
    LedgerEvidenceAttachmentViewRequest,
    LedgerEvidenceConsentListExecutionResult,
    LedgerEvidenceConsentListProjection,
    LedgerEvidenceConsentListRequest,
    LedgerEvidenceFollowupOperationPorts,
    LedgerEvidenceReviewListExecutionResult,
    LedgerEvidenceReviewListProjection,
    LedgerEvidenceReviewListRequest,
    LedgerEvidenceReviewViewExecutionResult,
    LedgerEvidenceReviewViewProjection,
    LedgerEvidenceReviewViewRequest,
)
from ....application.ledger.evidence_followup_registration import (
    build_ledger_evidence_followup_definitions,
    build_ledger_evidence_followup_registrations,
)
from ....application.ledger.evidence_followup_registration import (
    project_attachment_queue_result as _project_attachment_queue,
)
from ....application.ledger.evidence_followup_registration import (
    project_attachment_view_result as _project_attachment_view,
)
from ....application.ledger.evidence_followup_registration import (
    project_consent_list_result as _project_consent_list,
)
from ....application.ledger.evidence_followup_registration import (
    project_review_list_result as _project_review_list,
)
from ....application.ledger.evidence_followup_registration import (
    project_review_view_result as _project_review_view,
)
from ....application.ledger.extraction_draft_store import ExtractionDraftRepositoryFactory
from ....application.ledger.invoice_draft_records import InvoiceDraft
from ....application.ledger.invoice_evidence_operation_dtos import InvoiceDraftProjectionV1
from ....application.operations.access_resolution import OperationAccessContext, resolve_operation_access
from ....application.operations.models import OperationId, OperationIdentity, OperationRequest, OperationTerminalReceipt
from ....application.operations.registry import (
    OperationFrontendProjection,
    OperationPublicDefinitionContractV1,
    OperationRegistry,
)
from ....application.user_profile.access_contracts import (
    AccessAction,
    Availability,
    DisclosureCategory,
)
from ....application.user_profile.access_errors import ProfileAccessRefusedError
from ....core.config import Settings, load_settings
from ....core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ....core.time.clock import now
from ....domain.attachments.enums import AttachmentSource

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFILE = UUID("5aa00000-0000-4000-8000-0000000000aa")
_OTHER_PROFILE = UUID("6bb00000-0000-4000-8000-0000000000bb")
_ATTACHMENT_ID = "a" * 64
_EVIDENCE_REFERENCE = "evidence-followup-reference"
_DRIVE_FILE_ID = "1AbcDEfgHIjkLMnoPQRstuVWxyz12345"

_DEFINITION_IDS = (
    LEDGER_EVIDENCE_ATTACHMENT_QUEUE_OPERATION_DEFINITION_ID,
    LEDGER_EVIDENCE_ATTACHMENT_VIEW_OPERATION_DEFINITION_ID,
    LEDGER_EVIDENCE_CONSENT_LIST_OPERATION_DEFINITION_ID,
    LEDGER_EVIDENCE_REVIEW_LIST_OPERATION_DEFINITION_ID,
    LEDGER_EVIDENCE_REVIEW_VIEW_OPERATION_DEFINITION_ID,
)


def _unused_attachment_store(bucket_id: str, /):
    raise AssertionError(bucket_id)


def _unused_draft_store(*, bucket_id: str, settings: Settings):
    raise AssertionError((bucket_id, settings))


def _unused_consent_entries(*, bucket_id: str) -> tuple[ConsentedDispatch, ...]:
    raise AssertionError(bucket_id)


def _registry() -> OperationRegistry:
    ports = LedgerEvidenceFollowupOperationPorts(
        settings=load_settings(),
        attachment_store_factory=cast(AttachmentStoreFactory, _unused_attachment_store),
        extraction_draft_repository_factory=cast(ExtractionDraftRepositoryFactory, _unused_draft_store),
        consent_entries_factory=cast(EvidenceConsentEntriesFactory, _unused_consent_entries),
    )
    definitions = build_ledger_evidence_followup_definitions(ports)
    registrations = build_ledger_evidence_followup_registrations(definitions)
    return OperationRegistry(definitions=definitions, public_registrations=registrations)


def _request(definition_id: str, *, subject_profile_id: UUID = _PROFILE) -> OperationRequest[BaseModel]:
    payload: BaseModel
    if definition_id == LEDGER_EVIDENCE_ATTACHMENT_QUEUE_OPERATION_DEFINITION_ID:
        payload = LedgerEvidenceAttachmentQueueRequest(profile_id=_PROFILE)
    elif definition_id == LEDGER_EVIDENCE_ATTACHMENT_VIEW_OPERATION_DEFINITION_ID:
        payload = LedgerEvidenceAttachmentViewRequest(profile_id=_PROFILE, attachment_id=_ATTACHMENT_ID)
    elif definition_id == LEDGER_EVIDENCE_CONSENT_LIST_OPERATION_DEFINITION_ID:
        payload = LedgerEvidenceConsentListRequest(profile_id=_PROFILE)
    elif definition_id == LEDGER_EVIDENCE_REVIEW_LIST_OPERATION_DEFINITION_ID:
        payload = LedgerEvidenceReviewListRequest(profile_id=_PROFILE)
    elif definition_id == LEDGER_EVIDENCE_REVIEW_VIEW_OPERATION_DEFINITION_ID:
        payload = LedgerEvidenceReviewViewRequest(profile_id=_PROFILE, evidence_reference=_EVIDENCE_REFERENCE)
    else:
        raise AssertionError(definition_id)
    return OperationRequest[BaseModel](
        definition_id=definition_id,
        subject_ref=profile_operation_subject(str(subject_profile_id)),
        payload=payload,
    )


def _access_context(
    contract: OperationPublicDefinitionContractV1,
    *,
    profile_id: UUID = _PROFILE,
) -> OperationAccessContext:
    return OperationAccessContext(
        profile_id=profile_id,
        destination_id=uuid4(),
        action=AccessAction.RESULT,
        frontend=OperationFrontendProjection.CLI,
        contract=contract,
        published_authority=Availability.AVAILABLE,
    )


def _receipt(definition_id: str, *, profile_id: UUID = _PROFILE) -> OperationTerminalReceipt:
    return OperationTerminalReceipt(
        identity=OperationIdentity(
            operation_id=cast(OperationId, "f" * 64),
            definition_id=definition_id,
            subject_ref=profile_operation_subject(str(profile_id)),
        ),
        revision=1,
        condition=OperationTerminalCondition.SUCCEEDED,
        effect=OperationEffect.NONE,
        settled_at=now(),
        result_ref="a" * 64,
    )


def _sample_attachment() -> AttachmentReviewItem:
    return AttachmentReviewItem(
        attachment_id=_ATTACHMENT_ID,
        sha256=_ATTACHMENT_ID,
        mime_type="application/xml",
        bytes_size=64,
        source=AttachmentSource.GOOGLE_DRIVE,
        provider_locator=_DRIVE_FILE_ID,
        captured_at="2026-09-30T11:30:00+00:00",
        linked_invoice_ids=(),
        pending_review=True,
    )


type _Projector = Callable[[BaseModel, OperationTerminalReceipt], BaseModel]


def _projection_and_projector(definition_id: str) -> tuple[BaseModel, BaseModel, _Projector]:
    if definition_id == LEDGER_EVIDENCE_ATTACHMENT_QUEUE_OPERATION_DEFINITION_ID:
        projection = LedgerEvidenceAttachmentQueueProjection(profile_id=_PROFILE, count=0, rows=())
        return (
            LedgerEvidenceAttachmentQueueExecutionResult(profile_id=_PROFILE, result=projection),
            projection,
            _project_attachment_queue,
        )
    if definition_id == LEDGER_EVIDENCE_ATTACHMENT_VIEW_OPERATION_DEFINITION_ID:
        projection = LedgerEvidenceAttachmentViewProjection(profile_id=_PROFILE, item=_sample_attachment())
        return (
            LedgerEvidenceAttachmentViewExecutionResult(profile_id=_PROFILE, result=projection),
            projection,
            _project_attachment_view,
        )
    if definition_id == LEDGER_EVIDENCE_CONSENT_LIST_OPERATION_DEFINITION_ID:
        projection = LedgerEvidenceConsentListProjection(
            profile_id=_PROFILE,
            survey=ConsentWithdrawalSurveyProjection(),
        )
        return (
            LedgerEvidenceConsentListExecutionResult(profile_id=_PROFILE, result=projection),
            projection,
            _project_consent_list,
        )
    if definition_id == LEDGER_EVIDENCE_REVIEW_LIST_OPERATION_DEFINITION_ID:
        projection = LedgerEvidenceReviewListProjection(profile_id=_PROFILE)
        return (
            LedgerEvidenceReviewListExecutionResult(profile_id=_PROFILE, result=projection),
            projection,
            _project_review_list,
        )
    if definition_id == LEDGER_EVIDENCE_REVIEW_VIEW_OPERATION_DEFINITION_ID:
        projection = LedgerEvidenceReviewViewProjection(
            profile_id=_PROFILE,
            evidence_reference=_EVIDENCE_REFERENCE,
            extractor="fixture-reader",
            drafted_at=now(),
            draft=InvoiceDraftProjectionV1.from_draft(InvoiceDraft()),
        )
        return (
            LedgerEvidenceReviewViewExecutionResult(profile_id=_PROFILE, result=projection),
            projection,
            _project_review_view,
        )
    raise AssertionError(definition_id)


@pytest.mark.parametrize("definition_id", _DEFINITION_IDS)
def test_every_read_requires_profile_wide_tax_value_disclosure(definition_id: str) -> None:
    registry = _registry()
    contract = registry.lookup_public_contract(definition_id)
    request = _request(definition_id)
    context = _access_context(contract)

    resolved = resolve_operation_access(registry=registry, request=request, context=context)

    assert resolved.request.profile_id == _PROFILE
    assert resolved.request.periods == frozenset()
    assert resolved.request.period_independent is True
    assert resolved.policy.requires_all_periods is True
    assert resolved.policy.allow_period_independent is True
    result_schema = contract.result_schema
    assert result_schema is not None
    assert any(
        disclosure.destination_id == context.destination_id
        and disclosure.projection_id == result_schema.schema_id
        and disclosure.category is DisclosureCategory.TAX_VALUES
        for disclosure in resolved.policy.disclosures
    )


@pytest.mark.parametrize("definition_id", _DEFINITION_IDS)
def test_every_read_refuses_a_foreign_profile_subject(definition_id: str) -> None:
    registry = _registry()
    contract = registry.lookup_public_contract(definition_id)

    with pytest.raises(ProfileAccessRefusedError):
        resolve_operation_access(
            registry=registry,
            request=_request(definition_id, subject_profile_id=_OTHER_PROFILE),
            context=_access_context(contract),
        )


@pytest.mark.parametrize("definition_id", _DEFINITION_IDS)
def test_each_projector_requires_its_successful_none_effect_receipt(definition_id: str) -> None:
    result, projection, projector = _projection_and_projector(definition_id)
    receipt = _receipt(definition_id)

    assert projector(result, receipt) == projection

    wrong_effect = receipt.model_copy(update={"effect": OperationEffect.UPDATED})
    with pytest.raises(ValueError):
        projector(result, wrong_effect)
