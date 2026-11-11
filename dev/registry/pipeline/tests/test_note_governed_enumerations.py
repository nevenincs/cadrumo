"""A pointer-only slot takes the closed code domain its note's value table states."""

from __future__ import annotations

import warnings
from typing import Final

import openpyxl
import pytest
from pydantic import ValidationError

from cadrumo.core.filing_producer_key import FilingProducerKey
from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.export_value_policy import ExportValuePolicy
from cadrumo.domain.calculations.registry.form_context import resolve_form_context_field
from cadrumo.domain.calculations.registry.schema_form_layouts import FormContextFieldBlock
from cadrumo.domain.calculations.registry.tests.authored_editions import filing_year_envelope
from cadrumo.domain.calculations.registry.tests.published_authority import (
    published_snapshot,
    published_source_reference,
)

from ..export_field_numeric_derivation import numeric_derivation
from ..joined_record_design import JoinedRecordDesignField
from ..note_governed_enumerations import (
    NoteGovernedEnumerationDeclaration,
    note_governed_enumeration_for,
    note_governed_enumerations_for,
)
from ..record_design_intermediate import RecordDesignIntermediateField
from ..semantic_map import SemanticMapEntry

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_M303_SOURCE_REFS: Final = (
    "aeat-dr-303-2022",
    "aeat-dr-303-2023",
    "aeat-dr-303-2024-early",
    "aeat-dr-303-2024-late",
    "aeat-dr-303-2025",
    "aeat-dr-303-2026",
)
_POINTER: Final = "Nota 6. Nota 5"


def _declarations(source_ref: str) -> tuple[NoteGovernedEnumerationDeclaration, ...]:
    """Resolve the readings through the published source pin, as generation does."""
    return note_governed_enumerations_for(source_ref, published_source_reference(source_ref).sha256)


def _joined_field(*, source_cell: str = "A22", content: str = _POINTER, length: int = 1) -> JoinedRecordDesignField:
    row = int(source_cell[1:])
    parser_field = RecordDesignIntermediateField.model_validate(
        {
            "sheet": "DP30301",
            "record_identity": "DP30301",
            "source_row": row,
            "source_cell": source_cell,
            "ordinal": str(row - 5),
            "offset": 115,
            "length": length,
            "aeat_type": "Num",
            "normalized_description": "Identificación (1) - Opción por la aplicación de la prorrata especial",
            "content": content,
        }
    )
    entry = SemanticMapEntry.model_validate(
        {
            "anchor": {
                "sheet": parser_field.sheet,
                "source_row": parser_field.source_row,
                "source_cell": parser_field.source_cell,
                "ordinal": parser_field.ordinal,
                "record_identity": parser_field.record_identity,
            },
            "export_field_id": "m303-2025.dp30301.f017",
            "kind": "header",
            "producer_key": FilingProducerKey.M303_PRORRATA_SPECIAL_OPTION,
            "legal_refs": ("orden-eha-3786-2008:art-1",),
            "source_refs": ("aeat-dr-303-2025",),
        }
    )
    return JoinedRecordDesignField(parser_field=parser_field, semantic_entry=entry)


@pytest.mark.parametrize("source_ref", _M303_SOURCE_REFS)
def test_each_declaration_quotes_its_pinned_workbook_cell_for_cell(source_ref: str) -> None:
    source = published_source_reference(source_ref)
    declarations = _declarations(source_ref)
    assert {declaration.source_cell for declaration in declarations} == {"A22", "A23"}
    for declaration in declarations:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            workbook = openpyxl.load_workbook(bundled_path() / source.corpus_path, data_only=True)
        sheet = workbook[declaration.sheet]
        row = int(declaration.source_cell[1:])
        assert sheet[f"G{row}"].value == declaration.published_pointer
        assert sheet[f"C{row}"].value == 1
        assert sheet[declaration.note_cell].value == declaration.note_statement
        for table_row in declaration.value_table:
            assert str(sheet[table_row.value_cell].value) == table_row.value
            assert sheet[table_row.description_cell].value == table_row.description


@pytest.mark.parametrize("source_ref", _M303_SOURCE_REFS)
def test_the_domain_is_the_note_tables_value_column(source_ref: str) -> None:
    for declaration in _declarations(source_ref):
        assert declaration.allowed_values == ("1", "2")


def test_a_reading_refuses_a_design_other_than_the_reviewed_bytes() -> None:
    with pytest.raises(RegistryValidationError, match="not pinned"):
        note_governed_enumerations_for("aeat-dr-303-2025", "0" * 64)


def test_a_design_without_a_reading_has_none() -> None:
    assert note_governed_enumerations_for("aeat-dr-390-2025", "0" * 64) == ()


def test_the_declared_pointer_closes_the_slot_to_the_tabulated_codes() -> None:
    derived = numeric_derivation(
        _joined_field(),
        export_record_id="m303-declaration",
        note_governed_enumerations=_declarations("aeat-dr-303-2025"),
    )

    assert derived.derivation_code == "numeric-note-governed-enumeration-v1"
    assert derived.field.data_type == "integer"
    assert derived.field.value_policy is ExportValuePolicy.ENUMERATED_DIGITS
    assert derived.field.allowed_values == ("1", "2")


def test_without_the_reading_the_pointer_keeps_its_open_integer_shape() -> None:
    derived = numeric_derivation(_joined_field(), export_record_id="m303-declaration")

    assert derived.derivation_code == "numeric-integer-v1"
    assert derived.field.allowed_values is None


def test_a_reading_does_not_reach_another_cell_with_the_same_pointer() -> None:
    derived = numeric_derivation(
        _joined_field(source_cell="A28"),
        export_record_id="m303-declaration",
        note_governed_enumerations=_declarations("aeat-dr-303-2025"),
    )

    assert derived.derivation_code == "numeric-integer-v1"


def test_a_reissued_pointer_on_the_declared_cell_is_not_covered() -> None:
    declarations = _declarations("aeat-dr-303-2025")

    assert (
        note_governed_enumeration_for(declarations, sheet="DP30301", source_cell="A22", published_pointer="Nota 7")
        is None
    )


def test_a_code_that_does_not_fill_the_slot_is_refused() -> None:
    with pytest.raises(RegistryValidationError, match="slot width"):
        numeric_derivation(
            _joined_field(length=2),
            export_record_id="m303-declaration",
            note_governed_enumerations=_declarations("aeat-dr-303-2025"),
        )


def test_a_pointer_that_does_not_name_the_tabulated_note_is_refused() -> None:
    declaration = _declarations("aeat-dr-303-2025")[0]
    payload = declaration.model_dump()
    payload["published_pointer"] = "Nota 5"

    with pytest.raises(ValidationError, match="name the tabulated note"):
        NoteGovernedEnumerationDeclaration.model_validate(payload)


def test_a_table_that_repeats_a_code_is_refused() -> None:
    declaration = _declarations("aeat-dr-303-2025")[0]
    payload = declaration.model_dump()
    payload["value_table"] = (payload["value_table"][0], payload["value_table"][0])

    with pytest.raises(ValidationError, match="repeat a code"):
        NoteGovernedEnumerationDeclaration.model_validate(payload)


def _m303_period_tokens() -> tuple[str, ...]:
    """Every period token any authored 303 edition declares, read from the published directory."""
    with bundled_indexed_authority().operation() as operation:
        directory = operation.modelo_directory("303")
    return tuple(
        sorted(
            {
                str(period)
                for revision in directory.revisions
                for period in revision.period_selector.periods_for_year(revision.valid_from.year)
            }
        )
    )


@pytest.mark.parametrize("filing_year", filing_year_envelope().years)
def test_every_supported_year_and_period_closes_the_prorrata_option_pair(filing_year: int) -> None:
    for period in _m303_period_tokens():
        snapshot = published_snapshot("303", filing_year=filing_year, period=period)
        fields = {
            str(field.producer_key): field
            for layout in snapshot.revision.export_layouts
            for record in layout.records
            for field in record.fields
            if field.producer_key
            in {FilingProducerKey.M303_PRORRATA_SPECIAL_OPTION, FilingProducerKey.M303_PRORRATA_SPECIAL_REVOCATION}
        }
        assert set(fields) == {
            FilingProducerKey.M303_PRORRATA_SPECIAL_OPTION.value,
            FilingProducerKey.M303_PRORRATA_SPECIAL_REVOCATION.value,
        }, (filing_year, period)
        for field in fields.values():
            assert field.value_policy is ExportValuePolicy.ENUMERATED_DIGITS
            assert field.allowed_values == ("1", "2")


@pytest.mark.parametrize("filing_year", filing_year_envelope().years)
def test_every_supported_year_labels_both_prorrata_codes_on_the_form(filing_year: int) -> None:
    for period in _m303_period_tokens():
        snapshot = published_snapshot("303", filing_year=filing_year, period=period)
        with bundled_indexed_authority().operation() as operation:
            layout = operation.form_layout("303", str(snapshot.revision.id))
        assert layout is not None, (filing_year, period)
        blocks = [
            block
            for page in layout.pages
            for section in page.sections
            for block in section.blocks
            if block.id in {"opcion-prorrata", "revocacion-prorrata"}
        ]
        assert len(blocks) == 2, (filing_year, period)
        for block in blocks:
            assert isinstance(block, FormContextFieldBlock)
            assert tuple((choice.value, choice.heading_key) for choice in block.choices) == (
                ("1", "modelo.schema.303.form.authored.si.heading"),
                ("2", "modelo.schema.303.form.authored.prorrata-especial-no.heading"),
            )
            assert all(choice.official_heading for choice in block.choices)
            resolve_form_context_field(snapshot.revision, block)
