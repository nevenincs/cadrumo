"""The typed Facturae invoice-class axis is gated by the bundled schema extract."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from .. import FacturaeInvoiceClass

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]

_EXTRACT = Path(__file__).parents[4] / "_data" / "corpus" / "facturae" / "facturae-3-2-2-invoice-class.json"


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
