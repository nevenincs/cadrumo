"""Encrypted, full-payload fixtures for evidence follow-up operation conformance."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

from pydantic import BaseModel

from ...adapters.persistence.llm.consent_ledger import EvidenceConsentLedger
from ...adapters.persistence.storage.tests.profile_capsule_runtime import upsert_test_profile_facts
from ...application.ledger.attachment_review import get_attachment_review_item, list_attachment_review_queue
from ...application.ledger.confirmation_gate import confirmation_blockers
from ...application.ledger.consent_withdrawal import ConsentedDispatch, survey_cloud_consent
from ...application.ledger.country_vocabulary_advisory import country_vocabulary_advisory
from ...application.ledger.evidence import PurchaseInvoiceEvidenceService
from ...application.ledger.evidence_followup_contracts import (
    LEDGER_EVIDENCE_ATTACHMENT_QUEUE_OPERATION_DEFINITION_ID,
    LEDGER_EVIDENCE_ATTACHMENT_VIEW_OPERATION_DEFINITION_ID,
    LEDGER_EVIDENCE_CONSENT_LIST_OPERATION_DEFINITION_ID,
    LEDGER_EVIDENCE_REVIEW_LIST_OPERATION_DEFINITION_ID,
    LEDGER_EVIDENCE_REVIEW_VIEW_OPERATION_DEFINITION_ID,
    CloudDerivedArtefactProjection,
    ConsentedDispatchProjection,
    ConsentWithdrawalSurveyProjection,
    CountryVocabularyAdvisoryProjection,
    CountryVocabularyWarningProjection,
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
    PartyAttributionAdvisoryProjection,
    PartyAttributionWarningProjection,
)
from ...application.ledger.extraction_draft_repository import bind_extraction_draft_repository_factory
from ...application.ledger.extraction_draft_store import load_extraction_drafts, write_extraction_draft
from ...application.ledger.filer_establishment import FILER_POSTCODE_FACT_PATH
from ...application.ledger.invoice_draft_extraction import extract_invoice_draft_from_evidence
from ...application.ledger.invoice_evidence_operation_dtos import (
    ConfirmationBlockerProjectionV1,
    InvoiceDraftProjectionV1,
)
from ...application.ledger.invoice_extraction_authority import default_invoice_extraction_period
from ...application.ledger.party_attribution import party_attribution_advisory
from ...application.ledger.review_advisories import review_advisory_kinds
from ...core.time.clock import now
from ...domain.attachments.enums import AttachmentKind, AttachmentSource
from ...domain.attachments.models import Attachment
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.calculations.registry.governed_fact_scope import validating_governed_facts
from ...domain.iva.regime_legend import resolve_regime_legends
from ...domain.user_profile.values import UserProfileFact
from ..adapter_composition import build_attachment_store
from ..evidence_followup_operation_composition import build_ledger_evidence_followup_operation_ports
from ..invoice_evidence_operation_composition import build_invoice_evidence_operation_ports


@dataclass(frozen=True, slots=True)
class EvidenceFollowupConformanceCase:
    """Typed request and independently assembled, encrypted read expectation."""

    request: BaseModel
    expected_read: BaseModel


def prepare_evidence_followup_conformance_case(
    definition_id: str,
    *,
    profile_id: UUID,
    operation: PinnedAuthorityOperation,
) -> EvidenceFollowupConformanceCase:
    """Create real encrypted evidence, draft, consent and attachment rows for one route."""
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
    bucket_id = str(profile_id)
    invoice_ports = build_invoice_evidence_operation_ports(bucket_id=bucket_id)
    source = (
        Path(__file__).resolve().parents[2]
        / "application/ledger/tests/_evidence_corpus/facturae_32_recargo_invoice.xml"
    )
    evidence = (
        PurchaseInvoiceEvidenceService(ports=invoice_ports.evidence_ports)
        .add(
            bucket_id=bucket_id,
            source_path=source,
        )
        .record
    )

    attachment_store = build_attachment_store(bucket_id)
    drive_bytes = b"<drive-invoice-fixture>pending-review</drive-invoice-fixture>"
    attachment_id = attachment_store.put_bytes(drive_bytes)
    attachment_store.write_manifest(
        Attachment(
            attachment_id=attachment_id,
            sha256=attachment_id,
            kind=AttachmentKind.DRIVE_DOCUMENT,
            source=AttachmentSource.GOOGLE_DRIVE,
            source_reference="https://drive.google.com/file/d/1AbcDEfgHIjkLMnoPQRstuVWxyz12345",
            mime_type="application/xml",
            bytes_size=len(drive_bytes),
            captured_at=now(),
            bucket_id=bucket_id,
        ),
    )

    period = default_invoice_extraction_period()
    with validating_governed_facts(operation):
        legends = resolve_regime_legends(operation=operation, effective_date=period.end_date)
        draft = extract_invoice_draft_from_evidence(
            bucket_id=bucket_id,
            evidence_id=evidence.evidence_id,
            settings=invoice_ports.settings,
            ports=invoice_ports.extraction_ports,
            operation=operation,
            legends=legends,
        )

    followup_ports = build_ledger_evidence_followup_operation_ports(settings=invoice_ports.settings)
    with bind_extraction_draft_repository_factory(followup_ports.extraction_draft_repository_factory):
        write_extraction_draft(
            bucket_id=bucket_id,
            evidence_reference=evidence.evidence_id,
            draft=draft,
            extractor="structured-invoice-fixture",
            settings=invoice_ports.settings,
            read_transports=("openai",),
        )
        encrypted_drafts = load_extraction_drafts(bucket_id, invoice_ports.settings)
    stored = next(row for row in encrypted_drafts.drafts if row.evidence_reference == evidence.evidence_id)

    consent_ledger = EvidenceConsentLedger()
    consent_ledger.append(
        evidence_content_address=evidence.source_sha256,
        provider="openai",
        model="fixture-model",
        surface="app.ledger.evidence.extract",
    )
    consent_entries = tuple(
        ConsentedDispatch(
            profile_bucket_id=entry.profile_bucket_id,
            evidence_content_address=entry.evidence_content_address,
            provider=entry.provider,
            model=entry.model,
            surface=entry.surface,
            recorded_at=entry.recorded_at,
        )
        for entry in consent_ledger.load_entries()
    )

    if definition_id == LEDGER_EVIDENCE_ATTACHMENT_QUEUE_OPERATION_DEFINITION_ID:
        request: BaseModel = LedgerEvidenceAttachmentQueueRequest(profile_id=profile_id)
        rows = list_attachment_review_queue(attachment_store)
        expected: BaseModel = LedgerEvidenceAttachmentQueueProjection(
            profile_id=profile_id,
            count=len(rows),
            rows=rows,
        )
    elif definition_id == LEDGER_EVIDENCE_ATTACHMENT_VIEW_OPERATION_DEFINITION_ID:
        request = LedgerEvidenceAttachmentViewRequest(profile_id=profile_id, attachment_id=attachment_id)
        expected = LedgerEvidenceAttachmentViewProjection(
            profile_id=profile_id,
            item=get_attachment_review_item(attachment_store, attachment_id),
        )
    elif definition_id == LEDGER_EVIDENCE_CONSENT_LIST_OPERATION_DEFINITION_ID:
        request = LedgerEvidenceConsentListRequest(profile_id=profile_id)
        with bind_extraction_draft_repository_factory(followup_ports.extraction_draft_repository_factory):
            survey = survey_cloud_consent(
                bucket_id=bucket_id,
                settings=invoice_ports.settings,
                consent_entries=consent_entries,
            )
        assert survey.transmitted_bytes_are_unrecallable is True
        expected = LedgerEvidenceConsentListProjection(
            profile_id=profile_id,
            survey=ConsentWithdrawalSurveyProjection(
                consented_dispatches=tuple(
                    ConsentedDispatchProjection(
                        profile_bucket_id=row.profile_bucket_id,
                        evidence_content_address=row.evidence_content_address,
                        provider=row.provider,
                        model=row.model,
                        surface=row.surface,
                        recorded_at=row.recorded_at,
                    )
                    for row in survey.consented_dispatches
                ),
                cloud_derived_artefacts=tuple(
                    CloudDerivedArtefactProjection(
                        evidence_reference=row.evidence_reference,
                        provenance_stamp=row.provenance_stamp,
                        transport=row.transport,
                        drafted_at=row.drafted_at,
                    )
                    for row in survey.cloud_derived_artefacts
                ),
                transmitted_bytes_are_unrecallable=True,
            ),
        )
    elif definition_id == LEDGER_EVIDENCE_REVIEW_LIST_OPERATION_DEFINITION_ID:
        request = LedgerEvidenceReviewListRequest(profile_id=profile_id)
        with validating_governed_facts(operation):
            rows = tuple(
                EvidenceReviewQueueRowProjection(
                    evidence_reference=row.evidence_reference,
                    extractor=row.extractor,
                    drafted_at=row.drafted_at,
                    blocking_count=len(blockers := confirmation_blockers(row.draft)),
                    reasons=tuple(sorted({item.reason for item in blockers}, key=lambda item: item.value)),
                    advisory_count=len(advisories := review_advisory_kinds(row.draft, operation=operation)),
                    advisories=advisories,
                )
                for row in sorted(encrypted_drafts.drafts, key=lambda item: item.evidence_reference)
            )
        expected = LedgerEvidenceReviewListProjection(profile_id=profile_id, filters=(), rows=rows)
    elif definition_id == LEDGER_EVIDENCE_REVIEW_VIEW_OPERATION_DEFINITION_ID:
        request = LedgerEvidenceReviewViewRequest(
            profile_id=profile_id,
            evidence_reference=evidence.evidence_id,
        )
        # The registered read consumes the repository's hydrated value, not
        # the object returned before persistence. Build every expected review
        # fact from that same canonical roundtrip so serialization and
        # revalidation remain part of the conformance proof.
        persisted_draft = stored.draft
        with validating_governed_facts(operation):
            legends = resolve_regime_legends(operation=operation, effective_date=period.end_date)
            party_advisory = party_attribution_advisory(persisted_draft, legends=legends, operation=operation)
            country_advisory = country_vocabulary_advisory(persisted_draft, operation=operation)
        projected_party_advisory = (
            None
            if party_advisory is None
            else PartyAttributionAdvisoryProjection(
                parties=tuple(
                    PartyAttributionWarningProjection(
                        role=row.role,
                        fields=row.fields,
                        scope_if_attributed=(
                            row.scope_if_attributed.value if row.scope_if_attributed is not None else None
                        ),
                    )
                    for row in party_advisory.parties
                ),
            )
        )
        projected_country_advisory = (
            None
            if country_advisory is None
            else CountryVocabularyAdvisoryProjection(
                parties=tuple(
                    CountryVocabularyWarningProjection(
                        role=row.role,
                        field=row.field,
                        stated_code=row.stated_code,
                        status=row.status,
                        detail=row.detail,
                    )
                    for row in country_advisory.parties
                ),
            )
        )
        expected = LedgerEvidenceReviewViewProjection(
            profile_id=profile_id,
            evidence_reference=stored.evidence_reference,
            extractor=stored.extractor,
            drafted_at=stored.drafted_at,
            draft=InvoiceDraftProjectionV1.from_draft(persisted_draft),
            blockers=tuple(
                ConfirmationBlockerProjectionV1.from_blocker(row) for row in confirmation_blockers(persisted_draft)
            ),
            party_attribution_advisory=projected_party_advisory,
            country_vocabulary_advisory=projected_country_advisory,
        )
    else:
        raise ValueError(f"unsupported evidence follow-up operation: {definition_id}")

    return EvidenceFollowupConformanceCase(request=request, expected_read=expected)


__all__ = ["EvidenceFollowupConformanceCase", "prepare_evidence_followup_conformance_case"]
