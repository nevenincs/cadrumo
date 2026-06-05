"""Schema constraint regression tests for the invoice service models.

These tests guard the :class:`ReconciliationSuggestion` and
:class:`LinkInconsistency` value records against silent
``transaction_id`` length drift. The catalogue key for a
:class:`aeat.domain.transactions.Transaction` is a SHA-256 hex
digest — exactly 64 lowercase hex characters. Loose
``min_length=1`` constraints on the service-side records would let a
provider-raw id (often a 6 to 16 character string) flow into a
suggestion or inconsistency record and silently fail to round-trip
into the catalogue.

The constraint is encoded by the
:data:`aeat.domain.transactions._ids.TransactionId` typed alias so future
drift is a one-line change at the alias declaration. These tests pin
the constraint at the model boundary so the field cannot be silently
widened — which would still fail the :func:`link_transaction` runtime
check on the same value.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import ValidationError

from .._service import (
    LinkInconsistency,
    ReconciliationSuggestion,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


_SAMPLE_HEX_64 = "a" * 64


# ---------------------------------------------------------------------------
# ReconciliationSuggestion
# ---------------------------------------------------------------------------


def test_reconciliation_suggestion_accepts_64_char_transaction_id() -> None:
    """A SHA-256-shaped 64-character transaction id satisfies the
    catalogue-key contract."""

    suggestion = ReconciliationSuggestion(
        invoice_id="INV-1",
        transaction_id=_SAMPLE_HEX_64,
        amount_match=True,
        counterparty_match=True,
        score=Decimal("1"),
    )
    assert suggestion.transaction_id == _SAMPLE_HEX_64


def test_reconciliation_suggestion_rejects_short_transaction_id() -> None:
    """A provider-raw id (typically 6 to 16 chars) must not satisfy the
    constraint — it cannot round-trip into the
    :class:`aeat.domain.transactions.Transaction` catalogue keyed by
    the 64-character SHA-256 stable hash."""

    with pytest.raises(ValidationError, match=r"transaction_id|hex|length|pattern"):
        ReconciliationSuggestion(
            invoice_id="INV-1",
            transaction_id="raw-12345",
            amount_match=True,
            counterparty_match=True,
            score=Decimal("1"),
        )


def test_reconciliation_suggestion_rejects_oversized_transaction_id() -> None:
    """A 65-character value (e.g. accidental trailing newline) must
    also fail. ``max_length`` pins the upper edge."""

    with pytest.raises(ValidationError, match=r"transaction_id|length|String should have at most"):
        ReconciliationSuggestion(
            invoice_id="INV-1",
            transaction_id=_SAMPLE_HEX_64 + "x",
            amount_match=True,
            counterparty_match=True,
            score=Decimal("1"),
        )


# ---------------------------------------------------------------------------
# LinkInconsistency
# ---------------------------------------------------------------------------


def test_link_inconsistency_accepts_64_char_transaction_id() -> None:
    inconsistency = LinkInconsistency(
        invoice_id="INV-1",
        transaction_id=_SAMPLE_HEX_64,
        direction="invoice-only",
    )
    assert inconsistency.transaction_id == _SAMPLE_HEX_64


def test_link_inconsistency_rejects_short_transaction_id() -> None:
    with pytest.raises(ValidationError, match=r"transaction_id|hex|length|pattern"):
        LinkInconsistency(
            invoice_id="INV-1",
            transaction_id="raw-12345",
            direction="invoice-only",
        )


def test_link_inconsistency_rejects_oversized_transaction_id() -> None:
    with pytest.raises(ValidationError, match=r"transaction_id|length|String should have at most"):
        LinkInconsistency(
            invoice_id="INV-1",
            transaction_id=_SAMPLE_HEX_64 + "x",
            direction="transaction-only",
        )


def test_link_inconsistency_invoice_id_remains_non_empty_required() -> None:
    """The tightening of ``transaction_id`` did not relax the empty-
    string guard on the other side of the link."""

    with pytest.raises(ValidationError, match=r"invoice_id|at least 1 character"):
        LinkInconsistency(
            invoice_id="",
            transaction_id=_SAMPLE_HEX_64,
            direction="invoice-only",
        )
