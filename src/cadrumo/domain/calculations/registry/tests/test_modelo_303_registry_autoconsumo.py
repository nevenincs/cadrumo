"""Tests for Modelo 303 autoconsumo calculations and record-design authorities."""

from __future__ import annotations

import pytest

from . import modelo_303_registry_autoconsumo_scenarios as scenarios
from ._modelo_303_registry_support import load_modelo_303

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


@pytest.mark.parametrize("row", sorted(scenarios.RATE_ROWS))
def test_the_promotor_autoconsumo_is_declared_in_the_row_of_its_rate_in_every_edition(row: str) -> None:
    scenarios.check_the_promotor_autoconsumo_is_declared_in_the_row_of_its_rate_in_every_edition(load_modelo_303, row)


def test_the_rate_row_cuota_is_proportional_to_the_base_it_is_given() -> None:
    scenarios.check_the_rate_row_cuota_is_proportional_to_the_base_it_is_given(load_modelo_303)


def test_every_edition_refuses_a_profile_base_the_rate_rows_do_not_account_for() -> None:
    scenarios.check_every_edition_refuses_a_profile_base_the_rate_rows_do_not_account_for(load_modelo_303)


def test_modelo_303_workbook_parity_ref_anchors_record_design_layout() -> None:
    scenarios.check_modelo_303_workbook_parity_ref_anchors_record_design_layout(load_modelo_303)


def test_modelo_303_four_digit_cnae_width_has_a_distinct_authority_role() -> None:
    scenarios.check_modelo_303_four_digit_cnae_width_has_a_distinct_authority_role(load_modelo_303)


@pytest.mark.parametrize("period", ["01", "1T"])
def test_early_2026_112_zero_preserves_prior_result_and_nonzero_is_refused(period: str) -> None:
    scenarios.check_early_2026_112_zero_preserves_prior_result_and_nonzero_is_refused(load_modelo_303, period)


@pytest.mark.parametrize("period", ["02", "2T"])
def test_later_2026_112_payment_deduction_uses_current_result_formula(period: str) -> None:
    scenarios.check_later_2026_112_payment_deduction_uses_current_result_formula(load_modelo_303, period)


def test_historical_2025_contract_keeps_its_prior_casillas_and_result() -> None:
    scenarios.check_historical_2025_contract_keeps_its_prior_casillas_and_result(load_modelo_303)
