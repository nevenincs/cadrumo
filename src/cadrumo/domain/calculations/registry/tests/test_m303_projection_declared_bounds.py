"""Each 303 projection output refuses a row past what the registry declares."""

from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import ValidationError

from .....core.prorrata_register import ProrrataRegisterRegime
from ..form_codes import resolve_form_codes_leased
from ..m303_differentiated_deduction_projection import M303DifferentiatedDeductionRowProjection
from ..m303_prorrata_activity_projection import M303ProrrataActivityRowProjection
from ..m303_regimen_simplificado_projection import M303RegimenSimplificadoRecordProjection

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _declared(key: str) -> int:
    return int(resolve_form_codes_leased("form-row-codes").code(key))


def test_a_differentiated_row_past_the_declared_slots_is_refused() -> None:
    with pytest.raises(ValidationError, match="past the form's declared rows"):
        M303DifferentiatedDeductionRowProjection(
            slot=_declared("m303.differentiated.row_slots") + 1,
            sector_id="sector",
            regime=next(iter(ProrrataRegisterRegime)),
            percentage=Decimal(50),
            endpoints=(),
        )


def test_a_differentiated_row_short_of_its_endpoints_is_refused() -> None:
    with pytest.raises(ValidationError, match="one endpoint per declared field"):
        M303DifferentiatedDeductionRowProjection(
            slot=1,
            sector_id="sector",
            regime=next(iter(ProrrataRegisterRegime)),
            percentage=Decimal(50),
            endpoints=(),
        )


def test_a_prorrata_row_past_the_declared_slots_is_refused() -> None:
    with pytest.raises(ValidationError, match="past the form's declared rows"):
        M303ProrrataActivityRowProjection(slot=_declared("m303.prorrata.activity_slots") + 1, endpoints=())


def test_a_prorrata_row_short_of_its_endpoints_is_refused() -> None:
    with pytest.raises(ValidationError, match="one endpoint per declared field"):
        M303ProrrataActivityRowProjection(slot=1, endpoints=())


def test_a_simplified_regime_record_past_the_declared_pages_is_refused() -> None:
    with pytest.raises(ValidationError, match="past the form's declared pages"):
        M303RegimenSimplificadoRecordProjection(record=_declared("m303.dp30302.records") + 1, fields=())
