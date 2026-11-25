"""A statutory cap counts each row on the date its rule names, not on the bank date.

An annual cap (LIRPF art. 30.2.1.a and 30.2.5.a) limits what one ejercicio deducts, so a
row counts in the year it is imputed to. A daily cap (art. 30.2.5.c, RIRPF art. 9.A.3.a)
limits what one day of meals deducts, so a row counts on the day of the meal whichever
criterion places it and whenever the bank settled it.

Worked figures, by hand from the limits the article states:

* Annual, devengo, cap 500: 400 banked in June plus 400 invoiced on 20 December and banked
  on 10 January of the next year are both of the declared year: 500 in total, not 800.
* Daily, without overnight stay in Spain, 26,67: two meals of 40 on one day, banked on two
  days, deduct 26,67. Two meals of 40 on two days, banked on one day, deduct 53,34.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from cadrumo.domain.invoices.tests.catalogue_support import build_invoice_catalogue

from ....core.casilla_id import validated_casilla_id
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.categories.spending_category import SpendingCategory
from ....domain.invoices.catalogue import InvoiceCatalogue
from ....domain.invoices.enums import IvaRate, PaymentStatus
from ....domain.invoices.models import Invoice, InvoiceLine
from ....domain.iva.schema import InvoiceKind
from ....domain.renta.ledger_expenses import StatutoryCapClaim, statutory_cap_trims
from ....domain.transactions.models import Transaction, TransactionCatalogue
from ....domain.user_profile.values import UserProfileFact
from ..renta_gasto_ledger import aggregate_renta_gasto_ledger
from ..renta_imputation import ActivityImputationCriterion, ImputationCriteria
from ..renta_ledger import aggregate_renta_ledger_expenses, resolve_category_deduction_rules
from .renta_income_aggregation_support import renta_income_aggregation_period
from .renta_ledger_support import ledger_expense_transaction

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]

_BUCKET = "7a5e1c20-3f4b-4d6a-8b71-0c9d2e3f4a51"
_DECLARED = 2025
_SEGURO = SpendingCategory.from_registry("seguros_salud_autonomo")
_MUTUALIDAD = SpendingCategory.from_registry("mutualidad_alternativa")
_DIETA = SpendingCategory.from_registry("manutencion_dietas_nacional")
_NO_IVA = Decimal("0.00")


def _criteria(criterion: ActivityImputationCriterion) -> ImputationCriteria:
    facts = [
        UserProfileFact(
            path="irpf.activity_income_imputation_criterion",
            value=criterion.value,
            valid_from=date(year, 1, 1),
            valid_to=date(year, 12, 31),
        )
        for year in (_DECLARED, _DECLARED + 1)
    ]
    facts.extend(
        UserProfileFact(
            path="irpf.codigo_comercio_accounting",
            value=False,
            valid_from=date(year, 1, 1),
            valid_to=date(year, 12, 31),
        )
        for year in (_DECLARED, _DECLARED + 1)
    )
    facts.append(UserProfileFact(path="irpf.estimation_regime", value="directa_simplificada"))
    return ImputationCriteria(facts=tuple(facts))


def _row(
    name: str, *, category: SpendingCategory, amount: str, banked: date, invoice_id: str | None = None
) -> Transaction:
    return ledger_expense_transaction(
        name,
        amount=Decimal(amount),
        category=category,
        booked_date=banked,
        value_date=banked,
        purchase_invoice_evidence_id=invoice_id,
        taxable_base=Decimal(amount),
    )


def _invoice(transaction_id: str, *, amount: str, issued: date, number: str) -> Invoice:
    base = Decimal(amount)
    line = InvoiceLine(
        description="Servicio",
        quantity=Decimal("1"),
        unit_price=base,
        subtotal=base,
        iva_rate=IvaRate.from_registry("RATE_0"),
        iva_amount=_NO_IVA,
    )
    return Invoice.model_validate(
        {
            "bucket_id": _BUCKET,
            "kind": InvoiceKind.RECEIVED,
            "invoice_number": number,
            "issued_at": issued,
            "counterparty_name": "Proveedor SL",
            "counterparty_tax_id": "B00015016",
            "counterparty_country": "ES",
            "base_total": base,
            "iva_total": _NO_IVA,
            "grand_total": base,
            "currency": "EUR",
            "lines": (line,),
            "payment_status": PaymentStatus.PAID,
            "linked_transaction_ids": (transaction_id,),
        }
    )


def _invoiced_row(
    name: str, *, category: SpendingCategory, amount: str, issued: date, banked: date, number: str
) -> tuple[Transaction, Invoice]:
    bare = _row(name, category=category, amount=amount, banked=banked)
    invoice = _invoice(bare.transaction_id, amount=amount, issued=issued, number=number)
    return _row(name, category=category, amount=amount, banked=banked, invoice_id=invoice.invoice_id), invoice


def _annual_total(
    rows: tuple[Transaction, ...], invoices: InvoiceCatalogue, *, criteria: ImputationCriteria
) -> Decimal:
    result = aggregate_renta_ledger_expenses(
        TransactionCatalogue.from_transactions(rows),
        invoices,
        bucket_id=_BUCKET,
        period=renta_income_aggregation_period(_DECLARED, "0A"),
        profile_year=_DECLARED,
        criteria=criteria,
    )
    assert result.issues == (), [(issue.reason, issue.detail) for issue in result.issues]
    assert len(result.observations) == len(rows)
    return sum((observation.deductible_amount for observation in result.observations), Decimal("0"))


@pytest.mark.parametrize(
    ("category", "premium", "limit"),
    [
        (_SEGURO, "400.00", Decimal("500.00")),
        # The Manual Renta 2025 states the year's cuota maxima por contingencias comunes.
        (_MUTUALIDAD, "10000.00", Decimal("16672.66")),
    ],
    ids=["seguro", "mutualidad"],
)
def test_a_row_banked_next_year_counts_against_the_cap_of_the_year_it_is_imputed_to(
    category: SpendingCategory, premium: str, limit: Decimal
) -> None:
    """Both rows are of the declared year under devengo, so one annual limit holds both."""
    first, first_invoice = _invoiced_row(
        "june",
        category=category,
        amount=premium,
        issued=date(_DECLARED, 6, 1),
        banked=date(_DECLARED, 6, 1),
        number="JUN-1",
    )
    second, second_invoice = _invoiced_row(
        "december",
        category=category,
        amount=premium,
        issued=date(_DECLARED, 12, 20),
        banked=date(_DECLARED + 1, 1, 10),
        number="DEC-1",
    )

    total = _annual_total(
        (first, second),
        build_invoice_catalogue((first_invoice, second_invoice)),
        criteria=_criteria(ActivityImputationCriterion.DEVENGO),
    )

    assert total == limit, total


@pytest.mark.parametrize(
    "criterion",
    [ActivityImputationCriterion.DEVENGO, ActivityImputationCriterion.COBROS_Y_PAGOS],
    ids=["devengo", "cobros_y_pagos"],
)
def test_two_meals_of_one_day_share_one_limit_whenever_the_bank_settled_them(
    criterion: ActivityImputationCriterion,
) -> None:
    """The day of the meal decides, under either criterion: 26,67, not 53,34."""
    meal_day = date(_DECLARED, 3, 10)
    first, first_invoice = _invoiced_row(
        "meal-a", category=_DIETA, amount="40.00", issued=meal_day, banked=date(_DECLARED, 3, 11), number="A-1"
    )
    second, second_invoice = _invoiced_row(
        "meal-b", category=_DIETA, amount="40.00", issued=meal_day, banked=date(_DECLARED, 3, 12), number="B-1"
    )

    total = _annual_total(
        (first, second), build_invoice_catalogue((first_invoice, second_invoice)), criteria=_criteria(criterion)
    )

    assert total == Decimal("26.67"), total


def test_two_meals_of_two_days_keep_a_limit_each_when_the_bank_settled_them_together() -> None:
    """The discriminating converse: one bank date must not merge two days of meals."""
    banked = date(_DECLARED, 3, 12)
    first, first_invoice = _invoiced_row(
        "meal-a", category=_DIETA, amount="40.00", issued=date(_DECLARED, 3, 10), banked=banked, number="A-1"
    )
    second, second_invoice = _invoiced_row(
        "meal-b", category=_DIETA, amount="40.00", issued=date(_DECLARED, 3, 11), banked=banked, number="B-1"
    )

    total = _annual_total(
        (first, second),
        build_invoice_catalogue((first_invoice, second_invoice)),
        criteria=_criteria(ActivityImputationCriterion.COBROS_Y_PAGOS),
    )

    assert total == Decimal("53.34"), total


def test_a_meal_no_document_dates_counts_on_the_day_the_payment_moved() -> None:
    """With no invoice or stated date the payment is the only date there is."""
    day = date(_DECLARED, 3, 10)
    rows = (
        _row("meal-a", category=_DIETA, amount="40.00", banked=day),
        _row("meal-b", category=_DIETA, amount="40.00", banked=day),
    )

    total = _annual_total(rows, InvoiceCatalogue(), criteria=_criteria(ActivityImputationCriterion.COBROS_Y_PAGOS))

    assert total == Decimal("26.67"), total


def test_the_modelo_130_expense_path_counts_a_meal_on_its_own_day_under_cash() -> None:
    """The quarterly gasto owner goes through the same rule: one meal day, one limit."""
    meal_day = date(_DECLARED, 3, 10)
    first, first_invoice = _invoiced_row(
        "meal-a", category=_DIETA, amount="40.00", issued=meal_day, banked=date(_DECLARED, 3, 11), number="A-1"
    )
    second, second_invoice = _invoiced_row(
        "meal-b", category=_DIETA, amount="40.00", issued=meal_day, banked=date(_DECLARED, 3, 12), number="B-1"
    )

    result = aggregate_renta_gasto_ledger(
        TransactionCatalogue.from_transactions((first, second)),
        bucket_id=_BUCKET,
        period=renta_income_aggregation_period(_DECLARED, "1T"),
        modelo="130",
        target_casilla_id=validated_casilla_id("02", surface="the Modelo 130 expense box"),
        accept_activity_marker=True,
        invoices=build_invoice_catalogue((first_invoice, second_invoice)),
        criteria=_criteria(ActivityImputationCriterion.COBROS_Y_PAGOS),
    )

    assert result.issues == (), [(issue.reason, issue.detail) for issue in result.issues]
    total = sum((row.deductible_amount for row in result.observations), Decimal("0"))
    assert total == Decimal("26.67"), total


def test_the_cap_reads_each_date_for_its_own_period(operation: PinnedAuthorityOperation) -> None:
    """The two dates of a claim are not interchangeable: each rule reads only its own."""
    rules = resolve_category_deduction_rules(
        bucket_id=_BUCKET,
        profile_year=_DECLARED,
        modelo="100",
        usage_ratios=None,
        residence_ccaa=None,
        region_category_overrides=None,
        iva_deduction_ratio=None,
        profile_record=None,
        profile_decode_context=operation.profile_decode_context(),
        operation=operation,
    )

    def claim(name: str, *, category: SpendingCategory, imputed: date, incurred: date) -> StatutoryCapClaim:
        return StatutoryCapClaim(
            claim_id=name,
            transaction_id=name,
            category=category,
            imputed_on=imputed,
            incurred_on=incurred,
            deductible_amount=Decimal("400.00"),
        )

    annual_trims = statutory_cap_trims(
        (
            claim("a", category=_SEGURO, imputed=date(_DECLARED, 6, 1), incurred=date(_DECLARED - 1, 12, 1)),
            claim("b", category=_SEGURO, imputed=date(_DECLARED, 7, 1), incurred=date(_DECLARED, 7, 1)),
        ),
        profiles=rules.profiles,
        context=rules.context,
    )
    assert annual_trims == {"b": Decimal("100.00")}

    daily_trims = statutory_cap_trims(
        (
            claim("a", category=_DIETA, imputed=date(_DECLARED, 3, 11), incurred=date(_DECLARED, 3, 10)),
            claim("b", category=_DIETA, imputed=date(_DECLARED, 3, 12), incurred=date(_DECLARED, 3, 10)),
        ),
        profiles=rules.profiles,
        context=rules.context,
    )
    assert daily_trims == {"a": Decimal("26.67"), "b": Decimal("0.00")}
