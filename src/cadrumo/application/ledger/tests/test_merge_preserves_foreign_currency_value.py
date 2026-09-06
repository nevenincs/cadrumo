"""A merged row keeps the euro value its money still has.

``_build_merged_transaction`` copies the parent's amount and currency verbatim,
so the merged row restates the same money — but it dropped ``value_in_eur`` and
``fx_rate``, and ``summarize_manual_transactions`` counts a row with no euro
value at its face number. A merged 1000 USD parent re-entered the totals as
1000 EUR, and because the merge archives the parent the original figure was no
longer anywhere in the active catalogue.

This is the same shape as the edit-path loss ``_carry_forward_fx`` closed; the
class was fixed in one place and not swept. The split builder still drops it —
children carry a fraction of the parent's amount, so restoring their euro value
needs an apportionment decision rather than a copy, and that is not settled
here.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....domain.transactions.enums import BusinessClassification, TransactionDirection
from ....domain.transactions.models import Transaction
from ....domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat
from ..actions_split_merge import _build_merged_transaction

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_CONVERTED = Decimal("920.00")
_RATE = Decimal("0.92")
_OCCURRED = datetime(2026, 3, 5, 10, 0, tzinfo=UTC)
#: Split group ids are content-addressed; the model enforces the full width.
_GROUP = "9" * 64


def _parent(*, currency: str, value_in_eur: Decimal | None) -> Transaction:
    raw = RawTransaction(
        provider_transaction_id="parent",
        booked_date=date(2026, 3, 1),
        value_date=None,
        amount=Decimal("1000.00"),
        currency=currency,
        counterparty="Vendor Inc",
        description="software",
        provenance=RawProvenance(
            source_path=Path("x"),
            source_sha256="a" * 64,
            source_row_index=1,
            source_format=SourceFormat.MANUAL,
            ingested_at=datetime(2026, 3, 1, tzinfo=UTC),
            provider_name="t",
        ),
        raw_fields={},
    )
    transaction = Transaction.model_validate(
        {
            "raw": raw,
            "direction": TransactionDirection.OUTGOING,
            "business_classification": BusinessClassification.NOT_YET_PROCESSED,
            "source_jurisdiction": "ES",
            "group_label": None,
            "created_at": datetime(2026, 3, 1, tzinfo=UTC),
            "modified_at": datetime(2026, 3, 1, tzinfo=UTC),
        },
    )
    if value_in_eur is None:
        return transaction
    return transaction.model_copy(update={"value_in_eur": value_in_eur, "fx_rate": _RATE})


def _merge(parent: Transaction) -> Transaction:
    return _build_merged_transaction(
        parent=parent,
        split_group_id=_GROUP,
        sorted_child_ids=("c" * 64, "d" * 64),
        occurred_at=_OCCURRED,
        actor="operator",
        source_command="aeat app ledger merge",
    )


def test_a_merged_foreign_row_keeps_its_euro_value() -> None:
    """The defect: the conversion vanished with the archived parent."""
    merged = _merge(_parent(currency="USD", value_in_eur=_CONVERTED))

    assert merged.value_in_eur == _CONVERTED
    assert merged.fx_rate == _RATE


def test_the_merged_row_restates_the_parent_money_it_inherits_the_value_for() -> None:
    """The carry is only sound because the money is identical, so pin that.

    If the merged row ever stopped copying the parent's amount and currency,
    inheriting its euro value would become a fabrication rather than a
    continuation.
    """
    parent = _parent(currency="USD", value_in_eur=_CONVERTED)

    merged = _merge(parent)

    assert merged.raw.amount == parent.raw.amount
    assert merged.raw.currency == parent.raw.currency


def test_a_euro_parent_gains_no_conversion() -> None:
    """Nothing is invented for a row that never had a foreign value."""
    merged = _merge(_parent(currency="EUR", value_in_eur=None))

    assert merged.value_in_eur is None
    assert merged.fx_rate is None
