"""Received invoice evidence must not bypass ledger IVA authority.

A domestic reverse charge tells the recipient to self-assess, but an invoice
does not carry the exact deduction family or immutable provenance required for
an IVA input observation.  The invoice screen therefore withholds it and tells
the operator to record the matching classified ledger transaction; it must never
invent a domestic-current deduction merely to preserve a category projection.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from ....domain.invoices import Invoice, IvaRate
from ....domain.iva import InvoiceKind, IvaCategory
from .._modelo_bindings import (
    _invoice_line_iva_observation,
    _missing_invoice_deduction_authority_diagnostics,
    _reverse_charge_cuota_not_derivable,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BASE = Decimal("2000.00")
_DAY = date(2026, 3, 15)


def _received_reverse_charge(*, slot: IvaRate = IvaRate.EXEMPT, cuota: str = "0.00") -> Invoice:
    """A construction supply the recipient must self-assess.

    The supplier charges nothing, which is what an art. 84.Uno.2 invoice looks
    like: a base, a declared treatment, and no cuota.
    """
    total = _BASE + Decimal(cuota)
    return Invoice.model_validate(
        {
            "bucket_id": "29292929-2929-4929-8929-292929292929",
            "kind": InvoiceKind.RECEIVED.value,
            "invoice_number": "F-2026-0077",
            "issued_at": _DAY.isoformat(),
            "counterparty_name": "Constructora Ejemplo SL",
            "counterparty_tax_id": "ESB12345674",
            "counterparty_country": "ES",
            "base_total": format(_BASE, "f"),
            "iva_total": cuota,
            "grand_total": format(total, "f"),
            "currency": "EUR",
            "payment_status": "PENDING",
            "iva_category": IvaCategory.DOMESTIC_REVERSE_CHARGE.value,
            "lines": [
                {
                    "description": "Ejecucion de obra",
                    "quantity": "1",
                    "unit_price": format(_BASE, "f"),
                    "subtotal": format(_BASE, "f"),
                    "iva_rate": slot.value,
                    "iva_amount": cuota,
                },
            ],
        },
    )


def _observation_for(invoice: Invoice):
    return _invoice_line_iva_observation(
        invoice=invoice,
        line=invoice.lines[0],
        line_index=0,
        devengo_date=_DAY,
        recargo_amount=Decimal("0"),
    )


def test_received_reverse_charge_is_withheld_without_ledger_deduction_authority() -> None:
    """An invoice cannot manufacture the authority input IVA rows require."""
    observation = _observation_for(_received_reverse_charge())

    assert observation is None


def test_rated_received_reverse_charge_is_still_withheld_without_ledger_authority() -> None:
    """A rate supplies a cuota tier, not the separate deduction authority."""
    observation = _observation_for(_received_reverse_charge(slot=IvaRate.RATE_21, cuota="420.00"))

    assert observation is None


def test_withheld_received_invoice_names_the_required_ledger_remedy() -> None:
    """The hard cutover remains visible to the operator, not a silent omission."""
    invoice = _received_reverse_charge()

    (diagnostic,) = _missing_invoice_deduction_authority_diagnostics((invoice,), resolver_id="ledger_iva_aggregation")

    assert diagnostic.source_ref == f"invoice:{invoice.invoice_id}"
    assert diagnostic.message.endswith("no deductible IVA is declared on this modelo")
    assert diagnostic.remedy == (
        "Record the matching classified ledger transaction with its exact deduction family and "
        "evidence provenance, then recalculate"
    )


def test_an_underivable_self_assessment_is_reported_not_silent() -> None:
    """The loss is surfaced, because a short return with no signal is the defect.

    The cuota cannot be derived from this record: the line carries an exempt
    slot, so the rate the self-assessment would apply is simply not there. That
    is a legitimate refusal to invent a figure -- and it stops being acceptable
    the moment nobody is told.
    """
    assert _reverse_charge_cuota_not_derivable(_received_reverse_charge()) is True


def test_a_rated_reverse_charge_line_is_not_reported() -> None:
    """A record that CAN support the self-assessment raises no advisory.

    The negative case matters as much as the positive one: an advisory that
    fires on every reverse charge, including the ones carrying a rate, trains the
    operator to ignore the channel. Only the underivable shape is reported.
    """
    rated = _received_reverse_charge(slot=IvaRate.RATE_21, cuota="420.00")

    assert _reverse_charge_cuota_not_derivable(rated) is False
