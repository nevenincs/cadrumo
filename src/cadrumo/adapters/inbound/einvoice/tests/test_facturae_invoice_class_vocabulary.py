"""The typed Facturae invoice-class axis is gated by the bundled schema extract."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ..parsers import FacturaeInvoiceClass, parse_einvoice_document

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]

_EXTRACT = Path(__file__).parents[4] / "_data" / "corpus" / "facturae" / "facturae-3-2-2-invoice-class.json"
_CORPUS = Path(__file__).parents[4] / "application" / "ledger" / "tests" / "_evidence_corpus"
_ORDINARY = _CORPUS / "facturae_32_series_and_parties_invoice.xml"


def test_the_closed_enum_matches_the_bundled_facturae_vocabulary() -> None:
    """Adding, dropping, or mistyping a member must disagree with the corpus authority."""
    extract = json.loads(_EXTRACT.read_text(encoding="utf-8"))
    schema_codes = {entry["code"] for entry in extract["codes"]}

    assert {member.value for member in FacturaeInvoiceClass} == schema_codes


def test_the_vocabulary_extract_identifies_its_official_source() -> None:
    """The enum gate is meaningful only while its committed authority stays attributable."""
    provenance = json.loads(_EXTRACT.read_text(encoding="utf-8"))["provenance"]

    assert provenance["source_url"].startswith("https://www.facturae.gob.es/")
    assert provenance["simple_type"] == "InvoiceClassType"
    assert provenance["extracted_code_count"] == len(FacturaeInvoiceClass)
    assert len(provenance["source_sha256"]) == 64


def test_the_facturae_header_class_is_read_as_the_typed_member() -> None:
    parsed = parse_einvoice_document(_ORDINARY.read_bytes())

    assert parsed.facturae_invoice_class is FacturaeInvoiceClass.ORIGINAL_CORRECTIVE


@pytest.mark.parametrize("replacement", ["", "<InvoiceClass>ZZ</InvoiceClass>"])
def test_an_absent_or_unrecognised_class_does_not_refuse_the_document(replacement: str) -> None:
    xml = _ORDINARY.read_text(encoding="utf-8")
    assert xml.count("<InvoiceClass>OR</InvoiceClass>") == 1

    parsed = parse_einvoice_document(xml.replace("<InvoiceClass>OR</InvoiceClass>", replacement).encode())

    assert parsed.invoice_number == "0031"
    assert parsed.facturae_invoice_class is None


def test_a_nested_invoice_class_is_not_mistaken_for_the_headers_own_class() -> None:
    xml = _ORDINARY.read_text(encoding="utf-8")
    assert xml.count("<InvoiceClass>OR</InvoiceClass>") == 1
    replacement = "<Corrective><InvoiceClass>OR</InvoiceClass></Corrective>"

    parsed = parse_einvoice_document(xml.replace("<InvoiceClass>OR</InvoiceClass>", replacement).encode())

    assert parsed.facturae_invoice_class is None
