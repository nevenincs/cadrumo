"""A saver's interest and dividends reach the Modelo 100 XML as one detail record per occurrence.

Each edition the support envelope covers is read off the registry, never named. The
detail records, their fields and their bound come from the edition's input dictionary
and XSD through the real renderer, and the written file is read back through the real
export parser and the real export verification. The figures are synthetic: two
interest occurrences and one dividend occurrence, whose boxes are their sums.
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal
from pathlib import Path

import pytest
from defusedxml import ElementTree

from ....core.errors.error_codes import resolve_error_message
from ....core.period import Period
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.binding_targets import sole_bound_casilla
from ....domain.calculations.registry.bindings import resolve_available_bound_inputs_by_casilla_id
from ....domain.calculations.registry.capital_mobiliario_position_bindings import (
    CapitalMobiliarioPositionProvider,
    CapitalMobiliarioQuantity,
    capital_mobiliario_position_bindings,
)
from ....domain.calculations.registry.export_parse import parse_export_payload
from ....domain.calculations.registry.export_xml_dictionary import XmlDictionaryEntry, xml_dictionary_entries
from ....domain.calculations.registry.ids import BindingId
from ....domain.calculations.registry.tests.authored_editions import supported_authored_exercises
from ....domain.filing.errors import FilingExportCasillaValueRefusedError, FilingExportValidationError
from ....domain.filing.protocols import ModeloInputScalar, ModeloInputValue
from ....domain.filing.schema import ModeloDraft
from ....domain.submission.models import ModeloDraftStatus
from ..draft_construction import build_draft
from ..export_verification import verify_export
from ..export_xml_dictionary import render_xml_dictionary_layout
from ..export_xml_dictionary_xsd import xml_dictionary_repeating_element_paths, xml_dictionary_xsd_source
from ..export_xml_input_dictionary import declared_and_admitted_dictionary_entries
from ..export_xml_row_columns import nearest_repeating_element_path
from ..runtime import ModeloOperatorProfile, RegistrySchemaAccessor, build_runtime_schema_provider
from .export_support import filer_with_nothing_else

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

_EDITIONS = supported_authored_exercises("100")
_FIGURES: Mapping[CapitalMobiliarioQuantity, tuple[Decimal, ...]] = {
    CapitalMobiliarioQuantity.GROSS: (Decimal("300.00"), Decimal("100.00")),
    CapitalMobiliarioQuantity.WITHHOLDING: (Decimal("57.00"), Decimal("19.00")),
    CapitalMobiliarioQuantity.EXPENSES: (Decimal("5.00"), Decimal("2.50")),
}
"""Per quantity, the first record's two occurrences; the second record has one, the first figure."""


def _provider(operation: PinnedAuthorityOperation, year: int) -> RegistrySchemaAccessor:
    return build_runtime_schema_provider(
        filing_year=year,
        period=Period.from_year_and_code(year, "0A"),
        modelos=("100",),
        operation=operation,
    )


def _family(provider: RegistrySchemaAccessor) -> tuple[tuple[BindingId, CapitalMobiliarioPositionProvider], ...]:
    revision = provider.get_snapshot("100").revision
    return tuple((binding.id, selector) for binding, selector in capital_mobiliario_position_bindings(revision))


def _records(provider: RegistrySchemaAccessor) -> tuple[str, ...]:
    return tuple(
        sorted(
            {
                selector.detail_record
                for _binding, selector in _family(provider)
                if selector.dictionary_field is not None and selector.detail_record is not None
            }
        )
    )


def _occurrences(provider: RegistrySchemaAccessor, record: str, *, first_count: int) -> int:
    return first_count if record == _records(provider)[0] else 1


def _figure(quantity: CapitalMobiliarioQuantity, index: int) -> Decimal:
    figures = _FIGURES[quantity]
    return figures[index] if index < len(figures) else figures[0]


def _inputs(provider: RegistrySchemaAccessor, *, first_count: int = 2) -> dict[str, ModeloInputValue]:
    """State every row column's rows and every scalar total as the sum of the rows it totals."""
    family = _family(provider)
    figures: dict[BindingId, tuple[Decimal, ...]] = {
        binding_id: tuple(
            _figure(selector.quantity, index)
            for index in range(_occurrences(provider, selector.detail_record, first_count=first_count))
        )
        for binding_id, selector in family
        if selector.dictionary_field is not None and selector.detail_record is not None
    }
    inputs: dict[str, ModeloInputValue] = {}
    for binding_id, column in figures.items():
        rows: dict[str, ModeloInputScalar] = {str(index + 1): value for index, value in enumerate(column)}
        inputs[str(binding_id)] = rows
    selectors = dict(family)
    for binding_id, selector in family:
        if selector.dictionary_field is None:
            inputs[str(binding_id)] = sum(
                (
                    value
                    for column_id, column in figures.items()
                    if selectors[column_id].quantity is selector.quantity
                    and selector.detail_record in {None, selectors[column_id].detail_record}
                    for value in column
                ),
                Decimal("0"),
            )
    return inputs


def _draft(provider: RegistrySchemaAccessor, year: int, inputs: dict[str, ModeloInputValue]) -> ModeloDraft:
    stated = {**filer_with_nothing_else(provider), **inputs}
    amounts = {key: value for key, value in stated.items() if isinstance(value, Decimal)}
    bound_boxes = resolve_available_bound_inputs_by_casilla_id(provider.get_snapshot("100").revision, amounts)
    return build_draft(
        modelo="100",
        period=Period.from_year_and_code(year, "0A"),
        profile=ModeloOperatorProfile(tax_id="12345678Z", display_name="DECLARANTE PRUEBA"),
        inputs={**bound_boxes, **stated},
        schema_provider=provider,
    ).model_copy(update={"status": ModeloDraftStatus.APROBADO})


def _render(provider: RegistrySchemaAccessor, draft: ModeloDraft) -> bytes:
    return render_xml_dictionary_layout(
        provider.get_snapshot("100").revision.export_layouts[0],
        draft=draft,
        headers={},
        aux_version="001",
        schema_provider=provider,
    )


def _admitted(provider: RegistrySchemaAccessor) -> tuple[XmlDictionaryEntry, ...]:
    revision = provider.get_snapshot("100").revision
    _declared, admitted = declared_and_admitted_dictionary_entries(
        revision.export_layouts[0],
        bindings=revision.bindings,
        casillas=revision.casillas,
        sources=provider.sources,
        source_payloads=provider.source_payloads,
    )
    return admitted


def _repeating(provider: RegistrySchemaAccessor) -> Mapping[str, int | None]:
    layout = provider.get_snapshot("100").revision.export_layouts[0]
    return xml_dictionary_repeating_element_paths(
        xml_dictionary_xsd_source(layout, provider.sources), source_payloads=provider.source_payloads
    )


@pytest.mark.parametrize("year", _EDITIONS)
def test_every_edition_places_one_detail_record_per_occurrence_and_reads_it_back(
    operation: PinnedAuthorityOperation, year: int, tmp_path: Path
) -> None:
    provider = _provider(operation, year)
    revision = provider.get_snapshot("100").revision
    layout = revision.export_layouts[0]
    declared_fields = {
        entry.field_id
        for entry in xml_dictionary_entries(
            layout, sources=provider.sources, source_payloads=provider.source_payloads, casillas=revision.casillas
        )
    }
    admitted = _admitted(provider)
    columns = {s.dictionary_field: s for _b, s in _family(provider) if s.dictionary_field is not None}
    assert {entry.field_id for entry in admitted} == set(columns)
    assert not declared_fields & set(columns), "the declaration dictionary must not be displaced"
    draft = _draft(provider, year, _inputs(provider))

    payload = _render(provider, draft)

    document = ElementTree.fromstring(payload)
    repeating = _repeating(provider)
    for entry in admitted:
        element = nearest_repeating_element_path(entry.path, repeating)
        assert element is not None
        occurrences = document.findall(element.strip("/"))
        selector = columns[entry.field_id]
        assert selector.detail_record is not None
        count = _occurrences(provider, selector.detail_record, first_count=2)
        assert len(occurrences) == count
        written = [Decimal(node.findtext(entry.path.removeprefix(f"{element}/")) or "0") for node in occurrences]
        assert written == [_figure(selector.quantity, index) for index in range(count)]
    parsed = parse_export_payload(
        layout,
        payload,
        sources=provider.sources,
        source_payloads=provider.source_payloads,
        casillas=revision.casillas,
        admitted_entries=admitted,
    )
    for entry in admitted:
        read = [field.value for field in parsed.fields if field.field_id == entry.field_id]
        selector = columns[entry.field_id]
        assert selector.detail_record is not None
        count = _occurrences(provider, selector.detail_record, first_count=2)
        assert read == [_figure(selector.quantity, index) for index in range(count)]
    output = tmp_path / f"modelo-100-{year}.xml"
    output.write_bytes(payload)
    assert verify_export(draft, file_path=output, schema_provider=provider).verdict.value == "match"


def test_more_occurrences_than_the_schema_admits_are_refused_with_served_words(
    operation: PinnedAuthorityOperation,
) -> None:
    year = _EDITIONS[-1]
    provider = _provider(operation, year)
    record = _records(provider)[0]
    element = next(
        path
        for entry in _admitted(provider)
        if (path := nearest_repeating_element_path(entry.path, _repeating(provider))) is not None
        and path.endswith(f"/{record}")
    )
    limit = _repeating(provider)[element]
    assert limit is not None
    _render(provider, _draft(provider, year, _inputs(provider, first_count=limit)))

    with pytest.raises(FilingExportValidationError) as refused:
        _render(provider, _draft(provider, year, _inputs(provider, first_count=limit + 1)))

    assert refused.value.translated_message == "application.filing.export.errors.xml_rows_exceed_schema"
    assert refused.value.context == {"rows": limit + 1, "element_path": element, "limit": limit}
    for locale in ("es", "ca", "en", "hu"):
        message = resolve_error_message(refused.value, locale=locale)
        assert str(limit) in message
        assert "%{" not in message


def test_a_box_its_occurrences_do_not_add_up_to_is_refused(operation: PinnedAuthorityOperation) -> None:
    year = _EDITIONS[-1]
    provider = _provider(operation, year)
    revision = provider.get_snapshot("100").revision
    inputs = _inputs(provider)
    total = next(
        binding_id
        for binding_id, selector in _family(provider)
        if selector.dictionary_field is None and selector.quantity is CapitalMobiliarioQuantity.GROSS
    )
    stated = inputs[str(total)]
    assert isinstance(stated, Decimal)
    inputs[str(total)] = stated + Decimal("1.00")

    with pytest.raises(FilingExportCasillaValueRefusedError) as refused:
        _render(provider, _draft(provider, year, inputs))

    assert refused.value.casilla_id == sole_bound_casilla(revision, total)
    assert refused.value.translated_message == "application.filing.export.errors.box_not_stated_by_rows"
    for locale in ("es", "ca", "en", "hu"):
        assert "%{" not in resolve_error_message(refused.value, locale=locale)


def test_a_return_without_occurrences_places_no_detail_record(operation: PinnedAuthorityOperation) -> None:
    year = _EDITIONS[-1]
    provider = _provider(operation, year)
    repeating = _repeating(provider)

    document = ElementTree.fromstring(_render(provider, _draft(provider, year, {})))

    for entry in _admitted(provider):
        element = nearest_repeating_element_path(entry.path, repeating)
        assert element is not None
        assert document.findall(element.strip("/")) == []
