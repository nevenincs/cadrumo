"""A CSV row names a transaction the way an operator does, not the way storage does.

``BulkClassifyRow.transaction_id`` was typed as ``TransactionId`` -- the
resolved 64-character content address a row actually has. But a CSV is written
by hand from what ``ledger list`` prints, which is the short display id, and
the single-row verb has always accepted a prefix. So every prefix row was
refused by pydantic at PARSE time with ``String should have at least 64
characters``, before the apply path's ``resolve_transaction_id`` -- which was
already there and correct -- could resolve anything.

The whole-batch consequence was worse than the row. With one row in the file
and that row rejected, the run reported ``bulk classify failed: every row
failed; no ledger rows were updated``: a bulk verb that looked broken rather
than one that had been handed a short id.

The fix is a type distinction, not a relaxed constraint.
``TransactionIdReference`` is the unresolved sibling of ``TransactionId``, and
these tests hold both halves: the reference admits what an operator types, and
the resolved form still refuses it, so the field cannot be quietly tidied back.
"""

from __future__ import annotations

import pytest
from pydantic import BaseModel, ValidationError

from ....core.identity.transaction_ids import TransactionId, TransactionIdReference
from ....core.models import STRICT_FROZEN_CONFIG
from ....domain.transactions.enums import BusinessClassification
from ..models import BulkClassifyRow

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_FULL_ID = "e275cada" + "0" * 56
_DISPLAY_PREFIX = "e275cada"


class _ResolvedIdHolder(BaseModel):
    """A model typed with the RESOLVED id, for the contrast below."""

    model_config = STRICT_FROZEN_CONFIG

    transaction_id: TransactionId


class _ReferenceHolder(BaseModel):
    """A model typed with the reference an operator supplies."""

    model_config = STRICT_FROZEN_CONFIG

    transaction_id: TransactionIdReference


def _row(transaction_id: str) -> BulkClassifyRow:
    """One CSV row naming a transaction, with everything else at its default."""
    return BulkClassifyRow(
        transaction_id=transaction_id,
        classification=BusinessClassification.BUSINESS,
    )


def test_a_csv_row_may_name_a_transaction_by_display_prefix() -> None:
    """The defect: this is what an operator copies out of ``ledger list``."""
    assert _row(_DISPLAY_PREFIX).transaction_id == _DISPLAY_PREFIX


def test_a_csv_row_may_still_name_the_full_id() -> None:
    """The control: accepting a prefix must not stop accepting a resolved id.

    A machine-generated file carries full ids, and a relaxation that only
    widened the lower bound would be indistinguishable from one that moved it.
    """
    assert _row(_FULL_ID).transaction_id == _FULL_ID


def test_a_csv_row_still_refuses_an_empty_reference() -> None:
    """Bounded, not unbounded. An empty cell names nothing and never resolves.

    The resolver would refuse it too, but a row that reached the apply path
    with nothing in it would spend a catalogue load to say so.
    """
    with pytest.raises(ValidationError):
        _row("")


def test_a_reference_longer_than_a_resolved_id_is_refused() -> None:
    """No transaction id is longer than 64 characters, so this can never match."""
    with pytest.raises(ValidationError):
        _row("f" * 65)


def test_the_resolved_id_type_still_refuses_a_prefix() -> None:
    """The distinction the fix rests on, stated where it cannot be missed.

    ``TransactionId`` means "this HAS been resolved". If it ever admitted a
    prefix, storage and the domain would start holding operator input, and the
    reference type would have no reason to exist.
    """
    with pytest.raises(ValidationError):
        _ResolvedIdHolder(transaction_id=_DISPLAY_PREFIX)

    assert _ResolvedIdHolder(transaction_id=_FULL_ID).transaction_id == _FULL_ID


def test_the_reference_type_admits_both_forms() -> None:
    """The other side of the same distinction, so neither reads as a ban."""
    assert _ReferenceHolder(transaction_id=_DISPLAY_PREFIX).transaction_id == _DISPLAY_PREFIX
    assert _ReferenceHolder(transaction_id=_FULL_ID).transaction_id == _FULL_ID


def test_the_reference_does_not_pre_empt_the_resolver_on_shape() -> None:
    """Non-hex text reaches the resolver, which refuses it by name.

    Deliberate: the resolver answers a bad prefix with a localised refusal that
    names the collision candidates, and a pattern here would replace that with
    a pydantic message that says less. The row parses; resolution is what
    refuses.
    """
    assert _row("zzzz").transaction_id == "zzzz"
