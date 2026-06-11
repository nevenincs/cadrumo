from __future__ import annotations

import pytest

from ....core import Period
from .. import ModeloWorkPeriodTokenError, modelo_work_address_from_operator_target

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


@pytest.mark.parametrize(
    ("raw_period", "expected_period"),
    (
        ("1T", "1T"),
        ("0A", "0A"),
        ("03", "03"),
    ),
)
def test_operator_target_resolves_periods_through_core_period(
    raw_period: str,
    expected_period: str,
) -> None:
    address = modelo_work_address_from_operator_target(
        work_unit_id=None,
        modelo="303",
        year=2026,
        period=raw_period,
        registry_revision_id=None,
    )

    assert address.period == Period.from_year_and_code(2026, expected_period)
    assert address.filing_year == 2026


@pytest.mark.parametrize("raw_period", ("q1", "1", "anual", "annual", "2026", "2026Q1", "2026-03", "M03", "00", "13"))
def test_operator_target_rejects_legacy_aliases_combined_or_unknown_tokens(raw_period: str) -> None:
    with pytest.raises(ModeloWorkPeriodTokenError) as exc_info:
        modelo_work_address_from_operator_target(
            work_unit_id=None,
            modelo="130",
            year=2026,
            period=raw_period,
            registry_revision_id=None,
        )

    assert exc_info.value.context["token"] == raw_period
    assert "1T" in exc_info.value.context["tokens"]


def test_operator_target_rejects_period_year_mismatch() -> None:
    with pytest.raises(ModeloWorkPeriodTokenError) as exc_info:
        modelo_work_address_from_operator_target(
            work_unit_id=None,
            modelo="130",
            year=2025,
            period=Period.from_year_and_code(2026, "1T"),
            registry_revision_id=None,
        )

    assert exc_info.value.context["year"] == 2025
