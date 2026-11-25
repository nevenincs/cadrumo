"""Application reader ports that bind the real outbound text adapter over a fixed text layer."""

from __future__ import annotations

from cadrumo.adapters.outbound.llm.evidence_draft_text import TextInvoiceFieldExtractor
from cadrumo.application.ledger.document_transcription import DocumentTranscription
from cadrumo.application.ledger.evidence_input import EvidenceInput
from cadrumo.application.ledger.evidence_input_ports import EvidenceInputPorts
from cadrumo.application.ledger.evidence_textlayer_ports import EvidenceTextLayerPorts
from cadrumo.application.ledger.invoice_draft_extraction_ports import (
    EvidenceConsentProof,
    InvoiceDraftExtractionPorts,
    StructuredInvoiceReadError,
)
from cadrumo.application.ledger.invoice_draft_records import InvoiceDraft
from cadrumo.application.ledger.invoice_extraction_authority import InvoiceExtractionAuthorityValues
from cadrumo.application.ledger.structured_invoice_ports import StructuredInvoiceRecord
from cadrumo.core.config import Settings
from cadrumo.core.document_shape import DocumentShape
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation


def text_layer_reader_ports(
    evidence: EvidenceInput,
    *,
    text_layer_ports: EvidenceTextLayerPorts,
    operation: PinnedAuthorityOperation,
) -> InvoiceDraftExtractionPorts:
    """Bind the application reader contract to the real outbound text adapter."""

    def parse_structured_invoice(data: bytes) -> StructuredInvoiceRecord:
        del data
        raise StructuredInvoiceReadError()

    def read_text(
        transcription: DocumentTranscription,
        settings: Settings,
        _consent_token: EvidenceConsentProof | None,
        authority_values: object,
        /,
    ) -> InvoiceDraft:
        if not isinstance(authority_values, InvoiceExtractionAuthorityValues):
            raise TypeError("text reader requires resolved invoice extraction authority values")
        return TextInvoiceFieldExtractor(
            settings=settings, authority_values=authority_values, operation=operation
        ).extract(transcription=transcription)

    def vision_not_expected(*_args: object, **_kwargs: object) -> DocumentTranscription:
        raise AssertionError("the text-layer reader must not invoke the vision path")

    def document_shape_probe(data: bytes) -> DocumentShape:
        del data
        return DocumentShape.PDF_TEXT_LAYER

    return InvoiceDraftExtractionPorts(
        resolve_evidence_input=lambda *_args: evidence,
        evidence_input_ports=EvidenceInputPorts(document_shape_probe=document_shape_probe),
        text_layer_ports=text_layer_ports,
        parse_structured_invoice=parse_structured_invoice,
        read_text=read_text,
        propose_supply_nature=lambda *_args: None,
        rasterise_pdf=lambda _data: (),
        transcribe_vision=vision_not_expected,
        consent_binding_error=lambda _facts: RuntimeError("consent binding was not expected"),
    )
