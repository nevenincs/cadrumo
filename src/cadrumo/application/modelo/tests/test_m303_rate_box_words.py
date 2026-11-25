"""Modelo 303's rate boxes read as the percentages the designs print, in every supported quarter.

Each design prints a rate box as "Tipo %" in a five-digit field with two
decimals (the transitional [154] as the constant "00500"), so the box holds a
percentage. A ratio box whose declaration names no scale shows no figure, since
a filer could read it a hundredfold wrong; the window drew [154] blank while
the form held 5.00. Every rate box of every quarter's edition must therefore
declare its scale.
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

_QUARTERS = ("1T", "2T", "3T", "4T")
_EN = OutputLanguage.EN


def _supported_quarters() -> tuple[tuple[int, str], ...]:
    support = published_supported_filing_years()
    assert support is not None
    quarters: list[tuple[int, str]] = []
    for year in sorted(support.years):
        for period in _QUARTERS:
            try:
                published_snapshot("303", filing_year=year, period=period)
            except FilingYearOutsideSupportEnvelopeError:
                continue
            quarters.append((year, period))
    return tuple(quarters)


def _rate_boxes(year: int, period: str) -> dict[str, CasillaConstraints | None]:
    snapshot = published_snapshot("303", filing_year=year, period=period)
    return {item.id: item.constraints for item in snapshot.revision.casillas if item.data_type == "ratio"}


def _calculated(casilla_id: str, value: Decimal, constraints: CasillaConstraints | None) -> ModeloFormField:
    return ModeloFormField.model_validate(
        {
            "address": ModeloFormCasillaAddressV1(casilla_id=validated_casilla_id(casilla_id)),
            "box": casilla_id,
            "label": ModeloFormText(text="Tipo %", disclosure=ModeloFormTextDisclosure.LOCALIZED),
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


@pytest.mark.parametrize(("year", "period"), _supported_quarters())
def test_every_rate_box_of_each_quarter_declares_a_percentage(year: int, period: str) -> None:
    boxes = _rate_boxes(year, period)
    assert boxes, (year, period)
    undeclared = sorted(
        casilla_id
        for casilla_id, constraints in boxes.items()
        if constraints is None or ratio_unit("ratio", constraints.max_value) is not ModeloEditRatioUnit.PERCENT
    )
    assert undeclared == [], (year, period, undeclared)


def _quarters_with_transitional_rate() -> tuple[tuple[int, str], ...]:
    return tuple(quarter for quarter in _supported_quarters() if "154" in _rate_boxes(*quarter))


def test_some_supported_quarter_prints_the_transitional_rate_box() -> None:
    assert _quarters_with_transitional_rate()


@pytest.mark.parametrize(("year", "period"), _quarters_with_transitional_rate())
def test_the_transitional_rate_box_shows_its_rate_as_a_percentage(year: int, period: str) -> None:
    shown = field_value_text(_calculated("154", Decimal("5.00"), _rate_boxes(year, period)["154"]), _EN)

    # The form words a figure without the zeros that end its fraction.
    assert shown == format_casilla_value(
        Decimal(5), data_type="ratio", language=_EN, ratio_unit=ModeloEditRatioUnit.PERCENT
    )
    assert shown is not None and "%" in shown and "500" not in shown


def test_a_rate_box_with_no_declared_scale_shows_no_figure() -> None:
    assert field_value_text(_calculated("154", Decimal("5.00"), None), _EN) is None
