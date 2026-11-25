"""A dictionary row resolves its casilla by printed number and declares it where the design repeats a number.

Isolated fixtures for a synthetic modelo: the mechanism belongs to every
``xml_dictionary`` layout, so none of these names Modelo 100 or a year.
"""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal
from typing import Final

import pytest
from pydantic import ValidationError

from .....core.export_layout_format import ExportLayoutFormat
from ...export_field_kind import CasillaFieldKind
from ..errors import RegistryValidationError
from ..export_parse import parse_export_payload
from ..export_xml_dictionary import XmlDictionaryEntry, xml_dictionary_entries
from ..fixed_width_codec import ExportEncoding
from ..schema import ModeloRevision
from ..schema_base import CasillaDataType
from ..schema_exports import (
    ExportFieldDefinition,
    ExportLayoutDefinition,
    ExportRecordDefinition,
    XmlDictionaryRowTarget,
)
from ..schema_references import SourceReference
from ..schema_surfaces import CasillaDefinition
from ..validate_revision_identity import declared_repeated_casilla_numbers, revision_casilla_identity_failures
from .referential_integrity_support import REFERENCE_LEGAL_ID, minimal_revision, minimal_source_ref

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_DICTIONARY_ID: Final = "test-dictionary"
_XSD_ID: Final = "test-xsd"
_OTHER_DICTIONARY_ID: Final = "test-other-dictionary"
_LAYOUT_ID: Final = "test-xml-dictionary"
_DICTIONARY: Final = "\n".join(
    (
        "# synthetic dictionary",
        "RESULT=[/Doc/Resultado/RESULT][N102][20][Resultado (casilla [10] o casilla [20])]",
        "ALPHA=[/Doc/Alfa/ALPHA][N102][10][Importe con casilla de otro nombre]",
        "PAYABLE=[/Doc/Resto/PAYABLE][P102][20][Resto a ingresar]",
        "REFUNDABLE=[/Doc/Resto/REFUNDABLE][N102][20][Resto a devolver]",
        "PLAIN=[/Doc/Otros/PLAIN][N102][30][Importe sin repeticion]",
        "UNKNOWN=[/Doc/Otros/UNKNOWN][N102][40][Casilla que el registro no declara]",
        "",
    ),
)
_XSD: Final = b'<xs:schema><xs:element name="ALPHA"/><xs:element name="RESULT"/><xs:element name="PAYABLE"/><xs:element name="REFUNDABLE"/></xs:schema>'


def _casilla(casilla_id: str, number: str) -> CasillaDefinition:
    return CasillaDefinition(
        id=casilla_id,
        number=number,
        localization_keys=("test.schema.casilla.label",),
        section=("test",),
        data_type="money",
        legal_refs=(REFERENCE_LEGAL_ID,),
        source_refs=(_DICTIONARY_ID,),
    )


def _target(field_id: str, casilla_id: str, *, line: int, element: str | None = None) -> XmlDictionaryRowTarget:
    return XmlDictionaryRowTarget(
        field_id=field_id,
        casilla_id=casilla_id,
        dictionary_source_ref=_DICTIONARY_ID,
        dictionary_line=line,
        xsd_source_ref=_XSD_ID,
        xsd_element=element or field_id,
    )


def _layout(*targets: XmlDictionaryRowTarget) -> ExportLayoutDefinition:
    return ExportLayoutDefinition(
        id=_LAYOUT_ID,
        format=ExportLayoutFormat.XML_DICTIONARY,
        dictionary_source_ref=_DICTIONARY_ID,
        source_refs=(_DICTIONARY_ID, _XSD_ID),
        legal_refs=(REFERENCE_LEGAL_ID,),
        aux_idioma="E",
        dictionary_row_targets=targets,
    )


def _sources() -> dict[str, SourceReference]:
    return {
        source_id: minimal_source_ref().model_copy(update={"id": source_id})
        for source_id in (_DICTIONARY_ID, _XSD_ID, _OTHER_DICTIONARY_ID)
    }


def _payloads() -> dict[str, bytes]:
    return {_DICTIONARY_ID: _DICTIONARY.encode(), _XSD_ID: _XSD}


def _entries(
    layout: ExportLayoutDefinition, casillas: Sequence[CasillaDefinition], *, with_xsd: bool = True
) -> dict[str, XmlDictionaryEntry]:
    payloads = _payloads() if with_xsd else {_DICTIONARY_ID: _DICTIONARY.encode()}
    rows = xml_dictionary_entries(layout, sources=_sources(), source_payloads=payloads, casillas=casillas)
    return {row.field_id: row for row in rows}


_ALPHA = _casilla("alfa", "10")
_RESULT = _casilla("resultado", "20")
_REMAINDER = _casilla("20", "20")
_TARGETS = (
    _target("RESULT", "resultado", line=2),
    _target("PAYABLE", "20", line=4),
    _target("REFUNDABLE", "20", line=5),
)


def test_a_row_resolves_to_the_casilla_holding_its_printed_number_not_the_one_named_like_it() -> None:
    rows = _entries(_layout(), (_ALPHA, _REMAINDER))

    assert rows["ALPHA"].casilla_id == "alfa"
    assert rows["ALPHA"].printed_number == "10"
    assert rows["RESULT"].casilla_id == "20"
    assert rows["PAYABLE"].casilla_id == "20"
    assert rows["PLAIN"].casilla_id == "30"
    assert rows["UNKNOWN"].casilla_id == "40"
    assert rows["UNKNOWN"].printed_number == "40"


def test_a_printed_number_held_by_two_casillas_is_refused_on_a_row_without_a_declared_target() -> None:
    with pytest.raises(RegistryValidationError, match=r"prints box '20'.*declare the casilla the row reads"):
        _entries(_layout(), (_RESULT, _REMAINDER))


def test_declared_targets_override_the_number_lookup_for_their_rows_only() -> None:
    rows = _entries(_layout(*_TARGETS), (_ALPHA, _RESULT, _REMAINDER))

    assert {field: row.casilla_id for field, row in rows.items()} == {
        "ALPHA": "alfa",
        "RESULT": "resultado",
        "PAYABLE": "20",
        "REFUNDABLE": "20",
        "PLAIN": "30",
        "UNKNOWN": "40",
    }
    assert rows["RESULT"].printed_number == "20"


def test_a_target_naming_a_field_the_dictionary_does_not_carry_is_refused() -> None:
    with pytest.raises(RegistryValidationError, match=r"'ABSENT'.*would apply to nothing"):
        _entries(_layout(_target("ABSENT", "resultado", line=2), *_TARGETS), (_RESULT, _REMAINDER))


def test_a_target_citing_a_line_that_does_not_hold_its_row_is_refused() -> None:
    with pytest.raises(RegistryValidationError, match=r"cites dictionary line 5, which does not hold that row"):
        _entries(_layout(_target("RESULT", "resultado", line=5), *_TARGETS[1:]), (_RESULT, _REMAINDER))


def test_a_target_naming_a_casilla_the_edition_does_not_declare_is_refused() -> None:
    with pytest.raises(RegistryValidationError, match=r"names casilla 'nowhere', which the edition does not declare"):
        _entries(_layout(_target("RESULT", "nowhere", line=2), *_TARGETS[1:]), (_RESULT, _REMAINDER))


def test_a_target_whose_row_does_not_print_the_number_of_its_casilla_is_refused() -> None:
    with pytest.raises(RegistryValidationError, match=r"prints box '20', which is not the number of casilla 'alfa'"):
        _entries(_layout(_target("RESULT", "alfa", line=2), *_TARGETS[1:]), (_ALPHA, _RESULT, _REMAINDER))


def test_a_target_citing_an_xsd_element_the_xsd_does_not_declare_is_refused() -> None:
    with pytest.raises(RegistryValidationError, match=r"cites XSD element 'MISSING'"):
        _entries(
            _layout(_target("RESULT", "resultado", line=2, element="MISSING"), *_TARGETS[1:]), (_RESULT, _REMAINDER)
        )


def test_a_reader_holding_only_the_dictionary_cannot_judge_the_xsd_and_still_resolves_the_rows() -> None:
    rows = _entries(_layout(*_TARGETS), (_RESULT, _REMAINDER), with_xsd=False)

    assert rows["RESULT"].casilla_id == "resultado"


def test_the_payload_reader_and_the_row_set_resolve_the_same_casillas() -> None:
    layout = _layout(*_TARGETS)
    payload = b"<Doc><Resultado><RESULT>-14.50</RESULT></Resultado><Resto><REFUNDABLE>-3.25</REFUNDABLE></Resto></Doc>"

    parsed = parse_export_payload(
        layout,
        payload,
        sources=_sources(),
        source_payloads=_payloads(),
        casillas=(_RESULT, _REMAINDER),
    )

    assert {(value.field_id, value.casilla_id): value.value for value in parsed.casillas} == {
        ("RESULT", "resultado"): Decimal("-14.50"),
        ("REFUNDABLE", "20"): Decimal("-3.25"),
    }


def test_an_xml_layout_cannot_be_read_without_the_casillas_that_resolve_its_rows() -> None:
    with pytest.raises(RegistryValidationError, match="needs the edition's casillas"):
        parse_export_payload(_layout(), b"<Doc/>", sources=_sources(), source_payloads=_payloads())


def test_a_target_citing_a_dictionary_other_than_the_layouts_current_one_is_refused() -> None:
    stale = _target("RESULT", "resultado", line=2).model_copy(update={"dictionary_source_ref": _OTHER_DICTIONARY_ID})

    with pytest.raises(ValidationError, match=r"which is not the layout's dictionary.*never inherited"):
        _layout(stale)


def test_a_target_citing_an_xsd_outside_the_layouts_sources_is_refused() -> None:
    elsewhere = _target("RESULT", "resultado", line=2).model_copy(update={"xsd_source_ref": "unlisted-xsd"})

    with pytest.raises(ValidationError, match=r"XSD source 'unlisted-xsd' must be included in source_refs"):
        _layout(elsewhere)


def test_two_targets_for_one_row_are_refused_as_ambiguous() -> None:
    with pytest.raises(ValidationError, match=r"more than one dictionary row target for \['RESULT'\]"):
        _layout(_target("RESULT", "resultado", line=2), _target("RESULT", "20", line=2))


def test_a_layout_that_reads_no_dictionary_cannot_declare_row_targets() -> None:
    fixed = ExportLayoutDefinition(
        id="test-fixed",
        format=ExportLayoutFormat.FIXED_WIDTH,
        source_refs=(_DICTIONARY_ID,),
        legal_refs=(REFERENCE_LEGAL_ID,),
        records=(
            ExportRecordDefinition(
                id="record",
                record_type="record",
                order=0,
                encoding=ExportEncoding.ISO_8859_1,
                line_ending="crlf",
                required=True,
                fields=(
                    ExportFieldDefinition(
                        id="record.f1",
                        kind=CasillaFieldKind.LITERAL,
                        literal="X",
                        offset=1,
                        length=1,
                        data_type=CasillaDataType.TEXT,
                        required=True,
                        padding="none",
                        justification="none",
                        signed=False,
                        legal_refs=(REFERENCE_LEGAL_ID,),
                        source_refs=(_DICTIONARY_ID,),
                    ),
                ),
            ),
        ),
    )

    with pytest.raises(ValidationError, match="declares dictionary row targets on a fixed_width layout"):
        ExportLayoutDefinition.model_validate(
            fixed.model_dump() | {"dictionary_row_targets": (_target("RESULT", "resultado", line=2),)},
        )


def _revision(layout: ExportLayoutDefinition, *casillas: CasillaDefinition) -> ModeloRevision:
    return minimal_revision(casillas=tuple(casillas), export_layouts=(layout,))


def test_a_number_repeated_by_casillas_that_are_all_row_targets_is_a_declared_repeat() -> None:
    revision = _revision(_layout(*_TARGETS), _RESULT, _REMAINDER)

    assert declared_repeated_casilla_numbers(revision) == {"20"}
    assert revision_casilla_identity_failures("revision", revision) == ()


def test_a_repeated_number_without_a_row_target_for_every_holder_is_still_refused() -> None:
    only_one_holder_targeted = _layout(_target("PAYABLE", "20", line=3))
    revision = _revision(only_one_holder_targeted, _RESULT, _REMAINDER)

    assert declared_repeated_casilla_numbers(revision) == frozenset()
    failures = revision_casilla_identity_failures("revision", revision)
    assert "revision: duplicate casilla number '20'" in failures
    assert any("casilla number '20' is reused by multiple casillas" in failure for failure in failures)


def test_a_repeated_number_with_no_layout_target_at_all_is_refused_as_before() -> None:
    revision = _revision(_layout(), _RESULT, _REMAINDER)

    assert "revision: duplicate casilla number '20'" in revision_casilla_identity_failures("revision", revision)


def test_a_declared_repeat_does_not_excuse_a_different_repeated_number() -> None:
    other = _casilla("resultado-gemelo", "10")
    revision = _revision(_layout(*_TARGETS), _ALPHA, other, _RESULT, _REMAINDER)

    assert declared_repeated_casilla_numbers(revision) == {"20"}
    assert "revision: duplicate casilla number '10'" in revision_casilla_identity_failures("revision", revision)
