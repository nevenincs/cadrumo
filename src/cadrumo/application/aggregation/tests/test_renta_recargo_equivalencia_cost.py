"""A retailer in the recargo de equivalencia deducts the IVA and recargo she bears as cost.

LIVA art. 154.Dos gives the retailer no right to deduct the IVA or the recargo a supplier charges her,
so both join the acquisition cost for the IRPF (LIRPF art. 28, with the IS rules on non-deductible IVA). The
regime comes from the profile, so the same purchase under the general regime keeps only its base.

Worked figures: a purchase of 6.800,00 base, 1.428,00 IVA at 21 % and 353,60 recargo at 5,2 % costs
8.581,60 to the retailer; a purchase of 1.000,00 plus 210,00 IVA costs 1.210,00 to her and 1.000,00 to a
general-regime taxpayer, who recovers the IVA.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from cadrumo.domain.invoices.tests.catalogue_support import build_invoice_catalogue

from ....domain.calculations.registry.tests.authored_editions import open_ended_revision
from ....domain.categories.spending_category import SpendingCategory
from ....domain.invoices.enums import IvaRate, PaymentStatus
from ....domain.invoices.models import Invoice, InvoiceLine
from ....domain.iva.schema import InvoiceKind
from ....domain.transactions.models import Transaction
from ....domain.user_profile.values import UserProfileFact
from ...actividad_asset.history import ActivityAssetHistory
from .ledger_source_mesh_support import (
    BUCKET_ID,
    InMemoryInvoiceCatalogueRepository,
    cash_criterion_profile,
    ledger_source_mesh_revision,
    m130_binding_id,
    resolve_m130,
)
from .renta_ledger_support import ledger_expense_transaction
from .test_renta_gasto_linked_invoice import YEAR

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]

_CATEGORY = SpendingCategory.from_registry("suministros_cliente_directos")
_M130_REVISION_ID = str(open_ended_revision("130").id)


def _iva_block(regime: str) -> tuple[UserProfileFact, ...]:
    """The canonical IVA block of a common-territory filer under ``regime``, enrolled in no special scheme."""
    return (
        UserProfileFact(path="tax_residence.jurisdiction_scope", value="common_regime"),
        UserProfileFact(path="iva.regime", value=regime),
        UserProfileFact(path="iva.m303_regime_composition", value="general"),
        UserProfileFact(path="iva.redeme_enrolled", value=False),
        UserProfileFact(path="iva.cash_accounting_regime_enrolled", value=False),
        UserProfileFact(path="iva.voluntary_sii_enrolled", value=False),
        UserProfileFact(path="iva.hydrocarbon_deposit_advance_payment_deduction_entitled", value=False),
    )


def _purchase(*, base: str, iva: str, recargo: str | None = None) -> Transaction:
    gross = Decimal(base) + Decimal(iva) + Decimal(recargo or "0")
    return ledger_expense_transaction(
        "compra",
        amount=gross,
        category=_CATEGORY,
        booked_date=date(YEAR, 2, 10),
        value_date=date(YEAR, 2, 10),
        taxable_base=Decimal(base),
        iva_amount=Decimal(iva),
        recargo_amount=None if recargo is None else Decimal(recargo),
    )


def _expense_box(regime: str, row: Transaction) -> Decimal:
    profile = cash_criterion_profile(YEAR, extra_facts=_iva_block(regime))
    resolution = resolve_m130(ActivityAssetHistory(), "1T", rows=(row,), profile=profile)
    return resolution.binding_values[m130_binding_id(ledger_source_mesh_revision("130", _M130_REVISION_ID))]


def test_the_retailer_deducts_the_base_the_iva_and_the_recargo_as_cost() -> None:
    row = _purchase(base="6800.00", iva="1428.00", recargo="353.60")

    assert _expense_box("RECARGO_EQUIVALENCIA", row) == Decimal("8581.60")


def test_the_retailer_bears_the_iva_of_an_ordinary_purchase_as_cost() -> None:
    assert _expense_box("RECARGO_EQUIVALENCIA", _purchase(base="1000.00", iva="210.00")) == Decimal("1210.00")


def test_a_general_regime_taxpayer_keeps_only_the_base() -> None:
    assert _expense_box("GENERAL", _purchase(base="1000.00", iva="210.00")) == Decimal("1000.00")


def _recargo_invoice(row: Transaction) -> Invoice:
    line = InvoiceLine(
        description="Mercancia",
        quantity=Decimal("1"),
        unit_price=Decimal("6800.00"),
        subtotal=Decimal("6800.00"),
        iva_rate=IvaRate.from_registry("RATE_21"),
        iva_amount=Decimal("1428.00"),
    )
    return Invoice.model_validate(
        {
            "bucket_id": BUCKET_ID,
            "kind": InvoiceKind.RECEIVED,
            "invoice_number": "MAY-1",
            "issued_at": date(YEAR, 2, 5),
            "counterparty_name": "Mayorista SL",
            "counterparty_tax_id": "B00015016",
            "counterparty_country": "ES",
            "base_total": Decimal("6800.00"),
            "iva_total": Decimal("1428.00"),
            "recargo_amount": Decimal("353.60"),
            "grand_total": Decimal("8581.60"),
            "currency": "EUR",
            "lines": (line,),
            "payment_status": PaymentStatus.PAID,
            "linked_transaction_ids": (row.transaction_id,),
        }
    )


def test_the_linked_invoice_states_the_iva_and_recargo_the_row_does_not_carry() -> None:
    bare = ledger_expense_transaction(
        "compra-sin-cuotas",
        amount=Decimal("8581.60"),
        category=_CATEGORY,
        booked_date=date(YEAR, 2, 10),
        value_date=date(YEAR, 2, 10),
        taxable_base=Decimal("6800.00"),
    )
    invoice = _recargo_invoice(bare)
    linked = bare.model_copy(update={"invoice_id": invoice.invoice_id})
    repository = InMemoryInvoiceCatalogueRepository()
    repository.save(build_invoice_catalogue((invoice,)))
    profile = cash_criterion_profile(YEAR, extra_facts=_iva_block("RECARGO_EQUIVALENCIA"))

    quarterly = resolve_m130(ActivityAssetHistory(), "1T", rows=(linked,), profile=profile, invoices=repository)
    unlinked = resolve_m130(ActivityAssetHistory(), "1T", rows=(bare,), profile=profile)
    box = m130_binding_id(ledger_source_mesh_revision("130", _M130_REVISION_ID))

    assert quarterly.binding_values[box] == Decimal("8581.60")
    assert unlinked.binding_values[box] == Decimal("6800.00")
