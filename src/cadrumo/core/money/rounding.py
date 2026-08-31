"""Canonical :class:`~decimal.Decimal` money primitives.

Single authoritative implementation of the half-up euro-cent
rounding convention used across every AEAT calculation surface
(LIRPF art. 23.1 rental net income, IRPF deductions, IVA prorata,
asset depreciation, inventory cost basis). Callers in
``cadrumo.domain.*`` import :func:`round_to_cents` and the ``CENT`` quantum
from here rather than reimplementing the quantize call.

The half-up rounding mode (:data:`~decimal.ROUND_HALF_UP`) matches
the AEAT publication convention: a residual cent of exactly 0.5
rounds away from zero. Python's default banker's rounding
(``ROUND_HALF_EVEN``) does NOT match AEAT and must never be used at
the euro-cent boundary for any operator-facing or filed value.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

CENT = Decimal("0.01")


def round_to_cents(value: Decimal) -> Decimal:
    """Round *value* to euro-cent precision with half-up semantics.

    Args:
        value: The :class:`~decimal.Decimal` amount to round.

    Returns:
        A :class:`~decimal.Decimal` quantised to two fractional
        digits using :data:`decimal.ROUND_HALF_UP`.

    Raises:
        ~decimal.InvalidOperation: When quantising *value* to two fractional
            digits would exceed the active decimal context's precision — from 27
            integral digits under the default 28-digit context. Callers reachable
            from operator input must refuse an out-of-range magnitude at their own
            boundary rather than let this escape: this function is crossed long
            before the AEAT export encoder, so it, not the encoder, is the first
            boundary an unbounded figure meets.
    """
    return value.quantize(CENT, rounding=ROUND_HALF_UP)
