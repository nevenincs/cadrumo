"""Application evidence routing and structured-draft projection contracts.

The structured document reader itself is an inbound adapter concern and is
covered in the neighbouring inbound-einvoice test seam. These tests retain the
application decisions made after a structured document has been identified:
unsupported XML is refused, recognized shapes are admitted, and the draft
projection keeps every party fact the application needs.
"""

from __future__ import annotations

import re
from decimal import Decimal
from hashlib import sha256
from pathlib import Path

import pytest

from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority as _indexed_authority_for_test

from ....core.document_shape import STRUCTURED_DOCUMENT_SHAPES, DocumentShape
from ..evidence_errors import PurchaseInvoiceEvidenceInputError
from ..evidence_input import EvidenceInput
from ..invoice_draft_extraction import (
    _extract_invoice_fields_from_structured_record,
    _refuse_an_unrecognised_xml_document,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_CORPUS = Path(__file__).parent / "_evidence_corpus"


def _read(name: str) -> bytes:
    return (_CORPUS / name).read_bytes()


def test_the_core_draft_path_routes_a_structured_document_to_the_exact_reader() -> None:
    """The application evidence path reaches the exact structured projection."""
    with _indexed_authority_for_test().operation() as _authority_operation_for_test:
        data = _read("zugferd_en16931_invoice.pdf")
        evidence = EvidenceInput(
            mime_type="application/pdf",
            document_shape=DocumentShape.PDF_EMBEDDED_XML,
            data=data,
            content_sha256=sha256(data).hexdigest(),
            evidence_id="ev-structured",
            attachment_id=None,
        )

        assert evidence.document_shape in STRUCTURED_DOCUMENT_SHAPES
        draft = _extract_invoice_fields_from_structured_record(evidence, operation=_authority_operation_for_test)

        assert len(draft.iva_breakdown) == 2
        assert len(draft.lines) == 2
        assert draft.supplier_tax_id == "DE123456789"
        assert draft.taxable_base == Decimal("473.00")
        assert draft.grand_total == Decimal("529.87")


def test_an_unrecognised_xml_refuses_rather_than_reaching_the_vision_model() -> None:
    """Unsupported XML is refused before any fallback reader is considered."""
    sii_record = (
        b'<?xml version="1.0" encoding="UTF-8"?>'
        b'<sii:SuministroLRFacturasEmitidas xmlns:sii="https://www2.agenciatributaria.gob.es/'
        b'static_files/common/internet/dep/aplicaciones/es/aeat/ssii/fact/ws/SuministroLR.xsd">'
        b"<sii:Cabecera/></sii:SuministroLRFacturasEmitidas>"
    )
    evidence = EvidenceInput(
        mime_type="application/xml",
        document_shape=DocumentShape.XML_AEAT_SII,
        data=sii_record,
        content_sha256=sha256(sii_record).hexdigest(),
        evidence_id="ev-sii-record",
        attachment_id=None,
    )

    assert evidence.document_shape not in STRUCTURED_DOCUMENT_SHAPES
    with pytest.raises(
        PurchaseInvoiceEvidenceInputError, match=re.escape("errors.refused.refused_ledger_evidence_input")
    ):
        _refuse_an_unrecognised_xml_document(evidence)


def test_a_recognised_structured_xml_is_not_caught_by_the_unrecognised_xml_refusal() -> None:
    """Recognized invoice XML remains admitted by the application guard."""
    data = _read("facturae_32_series_and_parties_invoice.xml")
    evidence = EvidenceInput(
        mime_type="application/xml",
        document_shape=DocumentShape.XML_FACTURAE,
        data=data,
        content_sha256=sha256(data).hexdigest(),
        evidence_id="ev-facturae",
        attachment_id=None,
    )

    assert evidence.document_shape in STRUCTURED_DOCUMENT_SHAPES
    _refuse_an_unrecognised_xml_document(evidence)


def test_the_structured_draft_carries_both_parties_rather_than_discarding_the_customer() -> None:
    """Application projection preserves both party identities from the input."""
    with _indexed_authority_for_test().operation() as _authority_operation_for_test:
        data = _read("facturae_32_series_and_parties_invoice.xml")
        evidence = EvidenceInput(
            mime_type="application/xml",
            document_shape=DocumentShape.XML_FACTURAE,
            data=data,
            content_sha256=sha256(data).hexdigest(),
            evidence_id="ev-facturae-parties",
            attachment_id=None,
        )

        draft = _extract_invoice_fields_from_structured_record(evidence, operation=_authority_operation_for_test)

        assert draft.supplier_tax_id == "45821337R"
        assert draft.customer_tax_id == "A82645177"
        assert draft.supplier_name == "Marta Iglesias Ferrer"
        assert draft.customer_name == "Talleres Berrocal, S.A."
        assert draft.invoice_series == "R-2026"
