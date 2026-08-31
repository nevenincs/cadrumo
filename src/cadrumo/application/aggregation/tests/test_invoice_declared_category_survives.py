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
from ....domain.calculations.registry.authority import bundled_authority
from ....domain.calculations.registry.ledger_bindings import IvaLedgerObservation
from ....domain.invoices import Invoice, IvaRate
from ....domain.iva import (
    InvoiceKind,
    IvaCategory,
    IvaDeductionClassificationProvenance,
    IvaFlowDirection,
    IvaLedgerObservationRole,
    IvaRateKind,
)
from .._iva_ledger import resolve_iva_ledger_binding_values
from .._modelo_bindings import (
    _invoice_line_iva_observation,
    _reverse_charge_cuota_not_derivable,
    _screened_invoice_iva_result,
    _uncovered_withheld_invoice_cuota,
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
    line = invoice.lines[0]
    base_amount_eur = invoice.line_amount_eur(line.subtotal)
    iva_amount_eur = invoice.line_amount_eur(line.iva_amount)
    assert base_amount_eur is not None
    assert iva_amount_eur is not None
    return _invoice_line_iva_observation(
        invoice=invoice,
        line=line,
        line_index=0,
        devengo_date=_DAY,
        recargo_amount=Decimal("0"),
        base_amount_eur=base_amount_eur,
        iva_amount_eur=iva_amount_eur,
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
        observation_role=IvaLedgerObservationRole.SETTLEMENT,
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
    revision = bundled_authority().snapshot("303", filing_year=2026, period="2T").revision

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


def test_a_cuota_bearing_received_invoice_is_withheld_when_no_ledger_authority_is_linked() -> None:
    """An invoice never manufactures the deduction authority an input row needs.

    An invoice carries an amount and a direction. It does not carry the exact
    statutory deduction family, nor the immutable evidence provenance that
    separates a domestic current expense from an investment, an import, an
    acquisition or a rectification. That authority lives on the frozen
    transaction-ledger observation the invoice is linked to.

    So the screen withholds the invoice rather than defaulting it to
    domestic-current, and says so on ``deduction_authority_missing`` -- which the
    silence guard turns into a refusal naming the transaction ledger as the
    producer that must supply the missing facts. Defaulting instead would invent
    a statutory fact, and the invented value would be indistinguishable from a
    recorded one everywhere downstream.
    """
    rated = _received_reverse_charge(slot=IvaRate.RATE_21, cuota="420.00")

    screened = _screened_invoice_iva_result(rated, ledger_observations=())

    assert screened.deduction_authority_missing is True
    assert screened.observations == ()


def test_a_linked_ledger_authority_is_copied_onto_the_projection_not_reinvented() -> None:
    """The complement: with the authority linked, the row projects and carries it.

    The point of withholding is not that received invoices are unroutable -- it
    is that their deduction identity must come from the ledger. Once the link
    exists, the exact family and provenance are copied across UNCHANGED. Asserted
    against the authority object itself rather than against literals, because a
    literal would still pass if the projection substituted its own default.
    """
    authority = _received_reverse_charge_deduction_authority()
    linked = _received_reverse_charge(slot=IvaRate.RATE_21, cuota="420.00").model_copy(
        update={"linked_transaction_ids": (authority.ledger_id,)},
    )

    screened = _screened_invoice_iva_result(linked, ledger_observations=(authority,))

    assert screened.deduction_authority_missing is False
    (observation,) = screened.observations
    assert observation.deduction_fact_kind is authority.deduction_fact_kind
    assert observation.deduction_provenance == authority.deduction_provenance


def test_a_withheld_invoice_the_ledger_already_carries_is_not_counted_as_uncovered() -> None:
    """Withholding the row is unconditional; refusing the whole filing is not.

    An unlinked purchase invoice whose cuota the transaction ledger ALREADY
    carries is corroborating evidence of an operation that is declared. The
    totals are right, so there is nothing silent to refuse over -- the operator
    is told through the diagnostic channel instead. Refusing here would block a
    correct filing purely because an invoice-to-transaction link is absent.
    """
    rated = _received_reverse_charge(slot=IvaRate.RATE_21, cuota="420.00")

    uncovered = _uncovered_withheld_invoice_cuota(
        (rated,),
        screened_bindings=("modelo-303-iva-soportado-interiores-cuota",),
        transaction_binding_values={"modelo-303-iva-soportado-interiores-cuota": Decimal("420.00")},
    )

    assert uncovered == Decimal("0")


def test_a_withheld_invoice_absent_from_the_ledger_is_counted_as_uncovered() -> None:
    """The other half, and the reason the refusal still exists.

    With no matching ledger cuota the invoice's input IVA reaches no casilla at
    all. That is the genuine gap this guard was built for, so it is reported as
    an excess and the caller refuses rather than quietly filing short. Asserted
    on the exact shortfall, not merely on being positive, because a guard that
    fires with the wrong magnitude tells the operator to look in the wrong place.
    """
    rated = _received_reverse_charge(slot=IvaRate.RATE_21, cuota="420.00")

    uncovered = _uncovered_withheld_invoice_cuota(
        (rated,),
        screened_bindings=("modelo-303-iva-soportado-interiores-cuota",),
        transaction_binding_values={"modelo-303-iva-soportado-interiores-cuota": Decimal("100.00")},
    )

    assert uncovered == Decimal("320.00")
