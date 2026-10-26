"""Contract tests for operator-attested period token parsing."""

from __future__ import annotations

import pytest

from ....core.period import Period
from ..attested_period_tokens import parse_attested_period_keys
from ..m111_no_retenciones import m111_no_retenciones_periods_from_profile_values
from ..m115_no_relevant_payments import m115_no_relevant_payment_periods_from_profile_values

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_tokens_are_split_on_commas_semicolons_and_whitespace_and_uppercased() -> None:
    assert parse_attested_period_keys("2026:1t, 2026:2T;2026:12 2025:4T") == {
        (2026, "1T"),
        (2026, "2T"),
        (2026, "12"),
        (2025, "4T"),
    }


@pytest.mark.parametrize("raw", [None, "", "   ", "2026", "2026:", "abcd:1T", "2026:13", "2026:Q1", "26:1T"])
def test_absent_or_malformed_text_attests_nothing(raw: str | None) -> None:
    assert parse_attested_period_keys(raw) == frozenset()


def test_one_malformed_token_does_not_discard_its_valid_neighbours() -> None:
    assert parse_attested_period_keys("2026:1T, nonsense, 2026:2T") == {(2026, "1T"), (2026, "2T")}


def test_predicate_refuses_periods_it_does_not_accept() -> None:
    def quarterly(period: Period) -> bool:
        return period.registry_token.endswith("T")

    assert parse_attested_period_keys("2026:1T 2026:12", accepts=quarterly) == {(2026, "1T")}


def test_modelo_111_attests_monthly_and_quarterly_periods() -> None:
    values = {"withholding.modelo_111_no_retenciones_periods": "2026:1T 2026:12"}

    assert m111_no_retenciones_periods_from_profile_values(values) == {(2026, "1T"), (2026, "12")}


def test_modelo_115_attests_only_quarterly_periods() -> None:
    values = {"withholding.modelo_115_no_relevant_payment_periods": "2026:1T 2026:12"}

    assert m115_no_relevant_payment_periods_from_profile_values(values) == {(2026, "1T")}


def test_missing_profile_projection_attests_nothing() -> None:
    assert m111_no_retenciones_periods_from_profile_values(None) == frozenset()
    assert m115_no_relevant_payment_periods_from_profile_values({}) == frozenset()
