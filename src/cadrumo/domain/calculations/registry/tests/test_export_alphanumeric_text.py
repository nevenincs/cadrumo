"""A record design's alphanumeric text rule, declared once per record and applied by the codec.

DR347 (and the other designs that state it) says every alphanumeric and
alphabetic field is written "en mayúsculas sin caracteres especiales, y sin
vocales acentuadas", in ISO-8859-1, where "la letra 'Ñ' tendrá el valor ASCII
209 (Hex. D1) y la 'Ç' (cedilla mayúscula) el valor ASCII 199". A record whose
design states no such rule writes its text as given. Whatever the rule leaves
that the record cannot write is refused by name, never dropped.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from .....core.export_layout_format import ExportLayoutFormat
from ..errors import FixedWidthUnrepresentableCharacterError, FixedWidthValueOverflowError
from ..fixed_width_codec import (
    ExportAlphanumericText,
    FixedWidthRecordRenderError,
    render_fixed_width_export_field,
    render_fixed_width_export_record_body,
)
from ..schema_exports import ExportFieldDefinition, ExportLayoutDefinition, ExportRecordDefinition

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_DR347 = "aeat-dr-347-2025"


def _name_field(*, length: int = 40) -> ExportFieldDefinition:
    """DR347 type-2 positions 36-75, the declarado's name, as a text slot."""
    return ExportFieldDefinition.model_validate(
        {
            "id": "m347.declarado.nombre",
            "offset": 1,
            "length": length,
            "kind": "casilla",
            "casilla_id": "01",
            "data_type": "text",
            "required": True,
            "padding": "right_space",
            "justification": "left",
            "signed": False,
            "legal_refs": ("orden-hac-1431-2025:art-1",),
            "source_refs": (_DR347,),
        }
    )


def _record(**declaration: object) -> ExportRecordDefinition:
    return ExportRecordDefinition.model_validate(
        {
            "id": "m347-declarado",
            "record_type": "declarado",
            "order": 0,
            "encoding": "iso-8859-1",
            "line_ending": "crlf",
            "fields": (_name_field(),),
            **declaration,
        }
    )


def _declared() -> ExportRecordDefinition:
    return _record(alphanumeric_text="upper_unaccented", alphanumeric_text_source_ref=_DR347)


def _layout(record: ExportRecordDefinition, *, source_refs: tuple[str, ...]) -> ExportLayoutDefinition:
    return ExportLayoutDefinition(
        id="generated-modelo-347-fichero",
        format=ExportLayoutFormat.FIXED_WIDTH,
        source_refs=source_refs,
        legal_refs=("orden-hac-1431-2025:art-1",),
        records=(record,),
    )


@pytest.mark.parametrize(
    ("given", "written"),
    [
        pytest.param("Peña Muñoz, José María", "PEÑA MUÑOZ, JOSE MARIA", id="accented-lower-case-with-enye"),
        pytest.param("Françoise Ibáñez Güell", "FRANÇOISE IBAÑEZ GUELL", id="cedilla-and-dieresis"),
        pytest.param("ÀÈÌÒÙ âêîôû", "AEIOU AEIOU", id="every-vowel-accent"),
        pytest.param("Comunidad Cª Nº 3 (S.L.)", "COMUNIDAD Cª Nº 3 (S.L.)", id="ordinary-punctuation-kept"),
    ],
)
def test_a_declared_record_writes_its_text_upper_case_without_vowel_accents(given: str, written: str) -> None:
    rendered = render_fixed_width_export_field(_name_field(), given, record=_declared())

    assert rendered == written.ljust(40)
    rendered.encode("iso-8859-1")


def test_the_record_body_carries_the_rule_into_the_encoded_bytes() -> None:
    body = render_fixed_width_export_record_body(_declared(), field_values={"01": "Peña"})

    assert body == "PEÑA".ljust(40).encode("iso-8859-1")
    assert body[2] == 0xD1


def test_a_decomposed_accent_is_written_as_the_composed_letter_it_spells() -> None:
    rendered = render_fixed_width_export_field(_name_field(), "José Peña", record=_declared())

    assert rendered == "JOSE PEÑA".ljust(40)


def test_a_record_declaring_no_rule_writes_its_text_as_given() -> None:
    rendered = render_fixed_width_export_field(_name_field(), "Peña Muñoz, José", record=_record())

    assert rendered == "Peña Muñoz, José".ljust(40)


@pytest.mark.parametrize(
    ("given", "refused"),
    [
        pytest.param("Šimon Dvořák", "Š", id="letter-outside-iso-8859-1"),
        pytest.param("Taller 3 €", "€", id="euro-sign-outside-iso-8859-1"),
        pytest.param("Nombre\tApellido", "\t", id="control-character"),
    ],
)
def test_a_character_the_record_cannot_write_is_refused_by_name(given: str, refused: str) -> None:
    with pytest.raises(FixedWidthUnrepresentableCharacterError) as excinfo:
        render_fixed_width_export_field(_name_field(), given, record=_declared())

    assert (excinfo.value.field_id, excinfo.value.character) == ("m347.declarado.nombre", refused)


def test_a_record_declaring_no_rule_still_refuses_what_its_encoding_cannot_write() -> None:
    with pytest.raises(FixedWidthUnrepresentableCharacterError) as excinfo:
        render_fixed_width_export_field(_name_field(), "Taller 3 €", record=_record())

    assert excinfo.value.character == "€"


def test_the_record_body_refuses_rather_than_writing_an_unrepresentable_character() -> None:
    with pytest.raises(FixedWidthRecordRenderError) as excinfo:
        render_fixed_width_export_record_body(_declared(), field_values={"01": "Taller €"})

    assert (excinfo.value.field_id, excinfo.value.reason) == ("m347.declarado.nombre", "fixed_width_value")
    assert isinstance(excinfo.value.__cause__, FixedWidthUnrepresentableCharacterError)


def test_the_width_is_measured_on_the_text_the_rule_writes() -> None:
    """German sharp s upper-cases to two letters; the slot is checked after the rule, never cut."""
    with pytest.raises(FixedWidthValueOverflowError):
        render_fixed_width_export_field(_name_field(length=4), "Groß", record=_declared())


def test_the_rule_hydrates_to_its_closed_member() -> None:
    assert _declared().alphanumeric_text is ExportAlphanumericText.UPPER_UNACCENTED


def test_a_rule_outside_the_closed_vocabulary_is_refused() -> None:
    with pytest.raises(ValidationError):
        _record(alphanumeric_text="lower", alphanumeric_text_source_ref=_DR347)


def test_a_rule_without_the_design_that_states_it_is_refused() -> None:
    with pytest.raises(ValidationError, match="alphanumeric_text_source_ref"):
        _record(alphanumeric_text="upper_unaccented")


def test_a_source_without_a_rule_is_refused() -> None:
    with pytest.raises(ValidationError, match="alphanumeric_text_source_ref"):
        _record(alphanumeric_text_source_ref=_DR347)


def test_the_rule_must_cite_a_design_the_layout_is_built_from() -> None:
    assert _layout(_declared(), source_refs=(_DR347,)).records[0].alphanumeric_text_source_ref == _DR347
    with pytest.raises(ValidationError, match="must be included in source_refs"):
        _layout(_declared(), source_refs=("aeat-dr-347-2011",))
