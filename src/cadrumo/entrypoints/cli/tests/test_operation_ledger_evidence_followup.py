"""Registered runtime bridges retain complete evidence follow-up read DTOs."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import cast
from uuid import UUID

import pytest
import typer
from pydantic import BaseModel, ValidationError
from typer.core import TyperCommand

from cadrumo_client.commands.errors import CliRefusedBoundaryError
from cadrumo_client.contracts.contracts import RefusalCode

from ....application.ledger.attachment_review import AttachmentReviewItem
from ....application.ledger.confirmation_block_words import served_block_reason_words
from ....application.ledger.evidence_followup_contracts import (
    LEDGER_EVIDENCE_ATTACHMENT_QUEUE_OPERATION_DEFINITION_ID,
    LEDGER_EVIDENCE_ATTACHMENT_VIEW_OPERATION_DEFINITION_ID,
    LEDGER_EVIDENCE_CONSENT_LIST_OPERATION_DEFINITION_ID,
    LEDGER_EVIDENCE_REVIEW_LIST_OPERATION_DEFINITION_ID,
    LEDGER_EVIDENCE_REVIEW_VIEW_OPERATION_DEFINITION_ID,
    CloudDerivedArtefactProjection,
    ConsentedDispatchProjection,
    ConsentWithdrawalSurveyProjection,
    EvidenceReviewQueueRowProjection,
    LedgerEvidenceAttachmentQueueProjection,
    LedgerEvidenceAttachmentQueueRequest,
    LedgerEvidenceAttachmentViewProjection,
    LedgerEvidenceAttachmentViewRequest,
    LedgerEvidenceConsentListProjection,
    LedgerEvidenceConsentListRequest,
    LedgerEvidenceReviewListProjection,
    LedgerEvidenceReviewListRequest,
    LedgerEvidenceReviewViewProjection,
    LedgerEvidenceReviewViewRequest,
)
from ....application.ledger.invoice_draft_records import InvoiceDraft
from ....application.ledger.invoice_evidence_operation_dtos import InvoiceDraftProjectionV1
from ....application.operations.error_detail import MAX_OPERATION_ERROR_WORDS_LENGTH
from ....core.config import override_settings
from ....core.confirmation_gate import ConfirmationBlockReason, ReviewAdvisoryKind
from ....core.external_constants import OutputLanguage
from ....core.operations import OperationEffect
from ....domain.attachments.enums import AttachmentSource
from .. import operation_ledger_evidence_followup as bridge
from ..ledger_business_payloads import (
    AttachmentReviewQueueResult,
    AttachmentReviewViewResult,
    EvidenceConsentListResult,
    EvidenceReviewListResult,
    EvidenceReviewRowPayload,
)
from .operation_bridge_support import bind_exact_profile_read

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_PROFILE = UUID("5aa00000-0000-4000-8000-0000000000aa")
_OTHER_PROFILE = UUID("6bb00000-0000-4000-8000-0000000000bb")
_ATTACHMENT_ID = "a" * 64
_EVIDENCE_REFERENCE = "evidence-followup-reference"
_OPERATION_ID = "f" * 64
_DRIVE_FILE_ID = "1AbcDEfgHIjkLMnoPQRstuVWxyz12345"
_CAPTURED_AT = datetime(2026, 9, 30, 11, 30, tzinfo=UTC)
#: The review view carries the stored label-reading fallback beside its draft,
#: so it alone reads the second result schema.
_RESULT_VERSIONS = {
    LEDGER_EVIDENCE_ATTACHMENT_QUEUE_OPERATION_DEFINITION_ID: 1,
    LEDGER_EVIDENCE_ATTACHMENT_VIEW_OPERATION_DEFINITION_ID: 1,
    LEDGER_EVIDENCE_CONSENT_LIST_OPERATION_DEFINITION_ID: 1,
    LEDGER_EVIDENCE_REVIEW_LIST_OPERATION_DEFINITION_ID: 1,
    LEDGER_EVIDENCE_REVIEW_VIEW_OPERATION_DEFINITION_ID: 2,
}


def _attachment() -> AttachmentReviewItem:
    return AttachmentReviewItem(
        attachment_id=_ATTACHMENT_ID,
        sha256=_ATTACHMENT_ID,
        mime_type="application/xml",
        bytes_size=64,
        source=AttachmentSource.GOOGLE_DRIVE,
        provider_locator=_DRIVE_FILE_ID,
        captured_at=_CAPTURED_AT.isoformat(),
        linked_invoice_ids=(),
        pending_review=True,
    )


def _projection(definition_id: str, *, profile_id: UUID) -> BaseModel:
    if definition_id == LEDGER_EVIDENCE_ATTACHMENT_QUEUE_OPERATION_DEFINITION_ID:
        return LedgerEvidenceAttachmentQueueProjection(profile_id=profile_id, count=1, rows=(_attachment(),))
    if definition_id == LEDGER_EVIDENCE_ATTACHMENT_VIEW_OPERATION_DEFINITION_ID:
        return LedgerEvidenceAttachmentViewProjection(profile_id=profile_id, item=_attachment())
    if definition_id == LEDGER_EVIDENCE_CONSENT_LIST_OPERATION_DEFINITION_ID:
        return LedgerEvidenceConsentListProjection(
            profile_id=profile_id,
            survey=ConsentWithdrawalSurveyProjection(
                consented_dispatches=(
                    ConsentedDispatchProjection(
                        profile_bucket_id=str(profile_id),
                        evidence_content_address="b" * 64,
                        provider="openai",
                        model="fixture-model",
                        surface="app.ledger.evidence.extract",
                        recorded_at=_CAPTURED_AT,
                    ),
                ),
                cloud_derived_artefacts=(
                    CloudDerivedArtefactProjection(
                        evidence_reference=_EVIDENCE_REFERENCE,
                        provenance_stamp="fixture-reader",
                        transport="openai",
                        drafted_at=_CAPTURED_AT,
                    ),
                ),
            ),
        )
    if definition_id == LEDGER_EVIDENCE_REVIEW_LIST_OPERATION_DEFINITION_ID:
        return LedgerEvidenceReviewListProjection(
            profile_id=profile_id,
            rows=(
                EvidenceReviewQueueRowProjection(
                    evidence_reference=_EVIDENCE_REFERENCE,
                    extractor="fixture-reader",
                    drafted_at=_CAPTURED_AT,
                    blocking_count=0,
                    advisory_count=0,
                ),
            ),
        )
    if definition_id == LEDGER_EVIDENCE_REVIEW_VIEW_OPERATION_DEFINITION_ID:
        return LedgerEvidenceReviewViewProjection(
            profile_id=profile_id,
            evidence_reference=_EVIDENCE_REFERENCE,
            extractor="fixture-reader",
            drafted_at=_CAPTURED_AT,
            draft=InvoiceDraftProjectionV1.from_draft(InvoiceDraft()),
        )
    raise AssertionError(definition_id)


def _request(definition_id: str) -> BaseModel:
    if definition_id == LEDGER_EVIDENCE_ATTACHMENT_QUEUE_OPERATION_DEFINITION_ID:
        return LedgerEvidenceAttachmentQueueRequest(profile_id=_PROFILE)
    if definition_id == LEDGER_EVIDENCE_ATTACHMENT_VIEW_OPERATION_DEFINITION_ID:
        return LedgerEvidenceAttachmentViewRequest(profile_id=_PROFILE, attachment_id=_ATTACHMENT_ID)
    if definition_id == LEDGER_EVIDENCE_CONSENT_LIST_OPERATION_DEFINITION_ID:
        return LedgerEvidenceConsentListRequest(profile_id=_PROFILE)
    if definition_id == LEDGER_EVIDENCE_REVIEW_LIST_OPERATION_DEFINITION_ID:
        return LedgerEvidenceReviewListRequest(profile_id=_PROFILE)
    if definition_id == LEDGER_EVIDENCE_REVIEW_VIEW_OPERATION_DEFINITION_ID:
        return LedgerEvidenceReviewViewRequest(profile_id=_PROFILE, evidence_reference=_EVIDENCE_REFERENCE)
    raise AssertionError(definition_id)


def _invoke(ctx: typer.Context, definition_id: str) -> BaseModel:
    if definition_id == LEDGER_EVIDENCE_ATTACHMENT_QUEUE_OPERATION_DEFINITION_ID:
        return bridge.run_ledger_evidence_attachment_queue(ctx)
    if definition_id == LEDGER_EVIDENCE_ATTACHMENT_VIEW_OPERATION_DEFINITION_ID:
        return bridge.run_ledger_evidence_attachment_view(ctx, attachment_id=_ATTACHMENT_ID)
    if definition_id == LEDGER_EVIDENCE_CONSENT_LIST_OPERATION_DEFINITION_ID:
        return bridge.run_ledger_evidence_consent_list(ctx)
    if definition_id == LEDGER_EVIDENCE_REVIEW_LIST_OPERATION_DEFINITION_ID:
        return bridge.run_ledger_evidence_review_list(ctx)
    if definition_id == LEDGER_EVIDENCE_REVIEW_VIEW_OPERATION_DEFINITION_ID:
        return bridge.run_ledger_evidence_review_view(ctx, evidence_reference=_EVIDENCE_REFERENCE)
    raise AssertionError(definition_id)


def _bind(
    monkeypatch: pytest.MonkeyPatch,
    *,
    definition_id: str,
    profile_id: UUID,
    projection: BaseModel,
    submitted: list[BaseModel],
) -> None:
    bind_exact_profile_read(
        monkeypatch,
        bridge=bridge,
        definition_id=definition_id,
        profile_id=profile_id,
        projection=projection,
        submitted=submitted,
        result_version=_RESULT_VERSIONS[definition_id],
        operation_id=_OPERATION_ID,
    )


@pytest.mark.parametrize(
    ("definition_id", "result_type"),
    [
        (LEDGER_EVIDENCE_ATTACHMENT_QUEUE_OPERATION_DEFINITION_ID, AttachmentReviewQueueResult),
        (LEDGER_EVIDENCE_ATTACHMENT_VIEW_OPERATION_DEFINITION_ID, AttachmentReviewViewResult),
        (LEDGER_EVIDENCE_CONSENT_LIST_OPERATION_DEFINITION_ID, EvidenceConsentListResult),
        (LEDGER_EVIDENCE_REVIEW_LIST_OPERATION_DEFINITION_ID, EvidenceReviewListResult),
        (LEDGER_EVIDENCE_REVIEW_VIEW_OPERATION_DEFINITION_ID, LedgerEvidenceReviewViewProjection),
    ],
)
def test_each_bridge_submits_its_exact_profile_request_and_preserves_complete_result(
    monkeypatch: pytest.MonkeyPatch,
    definition_id: str,
    result_type: type[BaseModel],
) -> None:
    projection = _projection(definition_id, profile_id=_PROFILE)
    submitted: list[BaseModel] = []
    _bind(
        monkeypatch,
        definition_id=definition_id,
        profile_id=_PROFILE,
        projection=projection,
        submitted=submitted,
    )

    result = _invoke(cast(typer.Context, cast(object, None)), definition_id)

    assert submitted == [_request(definition_id)]
    assert isinstance(result, result_type)
    if isinstance(result, AttachmentReviewQueueResult):
        assert result.count == 1
        assert result.rows[0].sha256 == _ATTACHMENT_ID
    elif isinstance(result, AttachmentReviewViewResult):
        assert result.attachment_id == _ATTACHMENT_ID
        assert result.provider_locator == _DRIVE_FILE_ID
    elif isinstance(result, EvidenceConsentListResult):
        assert result.transmitted_bytes_are_unrecallable is True
        assert result.consented_dispatches[0].evidence_content_address == "b" * 64
        assert result.cloud_derived_artefacts[0].transport == "openai"
    elif isinstance(result, EvidenceReviewListResult):
        assert result.rows[0].evidence_reference == _EVIDENCE_REFERENCE
        assert result.rows[0].reason_words == []
        assert result.rows[0].reason_words_language is None
        assert isinstance(projection, LedgerEvidenceReviewListProjection)
        assert result.rows[0].model_dump(mode="json") == projection.rows[0].model_dump(mode="json")
    else:
        assert isinstance(result, LedgerEvidenceReviewViewProjection)
        assert isinstance(projection, LedgerEvidenceReviewViewProjection)
        assert result.evidence_reference == _EVIDENCE_REFERENCE
        assert result.draft == projection.draft


@pytest.mark.parametrize(
    "definition_id",
    [
        LEDGER_EVIDENCE_ATTACHMENT_QUEUE_OPERATION_DEFINITION_ID,
        LEDGER_EVIDENCE_ATTACHMENT_VIEW_OPERATION_DEFINITION_ID,
        LEDGER_EVIDENCE_CONSENT_LIST_OPERATION_DEFINITION_ID,
        LEDGER_EVIDENCE_REVIEW_LIST_OPERATION_DEFINITION_ID,
        LEDGER_EVIDENCE_REVIEW_VIEW_OPERATION_DEFINITION_ID,
    ],
)
def test_each_bridge_refuses_a_foreign_profile_projection_with_the_submitted_receipt(
    monkeypatch: pytest.MonkeyPatch,
    definition_id: str,
) -> None:
    projection = _projection(definition_id, profile_id=_OTHER_PROFILE)
    submitted: list[BaseModel] = []
    _bind(
        monkeypatch,
        definition_id=definition_id,
        profile_id=_PROFILE,
        projection=projection,
        submitted=submitted,
    )

    with pytest.raises(CliRefusedBoundaryError) as refused:
        _invoke(cast(typer.Context, cast(object, None)), definition_id)

    assert submitted == [_request(definition_id)]
    assert refused.value.context == {
        "operation_id": _OPERATION_ID,
        "reason": RefusalCode.INVALID_FRAME.value,
        "effect": OperationEffect.NONE.value,
        "terminal_condition": "succeeded",
    }


@pytest.mark.parametrize("language", list(OutputLanguage))
def test_review_list_preserves_every_populated_row_field_and_its_served_words(
    monkeypatch: pytest.MonkeyPatch, language: OutputLanguage
) -> None:
    reasons = (ConfirmationBlockReason.CLOSURE_DISCREPANCY, ConfirmationBlockReason.UNRESOLVED_DIRECTION)
    with override_settings(cadrumo_output_language=language.value):
        served = tuple(served_block_reason_words(reason) for reason in reasons)
    words = tuple(sentence for sentence, _language in served)
    row = EvidenceReviewQueueRowProjection(
        evidence_reference=_EVIDENCE_REFERENCE,
        extractor="fixture-reader",
        drafted_at=_CAPTURED_AT,
        blocking_count=len(reasons),
        reasons=reasons,
        reason_words=words,
        reason_words_language=language,
        advisory_count=1,
        advisories=(ReviewAdvisoryKind.PARTY_ATTRIBUTION,),
    )
    projection = LedgerEvidenceReviewListProjection(profile_id=_PROFILE, filters=("blocking_only",), rows=(row,))
    submitted: list[BaseModel] = []
    _bind(
        monkeypatch,
        definition_id=LEDGER_EVIDENCE_REVIEW_LIST_OPERATION_DEFINITION_ID,
        profile_id=_PROFILE,
        projection=projection,
        submitted=submitted,
    )

    result = bridge.run_ledger_evidence_review_list(typer.Context(TyperCommand("review-list")), blocking_only=True)

    assert submitted == [LedgerEvidenceReviewListRequest(profile_id=_PROFILE, blocking_only=True)]
    assert result.bucket_id == str(_PROFILE)
    assert result.filters == ["blocking_only"]
    assert len(result.rows) == 1
    assert result.rows[0].model_dump(mode="json") == row.model_dump(mode="json")
    assert result.rows[0].reasons == [reason.value for reason in reasons]
    assert result.rows[0].reason_words == list(words)
    assert result.rows[0].reason_words_language == language.value
    assert result.rows[0].advisories == [ReviewAdvisoryKind.PARTY_ATTRIBUTION.value]


def _review_row_wire(**changes: object) -> dict[str, object]:
    return {
        "evidence_reference": _EVIDENCE_REFERENCE,
        "extractor": "fixture-reader",
        "drafted_at": _CAPTURED_AT.isoformat(),
        "blocking_count": 1,
        "reasons": [ConfirmationBlockReason.CLOSURE_DISCREPANCY.value],
        "reason_words": ["Read the document's figures before confirming."],
        "reason_words_language": OutputLanguage.EN.value,
        "advisory_count": 0,
        "advisories": [],
        **changes,
    }


@pytest.mark.parametrize("length", [1, MAX_OPERATION_ERROR_WORDS_LENGTH])
def test_review_row_accepts_the_producers_sentence_length_boundaries(length: int) -> None:
    sentence = "x" * length
    payload = EvidenceReviewRowPayload.model_validate(_review_row_wire(reason_words=[sentence]))

    assert payload.reason_words == [sentence]
    assert payload.reason_words_language == OutputLanguage.EN.value


@pytest.mark.parametrize(
    ("field", "value", "error_type"),
    [
        ("reason_words", None, "list_type"),
        ("reason_words", "not a list", "list_type"),
        ("reason_words", ("a sentence",), "list_type"),
        ("reason_words", [1], "string_type"),
        ("reason_words", [True], "string_type"),
        ("reason_words", [None], "string_type"),
        ("reason_words", [b"a sentence"], "string_type"),
        ("reason_words", [{}], "string_type"),
        ("reason_words", [""], "string_too_short"),
        ("reason_words", ["x" * (MAX_OPERATION_ERROR_WORDS_LENGTH + 1)], "string_too_long"),
        ("reason_words", ["a sentence"] * 65, "too_long"),
        ("reason_words_language", 1, "string_type"),
        ("reason_words_language", True, "string_type"),
        ("reason_words_language", b"en", "string_type"),
        ("reason_words_language", [], "string_type"),
        ("reason_words_language", {}, "string_type"),
        ("reason_words_language", "", "value_error"),
        ("reason_words_language", "EN", "value_error"),
        ("reason_words_language", "de", "value_error"),
    ],
)
def test_review_row_refuses_wrong_word_shapes_and_languages(field: str, value: object, error_type: str) -> None:
    with pytest.raises(ValidationError) as refused:
        EvidenceReviewRowPayload.model_validate(_review_row_wire(**{field: value}))

    assert [(error["loc"][0], error["type"]) for error in refused.value.errors()] == [(field, error_type)]


def test_review_row_still_refuses_undeclared_fields() -> None:
    with pytest.raises(ValidationError) as refused:
        EvidenceReviewRowPayload.model_validate(_review_row_wire(undeclared_words="extra"))

    assert [(error["loc"], error["type"]) for error in refused.value.errors()] == [
        (("undeclared_words",), "extra_forbidden")
    ]
