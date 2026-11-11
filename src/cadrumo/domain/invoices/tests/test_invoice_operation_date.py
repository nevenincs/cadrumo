"""The fecha de operación contract on the invoice record.

RD 1619/2012 art. 6.1.i treats "the date the operation took place" and "the
date an advance payment was received" as ONE datum stated in one clause, so
:class:`~cadrumo.domain.invoices.Invoice` carries ONE date field plus a role
discriminator naming which of the two clauses the operator is stating --
never two separate date fields. Before this contract the invoice carried no
authoritative devengo-relevant date at all: the only date on the record was
``issued_at``, which art. 6.1.i itself says can differ from the operation
date and therefore cannot stand in for it.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date

import pytest
from pydantic import ValidationError

from ...calculations.registry.authority import bundled_indexed_authority
from ...calculations.registry.tests.authored_editions import filing_year_envelope
from ..enums import InvoiceOperationDateRole
from ..models import Invoice
from .issued_services_invoice_support import issued_services_invoice

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


@pytest.fixture(autouse=True)
def _authority_operation() -> Iterator[None]:
    """Validate invoices under the generation-pinned authority production uses."""
    with bundled_indexed_authority().operation():
        yield


_INVOICE_NUMBER = "2026/OP-1"


def test_an_invoice_can_state_its_operation_date_distinct_from_the_issue_date() -> None:
    """The fecha de operación is representable, naming which art. 6.1.i clause it answers."""
    invoice = issued_services_invoice(
        _INVOICE_NUMBER,
        operation_date=date(filing_year_envelope().horizon, 3, 28),
        operation_date_role=InvoiceOperationDateRole.from_registry("OPERATION_PERFORMED"),
    )

    assert invoice.operation_date == date(filing_year_envelope().horizon, 3, 28)
    assert invoice.operation_date_role == InvoiceOperationDateRole.from_registry("OPERATION_PERFORMED")
    assert invoice.operation_date != invoice.issued_at


def test_an_ordinary_invoice_declares_no_operation_date() -> None:
    """Most invoices never need the axis: the operation coincides with the issue date."""
    invoice = issued_services_invoice(_INVOICE_NUMBER)

    assert invoice.operation_date is None
    assert invoice.operation_date_role is None


def test_a_date_without_a_role_is_refused() -> None:
    """A bare date would leave a reader guessing which art. 6.1.i clause it answers."""
    with pytest.raises(ValidationError, match="operation_date and operation_date_role must be set together"):
        issued_services_invoice(_INVOICE_NUMBER, operation_date=date(filing_year_envelope().horizon, 3, 28))


def test_a_role_without_a_date_is_refused() -> None:
    """A role with nothing to date states nothing."""
    with pytest.raises(ValidationError, match="operation_date and operation_date_role must be set together"):
        issued_services_invoice(
            _INVOICE_NUMBER, operation_date_role=InvoiceOperationDateRole.from_registry("OPERATION_PERFORMED")
        )


def test_the_role_is_one_field_not_a_second_date() -> None:
    """The regulation's two clauses share one datum; the model must not grow a second field.

    This is a structural pin rather than a behavioural one: an
    ``advance_payment_date`` field appearing alongside ``operation_date``
    would silently reintroduce the two-clause-as-two-fields shape the brief
    explicitly rejected.
    """
    assert not hasattr(Invoice, "advance_payment_date")
    assert not hasattr(Invoice, "anticipo_date")
