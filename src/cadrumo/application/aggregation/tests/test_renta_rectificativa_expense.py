"""A received factura rectificativa corrects the accrued expense of the invoice it names.

The same reading and the same fallback as an issued one: same year nets, a later year
refuses because no bundled source says which year it reduces. Worked by hand:

- F: 100,00 base + 21,00 IVA paid, asesoria fiscal, 100,00 deductible.
- R: 20,00 base + 4,20 IVA, naming F: 20/100 of the row comes off, leaving 80,00.
- Two rows of 60,00 and 40,00 on F keep their shares: 48,00 and 32,00, still 80,00.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from cadrumo.domain.invoices.tests.catalogue_support import build_invoice_catalogue

from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.invoice_legal_classification import invoice_class_rectificativa
from ....domain.calculations.registry.tests.authored_editions import newest_authored_edition
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
_F_ON = date(_YEAR, 2, 1)
_R_ON = date(_YEAR, 5, 1)


def renta_rectificativa_expense_correction(
    on: date,
    *,
    rectifies: str | None = "R-1",
    base: Decimal = Decimal("20.00"),
    number: str = "AB-1",
    linked: tuple[str, ...] = (),
) -> Invoice:
    iva = (base * Decimal("0.21")).quantize(Decimal("0.01"))
    return Invoice.model_validate(
        {
            "bucket_id": BUCKET_ID,
            "kind": InvoiceKind.RECEIVED,
            "invoice_class": invoice_class_rectificativa(),
            "series": "AB",
            "rectifies_invoice_number": rectifies,
            "invoice_number": number,
            "issued_at": on,
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
            "payment_status": PaymentStatus.PAID if linked else PaymentStatus.PENDING,
            "linked_transaction_ids": linked,
        }
    )


def _ledger(*extra: Invoice, accrued: date = _F_ON) -> tuple[Transaction, InMemoryInvoiceCatalogueRepository]:
    unlinked = expense_row(accrued, evidence_id=None)
    invoice = received(accrued, linked=(unlinked.transaction_id,))
    repository = InMemoryInvoiceCatalogueRepository()
    repository.save(build_invoice_catalogue((invoice, *extra)))
    return expense_row(accrued, evidence_id=invoice.invoice_id), repository


def _m100_total(resolution: CalculationSourceResolution) -> Decimal:
    return sum(resolution.binding_values.values(), Decimal("0"))


def _refused(resolution: CalculationSourceResolution, token: str) -> bool:
    return any(item.reason == "unresolved_binding" and token in item.message for item in resolution.diagnostics)


def _blocked(resolution: CalculationSourceResolution) -> bool:
    return any(item.reason == "unresolved_binding" for item in resolution.diagnostics)


def test_a_same_year_correction_nets_the_annual_expense(operation: PinnedAuthorityOperation) -> None:
    row, invoices = _ledger(renta_rectificativa_expense_correction(_R_ON))
    profile = renta_imputation_criterion_profile(operation, declared((_YEAR, DEVENGO)))
    resolution = resolve_m100(ActivityAssetHistory(), rows=(row,), profile=profile, invoices=invoices)
    assert _m100_total(resolution) == Decimal("80.00")
    assert not _blocked(resolution)


@pytest.mark.parametrize(("period", "expected"), [("1T", Decimal("100.00")), ("2T", Decimal("80.00"))])
def test_the_instalment_nets_from_the_quarter_the_correction_accrues(
    operation: PinnedAuthorityOperation, period: str, expected: Decimal
) -> None:
    row, invoices = _ledger(renta_rectificativa_expense_correction(_R_ON))
    profile = renta_imputation_criterion_profile(operation, declared((_YEAR, DEVENGO)))
    resolution = resolve_m130(ActivityAssetHistory(), period, rows=(row,), profile=profile, invoices=invoices)
    assert m130_box(resolution) == expected
    assert not _blocked(resolution)


def test_a_correction_keeps_each_rows_share(operation: PinnedAuthorityOperation) -> None:
    """60,00 and 40,00 less a fifth are 48,00 and 32,00."""
    first_on, second_on = date(_YEAR, 2, 1), date(_YEAR, 2, 2)
    first = expense_row(first_on, evidence_id=None, amount=Decimal("72.60"), base=Decimal("60.00"))
    second = expense_row(second_on, evidence_id=None, amount=Decimal("48.40"), base=Decimal("40.00"))
    invoice = received(_F_ON, linked=(first.transaction_id, second.transaction_id))
    repository = InMemoryInvoiceCatalogueRepository()
    repository.save(build_invoice_catalogue((invoice, renta_rectificativa_expense_correction(_R_ON))))
    rows = (
        expense_row(first_on, evidence_id=invoice.invoice_id, amount=Decimal("72.60"), base=Decimal("60.00")),
        expense_row(second_on, evidence_id=invoice.invoice_id, amount=Decimal("48.40"), base=Decimal("40.00")),
    )
    profile = renta_imputation_criterion_profile(operation, declared((_YEAR, DEVENGO)))
    resolution = resolve_m130(ActivityAssetHistory(), "2T", rows=rows, profile=profile, invoices=repository)
    assert m130_box(resolution) == Decimal("80.00")


def test_a_correction_in_a_later_year_refuses(operation: PinnedAuthorityOperation) -> None:
    row, invoices = _ledger(renta_rectificativa_expense_correction(date(_YEAR, 3, 1)), accrued=date(_YEAR - 1, 11, 1))
    profile = renta_imputation_criterion_profile(operation, declared((_YEAR - 1, DEVENGO), (_YEAR, DEVENGO)))
    resolution = resolve_m100(ActivityAssetHistory(), rows=(row,), profile=profile, invoices=invoices)
    assert _m100_total(resolution) == Decimal("0")
    assert _refused(resolution, "rectificativa_across_years")


def test_a_correction_whose_invoice_is_not_recorded_refuses(operation: PinnedAuthorityOperation) -> None:
    row, invoices = _ledger(renta_rectificativa_expense_correction(_R_ON, rectifies="R-404"))
    profile = renta_imputation_criterion_profile(operation, declared((_YEAR, DEVENGO)))
    resolution = resolve_m100(ActivityAssetHistory(), rows=(row,), profile=profile, invoices=invoices)
    assert _m100_total(resolution) == Decimal("100.00")
    assert _refused(resolution, "rectificativa_target_unknown")


def test_a_correction_above_its_invoice_refuses(operation: PinnedAuthorityOperation) -> None:
    row, invoices = _ledger(renta_rectificativa_expense_correction(_R_ON, base=Decimal("120.00")))
    profile = renta_imputation_criterion_profile(operation, declared((_YEAR, DEVENGO)))
    resolution = resolve_m100(ActivityAssetHistory(), rows=(row,), profile=profile, invoices=invoices)
    assert _m100_total(resolution) == Decimal("100.00")
    assert _refused(resolution, "rectificativa_above_invoice")


def _supplier_refund(on: date, *, evidence_id: str | None) -> Transaction:
    return Transaction.model_validate(
        {
            "raw": ledger_raw_transaction(f"abono-{on.isoformat()}", booked_date=on, amount=Decimal("24.20")),
            "direction": TransactionDirection.INCOMING,
            "group_label": None,
            "business_classification": BusinessClassification.BUSINESS,
            "source_jurisdiction": "ES",
            "purchase_invoice_evidence_id": evidence_id,
            "category_id": SpendingCategory.from_registry("asesoria_fiscal").value,
            "classified_at": datetime(1980, 4, 6, 13, 0, tzinfo=UTC),
            "classified_by": "manual",
        },
    )


def test_a_supplier_refund_under_cash_refuses_in_its_year(operation: PinnedAuthorityOperation) -> None:
    """Under cash only a pago places an expense, and no source says a cobro on a correction nets it."""
    unlinked = _supplier_refund(_R_ON, evidence_id=None)
    corrected = renta_rectificativa_expense_correction(_R_ON, linked=(unlinked.transaction_id,))
    row, invoices = _ledger(corrected)
    refund = _supplier_refund(_R_ON, evidence_id=corrected.invoice_id)
    profile = renta_imputation_criterion_profile(operation, declared((_YEAR, CASH)))
    resolution = resolve_m100(ActivityAssetHistory(), rows=(row, refund), profile=profile, invoices=invoices)
    assert _m100_total(resolution) == Decimal("100.00")
    assert _refused(resolution, "rectificativa_refund_under_cash")


def test_an_unpaid_correction_moves_nothing_under_cash(operation: PinnedAuthorityOperation) -> None:
    row, invoices = _ledger(renta_rectificativa_expense_correction(_R_ON))
    profile = renta_imputation_criterion_profile(operation, declared((_YEAR, CASH)))
    resolution = resolve_m100(ActivityAssetHistory(), rows=(row,), profile=profile, invoices=invoices)
    assert _m100_total(resolution) == Decimal("100.00")
    assert not _blocked(resolution)


def _same_number_in_series_b() -> Invoice:
    """Return a second received R-1, in series B, for a base of 5.000,00."""
    base, iva = Decimal("5000.00"), Decimal("1050.00")
    first = received(_F_ON, linked=())
    line = first.lines[0].model_copy(update={"unit_price": base, "subtotal": base, "iva_amount": iva})
    return Invoice.model_validate(
        {
            **first.model_dump(exclude={"invoice_id"}),
            "series": "B",
            "base_total": base,
            "iva_total": iva,
            "grand_total": base + iva,
            "lines": (line,),
        }
    )


@pytest.mark.parametrize("second_first", [False, True], ids=["unseried_first", "series_b_first"])
def test_a_correction_two_invoices_could_answer_refuses(
    operation: PinnedAuthorityOperation, second_first: bool
) -> None:
    """A correction records only the number it names, so two R-1 leave the 20,00 with nowhere to go, in any order."""
    unlinked = expense_row(_F_ON, evidence_id=None)
    invoice = received(_F_ON, linked=(unlinked.transaction_id,))
    other = _same_number_in_series_b()
    repository = InMemoryInvoiceCatalogueRepository()
    ordered = (other, invoice) if second_first else (invoice, other)
    repository.save(build_invoice_catalogue((*ordered, renta_rectificativa_expense_correction(_R_ON))))
    row = expense_row(_F_ON, evidence_id=invoice.invoice_id)
    profile = renta_imputation_criterion_profile(operation, declared((_YEAR, DEVENGO)))
    resolution = resolve_m100(ActivityAssetHistory(), rows=(row,), profile=profile, invoices=repository)
    assert _m100_total(resolution) == Decimal("100.00")
    assert _refused(resolution, "rectificativa_target_ambiguous")
