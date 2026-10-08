"""Registered-executor conformance scenario for ledger evidence batch ingestion."""

from __future__ import annotations

import hashlib
import shutil
from pathlib import Path

from ...application.ledger.batch_ingest import batch_item_identity
from ...application.ledger.evidence import PurchaseInvoiceEvidenceService
from ...application.ledger.evidence_ingestion_contracts import (
    LEDGER_EVIDENCE_BATCH_OPERATION_DEFINITION_ID,
    LedgerEvidenceBatchProjection,
    LedgerEvidenceBatchRequest,
)
from ...application.ledger.extraction_draft_store import read_extraction_draft
from ...core.config import load_settings
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ...domain.iva.classification import InvoiceKind
from ..adapter_composition import build_ledger_evidence_ports
from .conformance_family_contract import (
    ConformanceFamily,
    ConformanceFamilyContext,
    ConformanceOutcome,
    ConformancePreparation,
    RegisteredExecutorConformanceCase,
)

# A bundled synthetic Facturae invoice: a structured document, so it is read by the
# deterministic structured reader and needs no model runtime.
_STRUCTURED_INVOICE = (
    Path(__file__).resolve().parents[2]
    / "application"
    / "ledger"
    / "tests"
    / "_evidence_corpus"
    / "facturae_32_recargo_invoice.xml"
)


def _prepare_batch(context: ConformanceFamilyContext) -> ConformancePreparation:
    source = context.input_root / _STRUCTURED_INVOICE.name
    shutil.copyfile(_STRUCTURED_INVOICE, source)
    content_address = hashlib.sha256(source.read_bytes()).hexdigest()
    bucket_id = str(context.profile_id)

    def verify(outcome: ConformanceOutcome) -> None:
        projection = outcome.resolve_result(LedgerEvidenceBatchProjection)
        assert projection.profile_id == context.profile_id
        assert projection.direction is InvoiceKind.RECEIVED
        assert projection.run.unresolved == ()
        assert projection.run.inference_pause is None
        (item,) = projection.run.items
        # Identity is the content address plus the declared direction. batch_ingest.py.
        assert item.content_address == content_address
        assert item.identity == batch_item_identity(content_address=content_address, direction=InvoiceKind.RECEIVED)
        assert item.source_name == source.name
        assert item.direction is InvoiceKind.RECEIVED
        assert item.needed_inference is False
        assert item.refusal_code is None
        assert item.refusal_verdict is None

        records = PurchaseInvoiceEvidenceService(ports=build_ledger_evidence_ports(bucket_id=bucket_id)).list_all(
            bucket_id=bucket_id
        )
        (record,) = records
        assert record.source_sha256 == content_address

        # A draft with an unresolved finding is held for review; a clean one is ingested.
        # batch_ingest.py `_ingest_one_batch_item`.
        stored = read_extraction_draft(
            bucket_id=bucket_id, evidence_reference=record.evidence_id, settings=load_settings()
        )
        assert stored is not None
        held = bool(stored.draft.discrepancies) or any(envelope.candidates for envelope in stored.draft.provenance)
        assert item.status == ("pending_review" if held else "ingested")

        # Both the evidence record and its draft were written, and nothing was refused.
        assert projection.effect is OperationEffect.UPDATED
        assert projection.write_count > 0

    return ConformancePreparation(
        subject_ref=profile_operation_subject(bucket_id),
        request=LedgerEvidenceBatchRequest(
            profile_id=context.profile_id,
            sources=(source.name,),
            source_directory=str(context.input_root),
            direction=InvoiceKind.RECEIVED,
        ),
        verify=verify,
    )


_PREPARE = {
    LEDGER_EVIDENCE_BATCH_OPERATION_DEFINITION_ID: _prepare_batch,
}


def _prepare(context: ConformanceFamilyContext) -> ConformancePreparation:
    prepare = _PREPARE.get(context.definition.definition_id)
    if prepare is None:
        raise AssertionError(
            f"no ledger evidence ingestion conformance scenario for {context.definition.definition_id}"
        )
    return prepare(context)


LEDGER_EVIDENCE_INGESTION_CONFORMANCE_FAMILY = ConformanceFamily(
    cases=(
        RegisteredExecutorConformanceCase(
            LEDGER_EVIDENCE_BATCH_OPERATION_DEFINITION_ID,
            OperationTerminalCondition.SUCCEEDED,
            OperationEffect.UPDATED,
            (LEDGER_EVIDENCE_BATCH_OPERATION_DEFINITION_ID,),
        ),
    ),
    prepare=_prepare,
    closes_model_runtime=True,
)
