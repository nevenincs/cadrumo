"""Versioned synthetic inputs and independent arithmetic for INCOME-01."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from enum import StrEnum
from typing import Literal

BRIEF_ID = "INCOME-01"
BRIEF_REVISION = "0.4"
SCENARIO_VERSION = "income-directa-normal-v1"
PERIODS = ("1T", "2T", "3T", "4T")
CENT = Decimal("0.01")
M130_RATE = Decimal("0.20")
M130_LOW_INCOME_REDUCTION = Decimal("100.00")


class AcceptanceOutcome(StrEnum):
    """Closed receipt outcome vocabulary."""

    PROVEN = "proven"
    FAILED = "failed"
    BLOCKED = "blocked"
    NOT_EXERCISED = "not_exercised"


class HistoryState(StrEnum):
    """History states that must remain distinct in acceptance evidence."""

    MISSING = "missing"
    RECORDED_ZERO = "recorded_zero"
    NOT_APPLICABLE = "not_applicable"
    AVAILABLE = "available"


@dataclass(frozen=True, slots=True)
class Taxpayer:
    """Synthetic taxpayer facts that bound every completion claim."""

    tax_id: str
    territory: str
    residence_country: str
    birth_date: date
    activity_start: date
    entity_type: str = "natural_person"
    irpf_income_category: str = "actividad_economica"
    estimation_regime: str = "directa_normal"
    marital_status: str = "single"
    descendants: int = 0
    ascendants: int = 0
    disability: bool = False


@dataclass(frozen=True, slots=True)
class IssuedInvoice:
    """One invoice and its coherently linked incoming bank transaction."""

    period: str
    invoice_id: str
    transaction_id: str
    invoice_date: date
    transaction_date: date
    taxable_base: Decimal
    iva_rate: Decimal
    withholding_rate: Decimal

    @property
    def iva(self) -> Decimal:
        return money(self.taxable_base * self.iva_rate)

    @property
    def withholding(self) -> Decimal:
        return money(self.taxable_base * self.withholding_rate)

    @property
    def net_receipt(self) -> Decimal:
        return money(self.taxable_base + self.iva - self.withholding)


@dataclass(frozen=True, slots=True)
class ExpenseInvoice:
    """One deductible expense and its linked outgoing transaction."""

    period: str
    invoice_id: str
    transaction_id: str
    invoice_date: date
    transaction_date: date
    category: str
    taxable_base: Decimal
    iva_rate: Decimal = Decimal("0.21")

    @property
    def iva(self) -> Decimal:
        return money(self.taxable_base * self.iva_rate)

    @property
    def bank_payment(self) -> Decimal:
        return money(self.taxable_base + self.iva)


@dataclass(frozen=True, slots=True)
class QuarterlyOracle:
    """Hand arithmetic for the M130 cumulative window."""

    period: str
    cumulative_income: Decimal
    cumulative_expenses: Decimal
    cumulative_net: Decimal
    twenty_percent: Decimal
    cumulative_withholding: Decimal
    prior_positive_results: Decimal
    partial_result: Decimal
    low_income_reduction: Decimal
    payment: Decimal


@dataclass(frozen=True, slots=True)
class AnnualOracle:
    """Annual activity totals and prior M130 payments, without a tax-liability oracle."""

    activity_income: Decimal
    deductible_expenses: Decimal
    activity_net_income: Decimal
    activity_withholding: Decimal
    m130_payments: Decimal


@dataclass(frozen=True, slots=True)
class IncomeTaxScenario:
    """One year-parameterized source definition consumed by every frontend path."""

    year: int
    taxpayer: Taxpayer
    income: tuple[IssuedInvoice, ...]
    expenses: tuple[ExpenseInvoice, ...]
    out_of_year_income: IssuedInvoice
    income_date_boundary: IssuedInvoice
    expense_date_boundary: ExpenseInvoice
    quarter_oracle: tuple[QuarterlyOracle, ...]
    annual_oracle: AnnualOracle
    excluded_income_categories: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class AcceptanceReceipt:
    """Machine-readable result identity shared by all scenario runners."""

    brief_revision: str
    scenario_id: str
    frontend_path: Literal["cli", "tui", "cli_to_tui", "tui_to_cli"]
    year: int
    authority_generation: str
    modelo_130_revision: str
    modelo_100_revision: str
    acceptance_id: str
    outcome: AcceptanceOutcome
    source_state: str
    artifact_validation: str | None = None
    diagnostic_code: str | None = None

    def to_dict(self) -> dict[str, object]:
        """Return a stable JSON-safe representation."""
        return asdict(self)


def money(value: Decimal) -> Decimal:
    """Round independent hand arithmetic to euro cents."""
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def build_scenario(year: int) -> IncomeTaxScenario:
    """Build the stable synthetic inputs for ``year``.

    RD 439/2007 art. 110.4 supplies the 20% M130 rate. The 7% withholding
    represents a professional in the activity-start year. Expected values are
    calculated here from fixture constants and never read from Cadrumo's
    calculation engine.
    """
    bases = (Decimal("4000"), Decimal("3500"), Decimal("2000"), Decimal("2500"))
    expenses = (Decimal("500"), Decimal("700"), Decimal("300"), Decimal("900"))
    months = (2, 5, 8, 11)
    expense_categories = ("material_oficina", "software_suscripcion", "formacion_profesional", "asesoria_fiscal")
    issued = tuple(
        IssuedInvoice(
            period=period,
            invoice_id=f"income-{year}-{period}",
            transaction_id=f"bank-income-{year}-{period}",
            invoice_date=date(year, month, 15),
            transaction_date=date(year, month, 20),
            taxable_base=base,
            iva_rate=Decimal("0.21"),
            withholding_rate=Decimal("0.07"),
        )
        for period, base, month in zip(PERIODS, bases, months, strict=True)
    )
    spent = tuple(
        ExpenseInvoice(
            period=period,
            invoice_id=f"expense-{year}-{period}",
            transaction_id=f"bank-expense-{year}-{period}",
            invoice_date=date(year, month, 22),
            transaction_date=date(year, month, 25),
            category=category,
            taxable_base=base,
        )
        for period, base, month, category in zip(PERIODS, expenses, months, expense_categories, strict=True)
    )
    quarterly = _quarterly_oracle(issued, spent)
    return IncomeTaxScenario(
        year=year,
        taxpayer=Taxpayer(
            tax_id="12345678Z",
            territory="ES-MD",
            residence_country="ES",
            birth_date=date(year - 35, 6, 15),
            activity_start=date(year, 1, 1),
        ),
        income=issued,
        expenses=spent,
        out_of_year_income=IssuedInvoice(
            period="CONTROL",
            invoice_id=f"income-{year - 1}-control",
            transaction_id=f"bank-income-{year - 1}-control",
            invoice_date=date(year - 1, 12, 31),
            transaction_date=date(year - 1, 12, 31),
            taxable_base=Decimal("777"),
            iva_rate=Decimal("0.21"),
            withholding_rate=Decimal("0.07"),
        ),
        income_date_boundary=IssuedInvoice(
            period="1T",
            invoice_id=f"income-{year}-boundary",
            transaction_id=f"bank-income-{year}-boundary",
            invoice_date=date(year, 3, 31),
            transaction_date=date(year, 4, 1),
            taxable_base=Decimal("111"),
            iva_rate=Decimal("0.21"),
            withholding_rate=Decimal("0.07"),
        ),
        expense_date_boundary=ExpenseInvoice(
            period="1T",
            invoice_id=f"expense-{year}-boundary",
            transaction_id=f"bank-expense-{year}-boundary",
            invoice_date=date(year, 3, 31),
            transaction_date=date(year, 4, 1),
            category="material_oficina",
            taxable_base=Decimal("99"),
        ),
        quarter_oracle=quarterly,
        annual_oracle=AnnualOracle(
            activity_income=sum(bases, Decimal()),
            deductible_expenses=sum(expenses, Decimal()),
            activity_net_income=sum(bases, Decimal()) - sum(expenses, Decimal()),
            activity_withholding=sum((item.withholding for item in issued), Decimal()),
            m130_payments=sum((item.payment for item in quarterly), Decimal()),
        ),
        excluded_income_categories=("trabajo", "capital_mobiliario", "capital_inmobiliario", "ganancias_patrimoniales"),
    )


def expected_history_state(*, year: int, period: str, available_periods: frozenset[str]) -> HistoryState:
    """Classify required M130 history without coercing absence to zero."""
    if period == "1T":
        return HistoryState.NOT_APPLICABLE
    prior = PERIODS[PERIODS.index(period) - 1]
    return HistoryState.AVAILABLE if prior in available_periods else HistoryState.MISSING


def _quarterly_oracle(
    income: tuple[IssuedInvoice, ...], expenses: tuple[ExpenseInvoice, ...]
) -> tuple[QuarterlyOracle, ...]:
    rows: list[QuarterlyOracle] = []
    prior_positive_results = Decimal()
    for index, period in enumerate(PERIODS, start=1):
        cumulative_income = sum((item.taxable_base for item in income[:index]), Decimal())
        cumulative_expenses = sum((item.taxable_base for item in expenses[:index]), Decimal())
        net = cumulative_income - cumulative_expenses
        twenty_percent = money(net * M130_RATE)
        withholding = sum((item.withholding for item in income[:index]), Decimal())
        partial_result = max(money(twenty_percent - withholding - prior_positive_results), Decimal())
        payment = max(money(partial_result - M130_LOW_INCOME_REDUCTION), Decimal())
        rows.append(
            QuarterlyOracle(
                period=period,
                cumulative_income=cumulative_income,
                cumulative_expenses=cumulative_expenses,
                cumulative_net=net,
                twenty_percent=twenty_percent,
            cumulative_withholding=withholding,
            prior_positive_results=prior_positive_results,
            partial_result=partial_result,
            low_income_reduction=M130_LOW_INCOME_REDUCTION,
            payment=payment,
            )
        )
        prior_positive_results += partial_result
    return tuple(rows)


__all__ = [
    "BRIEF_ID",
    "BRIEF_REVISION",
    "SCENARIO_VERSION",
    "AcceptanceOutcome",
    "AcceptanceReceipt",
    "AnnualOracle",
    "HistoryState",
    "IncomeTaxScenario",
    "build_scenario",
    "expected_history_state",
]
