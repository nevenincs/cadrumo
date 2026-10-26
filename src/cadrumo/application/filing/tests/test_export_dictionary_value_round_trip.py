"""Populated values survive every enrolled XML dictionary's real writer and parser."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from xml.etree import ElementTree

import pytest

from ....core.export_layout_format import ExportLayoutFormat
from ....core.resources.bundled_data import resolve_corpus_binary
from ....domain.calculations.registry.export_parse import (
    XML_DICTIONARY_BOOLEAN_TYPES,
    parse_export_payload,
    xml_dictionary_entries,
)
from ....domain.calculations.registry.tests.published_authority import (
    published_revision,
    published_revision_definitions,
    published_source_reference,
)
from .._export_xml_dictionary import _set_xml_dictionary_path, format_xml_dictionary_value

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


@pytest.mark.parametrize("boolean_value", (True, False))
def test_every_xml_dictionary_can_export_populated_values(boolean_value: bool) -> None:
    modelos = published_revision_definitions()
    checked: set[tuple[str, str, str]] = set()
    for modelo in modelos:
        for revision in modelo.revisions.values():
            for layout in revision.export_layouts:
                if layout.format is not ExportLayoutFormat.XML_DICTIONARY:
                    continue
                assert layout.dictionary_source_ref is not None
                source = published_source_reference(str(layout.dictionary_source_ref))
                sources = {str(source.id): source}
                source_path = resolve_corpus_binary(*source.corpus_path.split("/"))
                assert source_path is not None
                payloads = {str(source.id): source_path.read_bytes()}
                entries = xml_dictionary_entries(layout, sources=sources, source_payloads=payloads)
                root = ElementTree.Element("Declaracion")
                expected: dict[str, str] = {}
                for entry in entries:
                    data_type = entry.data_type.upper()
                    value: object
                    if data_type in XML_DICTIONARY_BOOLEAN_TYPES:
                        value = boolean_value
                    elif data_type.startswith(("N", "P")):
                        value = Decimal(1).scaleb(-int(data_type[-1]))
                    elif data_type == "FEC":
                        value = date(2025, 3, 14)
                    elif data_type == "TIT":
                        value = "declarante"
                    else:
                        value = "A"
                    raw = format_xml_dictionary_value(entry.data_type, value)
                    _set_xml_dictionary_path(root, entry.path, raw, element_order={})
                    expected[entry.field_id] = raw
                    checked.add((str(modelo.id), str(revision.id), entry.field_id))
                parsed = parse_export_payload(
                    layout,
                    ElementTree.tostring(root),
                    sources=sources,
                    source_payloads=payloads,
                )
                assert {field.field_id: field.raw for field in parsed.fields} == expected
                types = {entry.field_id: entry.data_type for entry in entries}
                for field in parsed.fields:
                    assert format_xml_dictionary_value(types[field.field_id], field.value) == field.raw
    assert checked, "no XML dictionary field was exercised"


def test_xml_attribute_values_retain_repeated_occurrences_and_ignore_element_text() -> None:
    layout = published_revision("100", "2024").export_layouts[0]
    assert layout.dictionary_source_ref is not None
    source = published_source_reference(str(layout.dictionary_source_ref))
    sources = {str(source.id): source}
    source_path = resolve_corpus_binary(*source.corpus_path.split("/"))
    assert source_path is not None
    payloads = {str(source.id): source_path.read_bytes()}
    entries = xml_dictionary_entries(layout, sources=sources, source_payloads=payloads)
    entry = next(entry for entry in entries if entry.field_id == "B11")
    assert entry.path.endswith("/B11/@valor")
    assert entry.data_type == "N102"
    payload = (
        b"<Declaracion><DatosEconomicos><TomaDatosAmpliada><RdtoCapitalMobiliario>"
        b'<RdtoCapitalMobiliarioAhorro><B11 valor="0.12">99.99</B11>'
        b'<B11 valor="34.56"/><B11>88.88</B11><B11 valor=" "/>'
        b"</RdtoCapitalMobiliarioAhorro></RdtoCapitalMobiliario>"
        b"</TomaDatosAmpliada></DatosEconomicos></Declaracion>"
    )
    parsed = parse_export_payload(layout, payload, sources=sources, source_payloads=payloads)
    values = [field for field in parsed.fields if field.field_id == entry.field_id]
    assert [field.value for field in values] == [Decimal("0.12"), Decimal("34.56")]
    assert [field.casilla_id for field in values] == ["0027", "0027"]
