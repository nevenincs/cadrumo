"""Application evidence routing contracts for structured and unrecognised XML.

The structured document reader itself is an inbound adapter concern, and the
exact structured draft projection is asserted through the real reader in the
inbound e-invoice tests. These tests retain the application decision made
before any reader runs: unsupported XML is refused and recognized invoice XML
is admitted.
"""

from __future__ import annotations

import re
from hashlib import sha256
from pathlib import Path

import pytest

from ....core.document_shape import STRUCTURED_DOCUMENT_SHAPES, DocumentShape
from ..evidence_errors import PurchaseInvoiceEvidenceInputError
from ..evidence_input import EvidenceInput
from ..invoice_draft_extraction import _refuse_an_unrecognised_xml_document

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_CORPUS = Path(__file__).parent / "_evidence_corpus"


def _read(name: str) -> bytes:
    return (_CORPUS / name).read_bytes()


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
