"""The Facturae code naming IRPF is a registry fact the bundled official schema itself decides."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation
from cadrumo.domain.calculations.registry.facturae_tax_type_codes import facturae_irpf_tax_type_code
from cadrumo.domain.calculations.registry.tests.authored_editions import filing_year_envelope

from ..xml import local_tag_name, parse_hardened_xml

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]

_SCHEMA = Path(__file__).parents[4] / "_data" / "corpus" / "facturae" / "Facturaev3_2_2.xml"
_XML_LANG = "{http://www.w3.org/XML/1998/namespace}lang"


def _schema_codes_naming(tax: str) -> list[str]:
    """Read ``TaxTypeCodeType`` from the schema, returning the members whose Spanish name starts with ``tax``."""
    root = parse_hardened_xml(_SCHEMA.read_bytes())
    simple_types = [
        node
        for node in root.iter()
        if local_tag_name(node.tag) == "simpleType" and node.get("name") == "TaxTypeCodeType"
    ]
    assert len(simple_types) == 1
    return [
        str(member.get("value"))
        for member in simple_types[0].iter()
        if local_tag_name(member.tag) == "enumeration"
        for doc in member.iter()
        if local_tag_name(doc.tag) == "documentation"
        and doc.get(_XML_LANG) == "es"
        and (doc.text or "").startswith(f"{tax}:")
    ]


def test_the_fact_names_the_member_the_schema_gives_irpf(operation: PinnedAuthorityOperation) -> None:
    assert [
        facturae_irpf_tax_type_code(issued_on=date(filing_year_envelope().horizon, 6, 30), authority=operation),
    ] == _schema_codes_naming("IRPF")


def test_an_invoice_stating_no_date_reads_the_code_in_force_today(operation: PinnedAuthorityOperation) -> None:
    assert [facturae_irpf_tax_type_code(issued_on=None, authority=operation)] == _schema_codes_naming("IRPF")
