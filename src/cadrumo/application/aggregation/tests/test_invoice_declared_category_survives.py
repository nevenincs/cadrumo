"""A declared IVA treatment must reach the record, and its loss must be reported.

The invoice projection derived an observation's category from the line's RATE
SLOT even when the invoice DECLARED one. For a received domestic reverse charge
(LIVA art. 84.Uno.2) that is doubly wrong: the supplier charges no cuota, so the
line carries an exempt slot, and the projection turned a declared
``domestic_reverse_charge`` into ``domestic_exempt`` at flow ``soportado``. The
same operation recorded as a bank row is classified correctly, because that path
reads the declared category first and derives the flow from it.

Two things are asserted here and they must not be confused with each other.

The record now STATES what the document stated. That is worth having on its own:
a record that silently relabels a reverse charge as an exemption is wrong on its
face, and every later reader inherits the wrong label.

It does NOT make the operation declare. The recipient-side binding selector is a
triple -- category, rate kind, flow -- and an exempt-slot line still carries the
wrong rate kind, so it selects nothing even with the category and the flow both
correct. That is asserted explicitly, so nobody reads this change as closing the
self-assessment gap. What closes that is a decision about whether an invoice line
may carry a rated slot with a zero cuota, which is open.

Because the loss remains, it is reported rather than left silent: the operator is
told the cuota could not be derived, through the same advisory channel that
already reports an invoice withheld for a category its counterparty contradicts.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from ....core import IvaDeductionEvidenceAuthority, IvaDeductionFactKind
from ....core.resources import resources
from ....domain.calculations.registry import IvaLedgerObservation
from ....domain.invoices import Invoice, IvaRate
from ....domain.iva import (
    InvoiceKind,
    IvaCategory,
    IvaDeductionClassificationProvenance,
    IvaFlowDirection,
    IvaRateKind,
)
from .._iva_ledger import resolve_iva_ledger_binding_values
from .._modelo_bindings import (
    _invoice_line_iva_observation,
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
        deduction_authority=_received_reverse_charge_deduction_authority(),
    )


def _received_reverse_charge_deduction_authority() -> IvaLedgerObservation:
    """The exact frozen ledger authority required for received input IVA."""
    return IvaLedgerObservation(
        ledger_id="transaction:received-reverse-charge",
        transaction_date=_DAY,
        category=IvaCategory.DOMESTIC_REVERSE_CHARGE,
        rate_kind=IvaRateKind.EXEMPT,
        flow_direction=IvaFlowDirection.INVERSION_SUJETO_PASIVO,
        base_amount=_BASE,
        iva_amount=Decimal("0"),
        deduction_fact_kind=IvaDeductionFactKind.DOMESTIC_CURRENT,
        deduction_provenance=IvaDeductionClassificationProvenance(
            authority=IvaDeductionEvidenceAuthority.INVOICE_EVIDENCE,
            source_locator="invoice:received-reverse-charge",
            evidence_digest="a" * 64,
        ),
    )


def test_the_declared_reverse_charge_survives_the_projection() -> None:
    """The observation states the treatment the invoice declared.

    Asserted on the flow as well as the category, because the two are separate
    losses. A preserved category at flow ``soportado`` would still describe the
    recipient as merely bearing input tax rather than self-assessing output tax,
    which is the substance of what a reverse charge is.
    """
    observation = _observation_for(_received_reverse_charge())

    assert observation is not None
    assert observation.category is IvaCategory.DOMESTIC_REVERSE_CHARGE, (
        f"the declared treatment was overwritten from the rate slot: {observation.category.value}"
    )
    assert observation.flow_direction is IvaFlowDirection.INVERSION_SUJETO_PASIVO, (
        f"the recipient is not recorded as self-assessing: {observation.flow_direction.value}"
    )
    assert observation.base_amount == _BASE


def test_the_preserved_category_does_not_by_itself_declare_the_cuota() -> None:
    """The honest half: the record is right and the return is still short.

    Pinned deliberately. The recipient-side selector is a triple and only two of
    its three conditions are now satisfied -- the rate kind is still ``exempt``
    because the line carries no rated slot. Asserting this stops the change being
    read, later and by someone else, as having closed the self-assessment gap.
    """
    observation = _observation_for(_received_reverse_charge())
    assert observation is not None
    revision = resources().modelos.authority.snapshot("303", filing_year=2026, period="2T").revision

    resolved = {str(k): v for k, v in resolve_iva_ledger_binding_values(revision, (observation,)).items()}

    assert not any(resolved.values()), (
        f"this change is not supposed to route anything yet, but it did: "
        f"{ {k: str(v) for k, v in resolved.items() if v} }"
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
