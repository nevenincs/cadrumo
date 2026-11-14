"""Modelo 100's average rates of tax (0534, 0535) read as the percentages the design prints, in every supported year.

The official design states ``[0534] = [0532] x 100 / [0505]`` and ``[0535] =
[0533] x 100 / [0505]``: the boxes hold a percentage. A ratio box whose
declaration names no scale shows no figure, since a filer could read it a
hundredfold wrong, so each year's edition must declare the scale for the form
to show these boxes at all.
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

_AVERAGE_RATES = ("0534", "0535")
_EN = OutputLanguage.EN


def _supported_years() -> tuple[int, ...]:
    support = published_supported_filing_years()
    assert support is not None
    years: list[int] = []
    for year in sorted(support.years):
        try:
            published_snapshot("100", filing_year=year, period="0A")
        except FilingYearOutsideSupportEnvelopeError:
            continue
        years.append(year)
    return tuple(years)


def _declared_constraints(year: int, casilla_id: str) -> CasillaConstraints | None:
    snapshot = published_snapshot("100", filing_year=year, period="0A")
    (casilla,) = (item for item in snapshot.revision.casillas if item.id == casilla_id)
    assert casilla.data_type == "ratio", (year, casilla_id)
    return casilla.constraints


def _calculated(casilla_id: str, value: Decimal, constraints: CasillaConstraints | None) -> ModeloFormField:
    return ModeloFormField.model_validate(
        {
            "address": ModeloFormCasillaAddressV1(casilla_id=validated_casilla_id(casilla_id)),
            "box": casilla_id,
            "label": ModeloFormText(text="Tipo medio", disclosure=ModeloFormTextDisclosure.LOCALIZED),
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


@pytest.mark.parametrize("year", _supported_years())
@pytest.mark.parametrize("casilla_id", _AVERAGE_RATES)
def test_each_supported_year_shows_the_average_rate_as_a_percentage(year: int, casilla_id: str) -> None:
    constraints = _declared_constraints(year, casilla_id)
    assert constraints is not None, (year, casilla_id)
    assert ratio_unit("ratio", constraints.max_value) is ModeloEditRatioUnit.PERCENT

    shown = field_value_text(_calculated(casilla_id, Decimal("8.28"), constraints), _EN)

    assert shown == format_casilla_value(
        Decimal("8.28"), data_type="ratio", language=_EN, ratio_unit=ModeloEditRatioUnit.PERCENT
    )
    assert shown is not None and "%" in shown and "828" not in shown


def test_an_average_rate_with_no_declared_scale_shows_no_figure() -> None:
    assert field_value_text(_calculated("0534", Decimal("8.28"), None), _EN) is None
