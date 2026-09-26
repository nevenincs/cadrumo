"""Auxiliary XML declaration identity is complete and product-derived."""

from __future__ import annotations

from xml.etree import ElementTree

import pytest

from ....core.export_layout_format import ExportLayoutFormat
from ....domain.calculations.registry.schema_exports import ExportLayoutDefinition
from ....domain.filing.errors import FilingExportError, FilingExportValidationError
from .._export_xml_dictionary import (
    _append_declaration_aux,
    _prune_zero_only_xml_subtrees,
    format_xml_dictionary_value,
)
from ..export_parity import assert_xml_declaration_aux_declared

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _xml_layout() -> ExportLayoutDefinition:
    return ExportLayoutDefinition(
        id="modelo-100-xml",
        format=ExportLayoutFormat.XML_DICTIONARY,
        dictionary_source_ref="aeat-dict-100",
        source_refs=("aeat-dict-100",),
        legal_refs=("ley-35-2006:art-1",),
        aux_idioma="E",
    )


def test_xml_aux_writes_the_product_token_after_layout_language() -> None:
    root = ElementTree.Element("Declaracion")

    _append_declaration_aux(root, _xml_layout(), aux_version="051")

    aux = root.find("Aux")
    assert aux is not None
    assert [(child.tag, child.text) for child in aux] == [("Idioma", "E"), ("VERSION", "051")]


def test_xml_aux_parity_refuses_an_empty_product_token() -> None:
    with pytest.raises(FilingExportError) as refusal:
        assert_xml_declaration_aux_declared(_xml_layout(), aux_version="")

    assert refusal.value.context == {
        "layout_id": "modelo-100-xml",
        "layout_format": "xml_dictionary",
        "undeclared_count": 1,
        "undeclared_fields": ("aux_version",),
    }


def test_optional_zero_only_branches_are_omitted_but_required_zero_siblings_remain() -> None:
    root = ElementTree.Element("Declaracion")
    optional = ElementTree.SubElement(root, "Optional")
    ElementTree.SubElement(optional, "RequiredZero").text = "0.00"
    populated = ElementTree.SubElement(root, "Populated")
    ElementTree.SubElement(populated, "RequiredZero").text = "0.00"
    ElementTree.SubElement(populated, "Amount").text = "12.00"

    _prune_zero_only_xml_subtrees(root, optional_element_paths=frozenset({"/Optional", "/Populated"}))

    assert root.find("Optional") is None
    retained = root.find("Populated")
    assert retained is not None
    assert retained.findtext("RequiredZero") == "0.00"
    assert retained.findtext("Amount") == "12.00"


def test_holder_role_is_encoded_to_the_official_tipo_titular_value() -> None:
    assert format_xml_dictionary_value("TIT", "declarante") == "2"
    with pytest.raises(FilingExportValidationError, match="holder"):
        format_xml_dictionary_value("TIT", "unknown-member")
