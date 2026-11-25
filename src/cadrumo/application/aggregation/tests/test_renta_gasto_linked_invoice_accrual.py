"""A received invoice paid by a row linked to it is covered, under accrual, by that row.

``ledger link`` stamps ``Transaction.invoice_id``, the catalogue key; attaching the
invoice's document stamps ``purchase_invoice_evidence_id`` with the evidence record's
own id, a different id space. Under devengo a received invoice accruing in the window
needs a ledger row that carries its category and business share (LIRPF art. 28 with
RIRPF arts. 7 and 30), so the coverage screen and the correction screen must find the
row through the link. Worked figures: one received invoice of 100,00 base + 21,00 IVA
dated in February and paid the same month, so the first-quarter expense is 100,00 with
nothing left to place.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from cadrumo.domain.calculations.registry.tests.authored_editions import newest_authored_edition
from cadrumo.domain.invoices.tests.catalogue_support import build_invoice_catalogue

from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.invoice_legal_classification import invoice_class_rectificativa
from ....domain.categories.spending_category import SpendingCategory
from ....domain.invoices.enums import IvaRate, PaymentStatus
from ....domain.invoices.models import Invoice, InvoiceLine
from ....domain.iva.schema import InvoiceKind
from ....domain.transactions.enums import BusinessClassification, TransactionDirection
from ....domain.transactions.models import Transaction
from ...actividad_asset.history import ActivityAssetHistory
from ..source_mesh import CalculationSourceResolution
from .ledger_source_mesh_support import (
    BUCKET_ID,
    InMemoryInvoiceCatalogueRepository,
    m130_box,
    resolve_m100,
    resolve_m130,
)
from .ledger_transaction_support import ledger_raw_transaction
from .test_renta_imputation_criterion import (
    CASH,
    DEVENGO,
    declared,
    expense_row,
    received,
    renta_imputation_criterion_profile,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]

_YEAR = newest_authored_edition("100")
_PAID_ON = date(_YEAR, 2, 1)
_EVIDENCE_ID = "evidence-0001"
_BASE = Decimal("100.00")


def _linked_ledger(*, link: bool) -> tuple[Transaction, InMemoryInvoiceCatalogueRepository]:
    """A paid expense row and its received invoice; the row names the invoice only when ``link`` is set."""
    bare = expense_row(_PAID_ON, evidence_id=None)
    invoice = received(_PAID_ON, linked=(bare.transaction_id,))
    repository = InMemoryInvoiceCatalogueRepository()
    repository.save(build_invoice_catalogue((invoice,)))
    if not link:
        return bare, repository
    return bare.model_copy(update={"invoice_id": invoice.invoice_id, "purchase_invoice_evidence_id": _EVIDENCE_ID}), (
        repository
    )


def _accrual_gap(resolution: CalculationSourceResolution) -> bool:
    return any(
        item.reason == "unresolved_binding" and "accrual_unclassified" in item.message
        for item in resolution.diagnostics
    )


def test_a_row_linked_by_invoice_id_covers_its_accruing_invoice_in_the_instalment(
    operation: PinnedAuthorityOperation,
) -> None:
    row, invoices = _linked_ledger(link=True)
    profile = renta_imputation_criterion_profile(operation, declared((_YEAR, DEVENGO)))
    resolution = resolve_m130(ActivityAssetHistory(), "1T", rows=(row,), profile=profile, invoices=invoices, year=_YEAR)
    assert m130_box(resolution) == _BASE
    assert not _accrual_gap(resolution)


def test_a_row_linked_by_invoice_id_covers_its_accruing_invoice_in_the_annual_return(
    operation: PinnedAuthorityOperation,
) -> None:
    row, invoices = _linked_ledger(link=True)
    profile = renta_imputation_criterion_profile(operation, declared((_YEAR, DEVENGO)))
    resolution = resolve_m100(ActivityAssetHistory(), rows=(row,), profile=profile, invoices=invoices, year=_YEAR)
    assert sum(resolution.binding_values.values(), Decimal("0")) == _BASE
    assert not _accrual_gap(resolution)


def test_an_accruing_invoice_no_row_names_still_withholds_the_expense_boxes(
    operation: PinnedAuthorityOperation,
) -> None:
    row, invoices = _linked_ledger(link=False)
    profile = renta_imputation_criterion_profile(operation, declared((_YEAR, DEVENGO)))
    resolution = resolve_m130(ActivityAssetHistory(), "1T", rows=(row,), profile=profile, invoices=invoices, year=_YEAR)
    assert _accrual_gap(resolution)


def _correction(*, linked: tuple[str, ...]) -> Invoice:
    base = Decimal("20.00")
    iva = Decimal("4.20")
    return Invoice.model_validate(
        {
            "bucket_id": BUCKET_ID,
            "kind": InvoiceKind.RECEIVED,
            "invoice_class": invoice_class_rectificativa(),
            "series": "AB",
            "rectifies_invoice_number": "R-1",
            "invoice_number": "AB-1",
            "issued_at": date(_YEAR, 5, 1),
            "counterparty_name": "Proveedor SL",
            "counterparty_tax_id": "B00015016",
            "counterparty_country": "ES",
            "base_total": base,
            "iva_total": iva,
            "grand_total": base + iva,
            "currency": "EUR",
            "lines": (
                InvoiceLine(
                    description="Abono",
                    quantity=Decimal("1"),
                    unit_price=base,
                    subtotal=base,
                    iva_rate=IvaRate.from_registry("RATE_21"),
                    iva_amount=iva,
                ),
            ),
            "payment_status": PaymentStatus.PAID,
            "linked_transaction_ids": linked,
        }
    )


def _supplier_refund() -> Transaction:
    on = date(_YEAR, 5, 1)
    return Transaction.model_validate(
        {
            "raw": ledger_raw_transaction(f"abono-{on.isoformat()}", booked_date=on, amount=Decimal("24.20")),
            "direction": TransactionDirection.INCOMING,
            "group_label": None,
            "business_classification": BusinessClassification.BUSINESS,
            "source_jurisdiction": "ES",
            "category_id": SpendingCategory.from_registry("asesoria_fiscal").value,
            "classified_at": datetime(_YEAR, 5, 2, 9, 0, tzinfo=UTC),
            "classified_by": "manual",
        },
    )


def test_a_supplier_refund_linked_by_invoice_id_to_a_correction_refuses_under_cash(
    operation: PinnedAuthorityOperation,
) -> None:
    """Under cash no source says what a cobro on a correction nets against, whichever id space names the link."""
    bare = expense_row(_PAID_ON, evidence_id=None)
    invoice = received(_PAID_ON, linked=(bare.transaction_id,))
    refund = _supplier_refund()
    corrected = _correction(linked=(refund.transaction_id,))
    repository = InMemoryInvoiceCatalogueRepository()
    repository.save(build_invoice_catalogue((invoice, corrected)))
    row = bare.model_copy(update={"invoice_id": invoice.invoice_id})
    linked_refund = refund.model_copy(update={"invoice_id": corrected.invoice_id})
    profile = renta_imputation_criterion_profile(operation, declared((_YEAR, CASH)))
    resolution = resolve_m100(
        ActivityAssetHistory(), rows=(row, linked_refund), profile=profile, invoices=repository, year=_YEAR
    )
    assert any(
        item.reason == "unresolved_binding" and "rectificativa_refund_under_cash" in item.message
        for item in resolution.diagnostics
    )
