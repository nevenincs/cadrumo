"""Modelo 210's tipo de gravamen [21] reads as the percentage the design prints, in every supported year.

Every design prints [21] as "Tipo de gravamen Ley IRNR (%)" while the
calculation stores the rate as a fraction (the general rate as 0.24). A ratio
box whose declaration names no scale shows no figure, so each year must declare
the fraction for the form to show 24 % where the design does.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from ....core.casilla_id import validated_casilla_id
from ....core.external_constants import OutputLanguage
from ....domain.calculations.registry.errors import FilingYearOutsideSupportEnvelopeError
from ....domain.calculations.registry.schema_surfaces import CasillaConstraints
from ....domain.calculations.registry.tests.published_authority import (
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

_RATE_BOX = "tipo_gravamen"
_PERIOD = "EVENT-1"
_EN = OutputLanguage.EN


def _supported_years() -> tuple[int, ...]:
    support = published_supported_filing_years()
    assert support is not None
    years: list[int] = []
    for year in sorted(support.years):
        try:
            published_snapshot("210", filing_year=year, period=_PERIOD)
        except FilingYearOutsideSupportEnvelopeError:
            continue
        years.append(year)
    return tuple(years)


def _declared_constraints(year: int) -> CasillaConstraints | None:
    snapshot = published_snapshot("210", filing_year=year, period=_PERIOD)
    (casilla,) = (item for item in snapshot.revision.casillas if item.id == _RATE_BOX)
    assert casilla.data_type == "ratio", year
    return casilla.constraints


def _calculated(value: Decimal, constraints: CasillaConstraints | None) -> ModeloFormField:
    return ModeloFormField.model_validate(
        {
            "address": ModeloFormCasillaAddressV1(casilla_id=validated_casilla_id(_RATE_BOX)),
            "box": "21",
            "label": ModeloFormText(text="Tipo de gravamen", disclosure=ModeloFormTextDisclosure.LOCALIZED),
            "help": None,
            "data_type": "ratio",
            "value": value,
            "origin": ModeloFormOrigin.CALCULATED,
            "editability": ModeloFormEditability.NOT_WRITABLE,
            "not_writable_reason": "computed",
            "required": True,
            "constraints": constraints,
        }
    )


def test_some_supported_year_prints_the_rate_box() -> None:
    assert _supported_years()


@pytest.mark.parametrize("year", _supported_years())
def test_each_supported_year_shows_the_stored_fraction_as_a_percentage(year: int) -> None:
    constraints = _declared_constraints(year)
    assert constraints is not None, year
    assert ratio_unit("ratio", constraints.max_value) is ModeloEditRatioUnit.FRACTION

    shown = field_value_text(_calculated(Decimal("0.24"), constraints), _EN)

    assert shown == format_casilla_value(
        Decimal("0.24"), data_type="ratio", language=_EN, ratio_unit=ModeloEditRatioUnit.FRACTION
    )
    assert shown is not None and "24" in shown and "%" in shown and "0.24" not in shown


def test_the_rate_box_with_no_declared_scale_shows_no_figure() -> None:
    assert field_value_text(_calculated(Decimal("0.24"), None), _EN) is None
