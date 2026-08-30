"""Schema constraint regression tests for the invoice service models.

These tests guard the :class:`ReconciliationSuggestion` and
:class:`LinkInconsistency` value records against silent
``transaction_id`` length drift. The catalogue key for a
:class:`cadrumo.domain.transactions.Transaction` is a SHA-256 hex
digest — exactly 64 lowercase hex characters. Loose
``min_length=1`` constraints on the service-side records would let a
provider-raw id (often a 6 to 16 character string) flow into a
suggestion or inconsistency record and silently fail to round-trip
into the catalogue.

The constraint is encoded by the
:data:`cadrumo.core.identity.TransactionId` typed alias so future
drift is a one-line change at the alias declaration. These tests pin
the constraint at the model boundary so the field cannot be silently
widened — which would still fail the :func:`link_transaction` runtime
check on the same value.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import ValidationError

from ....core import LinkInconsistencyDirection
from ..service import (
    LinkInconsistency,
    ReconciliationSuggestion,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


_SAMPLE_HEX_64 = "a" * 64


# ---------------------------------------------------------------------------
# Service records
# ---------------------------------------------------------------------------


def test_service_records_accept_64_char_transaction_id() -> None:
    """A SHA-256-shaped 64-character transaction id satisfies the
    catalogue-key contract."""
    # Test ReconciliationSuggestion
    suggestion = ReconciliationSuggestion(
        transaction_id=_SAMPLE_HEX_64,
        invoice_id=_SAMPLE_HEX_64,
        amount_match=True,
        counterparty_match=True,
        score=Decimal("1"),
    )
    assert suggestion.transaction_id == _SAMPLE_HEX_64

    # Test LinkInconsistency
    inconsistency = LinkInconsistency(
        transaction_id=_SAMPLE_HEX_64,
        invoice_id="INV-1",
        direction=LinkInconsistencyDirection.INVOICE_ONLY,
    )
    assert inconsistency.transaction_id == _SAMPLE_HEX_64


def test_service_records_reject_noncanonical_transaction_ids() -> None:
    # Test ReconciliationSuggestion with short transaction_id
    with pytest.raises(ValidationError, match=r"transaction_id|hex|length|pattern"):
        ReconciliationSuggestion(
            transaction_id="raw-12345",
            invoice_id="INV-1",
            amount_match=True,
            counterparty_match=True,
            score=Decimal("1"),
        )

    # Test ReconciliationSuggestion with too-long transaction_id
    with pytest.raises(ValidationError, match=r"transaction_id|length|String should have at most"):
        ReconciliationSuggestion(
            transaction_id=_SAMPLE_HEX_64 + "x",
            invoice_id="INV-1",
            amount_match=True,
            counterparty_match=True,
            score=Decimal("1"),
        )

    # Test LinkInconsistency with short transaction_id
    with pytest.raises(ValidationError, match=r"transaction_id|hex|length|pattern"):
        LinkInconsistency(
            transaction_id="raw-12345",
            invoice_id="INV-1",
            direction=LinkInconsistencyDirection.INVOICE_ONLY,
        )

    # Test LinkInconsistency with too-long transaction_id
    with pytest.raises(ValidationError, match=r"transaction_id|length|String should have at most"):
        LinkInconsistency(
            transaction_id=_SAMPLE_HEX_64 + "x",
            invoice_id="INV-1",
            direction=LinkInconsistencyDirection.TRANSACTION_ONLY,
        )


def test_link_inconsistency_invoice_id_remains_non_empty_required() -> None:
    """The tightening of ``transaction_id`` did not relax the empty-
    string guard on the other side of the link."""

    with pytest.raises(ValidationError, match=r"invoice_id|at least 1 character"):
        LinkInconsistency(
            invoice_id="",
            transaction_id=_SAMPLE_HEX_64,
            direction=LinkInconsistencyDirection.INVOICE_ONLY,
        )
