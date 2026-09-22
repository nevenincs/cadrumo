"""Independent checks for the shared INCOME-01 fixture and oracle."""

from __future__ import annotations

from decimal import Decimal

import pytest

from ..scenario import (
    AcceptanceOutcome,
    AcceptanceReceipt,
    HistoryState,
    build_boundary_control_scenario,
    build_retention_mutation_oracle,
    build_scenario,
    expected_history_state,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_invoice_decomposition_and_bank_amounts_are_coherent() -> None:
    scenario = build_scenario(2025)

    assert [item.taxable_base for item in scenario.income] == [
        Decimal("4000"),
        Decimal("3500"),
        Decimal("2000"),
        Decimal("2500"),
    ]
    assert [item.net_receipt for item in scenario.income] == [
        Decimal("4560.00"),
        Decimal("3990.00"),
        Decimal("2280.00"),
        Decimal("2850.00"),
    ]
    assert all(item.net_receipt == item.taxable_base + item.iva - item.withholding for item in scenario.income)
    assert all(item.bank_payment == item.taxable_base + item.iva for item in scenario.expenses)


def test_quarterly_oracle_is_cumulative_and_distinct() -> None:
    scenario = build_scenario(2025)

    assert [(row.cumulative_income, row.cumulative_expenses) for row in scenario.quarter_oracle] == [
        (Decimal("4000"), Decimal("500")),
        (Decimal("7500"), Decimal("1200")),
        (Decimal("9500"), Decimal("1500")),
        (Decimal("12000"), Decimal("2400")),
    ]
    assert [row.payment for row in scenario.quarter_oracle] == [
        Decimal("320.00"),
        Decimal("215.00"),
        Decimal("100.00"),
        Decimal("45.00"),
    ]
    assert [row.partial_result for row in scenario.quarter_oracle] == [
        Decimal("420.00"),
        Decimal("315.00"),
        Decimal("200.00"),
        Decimal("145.00"),
    ]
    assert {row.low_income_reduction for row in scenario.quarter_oracle} == {Decimal("100.00")}
    assert scenario.annual_oracle.activity_net_income == Decimal("9600")
    assert scenario.annual_oracle.activity_withholding == Decimal("840.00")
    assert scenario.annual_oracle.m130_payments == Decimal("680.00")


def test_year_parameterization_moves_every_control_date() -> None:
    scenario = build_scenario(2024)

    assert scenario.taxpayer.activity_start.isoformat() == "2024-01-01"
    assert {item.invoice_date.year for item in scenario.income + scenario.expenses} == {2024}
    assert scenario.out_of_year_income.invoice_date.year == 2023
    assert scenario.income_date_boundary.invoice_date.isoformat() == "2024-03-31"
    assert scenario.income_date_boundary.transaction_date.isoformat() == "2024-04-01"
    assert scenario.expense_date_boundary.invoice_date.isoformat() == "2024-03-31"
    assert scenario.expense_date_boundary.transaction_date.isoformat() == "2024-04-01"


def test_history_states_distinguish_first_period_missing_and_available() -> None:
    assert expected_history_state(year=2025, period="1T", available_periods=frozenset()) is HistoryState.NOT_APPLICABLE
    assert expected_history_state(year=2025, period="2T", available_periods=frozenset()) is HistoryState.MISSING
    assert expected_history_state(year=2025, period="2T", available_periods=frozenset({"1T"})) is HistoryState.AVAILABLE
    assert (
        expected_history_state(
            year=2025,
            period="2T",
            available_periods=frozenset({"1T"}),
            recorded_zero_periods=frozenset({"1T"}),
        )
        is HistoryState.RECORDED_ZERO
    )
    assert HistoryState.RECORDED_ZERO.value != HistoryState.MISSING.value


def test_retention_mutation_oracle_changes_the_persisted_q4_pair_without_additive_income() -> None:
    mutation = build_retention_mutation_oracle(2025)

    assert mutation.target_invoice.invoice_id == mutation.corrected_invoice.invoice_id == "income-2025-4T"
    assert mutation.target_invoice.withholding == Decimal("175.00")
    assert mutation.corrected_invoice.withholding == Decimal("0.00")
    assert mutation.target_invoice.net_receipt == Decimal("2850.00")
    assert mutation.corrected_invoice.net_receipt == Decimal("3025.00")
    assert mutation.corrected_quarter.cumulative_income == mutation.baseline_quarter.cumulative_income
    withholding_delta = (
        mutation.corrected_quarter.cumulative_withholding - mutation.baseline_quarter.cumulative_withholding
    )
    assert withholding_delta == Decimal("-175.00")
    assert mutation.corrected_quarter.payment - mutation.baseline_quarter.payment == Decimal("175.00")
    assert mutation.corrected_annual.activity_withholding == Decimal("665.00")
    assert mutation.corrected_annual.m130_payments == Decimal("855.00")


def test_boundary_control_oracle_uses_transaction_filing_dates_without_changing_baseline() -> None:
    baseline = build_scenario(2025)
    controls = build_boundary_control_scenario(2025)

    assert controls.excluded_income_ids == ("income-2024-control",)
    assert "income-2025-boundary" in controls.selected_income_ids
    assert controls.quarter_oracle[0] == baseline.quarter_oracle[0]
    assert controls.quarter_oracle[1].cumulative_income == Decimal("7611")
    assert controls.quarter_oracle[1].cumulative_expenses == Decimal("1299")
    assert controls.quarter_oracle[1].payment == Decimal("209.63")
    assert controls.annual_oracle.activity_income == Decimal("12111")
    assert controls.annual_oracle.deductible_expenses == Decimal("2499")
    assert controls.annual_oracle.activity_net_income == Decimal("9612")
    assert controls.annual_oracle.m130_payments == Decimal("674.63")
    assert baseline.annual_oracle.activity_income == Decimal("12000")
    assert baseline.annual_oracle.deductible_expenses == Decimal("2400")


def test_receipt_is_machine_readable_and_keeps_blocked_distinct() -> None:
    receipt = AcceptanceReceipt(
        brief_revision="0.6",
        scenario_id="income-directa-normal-v1:2025:cli",
        frontend_path="cli",
        year=2025,
        authority_generation="a" * 64,
        modelo_130_revision="2019-y-siguientes",
        modelo_100_revision="2025",
        acceptance_id="A9",
        outcome=AcceptanceOutcome.BLOCKED,
        source_state="export_refused",
        diagnostic_code="application.filing.export_parity.errors.aux_block_undeclared",
    )

    payload = receipt.to_dict()
    assert payload["outcome"] is AcceptanceOutcome.BLOCKED
    assert payload["diagnostic_code"] == "application.filing.export_parity.errors.aux_block_undeclared"
