"""Registered-executor conformance scenario for the stored-document page read."""

from __future__ import annotations

import hashlib

from ...application.ledger.evidence import PurchaseInvoiceEvidenceService
from ...application.ledger.evidence_page_contracts import (
    LEDGER_EVIDENCE_PAGE_OPERATION_DEFINITION_ID,
    EvidencePageMediaType,
    LedgerEvidencePageProjection,
    LedgerEvidencePageRequest,
)
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ...tests.pdf_fixtures import multi_page_text_pdf_bytes
from ..adapter_composition_work_ports import build_ledger_evidence_ports
from .conformance_family_contract import (
    ConformanceFamily,
    ConformanceFamilyContext,
    ConformanceOutcome,
    ConformancePreparation,
    RegisteredExecutorConformanceCase,
)

_EVIDENCE_FILE_NAME = "conformance-page-evidence.pdf"
_MAX_WIDTH = 480


def _prepare(context: ConformanceFamilyContext) -> ConformancePreparation:
    if context.definition.definition_id != LEDGER_EVIDENCE_PAGE_OPERATION_DEFINITION_ID:
        raise AssertionError(f"no page-read conformance scenario for {context.definition.definition_id}")
    bucket_id = str(context.profile_id)
    pdf = multi_page_text_pdf_bytes(("Conformance page one",), ("Conformance page two",))
    source = context.input_root / _EVIDENCE_FILE_NAME
    source.write_bytes(pdf)
    record = (
        PurchaseInvoiceEvidenceService(ports=build_ledger_evidence_ports(bucket_id=bucket_id))
        .add(bucket_id=bucket_id, source_path=source)
        .record
    )

    def verify(outcome: ConformanceOutcome) -> None:
        page = outcome.resolve_result(LedgerEvidencePageProjection)
        assert page.profile_id == context.profile_id
        assert (page.evidence_id, page.attachment_id) == (record.evidence_id, record.attachment_id)
        assert page.media_type is EvidencePageMediaType.PDF
        assert (page.page, page.page_count, page.width) == (2, 2, _MAX_WIDTH)
        assert page.source_sha256 == hashlib.sha256(pdf).hexdigest()
        assert page.file_name == _EVIDENCE_FILE_NAME
        released = page.model_dump_json()
        assert str(context.input_root) not in released
        assert context.input_root.name not in released

    return ConformancePreparation(
        subject_ref=profile_operation_subject(bucket_id),
        request=LedgerEvidencePageRequest(
            profile_id=context.profile_id, evidence_id=record.evidence_id, page=2, max_width=_MAX_WIDTH
        ),
        verify=verify,
    )


LEDGER_EVIDENCE_PAGE_CONFORMANCE_FAMILY = ConformanceFamily(
    cases=(
        # A single-phase read that publishes its own id and settles NONE
        # (application/ledger/evidence_page_operation.py LedgerEvidencePageExecutor).
        RegisteredExecutorConformanceCase(
            LEDGER_EVIDENCE_PAGE_OPERATION_DEFINITION_ID,
            OperationTerminalCondition.SUCCEEDED,
            OperationEffect.NONE,
            (LEDGER_EVIDENCE_PAGE_OPERATION_DEFINITION_ID,),
        ),
    ),
    prepare=_prepare,
)
