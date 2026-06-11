from __future__ import annotations

import pytest

from ....core import Period
from .. import ModeloWorkPeriodTokenError, normalize_modelo_work_period

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


@pytest.mark.parametrize(
    ("raw_period", "expected_period"),
    (
        ("q1", "1T"),
        ("1", "1T"),
        ("anual", "0A"),
        ("03", "03"),
    ),
)
def test_normalize_modelo_work_period_returns_bare_registry_tokens(
    raw_period: str,
    expected_period: str,
) -> None:
    period = normalize_modelo_work_period(2026, raw_period)

    assert period == Period.from_year_and_code(2026, expected_period)


@pytest.mark.parametrize("raw_period", ("2026", "2026Q1", "2026-03", "M03", "00", "13", "alta"))
def test_normalize_modelo_work_period_rejects_combined_or_unknown_tokens(raw_period: str) -> None:
    with pytest.raises(ModeloWorkPeriodTokenError) as exc_info:
        normalize_modelo_work_period(2026, raw_period, modelo="130")

    assert exc_info.value.context["token"] == raw_period
    assert "1T" in exc_info.value.context["tokens"]


def test_normalize_modelo_work_period_rejects_non_yyyy_year() -> None:
    with pytest.raises(ModeloWorkPeriodTokenError) as exc_info:
        normalize_modelo_work_period(26, "q1", modelo="130")

    assert exc_info.value.context["year"] == 26
