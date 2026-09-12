"""CLI composition for the invoice-draft extraction use case."""

from __future__ import annotations

import httpx

from ...adapters.inbound.einvoice.parsers import parse_einvoice_document
from ...adapters.inbound.einvoice.xml import EInvoiceXmlParseError
from ...adapters.outbound.llm.errors import LLMConsentError, LLMPdfRasterisationError, LLMProviderError
from ...adapters.outbound.llm.evidence_draft_text import TextInvoiceFieldExtractor, extract_invoice_fields_from_text
from ...adapters.outbound.llm.evidence_draft_vision import LocalVisionDocumentTranscriber, transcribe_document_images
from ...adapters.outbound.llm.models import MultimodalImageInput
from ...adapters.outbound.llm.preconditions import LLMPreconditionCondition, llm_no_recovery_verdict
from ...adapters.outbound.llm.providers.local import rasterise_pdf_pages_to_base64_png
from ...adapters.outbound.llm.supply_nature_proposal import SupplyNatureProposer
from ...adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from ...adapters.persistence.storage.attachment import AttachmentStore
from ...adapters.persistence.storage.runtime_repository import secure_object_repository_for_bucket
from ...application.ledger.document_transcription import DocumentTranscription
from ...application.ledger.evidence import PurchaseInvoiceEvidenceService
from ...application.ledger.evidence_errors import PurchaseInvoiceEvidenceInputError
from ...application.ledger.evidence_input import (
    EvidenceInput,
    resolve_attachment_evidence_input,
    resolve_purchase_invoice_evidence_input,
)
from ...application.ledger.evidence_reference import (
    EvidenceReferenceOutcome,
    classify_evidence_reference,
    refuse_reference_without_document_bytes,
    refuse_unresolved_evidence_reference,
)
from ...application.ledger.invoice_draft_extraction_ports import (
    EvidenceConsentProof,
    InvoiceDraftExtractionPorts,
    InvoiceDraftReaderUnavailableError,
    StructuredInvoiceReadError,
    VisionImage,
)
from ...application.ledger.invoice_extraction_authority import InvoiceExtractionAuthorityValues
from ...core.config import Settings
from ...core.config_support import LLMProvider
from ...core.operator_action_enums import ActionEvidenceProvenance
from ...core.optional_extras import MissingOptionalExtraError
from ...domain.iva.supply_nature import SupplyNature


def invoice_draft_extraction_ports() -> InvoiceDraftExtractionPorts:
    """Bind the CLI evidence commands to their concrete adapters."""

    def resolve_evidence_input(
        bucket_id: str, evidence_id: str | None, attachment_id: str | None, settings: Settings
    ) -> EvidenceInput:
        store = AttachmentStore(objects=secure_object_repository_for_bucket(bucket_id, settings))
        if evidence_id is not None:
            reference = classify_evidence_reference(
                evidence_id,
                bucket_id=bucket_id,
                evidence_records=PurchaseInvoiceEvidenceService(settings=settings).list_all(bucket_id=bucket_id),
                invoices=InvoiceCatalogueRepository(bucket_id=bucket_id).load(),
            )
            if reference.outcome is EvidenceReferenceOutcome.UNRESOLVED:
                raise refuse_unresolved_evidence_reference(evidence_id)
            if reference.record is None:
                raise refuse_reference_without_document_bytes(evidence_id)
            return resolve_purchase_invoice_evidence_input(reference.record, store=store)
        if attachment_id is None:
            raise PurchaseInvoiceEvidenceInputError(translated_message="errors.refused.refused_ledger_evidence_input")
        return resolve_attachment_evidence_input(attachment_id, store=store)

    def parse_structured_invoice(data: bytes) -> object:
        try:
            return parse_einvoice_document(data)
        except EInvoiceXmlParseError as exc:
            raise StructuredInvoiceReadError() from exc

    def read_text(
        transcription: DocumentTranscription,
        settings: Settings,
        provider: LLMProvider | None,
        consent_token: EvidenceConsentProof | None,
        authority_values: InvoiceExtractionAuthorityValues,
    ):
        try:
            if provider is None:
                return extract_invoice_fields_from_text(transcription, authority_values=authority_values)
            return TextInvoiceFieldExtractor(
                provider=provider,
                model=settings.cadrumo_llm_cloud_text_model,
                settings=settings,
                authority_values=authority_values,
                consent_token=consent_token,
            ).extract(transcription=transcription)
        except (MissingOptionalExtraError, LLMProviderError, httpx.HTTPError) as exc:
            raise InvoiceDraftReaderUnavailableError(exc) from exc

    def propose_supply_nature(transcription: DocumentTranscription, settings: Settings) -> SupplyNature | None:
        try:
            return SupplyNatureProposer(settings=settings).propose(transcription.text.splitlines()).nature
        except Exception:
            return None

    def rasterise_pdf(data: bytes) -> tuple[str, ...]:
        try:
            return tuple(rasterise_pdf_pages_to_base64_png(data))
        except LLMPdfRasterisationError as exc:
            raise InvoiceDraftReaderUnavailableError(exc) from exc

    def transcribe_vision(
        images: tuple[VisionImage, ...],
        source_content_sha256: str,
        settings: Settings,
        provider: LLMProvider | None,
        consent_token: EvidenceConsentProof | None,
    ) -> DocumentTranscription:
        try:
            inputs = tuple(MultimodalImageInput.from_base64(image.base64_data, image.media_type) for image in images)
            if provider is None:
                return transcribe_document_images(
                    inputs, source_content_sha256=source_content_sha256, settings=settings
                )
            return LocalVisionDocumentTranscriber(
                provider=provider,
                model=settings.cadrumo_llm_cloud_vision_model,
                settings=settings,
                consent_token=consent_token,
            ).transcribe(evidence_images=inputs, source_content_sha256=source_content_sha256)
        except (MissingOptionalExtraError, LLMProviderError, httpx.HTTPError) as exc:
            raise InvoiceDraftReaderUnavailableError(exc) from exc

    def consent_binding_error(facts: dict[str, object]) -> Exception:
        return LLMConsentError(
            translated_message="llm.evidence.consent.binding_mismatch",
            context=facts,
            precondition_verdict=llm_no_recovery_verdict(
                LLMPreconditionCondition.EVIDENCE_TOKEN_BOUND,
                facts=facts,
                provenance=ActionEvidenceProvenance.APPLICATION_STATE,
            ),
        )

    return InvoiceDraftExtractionPorts(
        resolve_evidence_input=resolve_evidence_input,
        parse_structured_invoice=parse_structured_invoice,
        read_text=read_text,
        propose_supply_nature=propose_supply_nature,
        rasterise_pdf=rasterise_pdf,
        transcribe_vision=transcribe_vision,
        consent_binding_error=consent_binding_error,
    )


__all__ = ["invoice_draft_extraction_ports"]
