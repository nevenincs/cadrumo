"""Per-class outcomes for slim records the canonical aggregate cannot hold.

The slim business-operation store is retired onto the canonical
:class:`~domain.invoices.Invoice`, and that is a NARROWING of the operator
input contract rather than a re-home: the slim model carries no cross-field
validator at all, while the canonical aggregate requires a non-empty
counterparty name, a two-letter country, at least one line, an exact totals
identity, and a rate drawn from a closed enum.

So a set of record shapes is valid as slim and unrepresentable as canonical.
This module states the outcome for each such class and proves it, one test per
class, each building the shape that is legal on the slim side.

**No data migration is written, and none is intended.** The regime is
pre-release, so there is no released data to carry across; the fold is the
operator re-entering records through the canonical verbs, not an automated
rewrite. That makes the fold rule for almost every class the same thing: the
canonical model REFUSES the shape, loudly and by name, at the moment the
record is offered. The rule being enforced by an invariant rather than by
migration code is what makes it durable -- there is no conversion path that
could later grow a silent coercion.

The one standard every outcome here is held to: a record that cannot be
represented must fail LOUDLY, never be silently dropped and never be silently
coerced into a different number. A wrong figure that looks clean is worse than
a refusal, because a filing rests on it.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from ....domain.invoices.enums import InvoiceClass, IvaRate, PaymentStatus
from ....domain.invoices.models import Invoice, InvoiceLine
from ....domain.iva import InvoiceKind

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _canonical_payload(**overrides: object) -> dict[str, object]:
    """A canonical payload that validates, so each test varies ONE axis.

    Every refusal below must be attributable to the class under test. Building
    each case from a known-good baseline is what makes that true: without it a
    test could pass on an unrelated invariant and be read as proving the class
    it names.
    """
    payload: dict[str, object] = {
        "kind": InvoiceKind.ISSUED,
        "invoice_number": "F-2026-FOLD-001",
        "issued_at": date(2026, 3, 10),
        "counterparty_name": "Cliente Valido SL",
        "counterparty_tax_id": "B12345674",
        "counterparty_country": "ES",
        "base_total": Decimal("100.00"),
        "iva_total": Decimal("21.00"),
        "grand_total": Decimal("121.00"),
        "currency": "EUR",
        "lines": (
            InvoiceLine(
                description="Servicio",
                quantity=Decimal("1"),
                unit_price=Decimal("100.00"),
                subtotal=Decimal("100.00"),
                iva_rate=IvaRate.RATE_21,
                iva_amount=Decimal("21.00"),
            ),
        ),
        "payment_status": PaymentStatus.PENDING,
    }
    payload.update(overrides)
    return payload


def test_the_baseline_payload_is_representable() -> None:
    """Anti-tautology control for every refusal in this module.

    If the baseline itself did not validate, each test below would pass for the
    wrong reason and the module would assert nothing about the class it names.
    """
    assert Invoice.model_validate(_canonical_payload()).invoice_number == "F-2026-FOLD-001"


def test_an_empty_counterparty_name_refuses() -> None:
    """RULE: refuse. The slim model defaults this to the empty string.

    Not synthesisable. The counterparty's legal name is declared on M347, so
    the only alternatives to refusing are inventing a name or filing a blank
    one, and both put a value into a return that nobody observed. The operator
    knows the name; the fold does not.
    """
    with pytest.raises(ValidationError):
        Invoice.model_validate(_canonical_payload(counterparty_name=""))


def test_a_missing_counterparty_country_refuses() -> None:
    """RULE: refuse. The slim model permits a null country.

    Deliberately NOT derived from a tax-id prefix here. The country routes both
    informativas, and the canonical aggregate's own rule is that a non-domestic
    country forces the tax id to be that country's NIF-IVA -- so deriving one
    from the other would make the two fields agree by construction and destroy
    the cross-check. The operator states it, which is why the canonical entry
    verbs now require it.
    """
    payload = _canonical_payload()
    del payload["counterparty_country"]
    with pytest.raises(ValidationError):
        Invoice.model_validate(payload)


def test_totals_that_do_not_reconcile_refuse() -> None:
    """RULE: refuse. The slim model has no cross-field validator at all.

    The most important refusal in this module. The alternatives to refusing are
    adjusting the total to match the lines or the lines to match the total, and
    each silently files a number the source document did not state. A record
    whose own arithmetic disagrees is evidence of an error upstream, and the
    fold is not the place to guess which figure was right.
    """
    with pytest.raises(ValidationError):
        Invoice.model_validate(_canonical_payload(grand_total=Decimal("999.00")))


def test_a_record_with_no_lines_refuses() -> None:
    """RULE: refuse the payload, but the WRITER supplies a line.

    Both halves are true and the distinction matters. The slim record has no
    line concept, so a bare fold of its fields has nothing to put here and the
    model refuses. An operator re-entering the same invoice through the
    canonical verb does not meet this refusal, because the builder synthesises
    a line from the base and rate.

    That synthesis is a representation change, not a value change: the line
    carries exactly the base and cuota the slim record already held. It invents
    no figure, which is why it is the one class where supplying a value rather
    than refusing is honest.
    """
    with pytest.raises(ValidationError):
        Invoice.model_validate(_canonical_payload(lines=()))


def test_a_rate_outside_the_closed_enum_refuses_rather_than_rounding() -> None:
    """RULE: refuse. The slim rate is a bare decimal, the canonical one an enum.

    Never round to the nearest member. The enum deliberately omits the
    transient 2022-2024 5% rate, so a pre-2025 document is exactly the case
    that must refuse. Rounding an unread rate to the nearest member, or letting
    it fall to the exempt slot, mints a zero-cuota invoice whose printed total
    still shows the cuota that was charged -- a silent under-declaration
    carrying a plausible-looking document behind it.
    """
    with pytest.raises(ValidationError):
        InvoiceLine(
            description="Servicio",
            quantity=Decimal("1"),
            unit_price=Decimal("100.00"),
            subtotal=Decimal("100.00"),
            iva_rate=Decimal("5"),
            iva_amount=Decimal("5.00"),
        )


def test_a_tax_id_that_does_not_match_its_country_refuses() -> None:
    """RULE: refuse. A class the original inventory did not name.

    The slim model couples neither field, so a domestic-format NIF against a
    foreign country is representable there. The canonical model validates the
    tax id against the country's published NIF-IVA pattern and refuses.

    This is the population a field-list inventory cannot predict: both stores
    carry both fields, so a presence comparison finds parity, and the
    incompatibility lives entirely in the cross-field rule one side has.
    """
    with pytest.raises(ValidationError):
        Invoice.model_validate(
            _canonical_payload(counterparty_country="DE", counterparty_tax_id="B12345674"),
        )


def test_a_simplificada_without_a_counterparty_tax_id_is_representable() -> None:
    """RULE: accept, but only when the record SAYS it is a simplificada.

    The one class where canonical is more permissive than slim -- and it is
    permissive precisely, not loosely. A factura simplificada legitimately
    carries no counterparty tax id, and the slim model cannot represent one at
    all because it requires a non-empty NIF. The canonical model accepts the
    omission only on an invoice explicitly declared SIMPLIFICADA and ISSUED:
    on a RECEIVED invoice the same field names the issuer's own identity and
    stays mandatory.

    So "canonical permits a null tax id" would be the wrong reading. It permits
    it on exactly the shape where the document really has none, and the
    informativa projection then excludes that record on a stated legal ground
    rather than by accident -- it has nothing M347 or M349 can declare about a
    third party.

    Recorded as a class because the fold makes it representable in the store
    that feeds the informativas for the first time, so it is a NEW population
    for the decomposition and renta-evidence paths even though it is a
    capability gain rather than a loss.
    """
    payload = _canonical_payload(invoice_class=InvoiceClass.SIMPLIFICADA)
    del payload["counterparty_tax_id"]

    invoice = Invoice.model_validate(payload)

    assert invoice.counterparty_tax_id is None
    assert invoice.invoice_class is InvoiceClass.SIMPLIFICADA


def test_a_received_invoice_without_a_tax_id_refuses_even_as_simplificada() -> None:
    """Positive control bounding the acceptance above.

    Without this, the acceptance test could be read as "the canonical model
    tolerates a missing tax id", which would make the fold look safe for a
    population it actually refuses. The permissiveness is bounded to the issued
    side, where the omission reflects the real document.
    """
    payload = _canonical_payload(
        kind=InvoiceKind.RECEIVED,
        invoice_class=InvoiceClass.SIMPLIFICADA,
    )
    del payload["counterparty_tax_id"]

    with pytest.raises(ValidationError):
        Invoice.model_validate(payload)
