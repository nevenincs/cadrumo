"""Structured evidence reaches the exact draft projection through the real e-invoice reader.

The application routes a structured document to the exact reader and projects
the parsed record into a draft. These cases bind the real inbound parser to the
application-owned structured-record port and drive the public extraction entry
point, so the projection is asserted on real corpus documents.
"""

from __future__ import annotations

from decimal import Decimal
from hashlib import sha256
from pathlib import Path

import pytest

from .....application.ledger.document_transcription import DocumentTranscription
from .....application.ledger.evidence_input import EvidenceInput
from .....application.ledger.evidence_input_ports import EvidenceInputPorts
from .....application.ledger.evidence_textlayer_ports import EvidenceTextLayerPorts
from .....application.ledger.invoice_draft_extraction import extract_invoice_draft_from_evidence
from .....application.ledger.invoice_draft_extraction_ports import (
    EvidenceConsentProof,
    InvoiceDraftExtractionPorts,
    StructuredInvoiceReadError,
    VisionImage,
)
from .....application.ledger.invoice_draft_records import InvoiceDraft
from .....application.ledger.invoice_extraction_authority import default_invoice_extraction_period
from .....application.ledger.structured_invoice_ports import StructuredInvoiceRecord
from .....core.config import Settings
from .....core.config_support import LLMProvider
from .....core.document_shape import STRUCTURED_DOCUMENT_SHAPES, DocumentShape
from .....domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from .....domain.iva.regime_legend import RegimeLegend, resolve_regime_legends
from .....domain.iva.supply_nature import SupplyNature
from ..application_translation import translate_parsed_einvoice
from ..parsers import parse_einvoice_document
from ..xml import EInvoiceXmlParseError

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]

_CORPUS = Path(__file__).resolve().parents[4] / "application" / "ledger" / "tests" / "_evidence_corpus"


def _evidence(name: str, *, mime_type: str, document_shape: DocumentShape, evidence_id: str) -> EvidenceInput:
    data = (_CORPUS / name).read_bytes()
    return EvidenceInput(
        mime_type=mime_type,
        document_shape=document_shape,
        data=data,
        content_sha256=sha256(data).hexdigest(),
        evidence_id=evidence_id,
        attachment_id=None,
    )


def _parse_structured_invoice(data: bytes) -> StructuredInvoiceRecord:
    """Bind the inbound parser to the application-owned structured record."""
    try:
        return translate_parsed_einvoice(parse_einvoice_document(data))
    except EInvoiceXmlParseError as exc:
        raise StructuredInvoiceReadError() from exc


def _unused_document_shape_probe(data: bytes) -> DocumentShape:
    del data
    raise AssertionError("document-shape probing is not part of this structured-record test")


def _unused_text_layer(data: bytes) -> tuple[str, ...]:
    del data
    raise AssertionError("text-layer reading is not part of this structured-record test")


def _unused_text_reader(
    _transcription: DocumentTranscription,
    _settings: Settings,
    _provider: LLMProvider | None,
    _consent_token: EvidenceConsentProof | None,
    _authority_values: object,
) -> InvoiceDraft:
    raise AssertionError("text reading is not part of this structured-record test")


def _unused_supply_nature(
    _transcription: DocumentTranscription,
    _settings: Settings,
) -> SupplyNature | None:
    raise AssertionError("supply-nature proposal is not part of this structured-record test")


def _unused_vision_reader(
    _images: tuple[VisionImage, ...],
    _prompt: str,
    _settings: Settings,
    _provider: LLMProvider | None,
    _consent_token: EvidenceConsentProof | None,
) -> DocumentTranscription:
    raise AssertionError("vision reading is not part of this structured-record test")


def _unused_consent_binding_error(_facts: dict[str, object]) -> Exception:
    raise AssertionError("consent binding is not part of this structured-record test")


def _structured_ports(evidence: EvidenceInput) -> InvoiceDraftExtractionPorts:
    def resolve_evidence_input(
        _bucket_id: str,
        _evidence_id: str | None,
        _attachment_id: str | None,
        _settings: Settings,
    ) -> EvidenceInput:
        return evidence

    return InvoiceDraftExtractionPorts(
        resolve_evidence_input=resolve_evidence_input,
        evidence_input_ports=EvidenceInputPorts(document_shape_probe=_unused_document_shape_probe),
        text_layer_ports=EvidenceTextLayerPorts(extract_pages_text=_unused_text_layer),
        parse_structured_invoice=_parse_structured_invoice,
        read_text=_unused_text_reader,
        propose_supply_nature=_unused_supply_nature,
        rasterise_pdf=lambda _data: (),
        transcribe_vision=_unused_vision_reader,
        consent_binding_error=_unused_consent_binding_error,
    )


def _registry_legends(operation: PinnedAuthorityOperation) -> tuple[RegimeLegend, ...]:
    period = default_invoice_extraction_period()
    return resolve_regime_legends(operation=operation, effective_date=period.end_date)


def _extract(evidence: EvidenceInput) -> InvoiceDraft:
    with bundled_indexed_authority().operation() as operation:
        return extract_invoice_draft_from_evidence(
            bucket_id="structured-evidence-bucket",
            evidence_id=evidence.evidence_id,
            ports=_structured_ports(evidence),
            operation=operation,
            legends=_registry_legends(operation),
        )


def test_the_core_draft_path_routes_a_structured_document_to_the_exact_reader() -> None:
    """The application evidence path reaches the exact structured projection."""
    evidence = _evidence(
        "zugferd_en16931_invoice.pdf",
        mime_type="application/pdf",
        document_shape=DocumentShape.PDF_EMBEDDED_XML,
        evidence_id="ev-structured",
    )

    assert evidence.document_shape in STRUCTURED_DOCUMENT_SHAPES
    draft = _extract(evidence)

    assert len(draft.iva_breakdown) == 2
    assert len(draft.lines) == 2
    assert draft.supplier_tax_id == "DE123456789"
    assert draft.taxable_base == Decimal("473.00")
    assert draft.grand_total == Decimal("529.87")


def test_the_structured_draft_carries_both_parties_rather_than_discarding_the_customer() -> None:
    """Application projection preserves both party identities from the input."""
    evidence = _evidence(
        "facturae_32_series_and_parties_invoice.xml",
        mime_type="application/xml",
        document_shape=DocumentShape.XML_FACTURAE,
        evidence_id="ev-facturae-parties",
    )

    draft = _extract(evidence)

    assert draft.supplier_tax_id == "45821337R"
    assert draft.customer_tax_id == "A82645177"
    assert draft.supplier_name == "Marta Iglesias Ferrer"
    assert draft.customer_name == "Talleres Berrocal, S.A."
    assert draft.invoice_series == "R-2026"
