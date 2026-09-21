"""Independent checks for the shared INCOME-01 fixture and oracle."""

from __future__ import annotations

from decimal import Decimal

from ..scenario import AcceptanceOutcome, AcceptanceReceipt, HistoryState, build_scenario, expected_history_state


def test_invoice_decomposition_and_bank_amounts_are_coherent() -> None:
    scenario = build_scenario(2025)

    assert [item.taxable_base for item in scenario.income] == [
        Decimal("4000"), Decimal("3500"), Decimal("2000"), Decimal("2500")
    ]
    assert [item.net_receipt for item in scenario.income] == [
        Decimal("4560.00"), Decimal("3990.00"), Decimal("2280.00"), Decimal("2850.00")
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
        Decimal("320.00"), Decimal("215.00"), Decimal("100.00"), Decimal("45.00")
    ]
    assert [row.partial_result for row in scenario.quarter_oracle] == [
        Decimal("420.00"), Decimal("315.00"), Decimal("200.00"), Decimal("145.00")
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
    assert HistoryState.RECORDED_ZERO.value != HistoryState.MISSING.value


def test_receipt_is_machine_readable_and_keeps_blocked_distinct() -> None:
    receipt = AcceptanceReceipt(
        brief_revision="0.4",
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
