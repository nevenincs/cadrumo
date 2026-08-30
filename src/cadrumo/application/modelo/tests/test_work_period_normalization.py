from __future__ import annotations

import pytest

from ....core.period import Period
from ..work_addressing import ModeloWorkPeriodTokenError, modelo_work_address_from_operator_target

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_operator_target_accepts_typed_core_period() -> None:
    periods = (
        Period.from_year_and_code(2026, "1T"),
        Period.from_year_and_code(2026, "0A"),
        Period.from_year_and_code(2026, "03"),
    )

    for period in periods:
        address = modelo_work_address_from_operator_target(
            work_unit_id=None,
            modelo="303",
            year=2026,
            period=period,
            registry_revision_id=None,
        )

        assert address.period == period
        assert address.filing_year == 2026


def test_operator_target_rejects_period_year_mismatch() -> None:
    with pytest.raises(ModeloWorkPeriodTokenError) as exc_info:
        modelo_work_address_from_operator_target(
            work_unit_id=None,
            modelo="130",
            year=2025,
            period=Period.from_year_and_code(2026, "1T"),
            registry_revision_id=None,
        )

    assert exc_info.value.context is not None
    assert exc_info.value.context["year"] == 2025
