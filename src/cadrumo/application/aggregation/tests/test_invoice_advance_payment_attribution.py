"""A stored pago anticipado on a partly collected price is refused, not attributed.

LIVA art. 75.Dos devengues an advance "por los importes efectivamente
percibidos", and art. 90.Dos applies the rate in force at devengo. An invoice
carries one devengo date, so a record that claims the advance role while only
part of its price is collected would file the whole base in the advance's
period at the advance-date rate. Write admission refuses that record now; one
stored earlier still hydrates, and the invoice IVA screen must refuse it rather
than produce that figure.

The screen runs for real over the published authority; only the catalogue read
is an in-memory boundary, and it decodes the stored record the way the store's
catalogue decode does.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from typing import Any

import pytest

from ....core.period import Period
from ....domain.calculations.registry.authority import bundled_indexed_authority
from ....domain.calculations.registry.invoice_legal_classification import require_invoice_operation_date_role
from ....domain.invoices.catalogue import InvoiceCatalogue
from ....domain.invoices.enums import PaymentStatus, resolve_iva_rate_token
from ....domain.invoices.models import Invoice, InvoiceLine
from ....domain.invoices.tests.invoice_catalogue_seed import window_middle
from ....domain.iva.lookup import coexisting_tier_rates
from ....domain.iva.schema import InvoiceKind, IvaRateKind, spanish_eu_member_state
from ..errors import AggregationValidationError
from ..invoice_devengo import invoice_devengo_in_period
from ..modelo_bindings_invoice_iva import ScreenedInvoiceIva, screened_invoice_iva_observations

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]

_BUCKET_ID = "31313131-3131-4131-8131-313131313131"
_BASE = Decimal("1000.00")
_RATE = Decimal("0.02")
# A date inside the registry's temporary 2 % super-reducido window; only the
# window's end date is load-bearing, and that is read from the registry.
_WINDOW_PROBE = window_middle("RATE_2")


def _rate_until() -> date:
    with bundled_indexed_authority().operation() as operation:
        (window,) = (
            record
            for record in coexisting_tier_rates(
                spanish_eu_member_state(effective_date=_WINDOW_PROBE, authority=operation),
                IvaRateKind("super_reduced"),
                _WINDOW_PROBE,
                operation=operation,
            )
            if record.pct == _RATE * 100
        )
    assert window.effective_until is not None
    return window.effective_until


def _quarter_of(day: date) -> Period:
    return Period.from_year_and_code(day.year, f"{(day.month - 1) // 3 + 1}T")


def _stored_record(advance_collected: date, payment_status: PaymentStatus) -> dict[str, Any]:
    """Return a stored invoice record: base 1,000 at the temporary rate, advance-dated."""
    cuota = (_BASE * _RATE).quantize(Decimal("0.01"))
    admitted = Invoice.model_validate(
        {
            "bucket_id": _BUCKET_ID,
            "kind": InvoiceKind.ISSUED,
            "invoice_number": "ANT-300",
            "issued_at": advance_collected,
            "counterparty_name": "Cliente Anticipo SL",
            "counterparty_tax_id": "B00015016",
            "counterparty_country": "ES",
            "base_total": _BASE,
            "iva_total": cuota,
            "grand_total": _BASE + cuota,
            "currency": "EUR",
            "lines": (
                InvoiceLine(
                    description="Entrega posterior con anticipo",
                    quantity=Decimal("1"),
                    unit_price=_BASE,
                    subtotal=_BASE,
                    iva_rate=resolve_iva_rate_token("RATE_2", advance_collected),
                    iva_amount=cuota,
                ),
            ),
            "payment_status": PaymentStatus.PAID,
            "operation_date": advance_collected,
            "operation_date_role": require_invoice_operation_date_role("ADVANCE_PAYMENT_RECEIVED"),
        },
    )
    return {**admitted.model_dump(mode="json"), "payment_status": payment_status.value}


class _StoredInvoices:
    """Decode stored records as the store's catalogue decode does, on every load."""

    bucket_id: str = _BUCKET_ID

    def __init__(self, *records: dict[str, Any]) -> None:
        self._records = {str(record["invoice_id"]): record for record in records}

    def exists(self) -> bool:
        return True

    def load(self) -> InvoiceCatalogue:
        return InvoiceCatalogue.model_validate({"invoices": self._records})

    def save(self, catalogue: InvoiceCatalogue) -> None:
        raise AssertionError("the screen must not write the catalogue it reads")


def _screen(period: Period, *records: dict[str, Any]) -> ScreenedInvoiceIva:
    with bundled_indexed_authority().operation() as operation:
        return screened_invoice_iva_observations(
            _StoredInvoices(*records).load(),
            bucket_id=_BUCKET_ID,
            period=period,
            linked_movements={},
            operation=operation,
        )


def test_the_screen_refuses_a_stored_advance_on_a_partly_collected_price() -> None:
    """300 collected before the rate ends, delivery after it: no figure is produced for the period."""
    advance_collected = _rate_until() - timedelta(days=20)
    record = _stored_record(advance_collected, PaymentStatus.PARTIALLY_PAID)

    with pytest.raises(AggregationValidationError) as refusal:
        _screen(_quarter_of(advance_collected), record)

    assert refusal.value.context is not None
    assert refusal.value.context["reason"] == "invoice_advance_payment_partially_collected"
    assert refusal.value.context["invoice_id"] == record["invoice_id"]


def test_a_period_after_the_advance_is_refused_too() -> None:
    """The remainder devengues at a delivery the record does not date, so a later period cannot be answered."""
    advance_collected = _rate_until() - timedelta(days=20)
    record = _stored_record(advance_collected, PaymentStatus.PARTIALLY_PAID)
    invoice = InvoiceCatalogue.model_validate({"invoices": {record["invoice_id"]: record}}).invoices[
        record["invoice_id"]
    ]
    after = _quarter_of(_rate_until() + timedelta(days=1))

    with pytest.raises(AggregationValidationError):
        invoice_devengo_in_period(invoice, period=after)


def test_a_period_ending_before_the_advance_is_unaffected() -> None:
    """Neither the advance nor the remainder can devengar before the advance was collected."""
    advance_collected = _rate_until() - timedelta(days=20)
    record = _stored_record(advance_collected, PaymentStatus.PARTIALLY_PAID)
    invoice = InvoiceCatalogue.model_validate({"invoices": {record["invoice_id"]: record}}).invoices[
        record["invoice_id"]
    ]
    before = _quarter_of(_quarter_of(advance_collected).start_date - timedelta(days=1))

    assert invoice_devengo_in_period(invoice, period=before) is False


def test_a_fully_collected_advance_is_compared_at_its_collection_date() -> None:
    """The control: the PAID advance is the truthful record and reaches the screen's comparison."""
    advance_collected = _rate_until() - timedelta(days=20)
    record = _stored_record(advance_collected, PaymentStatus.PAID)

    screened = _screen(_quarter_of(advance_collected), record)

    assert screened.invoice_ids == (record["invoice_id"],)
    assert {observation.transaction_date for observation in screened.observations} == {advance_collected}
    assert sum((observation.base_amount for observation in screened.observations), Decimal("0")) == _BASE
