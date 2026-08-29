"""A share of a whole, bounded to the inclusive zero-to-one interval.

Business-use percentages, usage ratios, prorrata shares and classifier
confidences are all the same quantity: a Decimal share of one. The bound was
open-coded as ``Decimal("0") <= value <= Decimal("1")`` at nine sites across
the ledger, renta, transactions and usage-ratio surfaces and the CLI, plus two
further local constant pairs spelling the same two numbers.

The predicate lives here so every caller asks the same question. Callers keep
their own refusal: the ledger raises a transaction error, the renta models a
renta error, and the CLI raises an operator-facing message naming the offending
value and its percentage. That difference is deliberate and worth preserving --
the operator's first instructive surface should say ``0.5 means 50 %`` where
the domain need only say the invariant broke. What must not differ is where the
interval ends.

The interval is INCLUSIVE at both ends: a zero share and a whole share are both
legitimate answers, and a caller that needs to exclude one says so itself.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Annotated, Final

from pydantic import Field

#: The smallest legitimate share: none of the whole.
UNIT_PROPORTION_MIN: Final[Decimal] = Decimal("0")

#: The largest legitimate share: all of the whole.
UNIT_PROPORTION_MAX: Final[Decimal] = Decimal("1")

UnitProportion = Annotated[Decimal, Field(ge=UNIT_PROPORTION_MIN, le=UNIT_PROPORTION_MAX)]
"""A Decimal share of one, for a model field that carries the bound in its type."""


def is_unit_proportion(value: Decimal) -> bool:
    """Whether ``value`` is a share of one, inclusive at both ends."""
    return UNIT_PROPORTION_MIN <= value <= UNIT_PROPORTION_MAX


__all__ = [
    "UNIT_PROPORTION_MAX",
    "UNIT_PROPORTION_MIN",
    "UnitProportion",
    "is_unit_proportion",
]
