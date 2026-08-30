"""A ledger IVA rate is a fraction, and a percentage must not pass for one.

This CLI carries the same tax concept under one option name, ``--iva-rate``, in
two different units. The inventory and asset ledgers take a **percentage**: their
field is bounded ``0..100``, their help says "in percent", and they divide by a
hundred themselves. The transaction ledger takes a **fraction**: its help says
"as a decimal, for example 0.21", and the stored value is used as-is.

Until this guard the fraction side was unbounded, so ``21`` -- the spelling the
inventory surface asks for -- was accepted here as a 2100% rate. Nothing refused
it, nothing warned, and every downstream aggregation reading the row inherited a
hundredfold over-statement of the cuota. The over-declaration direction is the
one this codebase watches least: an under-declaration eventually contradicts a
filing, while an over-statement produces a valid-looking return the taxpayer
simply overpays.

The bound is the unit boundary of a fraction rather than a tax rate. No Spanish
IVA rate approaches 100% (LIVA arts. 90-91 put the general rate at 21%), so the
guard cannot refuse a real filing, and it does not need to move when a rate does.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from ..enums import TransactionDirection
from ..models import Transaction
from ..raw_transaction import RawProvenance, RawTransaction, SourceFormat

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _transaction(*, iva_rate: Decimal | None) -> Transaction:
    return Transaction(
        raw=RawTransaction(
            provider_transaction_id="row-1",
            booked_date=date(2026, 4, 10),
            value_date=date(2026, 4, 10),
            amount=Decimal("121.00"),
            currency="EUR",
            counterparty="Acme SL",
            description="Consultancy",
            provenance=RawProvenance(
                source_path=Path(__file__),
                source_sha256="a" * 64,
                source_row_index=1,
                source_format=SourceFormat.CSV,
                ingested_at=datetime(2026, 4, 14, 9, 0, tzinfo=UTC),
                provider_name="CSV provider",
            ),
            raw_fields={},
        ),
        direction=TransactionDirection.OUTGOING,
        source_jurisdiction=None,
        group_label=None,
        taxable_base=Decimal("100.00"),
        iva_rate=iva_rate,
    )


@pytest.mark.parametrize(
    "rate",
    [
        Decimal("0.21"),  # general
        Decimal("0.10"),  # reducido
        Decimal("0.04"),  # superreducido
        Decimal("0.05"),  # the temporary reduced band
        Decimal("0"),  # exempt / zero-rated
        Decimal("1"),  # the boundary itself, admitted
    ],
)
def test_every_real_spanish_rate_expressed_as_a_fraction_is_accepted(rate: Decimal) -> None:
    """The guard must not narrow the rates a real filing can carry.

    This is the positive control, and it runs on the rates that actually exist
    rather than one convenient value: a bound placed a decimal place out would
    still refuse ``21`` while quietly rejecting the superreducido band, and a
    refusal test alone could not tell those two apart.
    """
    assert _transaction(iva_rate=rate).iva_rate == rate


def test_a_percentage_supplied_where_a_fraction_belongs_is_refused() -> None:
    """``21`` is the inventory surface's spelling, and it must not pass here."""
    with pytest.raises(ValidationError) as exc_info:
        _transaction(iva_rate=Decimal("21"))

    message = str(exc_info.value)
    assert "not a percentage" in message
    assert "0.21" in message, "the refusal must show the correct spelling, not just reject the wrong one"


def test_the_refusal_names_the_unit_rather_than_the_bound() -> None:
    """A bound-shaped message would not tell the operator what went wrong.

    The mistake this catches is a unit confusion carried over from a sibling
    command, so ``input should be less than or equal to 1`` would be a true
    statement that leaves the operator to rediscover the convention. Asserting
    the message's content keeps a later refactor to a plain ``le=1`` constraint
    -- which is the obvious simplification -- from silently removing the part
    that does the explaining.
    """
    with pytest.raises(ValidationError) as exc_info:
        _transaction(iva_rate=Decimal("10"))

    message = str(exc_info.value)
    assert "fraction" in message
    assert "less than or equal to" not in message


def test_a_rate_just_above_the_boundary_is_refused_and_just_below_is_kept() -> None:
    """Pins the boundary itself, so a later off-by-one cannot pass unnoticed.

    Without this, widening the guard to ``value > 100`` would leave both other
    refusal tests green -- ``21`` is above neither bound -- while restoring the
    exact hole the guard exists to close.
    """
    assert _transaction(iva_rate=Decimal("0.999")).iva_rate == Decimal("0.999")
    with pytest.raises(ValidationError):
        _transaction(iva_rate=Decimal("1.001"))
