"""Canonical :class:`~decimal.Decimal` constants shared across the AEAT domain.

Thirty-one modules each declared their own private copy of these values. A
duplicated constant is a correctness hazard rather than untidiness: the copies
drift, and a caller reaching the stale one gets a value nobody updated.

``ZERO`` and ``MONEY_ZERO`` are deliberately separate, and conflating them is a
real defect rather than a stylistic one. They compare equal, but they carry
different exponents, and Decimal arithmetic propagates the larger scale::

    str(Decimal("0") + Decimal("5"))     # "5"
    str(Decimal("0.00") + Decimal("5"))  # "5.00"

So a sum seeded with the wrong zero renders with the wrong number of decimals,
and a value returned from ``max(x, ZERO)`` carries the scale of whichever
operand won. On a filing surface that is the difference between an amount
written as ``5`` and one written as ``5,00``. Four modules were relying on the
two-decimal form when this module was introduced; they use ``MONEY_ZERO``.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Final

ZERO: Final[Decimal] = Decimal("0")
"""Unscaled zero, for comparisons, bounds, and non-monetary accumulation."""

MONEY_ZERO: Final[Decimal] = Decimal("0.00")
"""Zero at two-decimal money scale, for amounts that must render as ``0,00``.

Use this where the value can reach a rendered amount -- a returned total, a
casilla value, or an accumulator seed -- so the scale survives the arithmetic.
"""

ONE: Final[Decimal] = Decimal("1")
"""Multiplicative identity, and the upper bound of a unit ratio."""

HUNDRED: Final[Decimal] = Decimal("100")
"""The percentage scaling divisor.

Distinct from :data:`~cadrumo.core.percentage.PERCENTAGE_MAX`, which is the
same number used as a declared BOUND on a percentage value. This one is the
factor a ratio is scaled by; merging the two would tie a bound check to an
arithmetic constant.
"""

__all__ = ["HUNDRED", "MONEY_ZERO", "ONE", "ZERO"]
