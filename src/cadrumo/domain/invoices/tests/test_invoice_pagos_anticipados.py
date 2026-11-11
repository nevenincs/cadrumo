"""The pago anticipado devengo contract on the invoice record.

LIVA art. 75.Dos moves devengo forward to the date of collection for an
advance payment received before the hecho imponible, "por los importes
efectivamente percibidos" -- money must actually have been received -- and
its second párrafo excludes "las entregas de bienes comprendidas en el
artículo 25" (an entrega intracomunitaria exenta) from that rule outright:
those always devengue under art. 75.Uno.8.º regardless of any advance.

The invoice records this through the SAME ``operation_date`` /
``operation_date_role`` axis art. 6.1.i already carries for the general-regime
operation date (see ``test_invoice_operation_date.py``); this module tests
the two guards specific to the ``ADVANCE_PAYMENT_RECEIVED`` role.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

import pytest
from pydantic import ValidationError

from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority
from cadrumo.domain.calculations.registry.invoice_legal_classification import require_invoice_operation_date_role
from cadrumo.domain.invoices.enums import resolve_iva_rate_token

from ...calculations.registry.tests.authored_editions import filing_year_envelope
from ...iva.lookup import coexisting_tier_rates
from ...iva.schema import InvoiceKind, IvaCategory, IvaRateKind, spanish_eu_member_state
from ..catalogue import InvoiceCatalogue, decode_authenticated_invoice_catalogue
from ..enums import PaymentStatus
from ..errors import InvoiceValidationError
from ..models import INVOICE_WRITE_ADMISSION, Invoice, InvoiceLine
from ..rule_findings import InvoiceRuleFindingCode
from .invoice_catalogue_seed import window_middle

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


@pytest.fixture(autouse=True)
def _authority_operation() -> Iterator[None]:
    """Validate invoices under the generation-pinned authority production uses."""
    with bundled_indexed_authority().operation():
        yield


_YEAR = filing_year_envelope().horizon
_BASE = Decimal("1000.00")
_CUOTA = Decimal("210.00")
# A date inside the registry's temporary 2 % super-reducido window; only its end
# date is load-bearing, and that is read from the registry.
_WINDOW_PROBE = window_middle("RATE_2")


def _rated_line() -> InvoiceLine:
    return InvoiceLine(
        description="Anticipo de servicios",
        quantity=Decimal("1"),
        unit_price=_BASE,
        subtotal=_BASE,
        iva_rate=resolve_iva_rate_token("RATE_21", date.today()),
        iva_amount=_CUOTA,
    )


def _exempt_line() -> InvoiceLine:
    return InvoiceLine(
        description="Entrega intracomunitaria exenta",
        quantity=Decimal("1"),
        unit_price=_BASE,
        subtotal=_BASE,
        iva_rate=resolve_iva_rate_token("EXEMPT", date.today()),
        iva_amount=Decimal("0"),
    )


def _invoice(**overrides: Any) -> Invoice:
    payload: dict[str, Any] = {
        "kind": InvoiceKind.ISSUED,
        "invoice_number": "2026/ANT-1",
        "issued_at": date(_YEAR, 6, 20),
        "counterparty_name": "Cliente SL",
        "counterparty_tax_id": "B00015016",
        "counterparty_country": "ES",
        "base_total": _BASE,
        "iva_total": _CUOTA,
        "grand_total": _BASE + _CUOTA,
        "currency": "EUR",
        "lines": (_rated_line(),),
        "payment_status": PaymentStatus.PAID,
        "operation_date": date(_YEAR, 6, 10),
        "operation_date_role": require_invoice_operation_date_role("ADVANCE_PAYMENT_RECEIVED"),
    }
    payload.update(overrides)
    return Invoice(**payload)  # type: ignore[arg-type]


def test_a_fully_collected_advance_payment_devengues_on_collection() -> None:
    """The truthful pago anticipado invoice is representable."""
    invoice = _invoice()

    assert invoice.operation_date == date(_YEAR, 6, 10)
    assert invoice.operation_date_role == require_invoice_operation_date_role("ADVANCE_PAYMENT_RECEIVED")


def _payload(**overrides: Any) -> dict[str, Any]:
    return {**_invoice().model_dump(mode="json", exclude={"invoice_id"}), **overrides}


def _rule_finding_code(refusal: ValidationError) -> str:
    cause = refusal.errors()[0]["ctx"]["error"].__cause__
    assert isinstance(cause, InvoiceValidationError)
    assert cause.context is not None
    return str(cause.context["rule_finding_code"])


def _temporary_rate_window() -> tuple[str, date]:
    """Return a rate slot the registry prices only up to an end date, and that date.

    The scenario needs a rate that stops applying between an advance and the
    delivery it pays for. The registry's own temporary super-reducido window
    supplies one, read rather than restated so the dates stay its to answer.
    """
    with bundled_indexed_authority().operation() as operation:
        (window,) = (
            record
            for record in coexisting_tier_rates(
                spanish_eu_member_state(effective_date=_WINDOW_PROBE, authority=operation),
                IvaRateKind("super_reduced"),
                _WINDOW_PROBE,
                operation=operation,
            )
            if record.pct == Decimal("2")
        )
    assert window.effective_until is not None
    return "RATE_2", window.effective_until


def test_write_admission_refuses_an_advance_on_a_partly_collected_price() -> None:
    """Art. 75.Dos devengues "por los importes efectivamente percibidos", not the whole price.

    Base 1,000 at a rate in force only up to an end date; 300 is collected
    before it and the delivery follows after it. One invoice carries one
    devengo date, so admitting it would file all 1,000 in the advance's period
    at the advance-date rate (art. 90.Dos) while 700 devengues at the delivery
    (art. 75.Uno).
    """
    slot, rate_until = _temporary_rate_window()
    advance_collected = rate_until - timedelta(days=20)
    cuota = (_BASE * Decimal("0.02")).quantize(Decimal("0.01"))
    line = InvoiceLine(
        description="Anticipo de 300 sobre una entrega posterior",
        quantity=Decimal("1"),
        unit_price=_BASE,
        subtotal=_BASE,
        iva_rate=resolve_iva_rate_token(slot, advance_collected),
        iva_amount=cuota,
    )
    payload = _payload(
        issued_at=advance_collected.isoformat(),
        operation_date=advance_collected.isoformat(),
        lines=[line.model_dump(mode="json")],
        iva_total=str(cuota),
        grand_total=str(_BASE + cuota),
        payment_status=PaymentStatus.PARTIALLY_PAID.value,
    )

    with pytest.raises(ValidationError) as refusal:
        Invoice.model_validate(payload, context=INVOICE_WRITE_ADMISSION)

    assert _rule_finding_code(refusal.value) == InvoiceRuleFindingCode.ADVANCE_PAYMENT_NOT_FULLY_COLLECTED.value


def test_write_admission_accepts_a_fully_collected_advance() -> None:
    """The control: the same advance, collected in full, is the truthful record and is admitted."""
    invoice = Invoice.model_validate(_payload(), context=INVOICE_WRITE_ADMISSION)

    assert invoice.payment_status is PaymentStatus.PAID


def test_write_admission_leaves_a_partly_paid_performed_operation_alone() -> None:
    """The rule is keyed on the advance role: an ordinary operation date may be partly paid."""
    invoice = Invoice.model_validate(
        _payload(
            payment_status=PaymentStatus.PARTIALLY_PAID.value,
            operation_date_role=require_invoice_operation_date_role("OPERATION_PERFORMED").value,
        ),
        context=INVOICE_WRITE_ADMISSION,
    )

    assert invoice.payment_status is PaymentStatus.PARTIALLY_PAID


def test_a_stored_partly_collected_advance_still_hydrates() -> None:
    """A record written before the rule stays readable, so the operator can open and correct it.

    Both stored decodes are exercised: the authenticated inspection read and
    the plain catalogue decode every write path loads through.
    """
    record = _payload(payment_status=PaymentStatus.PARTIALLY_PAID.value)
    stored_id = Invoice.model_validate(_payload()).invoice_id

    (inspected,) = decode_authenticated_invoice_catalogue({stored_id: {**record, "invoice_id": stored_id}}).values()
    decoded = InvoiceCatalogue.model_validate({"invoices": {stored_id: {**record, "invoice_id": stored_id}}})

    assert inspected.payment_status is PaymentStatus.PARTIALLY_PAID
    assert decoded.invoices[stored_id].payment_status is PaymentStatus.PARTIALLY_PAID


@pytest.mark.parametrize("status", [PaymentStatus.PENDING, PaymentStatus.OVERDUE, PaymentStatus.CANCELLED])
def test_an_advance_payment_role_with_nothing_collected_is_refused(status: PaymentStatus) -> None:
    """Art. 75.Dos devengues on actual cobro; a status stating none happened contradicts the role."""
    with pytest.raises(ValidationError, match="requires a collected payment_status"):
        _invoice(payment_status=status)


def test_the_article_25_exclusion_refuses_an_advance_payment_devengo() -> None:
    """LIVA art. 75.Dos, párrafo segundo: an entrega intracomunitaria exenta is excluded outright.

    This is the load-bearing refusal: without it, the model would accept a
    devengo-shifting declaration the law does not permit for this category,
    silently misattributing the operation's period.
    """
    with pytest.raises(ValidationError, match="does not apply to an entrega intracomunitaria exenta"):
        _invoice(
            counterparty_country="DE",
            counterparty_tax_id="DE123456789",
            lines=(_exempt_line(),),
            iva_total=Decimal("0"),
            grand_total=_BASE,
            iva_category=IvaCategory("intra_community_supply"),
        )


def test_the_same_amounts_devengue_normally_without_the_advance_payment_role() -> None:
    """The control: an ordinary operation date on the same category is unaffected.

    Proves the exclusion is keyed on the ADVANCE_PAYMENT_RECEIVED role, not on
    the category alone -- otherwise this case would also be wrongly refused.
    """
    invoice = _invoice(
        counterparty_country="DE",
        counterparty_tax_id="DE123456789",
        lines=(_exempt_line(),),
        iva_total=Decimal("0"),
        grand_total=_BASE,
        iva_category=IvaCategory("intra_community_supply"),
        operation_date_role=require_invoice_operation_date_role("OPERATION_PERFORMED"),
    )

    assert invoice.operation_date_role == require_invoice_operation_date_role("OPERATION_PERFORMED")
