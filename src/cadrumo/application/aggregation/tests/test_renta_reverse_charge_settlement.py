"""A reverse-charge purchase settles at its base; an ordinary one still settles at base + IVA.

Under inversión del sujeto pasivo (LIVA art. 84.Uno.2.º) the supplier charges no
cuota: the recipient self-assesses the IVA its invoice records, so the bank pays the
supplier the base alone. The annual Renta expense resolver compares the linked
payment with what the invoice leaves to be paid, and that figure must exclude the
self-assessed cuota while an ordinary invoice keeps comparing cash with base + IVA.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from cadrumo.domain.invoices.tests.catalogue_support import build_invoice_catalogue

from ....core.period import Period
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.tests.authored_editions import filing_year_envelope
from ....domain.categories.registry import resolve_category_profiles
from ....domain.categories.spending_category import SpendingCategory
from ....domain.invoices.enums import IvaRate, PaymentStatus
from ....domain.invoices.models import Invoice, InvoiceLine
from ....domain.invoices.service import invoice_settlement, invoice_settlement_eur, recipient_self_assesses
from ....domain.iva.schema import InvoiceKind, IvaCategory
from ....domain.renta.ledger_expenses import RentaDeductibilityContext, RentaDeductibleExpenseObservation
from ....domain.transactions.enums import BusinessClassification, TransactionDirection
from ....domain.transactions.models import Transaction
from ....domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat
from ..renta_ledger_classification import classify_renta_transaction
from ..renta_ledger_models import RentaLedgerAggregationIssue, RentaLedgerAggregationIssueReason

_YEAR = filing_year_envelope().horizon
_DAY = date(_YEAR, 3, 3)
_BUCKET = "reverse-charge-bucket"
_BASE = Decimal("80.00")
_CUOTA = Decimal("16.80")
_IRISH_SUPPLIER = ("IE", "IE6388047V")
_SPANISH_SUPPLIER = ("ES", "B00015016")

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]


def _payment(amount: Decimal, *, label: str, iva_category: str | None, iva_amount: Decimal) -> Transaction:
    """An outgoing EUR payment for a business software subscription."""
    raw = RawTransaction(
        provider_transaction_id=f"row-reverse-charge-{label}",
        booked_date=_DAY,
        value_date=_DAY,
        amount=amount,
        currency="EUR",
        counterparty="Cloud Hosting Ltd",
        description="Servicio de alojamiento en la nube",
        provenance=RawProvenance(
            source_path=Path(__file__),
            source_sha256="e" * 64,
            source_row_index=1,
            source_format=SourceFormat.MANUAL,
            ingested_at=datetime(_YEAR, 3, 4, 9, 0, tzinfo=UTC),
            provider_name="manual",
        ),
        raw_fields={"Concepto": "Servicio de alojamiento en la nube"},
    )
    payload: dict[str, object] = {
        "raw": raw,
        "direction": TransactionDirection.OUTGOING,
        "group_label": None,
        "source_jurisdiction": "ES",
        "business_classification": BusinessClassification.BUSINESS,
        "category_id": SpendingCategory.from_registry("software_suscripcion").value,
        "taxable_base": _BASE,
        "iva_amount": iva_amount,
    }
    if iva_category is not None:
        payload["iva_category"] = iva_category
    return Transaction.model_validate(payload)


def _invoice(*, number: str, iva_category: str | None, supplier: tuple[str, str], transaction_id: str) -> Invoice:
    """A received invoice recording base 80.00 and a 21 % cuota of 16.80."""
    payload: dict[str, object] = {
        "bucket_id": _BUCKET,
        "kind": InvoiceKind.RECEIVED,
        "invoice_number": number,
        "issued_at": _DAY,
        "counterparty_name": "Cloud Hosting Ltd",
        "counterparty_tax_id": supplier[1],
        "counterparty_country": supplier[0],
        "base_total": _BASE,
        "iva_total": _CUOTA,
        "grand_total": _BASE + _CUOTA,
        "currency": "EUR",
        "lines": (
            InvoiceLine(
                description="Servicio de alojamiento en la nube",
                quantity=Decimal("1"),
                unit_price=_BASE,
                subtotal=_BASE,
                iva_rate=IvaRate.from_registry("RATE_21"),
                iva_amount=_CUOTA,
            ),
        ),
        "payment_status": PaymentStatus.PAID,
        "linked_transaction_ids": (transaction_id,),
    }
    if iva_category is not None:
        payload["iva_category"] = iva_category
    return Invoice.model_validate(payload)


def _classify(
    transaction: Transaction, invoice: Invoice, operation: PinnedAuthorityOperation
) -> RentaDeductibleExpenseObservation | RentaLedgerAggregationIssue | None:
    linked = Transaction.model_validate(
        {**transaction.model_dump(mode="python"), "purchase_invoice_evidence_id": invoice.invoice_id},
    )
    return classify_renta_transaction(
        linked,
        invoices=build_invoice_catalogue((invoice,)),
        bucket_id=_BUCKET,
        resolved_period=Period.from_year_and_code(_YEAR, "0A"),
        resolved_profile_year=_YEAR,
        profiles=resolve_category_profiles(_YEAR, operation=operation),
        region_overrides={},
        context=RentaDeductibilityContext(profile_year=_YEAR),
        activity_key="activity-1",
    )


def _reverse_charge_pair() -> tuple[Transaction, Invoice]:
    category = IvaCategory("intra_community_service_acquisition_reverse_charge").value
    payment = _payment(_BASE, label="intra-eu", iva_category=category, iva_amount=_CUOTA)
    invoice = _invoice(
        number="IE-HOST-01", iva_category=category, supplier=_IRISH_SUPPLIER, transaction_id=payment.transaction_id
    )
    return payment, invoice


def test_a_reverse_charge_invoice_settles_for_its_base_without_the_self_assessed_cuota() -> None:
    _, invoice = _reverse_charge_pair()

    assert recipient_self_assesses(invoice)
    assert invoice.grand_total == _BASE + _CUOTA
    assert invoice.iva_total == _CUOTA
    assert invoice_settlement(invoice) == _BASE
    assert invoice_settlement_eur(invoice) == _BASE


def test_a_reverse_charge_purchase_paid_at_its_base_is_admitted_as_an_expense(
    operation: PinnedAuthorityOperation,
) -> None:
    payment, invoice = _reverse_charge_pair()

    result = _classify(payment, invoice, operation)

    assert isinstance(result, RentaDeductibleExpenseObservation), result
    assert result.taxable_base == _BASE
    assert result.iva_amount == _CUOTA


def test_an_ordinary_purchase_paid_short_of_base_plus_iva_is_still_refused(
    operation: PinnedAuthorityOperation,
) -> None:
    category = IvaCategory("domestic_general").value
    payment = _payment(_BASE, label="domestic-short", iva_category=None, iva_amount=Decimal("0.00"))
    invoice = _invoice(
        number="ES-HOST-01", iva_category=category, supplier=_SPANISH_SUPPLIER, transaction_id=payment.transaction_id
    )

    assert not recipient_self_assesses(invoice)
    assert invoice_settlement(invoice) == _BASE + _CUOTA

    result = _classify(payment, invoice, operation)

    assert isinstance(result, RentaLedgerAggregationIssue), result
    assert result.reason is RentaLedgerAggregationIssueReason.AMOUNT_MISMATCH
    assert result.detail == "linked transaction amount does not match invoice grand total"


def test_an_ordinary_purchase_paid_at_base_plus_iva_is_admitted(operation: PinnedAuthorityOperation) -> None:
    category = IvaCategory("domestic_general").value
    payment = _payment(_BASE + _CUOTA, label="domestic-full", iva_category=None, iva_amount=_CUOTA)
    invoice = _invoice(
        number="ES-HOST-02", iva_category=category, supplier=_SPANISH_SUPPLIER, transaction_id=payment.transaction_id
    )

    result = _classify(payment, invoice, operation)

    assert isinstance(result, RentaDeductibleExpenseObservation), result
    assert result.taxable_base == _BASE
