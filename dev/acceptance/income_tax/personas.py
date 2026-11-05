"""Independent synthetic inputs and hand arithmetic for the employee, employee-autonomo and payer personas.

Every expected figure here is worked from a rule of the Spanish tax law or of the official forms'
instructions, never read from a run of the product:

* A payer's certificate is the evidence of a retention (Reglamento del IRPF, art. 108.3), and the credit
  of a work, capital or gain class is the retencion plus the ingreso a cuenta in full, whether or not the
  payer passed the ingreso a cuenta on to the taxpayer (Ley 35/2006, arts. 79.e and 99.6).
* An activity invoice's withholding is credited to the ejercicio the criterion imputes the income to
  (Ley 35/2006, art. 99.1; Reglamento, arts. 7 and 110.3.a).
* Each Modelo 130 quarter is 20 % of the cumulative net income, less the earlier quarters' positive results
  and the cumulative retention (Reglamento, art. 110.3.a). Under the simplified modality the instructions of
  casilla 02 add the gastos de dificil justificacion of Reglamento art. 30.2.4a, the percentage the year's
  official Renta manual states of the net income before them, capped at 2.000,00 a year.
* A fee paid to an independent professional for the activity is a deductible expense of it, at its base
  without the deductible IVA and before the retention practised on it (Ley 35/2006, art. 28.1, which takes
  the net income from the Impuesto sobre Sociedades rules, Ley 27/2014, art. 10.3).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, replace
from datetime import date
from decimal import Decimal
from importlib.resources import files
from typing import Final

from .scenario import CENT, PERIODS, ExpenseInvoice, IssuedInvoice, money

SIMPLIFIED_DIFFICULT_JUSTIFICATION_CAP = Decimal("2000.00")
# The manual's own sentence under "Modalidad simplificada", which states the year's percentage in every edition.
_DIFFICULT_JUSTIFICATION_SENTENCE: Final[re.Pattern[str]] = re.compile(
    r"gastos de dificil justificacion se cuantificaran exclusivamente aplicando el porcentaje del (\d+) por 100"
)
PAGO_FRACCIONADO_RATE = Decimal("0.20")

#: Synthetic CIFs whose control digit is hand-derived (digits zero but the last: 8 for 1, 6 for 2).
EMPLOYER_A = "B00000018"
EMPLOYER_B = "B00000299"
FREELANCER = "B12345674"

#: Casilla inputs naming the declarant as holder of the work and activity blocks, and the activity key.
WORK_HOLDER_INPUT = "0001=declarante"
ACTIVITY_HOLDER_INPUT = "0165=declarante"
ACTIVITY_KEY_INPUT = "0166=A05"


@dataclass(frozen=True, slots=True)
class EmployerCertificate:
    """One employer's certificate of the pay and the withholding it practised."""

    payer_tax_id: str
    importe_integro: Decimal
    retencion: Decimal
    ingreso_a_cuenta: Decimal = Decimal("0.00")
    ingreso_a_cuenta_repercutido: Decimal = Decimal("0.00")
    valoracion_especie: Decimal = Decimal("0.00")

    @property
    def pago_a_cuenta(self) -> Decimal:
        """The credit of the certificate: retencion plus the full ingreso a cuenta."""
        return self.retencion + self.ingreso_a_cuenta


@dataclass(frozen=True, slots=True)
class EmployeeOracle:
    """The employee's certificates and the credits they must produce."""

    certificates: tuple[EmployerCertificate, ...]
    salary_casillas: tuple[tuple[str, Decimal], ...]
    work_credit: Decimal


def build_employee_oracle() -> EmployeeOracle:
    """Two employers, the second paying part of the pay in kind with a passed-on ingreso a cuenta.

    Employer A withheld 3.120,00 on 24.000,00. Employer B withheld 600,00 and made a 200,00 ingreso a cuenta
    on a 1.000,00 valuation, passed on in full. The credit is 3.120,00 + 600,00 + 200,00 = 3.920,00.
    """
    certificates = (
        EmployerCertificate(EMPLOYER_A, importe_integro=Decimal("24000.00"), retencion=Decimal("3120.00")),
        EmployerCertificate(
            EMPLOYER_B,
            importe_integro=Decimal("6000.00"),
            retencion=Decimal("600.00"),
            ingreso_a_cuenta=Decimal("200.00"),
            ingreso_a_cuenta_repercutido=Decimal("200.00"),
            valoracion_especie=Decimal("1000.00"),
        ),
    )
    return EmployeeOracle(
        certificates=certificates,
        salary_casillas=(
            ("0003", sum((item.importe_integro for item in certificates), Decimal())),
            ("0004", Decimal("1000.00")),
            ("0005", Decimal("200.00")),
            ("0006", Decimal("200.00")),
        ),
        work_credit=sum((item.pago_a_cuenta for item in certificates), Decimal()),
    )


@dataclass(frozen=True, slots=True)
class SimplifiedQuarter:
    """One Modelo 130 quarter worked by hand under the simplified modality."""

    period: str
    cumulative_income: Decimal
    cumulative_expenses: Decimal
    difficult_justification: Decimal
    cumulative_withholding: Decimal
    prior_positive_results: Decimal
    result: Decimal

    @property
    def casilla_02(self) -> Decimal:
        """Casilla 02: the expenses plus the gastos de dificil justificacion the simplified modality adds."""
        return self.cumulative_expenses + self.difficult_justification


@dataclass(frozen=True, slots=True)
class AutonomoOracle:
    """The employee-autonomo's ledger, certificate and the credits they must produce."""

    year: int
    income: tuple[IssuedInvoice, ...]
    expenses: tuple[ExpenseInvoice, ...]
    employer: EmployerCertificate
    quarters: tuple[SimplifiedQuarter, ...]
    activity_net_income: Decimal
    activity_withholding: Decimal
    pagos_fraccionados: Decimal
    total_pagos_a_cuenta: Decimal


def stated_difficult_justification_rate(manual_text: str) -> Decimal:
    """The art. 30.2.4a percentage a Renta manual states, refusing a manual that states none or several."""
    stated = set(_DIFFICULT_JUSTIFICATION_SENTENCE.findall(manual_text))
    if len(stated) != 1:
        raise LookupError(f"the manual states {sorted(stated)} as the dificil justificacion percentage")
    return Decimal(stated.pop()) / 100


def simplified_difficult_justification_rate(year: int) -> Decimal:
    """The art. 30.2.4a percentage of ``year``, read from that year's official Renta manual.

    The percentage is the law's, not the product's: it comes from the AEAT manual's text for the periodo
    impositivo, never from the registry the calculation reads. A year whose manual is not bundled has no
    grounded expectation and is refused.
    """
    manual = files("cadrumo").joinpath(
        "_data", "manual_corpus_text", "manuals", "renta", str(year), "part1", "source.pdf.corpus_text.json"
    )
    if not manual.is_file():
        raise LookupError(f"no official Renta manual is bundled for the periodo impositivo {year}")
    return stated_difficult_justification_rate(json.loads(manual.read_text(encoding="utf-8"))["normalised_text"])


def simplified_quarters(
    income: tuple[IssuedInvoice, ...], expenses: tuple[ExpenseInvoice, ...], *, rate: Decimal
) -> tuple[SimplifiedQuarter, ...]:
    """Work the four cumulative quarters of a simplified-modality taxpayer at the year's art. 30.2.4a ``rate``."""
    rows: list[SimplifiedQuarter] = []
    prior = Decimal()
    for index, period in enumerate(PERIODS, start=1):
        gained = sum((item.taxable_base for item in income[:index]), Decimal())
        spent = sum((item.taxable_base for item in expenses[:index]), Decimal())
        difficult = money(
            min(
                max((gained - spent) * rate, Decimal()),
                SIMPLIFIED_DIFFICULT_JUSTIFICATION_CAP,
            )
        )
        withheld = sum((item.withholding for item in income[:index]), Decimal())
        net = gained - spent - difficult
        result = money(net * PAGO_FRACCIONADO_RATE) - prior - withheld
        rows.append(
            SimplifiedQuarter(
                period=period,
                cumulative_income=gained,
                cumulative_expenses=spent,
                difficult_justification=difficult,
                cumulative_withholding=withheld,
                prior_positive_results=prior,
                result=result,
            )
        )
        prior += max(result, Decimal())
    return tuple(rows)


def build_autonomo_oracle(year: int) -> AutonomoOracle:
    """Build the employee-autonomo of ``year`` at the percentage that year's official manual states."""
    return autonomo_oracle(year, rate=simplified_difficult_justification_rate(year))


def autonomo_oracle(year: int, *, rate: Decimal) -> AutonomoOracle:
    """Build the employee-autonomo of the persona: 15 % and 7 % invoices, four expenses and one employer.

    Invoices (Reglamento art. 95.1): 4.000,00 and 3.500,00 at 15 %, 2.000,00 and 2.500,00 at 7 %, so the
    withholding is 600,00 + 525,00 + 140,00 + 175,00 = 1.440,00. Expenses are 500,00, 700,00, 300,00 and
    900,00. The employer certifies 3.000,00 on 24.000,00 of pay.

    Hand-worked simplified quarters at a 5 % manual percentage (income, expenses, the percentage of the
    difference, cumulative retention); a year whose manual states another percentage applies it instead:

        1T  4.000  500  175  600  -> 20 % of 3.325 = 665   - 0   - 600   =  65
        2T  7.500 1.200 315 1.125  -> 20 % of 5.985 = 1.197 - 65  - 1.125 =   7
        3T  9.500 1.500 400 1.265  -> 20 % of 7.600 = 1.520 - 72  - 1.265 = 183
        4T 12.000 2.400 480 1.440  -> 20 % of 9.120 = 1.824 - 255 - 1.440 = 129

    so the annual casilla 0604 is 384,00 = 1.824,00 - 1.440,00, the net income of casilla 0224 is
    12.000 - 2.400 - 480 = 9.120,00 and the total pagos a cuenta 3.000 + 1.440 + 384 = 4.824,00.
    """
    rates = (Decimal("0.15"), Decimal("0.15"), Decimal("0.07"), Decimal("0.07"))
    bases = (Decimal("4000"), Decimal("3500"), Decimal("2000"), Decimal("2500"))
    months = (2, 5, 8, 11)
    income = tuple(
        IssuedInvoice(
            period=period,
            invoice_id=f"persona-{year}-{period}",
            transaction_id=f"bank-persona-{year}-{period}",
            invoice_date=date(year, month, 15),
            transaction_date=date(year, month, 20),
            taxable_base=base,
            iva_rate=Decimal("0.21"),
            withholding_rate=rate,
        )
        for period, base, month, rate in zip(PERIODS, bases, months, rates, strict=True)
    )
    spent = tuple(
        ExpenseInvoice(
            period=period,
            invoice_id=f"persona-expense-{year}-{period}",
            transaction_id=f"bank-persona-expense-{year}-{period}",
            invoice_date=date(year, month, 22),
            transaction_date=date(year, month, 25),
            category=category,
            taxable_base=base,
        )
        for period, base, month, category in zip(
            PERIODS,
            (Decimal("500"), Decimal("700"), Decimal("300"), Decimal("900")),
            months,
            ("material_oficina", "software_suscripcion", "formacion_profesional", "asesoria_fiscal"),
            strict=True,
        )
    )
    quarters = simplified_quarters(income, spent, rate=rate)
    employer = EmployerCertificate(EMPLOYER_A, importe_integro=Decimal("24000.00"), retencion=Decimal("3000.00"))
    withholding = sum((item.withholding for item in income), Decimal())
    payments = sum((max(item.result, Decimal()) for item in quarters), Decimal())
    last = quarters[-1]
    return AutonomoOracle(
        year=year,
        income=income,
        expenses=spent,
        employer=employer,
        quarters=quarters,
        activity_net_income=last.cumulative_income - last.cumulative_expenses - last.difficult_justification,
        activity_withholding=withholding,
        pagos_fraccionados=payments,
        total_pagos_a_cuenta=employer.pago_a_cuenta + withholding + payments,
    )


@dataclass(frozen=True, slots=True)
class PayerSideRetention:
    """One withholding the persona practised as a payer, which is another taxpayer's credit."""

    modelo: str
    period: str
    base: Decimal
    rate: Decimal

    @property
    def retention(self) -> Decimal:
        """The withholding: the rate on the base, to the cent."""
        return (self.base * self.rate).quantize(CENT)


def build_payer_side(year: int) -> PayerSideRetention:
    """The first-quarter professional fee the persona pays a freelancer: 1.000,00 at 15 %, 150,00 withheld."""
    del year
    return PayerSideRetention(modelo="111", period="1T", base=Decimal("1000.00"), rate=Decimal("0.15"))


def build_payer_oracle(year: int) -> AutonomoOracle:
    """Build the payer of ``year`` at the percentage that year's official manual states."""
    return payer_oracle(year, rate=simplified_difficult_justification_rate(year))


def payer_oracle(year: int, *, rate: Decimal) -> AutonomoOracle:
    """The employee-autonomo who also paid the freelancer's fee, booked after the four 130s were filed.

    The fee is an expense of the activity at its 1.000,00 base (Ley 35/2006, art. 28.1; Ley 27/2014,
    art. 10.3): the 150,00 retention is part of what the persona owes the freelancer, and the IVA is
    deductible, so neither changes the expense. The filed 130s stand as filed, so the quarters, the 0604
    pagos fraccionados and the credits are the employee-autonomo's; only the annual yield takes the fee.
    At a 5 % manual percentage the annual chain is:

        income 12.000 - expenses 2.400 - fee 1.000 = 8.600; 5 % of 8.600 = 430; 8.600 - 430 = 8.170,00
    """
    oracle = autonomo_oracle(year, rate=rate)
    fee = build_payer_side(year)
    income = sum((item.taxable_base for item in oracle.income), Decimal())
    expenses = sum((item.taxable_base for item in oracle.expenses), Decimal()) + fee.base
    difficult = money(
        min(
            max((income - expenses) * rate, Decimal()),
            SIMPLIFIED_DIFFICULT_JUSTIFICATION_CAP,
        )
    )
    return replace(oracle, activity_net_income=income - expenses - difficult)
