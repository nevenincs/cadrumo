"""An edit must not silently restate a foreign-currency row's amount.

Editing rebuilds the row from the command, and the rebuild re-derives the FX
conversion through a :class:`CurrencyNormalizationService`. No caller of
``update_manual_transaction`` has one, so the projection came back empty and the
replacement took the model default of ``None``.

That is not a cosmetic loss. ``summarize_manual_transactions`` falls back to
``abs(raw.amount)`` when ``value_in_eur`` is absent, so a 1000 USD row converted
at import was counted as 1000 EUR from the first unrelated edit onwards — fixing
a typo in the description restated the money.

The carry-forward is deliberately conditional. A stored euro value describes one
particular sum; if the amount or the currency moved, reusing it would replace a
lost figure with a wrong one, and absence is the honest answer there.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....domain.transactions.enums import BusinessClassification, TransactionDirection
from ....domain.transactions.models import Transaction
from ....domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat
from ..actions_manual import _carry_forward_fx

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_CONVERTED = Decimal("920.00")
_RATE = Decimal("0.92")


def _row(*, amount: Decimal, currency: str, value_in_eur: Decimal | None) -> Transaction:
    raw = RawTransaction(
        provider_transaction_id="p",
        booked_date=date(2026, 3, 1),
        value_date=None,
        amount=amount,
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


def _converted() -> Transaction:
    return _row(amount=Decimal("1000.00"), currency="USD", value_in_eur=_CONVERTED)


def test_an_unrelated_edit_keeps_the_converted_euro_value() -> None:
    """The defect: a description fix used to erase the conversion."""
    rebuilt = _row(amount=Decimal("1000.00"), currency="USD", value_in_eur=None)

    carried = _carry_forward_fx(_converted(), rebuilt)

    assert carried.value_in_eur == _CONVERTED
    assert carried.fx_rate == _RATE


def test_a_changed_amount_does_not_inherit_the_old_euro_value() -> None:
    """920 EUR described 1000 USD; it does not describe 900 USD.

    Absence here is a real loss, but a carried figure would be a wrong one, and
    a wrong euro value reaches the modelo as if it were measured.
    """
    rebuilt = _row(amount=Decimal("900.00"), currency="USD", value_in_eur=None)

    assert _carry_forward_fx(_converted(), rebuilt).value_in_eur is None


def test_a_changed_currency_does_not_inherit_the_old_euro_value() -> None:
    """The same sum in a different currency is a different sum."""
    rebuilt = _row(amount=Decimal("1000.00"), currency="GBP", value_in_eur=None)

    assert _carry_forward_fx(_converted(), rebuilt).value_in_eur is None


def test_a_freshly_derived_conversion_is_never_overwritten() -> None:
    """When a normalizer did resolve a rate, that rate is the current one."""
    rebuilt = _row(amount=Decimal("1000.00"), currency="USD", value_in_eur=Decimal("1.00"))

    assert _carry_forward_fx(_converted(), rebuilt).value_in_eur == Decimal("1.00")


def test_a_euro_row_gains_nothing() -> None:
    """Nothing to carry, and no field invented for a row that never had one."""
    euro = _row(amount=Decimal("50.00"), currency="EUR", value_in_eur=None)

    carried = _carry_forward_fx(euro, _row(amount=Decimal("50.00"), currency="EUR", value_in_eur=None))

    assert carried.value_in_eur is None
    assert carried.fx_rate is None
