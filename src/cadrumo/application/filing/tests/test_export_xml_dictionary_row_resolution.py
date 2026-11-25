"""Dictionary rows resolve to the casilla their edition declares, and only the declared repeats move.

Every supported Modelo 100 ejercicio is read through the real dictionary, XSD and registry
casillas; the years come from the registry envelope.
"""

from __future__ import annotations

import pytest

from ....core.period import Period
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.errors import RegistryFailureCondition, RegistryValidationError
from ....domain.calculations.registry.tests.authored_editions import supported_authored_exercises
from ..export_xml_dictionary_rows import xml_dictionary_layout_entries
from ..runtime import RegistrySchemaAccessor, build_runtime_schema_provider

pytestmark = [pytest.mark.integration, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]

_RESULT_ROW = "RESINGDEV"
_REMAINDER_ROWS = ("TCPP112", "TCNN112")


def _provider(operation: PinnedAuthorityOperation, year: int) -> RegistrySchemaAccessor:
    return build_runtime_schema_provider(
        filing_year=year, period=Period.from_year_and_code(year, "0A"), modelos=("100",), operation=operation
    )


def test_only_the_declared_rows_resolve_to_a_casilla_other_than_their_printed_number(
    operation: PinnedAuthorityOperation,
) -> None:
    for year in supported_authored_exercises("100"):
        provider = _provider(operation, year)
        layout = provider.get_snapshot("100").revision.export_layouts[0]
        entries = xml_dictionary_layout_entries(layout, schema_provider=provider)
        moved = {entry.field_id for entry in entries if entry.casilla_id != entry.printed_number}

        assert moved == {_RESULT_ROW}, year


def test_the_result_row_reads_its_own_casilla_and_the_remainder_rows_keep_reading_0695(
    operation: PinnedAuthorityOperation,
) -> None:
    for year in supported_authored_exercises("100"):
        provider = _provider(operation, year)
        layout = provider.get_snapshot("100").revision.export_layouts[0]
        rows = {entry.field_id: entry for entry in xml_dictionary_layout_entries(layout, schema_provider=provider)}

        assert rows[_RESULT_ROW].casilla_id == "RESINGDEV", year
        assert all(rows[name].casilla_id == "0695" == rows[name].printed_number for name in _REMAINDER_ROWS), year


def test_a_row_target_is_declared_only_where_the_edition_dictionary_prints_the_repeat(
    operation: PinnedAuthorityOperation,
) -> None:
    for year in supported_authored_exercises("100"):
        provider = _provider(operation, year)
        layout = provider.get_snapshot("100").revision.export_layouts[0]
        rows = {entry.field_id: entry for entry in xml_dictionary_layout_entries(layout, schema_provider=provider)}
        shared_with_result = rows[_RESULT_ROW].printed_number == rows[_REMAINDER_ROWS[0]].printed_number

        assert bool(layout.dictionary_row_targets) == shared_with_result, year
        assert all(
            target.dictionary_source_ref == layout.dictionary_source_ref for target in layout.dictionary_row_targets
        )


def test_a_layout_no_selected_edition_declares_is_refused_with_its_registry_condition(
    operation: PinnedAuthorityOperation,
) -> None:
    year = supported_authored_exercises("100")[0]
    provider = _provider(operation, year)
    declared = provider.get_snapshot("100").revision.export_layouts[0]
    undeclared = declared.model_copy(update={"id": f"{declared.id}-undeclared"})

    with pytest.raises(RegistryValidationError) as raised:
        xml_dictionary_layout_entries(undeclared, schema_provider=provider)

    failure = raised.value.registry_failure
    assert failure is not None
    assert failure.condition is RegistryFailureCondition.SNAPSHOT_EXPORT_LAYOUT_DECLARED
    assert failure.facts == {"export_layout": str(undeclared.id), "export_layout_declared": False}
