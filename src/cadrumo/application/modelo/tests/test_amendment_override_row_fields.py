"""An amendment override never replaces a casilla that detail rows carry."""

from __future__ import annotations

from decimal import Decimal

import pytest

from ....core.authority_grade import RegistryAuthorityGrade
from ....core.period import Period
from ....domain.calculations.registry.casilla_membership import row_field_template_records_by_casilla
from ....domain.calculations.registry.tests.published_authority import published_snapshot
from .._registry_helpers import reject_unknown_override_casillas
from ..action_errors import AmendmentOverrideCasillaError

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PERIOD = Period.from_year_and_code(2024, "0A")
_ROW_FIELD = "perc.base"
_SCALAR = "decl.total-perceptores"


def test_an_override_of_a_row_field_casilla_is_refused_naming_its_records() -> None:
    """Modelo 180's perceptor base is filled once per perceptor row, so no single override replaces it."""
    revision = published_snapshot(
        "180", filing_year=2024, period="0A", grade=RegistryAuthorityGrade.CALCULATION
    ).revision
    records = row_field_template_records_by_casilla(revision)[_ROW_FIELD]

    with pytest.raises(AmendmentOverrideCasillaError) as refusal:
        reject_unknown_override_casillas(
            modelo="180",
            filing_year=2024,
            period=_PERIOD,
            overrides={_ROW_FIELD: Decimal("100.00"), _SCALAR: Decimal("1")},
        )

    assert refusal.value.translated_message == "errors.calc.row_field_template_supplied_as_input"
    assert refusal.value.context == {"casilla_ids": _ROW_FIELD, "record_ids": ",".join(records)}


def test_an_override_of_a_scalar_casilla_is_accepted() -> None:
    """Detector teeth: the refusal keys on row fields, not on every Modelo 180 override."""
    accepted = reject_unknown_override_casillas(
        modelo="180",
        filing_year=2024,
        period=_PERIOD,
        overrides={_SCALAR: Decimal("1")},
    )

    assert {str(casilla_id) for casilla_id in accepted} == {_SCALAR}
