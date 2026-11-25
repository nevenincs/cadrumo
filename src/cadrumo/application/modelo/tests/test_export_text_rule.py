"""The record design's text rule and encoding reach modelo.export through the shared renderer.

A record that declares ``upper_unaccented`` (DR347 states it) writes its names
upper-case without vowel accents and keeps Ñ; a character the record cannot
write refuses the export with served words, naming the field and the
character, never dropping it. A record whose design states no rule (DR303)
writes its text as given.
"""

from __future__ import annotations

import pytest

from cadrumo.application.modelo.export_contracts import ModeloExportCommand
from cadrumo.domain.calculations.registry.tests.published_authority import published_snapshot

from ....application.operations.error_detail import build_operation_error_detail
from ....core.errors.error_codes import ErrorCategory, get_registered_error_code, resolve_error_message
from ....core.operator_action_enums import NoRecoveryOutcome
from ....domain.calculations.export_field_kind import CasillaFieldKind
from ....domain.calculations.registry.fixed_width_codec import ExportAlphanumericText
from ....domain.calculations.registry.schema_base import CasillaDataType
from ....domain.calculations.registry.schema_exports import ExportFieldDefinition, ExportRecordDefinition
from ....domain.calculations.registry.tests.authored_editions import filing_year_envelope
from ....domain.filing.errors import FilingExportUnrepresentableCharacterError
from ...cli_exception_preconditions import nested_terminal_precondition_verdict
from ...filing.record_field_renderer import format_field
from ..export import export_write_failure
from ..export_contracts import ModeloExportUnrepresentableCharacterError

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_FILING_YEAR = filing_year_envelope().horizon
_NAME_BINDING = "modelo-347-contraparte-row-nombre"


def _published_record(modelo: str, period: str, record_type: str) -> ExportRecordDefinition:
    snapshot = published_snapshot(modelo, filing_year=_FILING_YEAR, period=period)
    (record,) = (
        record
        for layout in snapshot.revision.export_layouts
        for record in layout.records
        if record.record_type == record_type
    )
    return record


def _m347_declarado() -> tuple[ExportRecordDefinition, ExportFieldDefinition]:
    """The published declarado record, which declares the rule DR347 states for it."""
    record = _published_record("347", "0A", "declarado")
    assert record.alphanumeric_text == ExportAlphanumericText.UPPER_UNACCENTED
    assert record.alphanumeric_text_source_ref is not None
    assert {record.alphanumeric_text_source_ref} == {ref for field in record.fields for ref in field.source_refs}
    (field,) = (field for field in record.fields if field.binding == _NAME_BINDING)
    assert (field.offset, field.length) == (36, 40)
    return record, field


def test_a_dr347_name_is_written_upper_case_without_accents_keeping_the_enye() -> None:
    record, field = _m347_declarado()

    rendered = format_field(field, "Muñoz Ibáñez, José Ángel", record=record)

    assert rendered == "MUÑOZ IBAÑEZ, JOSE ANGEL".ljust(40)


@pytest.mark.parametrize("locale", ["es", "ca", "en", "hu"])
def test_a_character_the_record_cannot_write_refuses_the_export_with_words(locale: str) -> None:
    record, field = _m347_declarado()
    name = "Dvořák Taller"
    command = ModeloExportCommand.model_construct(calculation_revision_id="revision-1")

    with pytest.raises(FilingExportUnrepresentableCharacterError) as refused:
        format_field(field, name, record=record)
    failure = export_write_failure(command, refused.value.in_record(record.record_type))

    assert isinstance(failure, ModeloExportUnrepresentableCharacterError)
    registered = get_registered_error_code(failure)
    assert (registered.code, registered.category) == (
        "REFUSED_MODELO_EXPORT_UNREPRESENTABLE_CHARACTER",
        ErrorCategory.REFUSED,
    )
    message = resolve_error_message(failure, locale=locale)
    for shown in ("DVOŘAK TALLER", "Ř", "U+0158", "36-75", "declarado"):
        assert shown in message
    verdict = nested_terminal_precondition_verdict(failure)
    assert verdict is not None
    assert verdict.no_recovery_outcome is NoRecoveryOutcome.OPERATOR_DECISION
    assert nested_terminal_precondition_verdict(refused.value) is not None
    detail = build_operation_error_detail(failure)
    assert detail is not None
    assert detail.error_code == "REFUSED_MODELO_EXPORT_UNREPRESENTABLE_CHARACTER"
    assert detail.refusal_words is not None
    assert "DVOŘAK" not in detail.refusal_words
    assert "field_value" not in {entry.key for entry in detail.context}
    for shown in (field.id, "U+0158"):
        assert shown in detail.refusal_words


def test_a_dr303_text_field_is_written_as_given() -> None:
    """DR303's design text states no case rule, so its record declares none."""
    record = _published_record("303", "1T", "declaracion")
    assert record.alphanumeric_text is None
    field = next(
        field
        for field in record.fields
        if field.data_type == CasillaDataType.TEXT
        and field.kind not in {CasillaFieldKind.LITERAL, CasillaFieldKind.FILLER}
        and (field.length or 0) >= 12
    )
    value = "Peña José"

    assert format_field(field, value, record=record) == value.ljust(field.length or 0)
