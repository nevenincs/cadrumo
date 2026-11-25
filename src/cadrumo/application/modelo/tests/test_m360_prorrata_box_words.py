"""Modelo 360's prorrata definitiva (campo 112) reads and exports as the percentage the design means.

The design prints campo 112 as "Prorrata definitiva 2 decimales" in a five-digit
numeric slot, which holds 100,00, and LIVA art. 104.Dos states the prorrata as a
percentage: one hundred times the deduction fraction. The box is stored as that
percentage, so the form shows 56 % and the file carries 05600.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from ....core.casilla_id import validated_casilla_id
from ....core.external_constants import OutputLanguage
from ....domain.calculations.registry.errors import FilingYearOutsideSupportEnvelopeError
from ....domain.calculations.registry.fixed_width_codec import render_fixed_width_export_field
from ....domain.calculations.registry.schema import RegistrySnapshot
from ....domain.calculations.registry.schema_surfaces import CasillaConstraints
from ....domain.calculations.registry.tests.published_authority import (
    published_revision,
    published_snapshot,
    published_supported_filing_years,
)
from ..edit_value_grammar import ModeloEditRatioUnit, ratio_unit
from ..value_presentation import format_casilla_value
from ..work_form_field_vocabulary import (
    ModeloFormCasillaAddressV1,
    ModeloFormEditability,
    ModeloFormOrigin,
    ModeloFormText,
    ModeloFormTextDisclosure,
)
from ..work_form_models import ModeloFormField
from ..work_form_wording import field_value_text

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BOX = "prorrata.definitiva"
_PERIOD = "0A"
_EN = OutputLanguage.EN


def _supported_years() -> tuple[int, ...]:
    support = published_supported_filing_years()
    assert support is not None
    years: list[int] = []
    for year in sorted(support.years):
        try:
            published_snapshot("360", filing_year=year, period=_PERIOD)
        except FilingYearOutsideSupportEnvelopeError:
            continue
        years.append(year)
    return tuple(years)


def _snapshot(year: int) -> RegistrySnapshot:
    return published_snapshot("360", filing_year=year, period=_PERIOD)


def _declared_constraints(year: int) -> CasillaConstraints | None:
    (casilla,) = (item for item in _snapshot(year).revision.casillas if item.id == _BOX)
    assert casilla.data_type == "ratio", year
    return casilla.constraints


def _calculated(value: Decimal, constraints: CasillaConstraints | None) -> ModeloFormField:
    return ModeloFormField.model_validate(
        {
            "address": ModeloFormCasillaAddressV1(casilla_id=validated_casilla_id(_BOX)),
            "box": "112",
            "label": ModeloFormText(text="Prorrata definitiva", disclosure=ModeloFormTextDisclosure.LOCALIZED),
            "help": None,
            "data_type": "ratio",
            "value": value,
            "origin": ModeloFormOrigin.CALCULATED,
            "editability": ModeloFormEditability.NOT_WRITABLE,
            "not_writable_reason": "computed",
            "required": False,
            "constraints": constraints,
        }
    )


def test_some_supported_year_prints_the_prorrata_box() -> None:
    assert _supported_years()


@pytest.mark.parametrize("year", _supported_years())
def test_each_supported_year_shows_the_stored_percentage(year: int) -> None:
    constraints = _declared_constraints(year)
    assert constraints is not None, year
    assert ratio_unit("ratio", constraints.max_value) is ModeloEditRatioUnit.PERCENT

    shown = field_value_text(_calculated(Decimal("56"), constraints), _EN)

    assert shown == format_casilla_value(
        Decimal("56"), data_type="ratio", language=_EN, ratio_unit=ModeloEditRatioUnit.PERCENT
    )
    assert shown is not None and "56" in shown and "%" in shown and "5600" not in shown


@pytest.mark.parametrize("year", _supported_years())
def test_each_supported_year_exports_the_percentage_with_two_implied_decimals(year: int) -> None:
    revision = published_revision("360", str(_snapshot(year).revision.id))
    (field,) = (
        field
        for layout in revision.export_layouts
        for record in layout.records
        for field in record.fields
        if getattr(field, "casilla_id", None) == _BOX
    )
    assert (field.offset, field.length, field.decimals) == (1907, 5, 2), year

    assert render_fixed_width_export_field(field, Decimal("56")) == "05600"
    assert render_fixed_width_export_field(field, Decimal("100")) == "10000"
    assert render_fixed_width_export_field(field, Decimal("33.50")) == "03350"
