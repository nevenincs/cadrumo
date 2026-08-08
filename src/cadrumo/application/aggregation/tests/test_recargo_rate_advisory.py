"""The recorded recargo is compared against art. 161, and never replaced by it.

The accepted source-of-truth record settles what establishes a recargo de
equivalencia cuota: the supplier charges it and the invoice records it, so the
invoice is the document of record and the figure it carries is the one that
reaches the return. Deriving the cuota from the rate table was considered and
rejected, because a computed figure that disagrees with a real invoice is wrong
about that transaction however well grounded the computation is.

What the record adds is the other half of that posture. An operator entering a
wrong recargo today produces a wrong return with no signal at all, and AEAT can
see the contradiction from the filed record without any audit -- the design
prints each rung's Tipo as a constant, so a declared base and cuota that do not
pair arithmetically are detectable on their face.

So the table becomes a validation reference. It compares, it says so when the
two differ, and it changes nothing.

THE SILENCES ARE THE DESIGN, not gaps in it, and each is asserted below. The
advisory must not fire where the table has no opinion: an unmodelled window is a
gap in OUR data, and reporting it as a mismatch would turn that gap into an
accusation about the supplier's invoice. That case is the one most likely to be
"fixed" later by someone who reads silence as an oversight, which is why it
carries its own test rather than being covered incidentally.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from ....domain.invoices import Invoice, IvaRate
from ....domain.iva import InvoiceKind, IvaCategory
from .._modelo_bindings import (
    _recargo_rate_divergence,
    _recargo_rate_mismatch_diagnostics,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BASE = Decimal("1000.00")

#: Inside the ordinary art. 161 pairing: 21 % general carries 5,2 % recargo.
_ORDINARY_DAY = date(2025, 6, 15)

#: Before Ley 41/1994 art. 78.Segundo, so no ES window of any tier covers it and
#: the table has nothing to say about any rate.
_UNCOVERED_DAY = date(1994, 6, 15)


def _recargo_invoice(*, recargo: str, day: date = _ORDINARY_DAY, slot: IvaRate = IvaRate.RATE_21) -> Invoice:
    """A retailer's purchase invoice bearing recargo de equivalencia."""
    cuota = Decimal("210.00")
    total = _BASE + cuota + Decimal(recargo)
    return Invoice.model_validate(
        {
            "bucket_id": "31313131-3131-4131-8131-313131313131",
            "kind": InvoiceKind.RECEIVED.value,
            "invoice_number": "F-2025-0451",
            "issued_at": day.isoformat(),
            "counterparty_name": "Mayorista Ejemplo SL",
            "counterparty_tax_id": "ESB12345674",
            "counterparty_country": "ES",
            "base_total": format(_BASE, "f"),
            "iva_total": format(cuota, "f"),
            "recargo_amount": recargo,
            "grand_total": format(total, "f"),
            "currency": "EUR",
            "payment_status": "PENDING",
            "iva_category": IvaCategory.RECARGO_EQUIVALENCIA.value,
            "lines": [
                {
                    "description": "Genero para reventa",
                    "quantity": "1",
                    "unit_price": format(_BASE, "f"),
                    "subtotal": format(_BASE, "f"),
                    "iva_rate": slot.value,
                    "iva_amount": format(cuota, "f"),
                },
            ],
        },
    )


def test_a_recargo_matching_the_published_rate_raises_nothing() -> None:
    """The ordinary invoice is silent, and that is what keeps the advisory usable.

    1000,00 at the 21 % general rate pairs with 5,2 % under art. 161, so 52,00 is
    exactly right. An advisory that also fired here would fire on nearly every
    recargo invoice, and an operator who sees it on correct documents stops
    reading it -- which costs more than never having built it.
    """
    assert _recargo_rate_divergence(_recargo_invoice(recargo="52.00"), devengo_date=_ORDINARY_DAY) is None


def test_a_mistyped_recargo_is_reported_with_both_figures() -> None:
    """The wrong-entry case, which is silent today.

    Asserted on both figures rather than on the fact of a mismatch: an advisory
    that says only "these disagree" cannot be acted on, because the operator
    cannot tell which of the two to go and check.
    """
    divergence = _recargo_rate_divergence(_recargo_invoice(recargo="25.00"), devengo_date=_ORDINARY_DAY)

    assert divergence is not None
    assert divergence.recorded == Decimal("25.00")
    assert divergence.expected == Decimal("52.00")
    assert divergence.recargo_rate == Decimal("0.052")


def test_an_uncovered_date_stays_silent_rather_than_alleging_a_mismatch() -> None:
    """The silence that must survive, and the one most likely to be removed.

    Before 1995 the table holds no ES window at all, so it has no opinion about
    what this invoice should carry. Reporting that as a mismatch would convert a
    gap in our own data into a claim that the supplier's invoice is wrong.

    A later reader finding this branch may well read it as an unhandled case.
    It is not: an unmodelled window and a wrong figure are different facts and
    only one of them is the operator's to act on.
    """
    invoice = _recargo_invoice(recargo="999.00", day=_UNCOVERED_DAY)

    assert _recargo_rate_divergence(invoice, devengo_date=_UNCOVERED_DAY) is None


def test_an_invoice_bearing_no_recargo_is_not_this_screens_business() -> None:
    """An ordinary invoice carries no recargo, and absence is not a divergence of zero."""
    assert _recargo_rate_divergence(_recargo_invoice(recargo="0.00"), devengo_date=_ORDINARY_DAY) is None


def test_the_advisory_names_the_provision_and_disclaims_the_correction() -> None:
    """Two properties the message must carry, for different reasons.

    It names art. 161, because an advisory that cites no authority reads as the
    application second-guessing the supplier and gets dismissed.

    It states that the recorded figure is the one declared, because this is a
    diagnostic and not a correction. Without that sentence an operator may
    reasonably assume the application has already substituted the computed
    figure, and file believing something the record does not do.
    """
    divergence = _recargo_rate_divergence(_recargo_invoice(recargo="25.00"), devengo_date=_ORDINARY_DAY)
    assert divergence is not None

    diagnostics = _recargo_rate_mismatch_diagnostics((divergence,), resolver_id="test-resolver")

    assert len(diagnostics) == 1
    message = diagnostics[0].message
    assert "art. 161" in message
    assert "25.00" in message
    assert "52.00" in message
    assert "does not change it" in message
    assert diagnostics[0].reason == "invoice_recargo_departs_from_published_rate"


def test_the_advisory_is_not_a_refusal() -> None:
    """A divergence yields a diagnostic and nothing that stops a filing.

    Refusing on mismatch was considered and rejected: a legitimate invoice can
    carry a figure the table does not predict, and blocking a correct filing on
    a correct invoice is the worse error. Pinned so a later author does not
    "harden" the advisory into a refusal and read that as an improvement.
    """
    divergence = _recargo_rate_divergence(_recargo_invoice(recargo="25.00"), devengo_date=_ORDINARY_DAY)
    assert divergence is not None

    diagnostics = _recargo_rate_mismatch_diagnostics((divergence,), resolver_id="test-resolver")

    # The declared figure is untouched by the comparison.
    assert divergence.invoice.recargo_amount == Decimal("25.00")
    assert all(diagnostic.remedy is not None for diagnostic in diagnostics)
