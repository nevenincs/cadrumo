"""Compare a ledger row's recorded IVA cuota with the cuota its base and tipo give."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from ...core.money.rounding import CENT, round_to_cents
from ...domain.transactions.models import Transaction


@dataclass(frozen=True, slots=True)
class CuotaDisagreement:
    """One row's recorded cuota set beside the cuota its base and tipo give."""

    base: Decimal
    rate: Decimal
    expected: Decimal
    declared: Decimal


def cuota_disagreement(transaction: Transaction) -> CuotaDisagreement | None:
    """Return the row's figures when its cuota is not its base at its tipo beyond one cent.

    Recargo de equivalencia is left out: its own tipo is not carried on the row,
    only its amount, so only the IVA cuota is recomputed. A row without a base,
    a cuota or a tipo has nothing to compare.
    """
    taxable_base = transaction.taxable_base
    iva_amount = transaction.iva_amount
    iva_rate = transaction.iva_rate
    if taxable_base is None or iva_amount is None or iva_rate is None:
        return None
    expected_cuota = (taxable_base * iva_rate).quantize(Decimal("0.0001"))
    if abs(iva_amount - expected_cuota) <= CENT:
        return None
    return CuotaDisagreement(
        base=taxable_base, rate=iva_rate, expected=round_to_cents(expected_cuota), declared=iva_amount
    )


def eur_figure(amount: Decimal) -> str:
    """An amount as the operator reads it: two decimals and the currency, whatever scale it was stored at."""
    return f"{round_to_cents(amount):.2f} EUR"


def percent_figure(rate: Decimal) -> str:
    """A fractional tipo as a percentage without trailing zeros, ``0.21`` as ``21%`` and ``0.055`` as ``5.5%``."""
    percent = (rate * 100).normalize()
    return f"{percent:f}%"
