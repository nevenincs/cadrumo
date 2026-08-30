"""Tests for LIVA art. 75 devengo resolution and invoice period attribution.

Three things are pinned here. The resolution itself -- that the invoice's own
recorded ``operation_date`` (under either art. 75 role) is preferred over the
issue-date proxy, and that the proxy is the correct fallback when no
``operation_date`` was ever recorded. The RANK that comes with it, without
which a consumer cannot tell a declared legal fact from a substitute. And the
period attribution built on both: an operation performed in one quarter and
invoiced in the next belongs to the quarter it was performed, which is the
boundary case the whole mechanism exists for.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

import pytest

from ....core import Period
from ....core.aggregation import InvoiceDevengoRank
from ....domain.invoices.enums import InvoiceOperationDateRole, IvaRate, PaymentStatus
from ....domain.invoices.models import Invoice, InvoiceLine
from ....domain.iva.classification import InvoiceKind
from .. import (
    DIAGNOSTIC_MESSAGE_MAX_LENGTH,
    invoice_devengo_in_period,
    proxy_attributed_invoice_ids,
    resolve_invoice_devengo,
)
from .._invoice_devengo import devengo_proxy_attribution_diagnostics

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BASE = Decimal("1000.00")
_CUOTA = Decimal("210.00")


def _line() -> InvoiceLine:
    return InvoiceLine(
        description="Servicios profesionales",
        quantity=Decimal("1"),
        unit_price=_BASE,
        subtotal=_BASE,
        iva_rate=IvaRate.RATE_21,
        iva_amount=_CUOTA,
    )


def _invoice(**overrides: Any) -> Invoice:
    payload: dict[str, Any] = {
        "kind": InvoiceKind.ISSUED,
        "invoice_number": "2026/DEV-1",
        "issued_at": date(2026, 4, 15),
        "counterparty_name": "Cliente SL",
        "counterparty_tax_id": "B12345674",
        "counterparty_country": "ES",
        "base_total": _BASE,
        "iva_total": _CUOTA,
        "grand_total": _BASE + _CUOTA,
        "currency": "EUR",
        "lines": (_line(),),
        "payment_status": PaymentStatus.PAID,
    }
    payload.update(overrides)
    return Invoice(**payload)  # type: ignore[arg-type]


def test_an_undated_invoice_falls_back_to_the_issue_date_proxy() -> None:
    """No recorded operation date: the only date on the record is the proxy."""
    devengo = resolve_invoice_devengo(_invoice())

    assert devengo.devengo_date == date(2026, 4, 15)
    assert devengo.rank is InvoiceDevengoRank.ISSUE_DATE_PROXY


def test_a_recorded_operation_date_takes_precedence_over_the_issue_date() -> None:
    """Art. 75.Uno: the general-regime devengo date, when it differs from issue."""
    devengo = resolve_invoice_devengo(
        _invoice(
            operation_date=date(2026, 3, 28),
            operation_date_role=InvoiceOperationDateRole.OPERATION_PERFORMED,
        ),
    )

    assert devengo.devengo_date == date(2026, 3, 28)
    assert devengo.rank is InvoiceDevengoRank.OPERATION_DATE_DECLARED


def test_a_pago_anticipado_collection_date_is_read_identically() -> None:
    """Art. 75.Dos: the collection date is the devengo date, read the same way.

    The role changes WHICH clause supplied the date, not how this helper reads
    it -- both cases resolve to the recorded ``operation_date`` and both rank
    as a declared fact.
    """
    devengo = resolve_invoice_devengo(
        _invoice(
            operation_date=date(2026, 4, 1),
            operation_date_role=InvoiceOperationDateRole.ADVANCE_PAYMENT_RECEIVED,
        ),
    )

    assert devengo.devengo_date == date(2026, 4, 1)
    assert devengo.rank is InvoiceDevengoRank.OPERATION_DATE_DECLARED


def test_an_operation_performed_in_q1_and_invoiced_in_q2_is_attributed_to_q1() -> None:
    """The boundary case the whole mechanism exists for.

    RD 1619/2012 art. 11 lets a B2B invoice be issued up to the fifteenth of
    the month following the operation, so this record is entirely lawful. Its
    cuota is nevertheless devengada in Q1 and belongs on Q1's Modelo 303.
    """
    invoice = _invoice(
        issued_at=date(2026, 4, 15),
        operation_date=date(2026, 3, 28),
        operation_date_role=InvoiceOperationDateRole.OPERATION_PERFORMED,
    )
    q1 = Period.from_year_and_code(2026, "1T")
    q2 = Period.from_year_and_code(2026, "2T")

    assert invoice_devengo_in_period(invoice, period=q1) is True
    assert invoice_devengo_in_period(invoice, period=q2) is False
    # The issue date alone would have said the opposite, which is the defect.
    assert q2.contains(invoice.issued_at) is True


def test_an_invoice_with_no_operation_date_is_attributed_on_its_issue_date() -> None:
    """The proxy still attributes -- degraded, not withheld.

    Refusing to place an invoice that records no operation date would make an
    ordinary catalogue unfileable. The placement happens and the rank says it
    was a substitution.
    """
    invoice = _invoice(issued_at=date(2026, 4, 15))

    assert invoice_devengo_in_period(invoice, period=Period.from_year_and_code(2026, "2T")) is True
    assert invoice_devengo_in_period(invoice, period=Period.from_year_and_code(2026, "1T")) is False


def test_proxy_attributed_ids_name_only_the_records_resting_on_a_substitute() -> None:
    """The reporting half: declared-date invoices are not named."""
    declared = _invoice(
        invoice_number="2026/DEV-DECLARED",
        operation_date=date(2026, 3, 28),
        operation_date_role=InvoiceOperationDateRole.OPERATION_PERFORMED,
    )
    proxied = _invoice(invoice_number="2026/DEV-PROXY")

    named = proxy_attributed_invoice_ids((declared, proxied))

    assert named == (proxied.invoice_id,)


def test_a_period_built_only_on_declared_dates_raises_no_advisory() -> None:
    """The negative direction of the guard.

    A guard proved only by its firing case passes while firing on everything,
    so the silent case is asserted as explicitly as the noisy one.
    """
    declared = _invoice(
        operation_date=date(2026, 3, 28),
        operation_date_role=InvoiceOperationDateRole.OPERATION_PERFORMED,
    )

    assert (
        devengo_proxy_attribution_diagnostics(
            (declared,),
            source_kind="ledger_iva_aggregation",
            resolver_id="ledger_iva_aggregation",
        )
        == ()
    )


def test_a_proxy_attributed_invoice_raises_one_advisory_naming_it() -> None:
    """The rank reaches an operator, not just a return value."""
    proxied = _invoice()

    diagnostics = devengo_proxy_attribution_diagnostics(
        (proxied,),
        source_kind="ledger_iva_aggregation",
        resolver_id="ledger_iva_aggregation",
    )

    assert len(diagnostics) == 1
    diagnostic = diagnostics[0]
    assert diagnostic.reason == "devengo_date_proxy_attribution"
    # Named by the number the operator sees in the catalogue listing, because
    # the remedy asks them to open that record; the content-addressed id would
    # be unrecognisable and would exhaust the message bound.
    assert proxied.invoice_number in diagnostic.message
    assert diagnostic.remedy is not None
    # Advisory-asserted: this module holds no revision, snapshot or casilla
    # definition anywhere, so the LIVA art. 75 claim the message states is
    # declared rather than read off a registry object.
    assert diagnostic.asserted_legal_refs == ("ley-37-1992:art-75",)


def test_the_advisory_message_stays_inside_its_bound_for_a_large_catalogue() -> None:
    """A household's worth of invoices must not overflow the message field.

    The diagnostic message is length-bounded, and the interpolated part scales
    with taxpayer data -- exactly the shape that has crashed advisories before.
    """
    invoices = tuple(_invoice(invoice_number=f"2026/DEV-{index:04d}") for index in range(400))

    diagnostics = devengo_proxy_attribution_diagnostics(
        invoices,
        source_kind="ledger_iva_aggregation",
        resolver_id="ledger_iva_aggregation",
    )

    assert len(diagnostics) == 1
    message = diagnostics[0].message
    assert "400 invoice(s)" in message
    assert "and 395 more" in message
    # The bound truncates rather than raises, so an overflowing message would
    # swallow the elision notice above and read as a complete list.
    assert len(message) <= DIAGNOSTIC_MESSAGE_MAX_LENGTH
    assert not message.endswith("[...]")
