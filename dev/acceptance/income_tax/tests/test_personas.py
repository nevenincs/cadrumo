"""The persona oracles equal the figures worked by hand from the law and the forms' instructions."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from ..personas import build_autonomo_oracle, build_employee_oracle, build_payer_side, simplified_quarters
from ..scenario import ExpenseInvoice, IssuedInvoice

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_YEAR = 2025


def test_the_employee_credit_is_each_certificates_retencion_plus_its_full_ingreso_a_cuenta() -> None:
    oracle = build_employee_oracle()

    # oracle: Ley 35/2006 arts. 79.e and 99.6: 3.120,00 + (600,00 + 200,00 passed on in full).
    assert [item.pago_a_cuenta for item in oracle.certificates] == [Decimal("3120.00"), Decimal("800.00")]
    assert oracle.work_credit == Decimal("3920.00")
    # oracle: the cash pay of both employers, 24.000,00 + 6.000,00.
    assert dict(oracle.salary_casillas)["0003"] == Decimal("30000.00")


def test_the_autonomo_withholding_follows_the_15_and_7_percent_invoices() -> None:
    oracle = build_autonomo_oracle(_YEAR)

    # oracle: Reglamento del IRPF art. 95.1: 600 + 525 at 15 %, 140 + 175 at 7 %.
    assert [item.withholding for item in oracle.income] == [
        Decimal("600.00"),
        Decimal("525.00"),
        Decimal("140.00"),
        Decimal("175.00"),
    ]
    assert oracle.activity_withholding == Decimal("1440.00")


def test_the_simplified_quarters_include_the_five_percent_of_dificil_justificacion() -> None:
    quarters = build_autonomo_oracle(_YEAR).quarters

    # oracle: Modelo 130 instructions, casilla 02, with Reglamento art. 30.2.4a: 5 % of 3.500 / 6.300 / 8.000 / 9.600.
    assert [item.difficult_justification for item in quarters] == [
        Decimal("175.00"),
        Decimal("315.00"),
        Decimal("400.00"),
        Decimal("480.00"),
    ]
    # oracle: 20 % of 3.325 less 600; of 5.985 less 65 and 1.125; of 7.600 less 72 and 1.265;
    # of 9.120 less 255 and 1.440.
    assert [item.result for item in quarters] == [
        Decimal("65.00"),
        Decimal("7.00"),
        Decimal("183.00"),
        Decimal("129.00"),
    ]


def test_the_2023_simplified_quarters_take_seven_percent_of_dificil_justificacion() -> None:
    quarters = build_autonomo_oracle(2023).quarters

    # oracle: Ley 35/2006 disposicion adicional quincuagesima sexta: 7 % of 3.500 / 6.300 / 8.000 / 9.600.
    assert [item.difficult_justification for item in quarters] == [
        Decimal("245.00"),
        Decimal("441.00"),
        Decimal("560.00"),
        Decimal("672.00"),
    ]
    # oracle: 20 % of 3.255 less 600; of 5.859 less 51 and 1.125; of 7.440 less 51 and 1.265 (the negative
    # second quarter adds nothing to the earlier payments); of 8.928 less 223 and 1.440.
    assert [item.result for item in quarters] == [
        Decimal("51.00"),
        Decimal("-4.20"),
        Decimal("172.00"),
        Decimal("122.60"),
    ]


def test_the_autonomo_annual_credits_total_the_work_activity_and_fractional_payments() -> None:
    oracle = build_autonomo_oracle(_YEAR)

    # oracle: 20 % of 9.120,00 less the year's 1.440,00 withholding.
    assert oracle.pagos_fraccionados == Decimal("384.00")
    # oracle: 12.000 - 2.400 - 5 % of 9.600.
    assert oracle.activity_net_income == Decimal("9120.00")
    # oracle: Ley 35/2006 art. 99.1: 3.000 + 1.440 + 384.
    assert oracle.total_pagos_a_cuenta == Decimal("4824.00")


def test_the_dificil_justificacion_provision_stops_at_two_thousand_euros() -> None:
    income = (
        IssuedInvoice(
            period="1T",
            invoice_id="cap",
            transaction_id="cap",
            invoice_date=date(_YEAR, 2, 1),
            transaction_date=date(_YEAR, 2, 1),
            taxable_base=Decimal("100000"),
            iva_rate=Decimal("0.21"),
            withholding_rate=Decimal("0"),
        ),
    ) * 4
    expenses = (
        ExpenseInvoice(
            period="1T",
            invoice_id="cap",
            transaction_id="cap",
            invoice_date=date(_YEAR, 2, 1),
            transaction_date=date(_YEAR, 2, 1),
            category="material_oficina",
            taxable_base=Decimal("0"),
        ),
    ) * 4

    # oracle: Reglamento del IRPF art. 30.2.4a: 5 % of 100.000,00 is 5.000,00, capped at 2.000,00 a year.
    assert simplified_quarters(income, expenses, year=_YEAR)[0].difficult_justification == Decimal("2000.00")


def test_the_payer_side_retention_is_the_freelancers_credit_not_the_payers() -> None:
    fee = build_payer_side(_YEAR)

    # oracle: Reglamento del IRPF art. 101.5: 15 % of a 1.000,00 professional fee.
    assert fee.retention == Decimal("150.00")
