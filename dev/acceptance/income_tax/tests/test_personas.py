"""The persona oracles equal the figures worked by hand from the law and the forms' instructions."""

from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from importlib.resources import files

import pytest

from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation

from ..personas import (
    autonomo_oracle,
    build_employee_oracle,
    build_payer_side,
    payer_oracle,
    simplified_difficult_justification_rate,
    simplified_quarters,
    stated_difficult_justification_rate,
)
from ..scenario import ExpenseInvoice, IssuedInvoice

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_FIVE_PERCENT = Decimal("0.05")
_SEVEN_PERCENT = Decimal("0.07")


@pytest.fixture
def year(operation: PinnedAuthorityOperation) -> int:
    """Any supported filing year: the arithmetic below depends on the rate it is given, not on the year."""
    return operation.supported_filing_years().floor


def test_the_employee_credit_is_each_certificates_retencion_plus_its_full_ingreso_a_cuenta() -> None:
    oracle = build_employee_oracle()

    # oracle: Ley 35/2006 arts. 79.e and 99.6: 3.120,00 + (600,00 + 200,00 passed on in full).
    assert [item.pago_a_cuenta for item in oracle.certificates] == [Decimal("3120.00"), Decimal("800.00")]
    assert oracle.work_credit == Decimal("3920.00")
    # oracle: the cash pay of both employers, 24.000,00 + 6.000,00.
    assert dict(oracle.salary_casillas)["0003"] == Decimal("30000.00")


def test_the_autonomo_withholding_follows_the_15_and_7_percent_invoices(year: int) -> None:
    oracle = autonomo_oracle(year, rate=_FIVE_PERCENT)

    # oracle: Reglamento del IRPF art. 95.1: 600 + 525 at 15 %, 140 + 175 at 7 %.
    assert [item.withholding for item in oracle.income] == [
        Decimal("600.00"),
        Decimal("525.00"),
        Decimal("140.00"),
        Decimal("175.00"),
    ]
    assert oracle.activity_withholding == Decimal("1440.00")


def test_the_simplified_quarters_include_the_five_percent_of_dificil_justificacion(year: int) -> None:
    quarters = autonomo_oracle(year, rate=_FIVE_PERCENT).quarters

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


def test_a_seven_percent_year_takes_seven_percent_of_dificil_justificacion(year: int) -> None:
    quarters = autonomo_oracle(year, rate=_SEVEN_PERCENT).quarters

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


def test_the_autonomo_annual_credits_total_the_work_activity_and_fractional_payments(year: int) -> None:
    oracle = autonomo_oracle(year, rate=_FIVE_PERCENT)

    # oracle: 20 % of 9.120,00 less the year's 1.440,00 withholding.
    assert oracle.pagos_fraccionados == Decimal("384.00")
    # oracle: 12.000 - 2.400 - 5 % of 9.600.
    assert oracle.activity_net_income == Decimal("9120.00")
    # oracle: Ley 35/2006 art. 99.1: 3.000 + 1.440 + 384.
    assert oracle.total_pagos_a_cuenta == Decimal("4824.00")


def test_the_payers_fee_is_an_activity_expense_of_the_annual_yield_only(year: int) -> None:
    autonomo = autonomo_oracle(year, rate=_FIVE_PERCENT)
    payer = payer_oracle(year, rate=_FIVE_PERCENT)

    # oracle: Ley 35/2006 art. 28.1 with Ley 27/2014 art. 10.3: the 1.000,00 fee is an expense, so
    # 12.000 - 2.400 - 1.000 = 8.600, less 5 % of 8.600 (430,00).
    assert payer.activity_net_income == Decimal("8170.00")
    # oracle: the four 130s were filed before the fee was booked, so they and the credits stand as filed.
    assert payer.quarters == autonomo.quarters
    assert payer.pagos_fraccionados == autonomo.pagos_fraccionados
    assert payer.total_pagos_a_cuenta == autonomo.total_pagos_a_cuenta


def test_the_dificil_justificacion_provision_stops_at_two_thousand_euros(year: int) -> None:
    income = (
        IssuedInvoice(
            period="1T",
            invoice_id="cap",
            transaction_id="cap",
            invoice_date=date(year, 2, 1),
            transaction_date=date(year, 2, 1),
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
            invoice_date=date(year, 2, 1),
            transaction_date=date(year, 2, 1),
            category="material_oficina",
            taxable_base=Decimal("0"),
        ),
    ) * 4

    # oracle: Reglamento del IRPF art. 30.2.4a: 5 % of 100.000,00 is 5.000,00, capped at 2.000,00 a year.
    assert simplified_quarters(income, expenses, rate=_FIVE_PERCENT)[0].difficult_justification == Decimal("2000.00")


def test_the_manual_percentage_is_the_one_its_simplified_modality_sentence_states() -> None:
    sentence = (
        "los gastos de dificil justificacion se cuantificaran exclusivamente aplicando el porcentaje del {} por 100"
    )

    assert stated_difficult_justification_rate(f"... {sentence.format(7)} sobre el rendimiento neto") == _SEVEN_PERCENT
    assert stated_difficult_justification_rate(f"{sentence.format(5)}. {sentence.format(5)}") == _FIVE_PERCENT
    with pytest.raises(LookupError):
        stated_difficult_justification_rate(f"{sentence.format(5)}. {sentence.format(7)}")
    with pytest.raises(LookupError):
        stated_difficult_justification_rate("el porcentaje del 5 por 100 en concepto de provisiones deducibles")


def test_every_supported_year_with_a_bundled_manual_states_one_percentage(operation: PinnedAuthorityOperation) -> None:
    manuals = files("cadrumo").joinpath("_data", "manual_corpus_text", "manuals", "renta")
    years = [
        year
        for year in operation.supported_filing_years().years
        if manuals.joinpath(str(year), "part1", "source.pdf.corpus_text.json").is_file()
    ]

    assert years
    stated_from = "se cuantificaran exclusivamente aplicando el porcentaje del "
    for year in years:
        manual = manuals.joinpath(str(year), "part1", "source.pdf.corpus_text.json")
        text = json.loads(manual.read_text(encoding="utf-8"))["normalised_text"]
        # oracle: the figure the manual prints after its art. 30.2.4a sentence, "del N por 100".
        figure, unit, base = text[text.index(stated_from) + len(stated_from) :].split(maxsplit=3)[:3]
        assert (unit, base) == ("por", "100")
        assert simplified_difficult_justification_rate(year) == Decimal(figure) / 100


def test_the_payer_side_retention_is_the_freelancers_credit_not_the_payers(year: int) -> None:
    fee = build_payer_side(year)

    # oracle: Reglamento del IRPF art. 101.5: 15 % of a 1.000,00 professional fee.
    assert fee.retention == Decimal("150.00")
