"""Modelo 322 writes the zero its open-ended design admits for three Yes/No boxes.

The open-ended Modelo 322 design prints positions 134, 135 and 136 (the
modelo 390 exemption, the non-zero annual volume and the fuel deduction) as
``0 , Si=1, No=2`` and ``0=Vacío, Si=1, No=2``: zero is an admitted wire value
beside Yes and No. A draft storing it is written through the export field
codec at each published position, and a value outside the design stays refused.
"""

from __future__ import annotations

import pytest

from ....core.casilla_id import CasillaId, validated_casilla_id
from ....core.period import Period
from ....domain.calculations.registry.errors import FilingYearOutsideSupportEnvelopeError, RegistryValidationError
from ....domain.calculations.registry.fixed_width_codec import render_fixed_width_export_field
from ....domain.calculations.registry.schema_exports import ExportFieldDefinition, ExportRecordDefinition
from ....domain.calculations.registry.tests.authored_editions import open_ended_revision
from ....domain.calculations.registry.tests.published_authority import (
    published_snapshot,
    published_supported_filing_years,
)
from ....domain.filing.schema import ModeloDraft, ModeloDraftStatus
from ..draft_construction import build_draft
from ..runtime import ModeloOperatorProfile, RegistrySchemaAccessor
from .export_support import export_schema_provider

pytestmark = [pytest.mark.integration, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]

_MODELO = "322"
_PROJECTED_YEAR = "errors.snapshot.filing_year_projected"
_CHOICE_BOXES: tuple[CasillaId, ...] = (
    validated_casilla_id("decl.exonerado-modelo-390"),
    validated_casilla_id("decl.volumen-anual-no-cero"),
    validated_casilla_id("decl.deduccion-pago-cuenta-gasolinas"),
)


def _period() -> str:
    periods = open_ended_revision(_MODELO).period_selector.periods
    assert periods
    return periods[0]


def _provider(filing_year: int) -> RegistrySchemaAccessor:
    return export_schema_provider(filing_year=filing_year, period=_period(), modelos=(_MODELO,))


def _draft(filing_year: int, choice: str) -> ModeloDraft:
    draft = build_draft(
        modelo=_MODELO,
        period=Period.from_year_and_code(filing_year, _period()),
        profile=ModeloOperatorProfile(tax_id="12345678Z", display_name="Grupo IVA prueba"),
        inputs=dict.fromkeys(_CHOICE_BOXES, choice),
        schema_provider=_provider(filing_year),
    )
    return draft.model_copy(update={"status": ModeloDraftStatus.APROBADO})


def _designed_fields(filing_year: int) -> dict[CasillaId, tuple[ExportRecordDefinition, ExportFieldDefinition]]:
    layout = _provider(filing_year).get_snapshot(_MODELO).revision.export_layouts[0]
    return {
        field.casilla_id: (record, field)
        for record in layout.records
        for field in record.fields
        if field.casilla_id in _CHOICE_BOXES
    }


def _open_ended_years() -> tuple[int, ...]:
    """The supported years the open-ended edition exports with a design of its own."""
    support = published_supported_filing_years()
    assert support is not None
    edition = open_ended_revision(_MODELO).id
    years: list[int] = []
    for year in sorted(support.years):
        try:
            snapshot = published_snapshot(_MODELO, filing_year=year, period=_period())
        except FilingYearOutsideSupportEnvelopeError:
            continue
        except RegistryValidationError as refused:
            if refused.translated_message != _PROJECTED_YEAR:
                raise
            continue
        if snapshot.revision.id == edition:
            years.append(year)
    return tuple(years)


def test_some_supported_year_exports_the_open_ended_edition() -> None:
    assert _open_ended_years()


@pytest.mark.parametrize("choice", ["0", "1", "2"])
@pytest.mark.parametrize("year", _open_ended_years())
def test_each_choice_the_design_admits_is_written_to_its_position(year: int, choice: str) -> None:
    draft = _draft(year, choice)
    stored = {value.casilla_id: value.value for value in draft.values}
    designed = _designed_fields(year)
    assert set(designed) == set(_CHOICE_BOXES), year

    for casilla_id, (record, field) in designed.items():
        assert stored[casilla_id] == choice, (year, casilla_id)
        assert render_fixed_width_export_field(field, stored[casilla_id], record=record) == choice, (year, casilla_id)


@pytest.mark.parametrize("year", _open_ended_years())
def test_a_value_the_design_does_not_admit_stays_refused(year: int) -> None:
    for casilla_id, (record, field) in _designed_fields(year).items():
        with pytest.raises(RegistryValidationError, match="outside allowed_values"):
            render_fixed_width_export_field(field, "3", record=record)
        assert field.allowed_values == ("0", "1", "2"), (year, casilla_id)
