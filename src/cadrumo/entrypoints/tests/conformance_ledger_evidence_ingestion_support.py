"""Registered-executor conformance scenarios for ledger evidence batch ingestion and Drive acquisition."""

from __future__ import annotations

import hashlib
import shutil
from datetime import date
from decimal import Decimal
from pathlib import Path

from ...adapters.outbound.storage.errors import OutboundStorageValidationError
from ...application.ledger.batch_ingest import batch_item_identity
from ...application.ledger.evidence import PurchaseInvoiceEvidenceService
from ...application.ledger.evidence_ingestion_contracts import (
    LEDGER_EVIDENCE_BATCH_OPERATION_DEFINITION_ID,
    LEDGER_EVIDENCE_PULL_ALL_OPERATION_DEFINITION_ID,
    LEDGER_EVIDENCE_PULL_OPERATION_DEFINITION_ID,
    LedgerEvidenceBatchProjection,
    LedgerEvidenceBatchRequest,
    LedgerEvidencePullAllRequest,
    LedgerEvidencePullRequest,
)
from ...application.ledger.extraction_draft_store import read_extraction_draft
from ...core.config import load_settings
from ...core.errors.error_codes import get_registered_error_code
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ...domain.attachments.enums import DocumentLinkSource
from ...domain.iva.classification import InvoiceKind
from ..adapter_composition import build_ledger_evidence_ports
from .conformance_family_contract import (
    ConformanceFamily,
    ConformanceFamilyContext,
    ConformanceOutcome,
    ConformancePreparation,
    RegisteredExecutorConformanceCase,
)
from .conformance_ledger_seed_support import ledger_unchanged_verifier, seed_manual_transaction

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
_DRIVE_FILE_URL = "https://drive.google.com/file/d/1AbCdEfGhIjKlMnOpQrStUvWxYz0123/view"
_DRIVE_FOLDER_URL = "https://drive.google.com/drive/folders/1AbCdEfGhIjKlMnOpQrStUvWxYz0123"


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


def _prepare_pull(context: ConformanceFamilyContext) -> ConformancePreparation:
    transaction_id = seed_manual_transaction(
        context, booked_date=date(2025, 4, 3), amount=Decimal("35.00"), description="evidence pull row"
    )
    return ConformancePreparation(
        subject_ref=profile_operation_subject(str(context.profile_id)),
        request=LedgerEvidencePullRequest(
            profile_id=context.profile_id,
            transaction_id=transaction_id[:12],
            source=DocumentLinkSource.GOOGLE_DRIVE,
            reference=_DRIVE_FILE_URL,
        ),
        verify=ledger_unchanged_verifier(context),
    )


def _prepare_pull_all(context: ConformanceFamilyContext) -> ConformancePreparation:
    return ConformancePreparation(
        subject_ref=profile_operation_subject(str(context.profile_id)),
        request=LedgerEvidencePullAllRequest(profile_id=context.profile_id, folder=_DRIVE_FOLDER_URL),
        verify=ledger_unchanged_verifier(context),
    )


_PREPARE = {
    LEDGER_EVIDENCE_BATCH_OPERATION_DEFINITION_ID: _prepare_batch,
    LEDGER_EVIDENCE_PULL_OPERATION_DEFINITION_ID: _prepare_pull,
    LEDGER_EVIDENCE_PULL_ALL_OPERATION_DEFINITION_ID: _prepare_pull_all,
}


def _prepare(context: ConformanceFamilyContext) -> ConformancePreparation:
    prepare = _PREPARE.get(context.definition.definition_id)
    if prepare is None:
        raise AssertionError(
            f"no ledger evidence ingestion conformance scenario for {context.definition.definition_id}"
        )
    return prepare(context)


# The isolated profile has no Google OAuth client, so the first outbound read refuses
# before any byte is fetched or written. factory.py `_build_oauth_desktop_credentials`.
_DRIVE_NOT_CONFIGURED_REFUSAL = get_registered_error_code(OutboundStorageValidationError).code

LEDGER_EVIDENCE_INGESTION_CONFORMANCE_FAMILY = ConformanceFamily(
    cases=(
        RegisteredExecutorConformanceCase(
            LEDGER_EVIDENCE_BATCH_OPERATION_DEFINITION_ID,
            OperationTerminalCondition.SUCCEEDED,
            OperationEffect.UPDATED,
            (LEDGER_EVIDENCE_BATCH_OPERATION_DEFINITION_ID,),
        ),
        RegisteredExecutorConformanceCase(
            LEDGER_EVIDENCE_PULL_OPERATION_DEFINITION_ID,
            OperationTerminalCondition.REFUSED,
            OperationEffect.NONE,
            (LEDGER_EVIDENCE_PULL_OPERATION_DEFINITION_ID,),
            expected_refusal_ref=_DRIVE_NOT_CONFIGURED_REFUSAL,
        ),
        RegisteredExecutorConformanceCase(
            LEDGER_EVIDENCE_PULL_ALL_OPERATION_DEFINITION_ID,
            OperationTerminalCondition.REFUSED,
            OperationEffect.NONE,
            (LEDGER_EVIDENCE_PULL_ALL_OPERATION_DEFINITION_ID,),
            expected_refusal_ref=_DRIVE_NOT_CONFIGURED_REFUSAL,
        ),
    ),
    prepare=_prepare,
    closes_model_runtime=True,
)
