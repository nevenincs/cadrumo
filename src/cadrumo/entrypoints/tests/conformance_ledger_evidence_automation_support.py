"""Registered-executor conformance scenarios for the automation-facing evidence reads."""

from __future__ import annotations

from ...application.ledger.evidence import PurchaseInvoiceEvidenceService
from ...application.ledger.evidence_followup_contracts import (
    DRAFT_TEXT_FIELDS_WITHHELD_FROM_AUTOMATION,
    LEDGER_EVIDENCE_REVIEW_SUMMARY_OPERATION_DEFINITION_ID,
    LEDGER_EVIDENCE_REVIEW_VIEW_OPERATION_DEFINITION_ID,
    LedgerEvidenceReviewSummaryProjection,
    LedgerEvidenceReviewViewProjection,
)
from ...application.ledger.evidence_read_operation import (
    LEDGER_EVIDENCE_QUERY_OPERATION_DEFINITION_ID,
    LedgerEvidenceAutomationRecordProjection,
    LedgerEvidenceQueryProjection,
    LedgerEvidenceQueryRequest,
)
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ..adapter_composition import build_ledger_evidence_ports
from .conformance_family_contract import (
    ConformanceFamily,
    ConformanceFamilyContext,
    ConformanceOutcome,
    ConformancePreparation,
    RegisteredExecutorConformanceCase,
)
from .evidence_followup_operation_test_support import prepare_evidence_followup_conformance_case

_EVIDENCE_FILE_NAME = "conformance-automation-evidence.pdf"
_MINIMAL_PDF = b"%PDF-1.4\n1 0 obj<</Type/Catalog>>endobj\ntrailer<</Root 1 0 R>>\n%%EOF\n"
# A shorter text, such as a currency or country code, can occur in a released
# token by coincidence, and a printed figure equals the amount the summary
# releases as a number. Neither would prove anything about the document's text.
_DISTINCTIVE_TEXT_LENGTH = 6


def _is_distinctive_text(text: object) -> bool:
    return isinstance(text, str) and len(text) >= _DISTINCTIVE_TEXT_LENGTH and any(char.isalpha() for char in text)


def _prepare_query(context: ConformanceFamilyContext) -> ConformancePreparation:
    profile_id = context.profile_id
    bucket_id = str(profile_id)
    evidence_file = context.input_root / _EVIDENCE_FILE_NAME
    evidence_file.write_bytes(_MINIMAL_PDF)
    record = (
        PurchaseInvoiceEvidenceService(ports=build_ledger_evidence_ports(bucket_id=bucket_id))
        .add(bucket_id=bucket_id, source_path=evidence_file)
        .record
    )
    typed_directory = str(context.input_root)
    assert typed_directory in record.source_path

    def verify(outcome: ConformanceOutcome) -> None:
        released = outcome.resolve_result(LedgerEvidenceQueryProjection).model_dump_json()
        assert typed_directory not in released
        assert typed_directory.replace("\\", "\\\\") not in released
        assert context.input_root.name not in released

    return ConformancePreparation(
        subject_ref=profile_operation_subject(bucket_id),
        request=LedgerEvidenceQueryRequest(profile_id=profile_id),
        expected_result=LedgerEvidenceQueryProjection(
            profile_id=profile_id,
            count=1,
            rows=(
                LedgerEvidenceAutomationRecordProjection(
                    evidence_id=record.evidence_id,
                    bucket_id=record.bucket_id,
                    source_file_name=_EVIDENCE_FILE_NAME,
                    source_sha256=record.source_sha256,
                    attachment_id=record.attachment_id,
                    media_kind=record.media_kind,
                    notes=record.notes,
                    created_at=record.created_at,
                    updated_at=record.updated_at,
                ),
            ),
        ),
        verify=verify,
    )


def _document_texts(view: LedgerEvidenceReviewViewProjection) -> tuple[str, ...]:
    """Every distinctive text the person's review carries from the document."""
    draft = view.draft
    texts = [getattr(draft, name) for name in DRAFT_TEXT_FIELDS_WITHHELD_FROM_AUTOMATION]
    texts.extend(line.description for line in draft.lines)
    for row in draft.provenance:
        texts.extend((row.anchor, row.refused_anchor, row.role_evidence))
        texts.extend(candidate.value for candidate in row.candidates)
    return tuple(sorted({text for text in texts if isinstance(text, str) and _is_distinctive_text(text)}))


def _prepare_review_summary(context: ConformanceFamilyContext) -> ConformancePreparation:
    profile_id = context.profile_id
    seeded = prepare_evidence_followup_conformance_case(
        LEDGER_EVIDENCE_REVIEW_VIEW_OPERATION_DEFINITION_ID, profile_id=profile_id, operation=context.operation
    )
    view = seeded.expected_read
    assert isinstance(view, LedgerEvidenceReviewViewProjection)
    document_texts = _document_texts(view)
    # The scenario proves nothing unless the stored draft holds document text.
    assert document_texts

    def verify(outcome: ConformanceOutcome) -> None:
        summary = outcome.resolve_result(LedgerEvidenceReviewSummaryProjection)
        draft = view.draft
        assert summary.profile_id == profile_id
        assert summary.evidence_reference == view.evidence_reference
        assert summary.extractor == view.extractor
        assert summary.drafted_at == view.drafted_at
        assert summary.grand_total == draft.grand_total
        assert summary.taxable_base == draft.taxable_base
        assert summary.iva_amount == draft.iva_amount
        assert summary.suggested_kind == draft.suggested_kind
        assert len(summary.lines) == len(draft.lines)
        assert [row.field for row in summary.fields] == [row.field for row in draft.provenance]
        assert [row.grounding for row in summary.fields] == [row.grounding for row in draft.provenance]
        assert [row.kind for row in summary.discrepancies] == [row.kind for row in draft.discrepancies]
        assert [row.blocker_id for row in summary.blockers] == [row.blocker_id for row in view.blockers]
        assert set(summary.withheld_text_fields) == {
            name for name in DRAFT_TEXT_FIELDS_WITHHELD_FROM_AUTOMATION if getattr(draft, name) is not None
        }
        assert summary.text_withheld is True
        released = summary.model_dump_json()
        leaked = [text for text in document_texts if text in released]
        assert not leaked

    return ConformancePreparation(
        subject_ref=profile_operation_subject(str(profile_id)),
        request=seeded.request,
        verify=verify,
    )


def _prepare(context: ConformanceFamilyContext) -> ConformancePreparation:
    definition_id = context.definition.definition_id
    if definition_id == LEDGER_EVIDENCE_QUERY_OPERATION_DEFINITION_ID:
        return _prepare_query(context)
    if definition_id == LEDGER_EVIDENCE_REVIEW_SUMMARY_OPERATION_DEFINITION_ID:
        return _prepare_review_summary(context)
    raise AssertionError(f"no automation-facing evidence conformance scenario for {definition_id}")


LEDGER_EVIDENCE_AUTOMATION_CONFORMANCE_FAMILY = ConformanceFamily(
    cases=tuple(
        # Each is a single-phase read that publishes its own id and settles NONE
        # (application/ledger/evidence_read_operation.py execute_query,
        # application/ledger/evidence_followup_operation.py LedgerEvidenceReviewSummaryExecutor).
        RegisteredExecutorConformanceCase(
            definition_id,
            OperationTerminalCondition.SUCCEEDED,
            OperationEffect.NONE,
            (definition_id,),
        )
        for definition_id in (
            LEDGER_EVIDENCE_QUERY_OPERATION_DEFINITION_ID,
            LEDGER_EVIDENCE_REVIEW_SUMMARY_OPERATION_DEFINITION_ID,
        )
    ),
    prepare=_prepare,
)
