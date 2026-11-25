"""A received invoice reaches an expense row through the ledger link, not only through attached evidence.

``ledger link`` stamps ``Transaction.invoice_id``, the catalogue key; the evidence
reference addresses its own id space. An expense row linked to a received invoice
accrues on that invoice's date under devengo (LIRPF art. 28 with RIRPF art. 30 on
the deductible expense and its justification), so the Modelo 130 first-quarter
casilla 02 holds an invoice of February that the bank settled in April.

Worked figures: one received invoice of 200,00 dated in the first quarter, banked in the
second. Under devengo the first-quarter expense is 200,00 when the row is linked by
``invoice_id``; with no link there is no document to place it by, so the payment date
puts it in the second quarter and the first quarter holds 0,00.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from cadrumo.domain.calculations.registry.tests.authored_editions import newest_authored_edition
from cadrumo.domain.invoices.tests.catalogue_support import build_invoice_catalogue

from ....core.casilla_id import validated_casilla_id
from ....domain.categories.spending_category import SpendingCategory
from ....domain.invoices.catalogue import InvoiceCatalogue
from ....domain.invoices.enums import IvaRate, PaymentStatus
from ....domain.invoices.models import Invoice, InvoiceLine
from ....domain.iva.schema import InvoiceKind
from ....domain.transactions.models import Transaction, TransactionCatalogue
from ....domain.user_profile.values import UserProfileFact
from ..renta_gasto_ledger import aggregate_renta_gasto_ledger
from ..renta_imputation import (
    ActivityImputationCriterion,
    ImputationCriteria,
    received_invoice_reference,
    rows_touching_window,
)
from .renta_income_aggregation_support import renta_income_aggregation_period
from .renta_ledger_support import ledger_expense_transaction

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]

BUCKET = "7a5e1c20-3f4b-4d6a-8b71-0c9d2e3f4a51"
YEAR = newest_authored_edition("100")
_CATEGORY = SpendingCategory.from_registry("asesoria_fiscal")
_AMOUNT = Decimal("200.00")


def criteria() -> ImputationCriteria:
    facts = [
        UserProfileFact(
            path="irpf.activity_income_imputation_criterion",
            value=ActivityImputationCriterion.DEVENGO.value,
            valid_from=date(year, 1, 1),
            valid_to=date(year, 12, 31),
        )
        for year in (YEAR, YEAR + 1)
    ]
    facts.extend(
        UserProfileFact(
            path="irpf.codigo_comercio_accounting",
            value=False,
            valid_from=date(year, 1, 1),
            valid_to=date(year, 12, 31),
        )
        for year in (YEAR, YEAR + 1)
    )
    facts.append(UserProfileFact(path="irpf.estimation_regime", value="directa_simplificada"))
    return ImputationCriteria(facts=tuple(facts))


def _row() -> Transaction:
    return ledger_expense_transaction(
        "asesoria-febrero",
        amount=_AMOUNT,
        category=_CATEGORY,
        booked_date=date(YEAR, 4, 10),
        value_date=date(YEAR, 4, 10),
        taxable_base=_AMOUNT,
    )


def _invoice(row: Transaction) -> Invoice:
    line = InvoiceLine(
        description="Asesoria",
        quantity=Decimal("1"),
        unit_price=_AMOUNT,
        subtotal=_AMOUNT,
        iva_rate=IvaRate.from_registry("RATE_0"),
        iva_amount=Decimal("0.00"),
    )
    return Invoice.model_validate(
        {
            "bucket_id": BUCKET,
            "kind": InvoiceKind.RECEIVED,
            "invoice_number": "ASE-FEB-1",
            "issued_at": date(YEAR, 2, 12),
            "counterparty_name": "Asesoria SL",
            "counterparty_tax_id": "B00015016",
            "counterparty_country": "ES",
            "base_total": _AMOUNT,
            "iva_total": Decimal("0.00"),
            "grand_total": _AMOUNT,
            "currency": "EUR",
            "lines": (line,),
            "payment_status": PaymentStatus.PAID,
            "linked_transaction_ids": (row.transaction_id,),
        }
    )


def _first_quarter_expense(row: Transaction, invoices: InvoiceCatalogue) -> Decimal:
    result = aggregate_renta_gasto_ledger(
        TransactionCatalogue.from_transactions((row,)),
        bucket_id=BUCKET,
        period=renta_income_aggregation_period(YEAR, "1T"),
        modelo="130",
        target_casilla_id=validated_casilla_id("02", surface="the Modelo 130 expense box"),
        accept_activity_marker=True,
        invoices=invoices,
        criteria=criteria(),
    )
    return sum((observation.deductible_amount for observation in result.observations), Decimal("0.00"))


def test_a_row_linked_by_invoice_id_accrues_on_its_invoice_date_in_the_modelo_130_expense_box() -> None:
    bare = _row()
    invoice = _invoice(bare)
    linked = bare.model_copy(update={"invoice_id": invoice.invoice_id})

    assert _first_quarter_expense(linked, build_invoice_catalogue((invoice,))) == _AMOUNT


def test_a_row_with_no_link_is_placed_by_its_payment_date() -> None:
    bare = _row()
    invoice = _invoice(bare)

    assert _first_quarter_expense(bare, build_invoice_catalogue((invoice,))) == Decimal("0.00")


def test_the_evidence_reference_still_names_the_invoice_when_no_link_does() -> None:
    bare = _row()
    invoice = _invoice(bare)
    evidenced = bare.model_copy(update={"purchase_invoice_evidence_id": invoice.invoice_id})

    assert received_invoice_reference(evidenced) == invoice.invoice_id
    assert _first_quarter_expense(evidenced, build_invoice_catalogue((invoice,))) == _AMOUNT


def test_the_link_wins_over_an_evidence_reference_in_another_id_space() -> None:
    bare = _row()
    invoice = _invoice(bare)
    both = bare.model_copy(update={"invoice_id": invoice.invoice_id, "purchase_invoice_evidence_id": "evidence-0001"})

    assert received_invoice_reference(both) == invoice.invoice_id


def test_the_cumulative_window_keeps_a_row_whose_linked_invoice_accrues_in_it() -> None:
    bare = _row()
    invoice = _invoice(bare)
    linked = bare.model_copy(update={"invoice_id": invoice.invoice_id})

    def kept(row: Transaction) -> int:
        window = rows_touching_window(
            TransactionCatalogue.from_transactions((row,)),
            build_invoice_catalogue((invoice,)),
            kind=InvoiceKind.RECEIVED,
            invoice_id_of=received_invoice_reference,
            start=date(YEAR, 1, 1),
            end=date(YEAR, 3, 31),
            criteria=criteria(),
        )
        return len(window)

    assert kept(linked) == 1
    assert kept(bare) == 0
