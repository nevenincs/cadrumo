"""Encrypted structured-document fixtures for supervised evidence operations."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

from pydantic import BaseModel

from ...adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from ...adapters.persistence.storage.tests.profile_capsule_runtime import upsert_test_profile_facts
from ...application.ledger.confirmation_record import load_confirmation_records, re_stamped_provenance
from ...application.ledger.evidence import PurchaseInvoiceEvidenceService
from ...application.ledger.evidence_draft import printed_total_discrepancy
from ...application.ledger.filer_establishment import FILER_POSTCODE_FACT_PATH
from ...application.ledger.invoice_confirmation import (
    InvoiceConfirmationResult,
    PreparedInvoiceConfirmation,
    invoice_draft_review_sha256,
    prepare_invoice_confirmation_from_evidence,
)
from ...application.ledger.invoice_draft_extraction import extract_invoice_draft_from_evidence
from ...application.ledger.invoice_evidence_operation import (
    LedgerEvidenceConfirmProjection,
    LedgerEvidenceConfirmRequest,
    LedgerEvidenceExtractProjection,
    LedgerEvidenceExtractRequest,
    LedgerEvidenceReaderReadinessProjection,
    LedgerEvidenceReaderReadinessRequest,
)
from ...application.ledger.invoice_evidence_operation_dtos import (
    InvoiceConfirmationProjectionV1,
    InvoiceDraftProjectionV1,
)
from ...application.ledger.invoice_extraction_authority import default_invoice_extraction_period
from ...application.local_reader import read_local_reader_status
from ...core.operations import OperationEffect
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.calculations.registry.governed_fact_scope import validating_governed_facts
from ...domain.iva.classification import InvoiceKind
from ...domain.iva.regime_legend import resolve_regime_legends
from ...domain.user_profile.values import UserProfileFact
from ..invoice_evidence_operation_composition import build_invoice_evidence_operation_ports


@dataclass(frozen=True)
class InvoiceEvidenceConformanceCase:
    """Exact request and independent canonical pre-write expectations."""

    request: BaseModel
    expected_read: BaseModel | None = None
    prepared: PreparedInvoiceConfirmation | None = None


def prepare_invoice_evidence_conformance_case(
    definition_id: str, *, profile_id: UUID, operation: PinnedAuthorityOperation
) -> InvoiceEvidenceConformanceCase:
    """Register a bundled synthetic XML in actual encrypted attachment custody."""
    if definition_id == "ledger.evidence.reader-readiness":
        return InvoiceEvidenceConformanceCase(
            request=LedgerEvidenceReaderReadinessRequest(profile_id=profile_id),
            expected_read=LedgerEvidenceReaderReadinessProjection.from_status(
                profile_id=profile_id, status=read_local_reader_status()
            ),
        )
    upsert_test_profile_facts(
        profile_id,
        (
            UserProfileFact(path="iva.m303_regime_composition", value="general"),
            UserProfileFact(path="tax_residence.jurisdiction_scope", value="common_regime"),
            UserProfileFact(path="iva.redeme_enrolled", value=False),
            UserProfileFact(path="iva.cash_accounting_regime_enrolled", value=False),
            UserProfileFact(path="iva.voluntary_sii_enrolled", value=False),
            UserProfileFact(path="iva.hydrocarbon_deposit_advance_payment_deduction_entitled", value=False),
            UserProfileFact(path=FILER_POSTCODE_FACT_PATH, value="28013"),
        ),
    )
    ports = build_invoice_evidence_operation_ports(bucket_id=str(profile_id))
    source = (
        Path(__file__).resolve().parents[2]
        / "application/ledger/tests/_evidence_corpus/facturae_32_recargo_invoice.xml"
    )
    evidence = (
        PurchaseInvoiceEvidenceService(ports=ports.evidence_ports)
        .add(bucket_id=str(profile_id), source_path=source)
        .record
    )
    with validating_governed_facts(operation):
        legends = resolve_regime_legends(
            operation=operation, effective_date=default_invoice_extraction_period().end_date
        )
        draft = extract_invoice_draft_from_evidence(
            bucket_id=str(profile_id),
            evidence_id=evidence.evidence_id,
            settings=ports.settings,
            ports=ports.extraction_ports,
            operation=operation,
            legends=legends,
        )
        review_sha256 = invoice_draft_review_sha256(draft)
        if definition_id == "ledger.evidence.extract":
            return InvoiceEvidenceConformanceCase(
                request=LedgerEvidenceExtractRequest(profile_id=profile_id, evidence_id=evidence.evidence_id),
                expected_read=LedgerEvidenceExtractProjection(
                    profile_id=profile_id,
                    evidence_id=evidence.evidence_id,
                    source_sha256=evidence.source_sha256,
                    draft_review_sha256=review_sha256,
                    consent_audit_effect=OperationEffect.NONE,
                    draft=InvoiceDraftProjectionV1.from_draft(draft),
                ),
            )
        prepared = prepare_invoice_confirmation_from_evidence(
            bucket_id=str(profile_id),
            kind=InvoiceKind.RECEIVED,
            counterparty_country="ES",
            evidence_id=evidence.evidence_id,
            expected_source_sha256=evidence.source_sha256,
            expected_draft_review_sha256=review_sha256,
            settings=ports.settings,
            catalogue_creation_ports=ports.catalogue_creation_ports,
            counterparty_establishment_repository=ports.counterparty_establishment_repository,
            evidence_ports=ports.evidence_ports,
            extraction_ports=ports.extraction_ports,
            operation=operation,
            legends=legends,
        )
    return InvoiceEvidenceConformanceCase(
        request=LedgerEvidenceConfirmRequest(
            profile_id=profile_id,
            evidence_id=evidence.evidence_id,
            kind=InvoiceKind.RECEIVED,
            expected_source_sha256=evidence.source_sha256,
            expected_draft_review_sha256=review_sha256,
        ),
        prepared=prepared,
    )


def assert_invoice_evidence_confirmation_persisted(
    case: InvoiceEvidenceConformanceCase, result: LedgerEvidenceConfirmProjection, *, operation_id: str
) -> None:
    """Compare the full disclosure with encrypted invoice, link and audit records."""
    assert case.prepared is not None
    prepared = case.prepared
    ports = build_invoice_evidence_operation_ports(bucket_id=prepared.bucket_id)
    catalogue = InvoiceCatalogueRepository(bucket_id=prepared.bucket_id).load()
    assert len(catalogue.invoices) == 1
    stored = catalogue.invoices[prepared.candidate.invoice_id]
    assert stored == prepared.candidate.model_copy(
        update={"created_at": stored.created_at, "updated_at": stored.updated_at}
    )
    assert stored.created_at is not None
    records = load_confirmation_records(prepared.bucket_id).records
    assert len(records) == 1
    record = records[0]
    assert record.confirmation_id == result.confirmation.confirmation_id
    assert record.confirmed_by == f"operation:{operation_id}"
    assert record.bucket_id == prepared.bucket_id
    assert record.invoice_id == stored.invoice_id
    assert record.evidence_reference == prepared.evidence_id
    assert record.evidence_sha256 == result.source_sha256
    manifest = ports.invoice_confirmation_ports.attachment_store.load_manifest(prepared.preparation.attachment_id)
    assert manifest.linked_invoice_ids == (stored.invoice_id,)
    canonical = InvoiceConfirmationResult(
        invoice=stored,
        draft=prepared.preparation.draft,
        created=True,
        confirmation_id=record.confirmation_id,
        confirmed_provenance=re_stamped_provenance(draft=prepared.preparation.draft, assertions=record.assertions),
        total_discrepancy=printed_total_discrepancy(draft=prepared.preparation.draft, invoice=stored),
        establishment=prepared.preparation.establishment,
    )
    assert result.confirmation == InvoiceConfirmationProjectionV1.from_result(canonical)


__all__ = [
    "InvoiceEvidenceConformanceCase",
    "assert_invoice_evidence_confirmation_persisted",
    "prepare_invoice_evidence_conformance_case",
]
