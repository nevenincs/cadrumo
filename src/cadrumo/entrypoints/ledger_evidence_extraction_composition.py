"""Entrypoint-neutral composition for the invoice-draft extraction use case."""

from __future__ import annotations

import httpx

from ..adapters.inbound.einvoice.application_translation import translate_parsed_einvoice
from ..adapters.inbound.einvoice.parsers import parse_einvoice_document
from ..adapters.inbound.einvoice.shape import probe_document_shape
from ..adapters.inbound.einvoice.xml import EInvoiceXmlParseError
from ..adapters.inbound.pdf.page_text_extraction import extract_pages_text_from_bytes
from ..adapters.outbound.llm.consent import EvidenceConsentToken
from ..adapters.outbound.llm.errors import LLMConsentError, LLMPdfRasterisationError, LLMProviderError
from ..adapters.outbound.llm.evidence_draft_text import TextInvoiceFieldExtractor, extract_invoice_fields_from_text
from ..adapters.outbound.llm.evidence_draft_vision import LocalVisionDocumentTranscriber, transcribe_document_images
from ..adapters.outbound.llm.models import MultimodalImageInput
from ..adapters.outbound.llm.preconditions import LLMPreconditionCondition, llm_no_recovery_verdict
from ..adapters.outbound.llm.providers.local import rasterise_pdf_pages_to_base64_png
from ..adapters.outbound.llm.supply_nature_proposal import SupplyNatureProposer
from ..adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from ..adapters.persistence.storage.attachment import AttachmentStore
from ..adapters.persistence.storage.runtime_repository import secure_object_repository_for_bucket
from ..application.ledger.document_transcription import DocumentTranscription
from ..application.ledger.evidence import PurchaseInvoiceEvidenceService
from ..application.ledger.evidence_errors import PurchaseInvoiceEvidenceInputError
from ..application.ledger.evidence_input import (
    EvidenceInput,
    resolve_attachment_evidence_input,
    resolve_purchase_invoice_evidence_input,
)
from ..application.ledger.evidence_input_ports import EvidenceInputPorts
from ..application.ledger.evidence_ports import LedgerEvidencePorts
from ..application.ledger.evidence_reference import (
    EvidenceReferenceOutcome,
    classify_evidence_reference,
    refuse_reference_without_document_bytes,
    refuse_unresolved_evidence_reference,
)
from ..application.ledger.evidence_textlayer_ports import EvidenceTextLayerPorts
from ..application.ledger.invoice_draft_extraction_ports import (
    EvidenceConsentProof,
    InvoiceDraftExtractionPorts,
    InvoiceDraftReaderUnavailableError,
    StructuredInvoiceReadError,
    VisionImage,
)
from ..application.ledger.invoice_draft_records import InvoiceDraft
from ..application.ledger.invoice_extraction_authority import InvoiceExtractionAuthorityValues
from ..application.ledger.preconditions import LedgerPreconditionCondition, ledger_no_recovery_verdict
from ..application.ledger.structured_invoice_ports import StructuredInvoiceRecord
from ..core.config import Settings
from ..core.config_support import LLMProvider
from ..core.operator_action_enums import ActionEvidenceProvenance
from ..core.optional_extras import MissingOptionalExtraError
from ..domain.iva.supply_nature import SupplyNature


def evidence_text_layer_ports() -> EvidenceTextLayerPorts:
    """Bind the application text-layer capability to the PDF adapter."""

    def extract_pages_text(data: bytes) -> tuple[str, ...]:
        try:
            return extract_pages_text_from_bytes(
                data,
                error_class=ValueError,
                pdf_label="the invoice PDF",
            )
        except ValueError as exc:
            raise PurchaseInvoiceEvidenceInputError(
                "evidence text-layer extraction failed",
                precondition_verdict=ledger_no_recovery_verdict(
                    LedgerPreconditionCondition.EVIDENCE_TEXT_LAYER_AVAILABLE,
                    facts={
                        "pdf_layer_present": False,
                        "pdf_layer_extraction_succeeded": False,
                    },
                ),
            ) from exc

    return EvidenceTextLayerPorts(extract_pages_text=extract_pages_text)


def invoice_draft_extraction_ports(*, evidence_ports: LedgerEvidencePorts) -> InvoiceDraftExtractionPorts:
    """Bind the CLI evidence commands to their concrete adapters."""
    evidence_input_ports = EvidenceInputPorts(document_shape_probe=probe_document_shape)

    def resolve_evidence_input(
        bucket_id: str, evidence_id: str | None, attachment_id: str | None, settings: Settings
    ) -> EvidenceInput:
        store = AttachmentStore(objects=secure_object_repository_for_bucket(bucket_id, settings))
        if evidence_id is not None:
            reference = classify_evidence_reference(
                evidence_id,
                bucket_id=bucket_id,
                evidence_records=PurchaseInvoiceEvidenceService(ports=evidence_ports).list_all(bucket_id=bucket_id),
                invoices=InvoiceCatalogueRepository(bucket_id=bucket_id).load(),
            )
            if reference.outcome is EvidenceReferenceOutcome.UNRESOLVED:
                raise refuse_unresolved_evidence_reference(evidence_id)
            if reference.record is None:
                raise refuse_reference_without_document_bytes(evidence_id)
            return resolve_purchase_invoice_evidence_input(reference.record, store=store, ports=evidence_input_ports)
        if attachment_id is None:
            raise PurchaseInvoiceEvidenceInputError(translated_message="errors.refused.refused_ledger_evidence_input")
        return resolve_attachment_evidence_input(attachment_id, store=store, ports=evidence_input_ports)

    def parse_structured_invoice(data: bytes) -> StructuredInvoiceRecord:
        try:
            return translate_parsed_einvoice(parse_einvoice_document(data))
        except EInvoiceXmlParseError as exc:
            raise StructuredInvoiceReadError() from exc

    def require_llm_consent_token(consent_token: EvidenceConsentProof | None) -> EvidenceConsentToken | None:
        if consent_token is None:
            return None
        if not isinstance(consent_token, EvidenceConsentToken):
            raise TypeError("LLM readers require the canonical EvidenceConsentToken")
        return consent_token

    def read_text(
        transcription: DocumentTranscription,
        settings: Settings,
        provider: LLMProvider | None,
        consent_token: EvidenceConsentProof | None,
        authority_values: object,
    ) -> InvoiceDraft:
        try:
            if not isinstance(authority_values, InvoiceExtractionAuthorityValues):
                raise TypeError("text reader requires resolved invoice extraction authority values")
            from ..domain.calculations.registry.authority import bundled_indexed_authority

            with bundled_indexed_authority().operation() as operation:
                if provider is None:
                    return extract_invoice_fields_from_text(
                        transcription,
                        operation=operation,
                        authority_values=authority_values,
                    )
                return TextInvoiceFieldExtractor(
                    provider=provider,
                    model=settings.cadrumo_llm_cloud_text_model,
                    operation=operation,
                    settings=settings,
                    authority_values=authority_values,
                    consent_token=require_llm_consent_token(consent_token),
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
                consent_token=require_llm_consent_token(consent_token),
            ).transcribe(evidence_images=inputs, source_content_sha256=source_content_sha256)
        except (MissingOptionalExtraError, LLMProviderError, httpx.HTTPError) as exc:
            raise InvoiceDraftReaderUnavailableError(exc) from exc

    def consent_binding_error(facts: dict[str, object]) -> Exception:
        typed_facts: dict[str, str | int | bool] = {
            key: value if isinstance(value, (str, int, bool)) else str(value) for key, value in facts.items()
        }
        return LLMConsentError(
            translated_message="llm.evidence.consent.binding_mismatch",
            context=facts,
            precondition_verdict=llm_no_recovery_verdict(
                LLMPreconditionCondition.EVIDENCE_TOKEN_BOUND,
                facts=typed_facts,
                provenance=ActionEvidenceProvenance.APPLICATION_STATE,
            ),
        )

    return InvoiceDraftExtractionPorts(
        resolve_evidence_input=resolve_evidence_input,
        evidence_input_ports=evidence_input_ports,
        text_layer_ports=evidence_text_layer_ports(),
        parse_structured_invoice=parse_structured_invoice,
        read_text=read_text,
        propose_supply_nature=propose_supply_nature,
        rasterise_pdf=rasterise_pdf,
        transcribe_vision=transcribe_vision,
        consent_binding_error=consent_binding_error,
    )


__all__ = ["evidence_text_layer_ports", "invoice_draft_extraction_ports"]
