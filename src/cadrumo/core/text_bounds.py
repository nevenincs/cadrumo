"""The bounded scalar shapes that recur across every layer, stated once.

Most of this campaign's aliases name a DOMAIN concept -- a filing year, a share
of one, a country code -- and carry its bound as a consequence. These are
different: they name a SHAPE. ``NonEmptyStr`` says only that a string carries
something, and ``PositiveCount`` only that a count is at least one.

That is a weaker kind of canonicality and worth being honest about. The value
is not that the name teaches a reader something new; it is that the shape is
written down once instead of a hundred and eight times, so a payload cannot
quietly disagree with the model it projects about whether empty is allowed.
Where a real domain concept exists, its own alias is the better home and these
should not be reached for -- an evidence reference is
:obj:`EvidenceReference`, not a bounded string that happens to be non-empty.

``PositiveCount`` exists because pydantic's ``PositiveInt`` is not a drop-in
substitute at these sites. It is ``Gt(0)`` where these are ``Ge(1)``; for an
integer those admit the same values, but they serialise to different JSON
schemas -- ``exclusiveMinimum: 0`` against ``minimum: 1`` -- and these bounds
sit on a published envelope contract. ``NonNegativeInt`` has no such problem
and is used directly; only the positive case needs a local name.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Annotated, Final

from pydantic import Field, StringConstraints

NonEmptyStr = Annotated[str, StringConstraints(min_length=1)]
"""A string that carries something. The weakest useful claim about text."""

PositiveCount = Annotated[int, Field(ge=1)]
"""A count of at least one, keeping the inclusive bound the wire contract shows."""

NonNegativeDecimal = Annotated[Decimal, Field(ge=Decimal("0"))]
"""A decimal quantity that cannot go below zero."""

PositiveDecimal = Annotated[Decimal, Field(gt=Decimal("0"))]
"""A decimal quantity that must be strictly above zero.

Separate from :obj:`NonNegativeDecimal` because the difference is the whole
point at the sites that need it: an exchange rate of zero is not a rate,
while a total of zero is a legitimate total.
"""

#: The first month AEAT numbers.
CALENDAR_MONTH_MIN: Final[int] = 1

#: The last month AEAT numbers.
CALENDAR_MONTH_MAX: Final[int] = 12

CalendarMonth = Annotated[int, Field(ge=CALENDAR_MONTH_MIN, le=CALENDAR_MONTH_MAX)]
"""A month of the year, numbered as AEAT numbers them."""


def is_calendar_month(value: int) -> bool:
    """Whether ``value`` names a month, inclusive at both ends.

    For the callers that cannot use the annotation because they must raise
    their OWN refusal: the profile answer reader raises a
    ``ProfileAnswerTypeError`` naming the answer key, the descendant record a
    ``ProfileValidationError``, the setup wizard returns a failed verdict
    carrying a locale key, and the CLI payload a plain ``ValueError`` pydantic
    wraps. Those differ on purpose -- the operator's first instructive surface
    should name the field they typed into -- so what is shared is the question,
    not the answer.

    The bound was open-coded as ``1 <= month <= 12`` at five sites, twice within
    a single module for the SAME field, which is how a bound stops being one
    rule and becomes five that happen to agree.
    """
    return CALENDAR_MONTH_MIN <= value <= CALENDAR_MONTH_MAX


def is_canonical_month_set(months: tuple[int, ...]) -> bool:
    """Whether ``months`` is a canonical set: real months, no repeat, ascending.

    The three rules travel together and were written out twice -- once on the
    descendant record and once on the wire payload that projects it. Only the
    first of the three delegated; uniqueness and ordering were restated.

    Ascending order is ENFORCED rather than applied, so a record has exactly one
    representation of a given set and a save-then-reload cannot reorder it. A
    repeat is refused rather than collapsed, because a month either qualified or
    it did not and silently dropping the second mention would hide a
    transcription slip while changing nothing the operator can see.

    A predicate rather than a validator because the two callers raise different
    errors on purpose -- the record a ``ProfileValidationError`` naming the
    repeated months, the payload a plain ``ValueError`` pydantic wraps -- and the
    detail each builds is a message, not a rule.
    """
    return (
        all(is_calendar_month(month) for month in months)
        and len(set(months)) == len(months)
        and list(months) == sorted(months)
    )

type NonEmptyList[T] = Annotated[list[T], Field(min_length=1)]
"""A list that carries at least one element.

The container is part of a payload's wire shape, so this keeps the list rather
than quietly promoting it to a tuple: the strict models refuse the coercion,
and a projection has no business changing what a caller may hand it.
"""

__all__ = [
    "CALENDAR_MONTH_MAX",
    "CALENDAR_MONTH_MIN",
    "CalendarMonth",
    "NonEmptyList",
    "NonEmptyStr",
    "NonNegativeDecimal",
    "PositiveCount",
    "PositiveDecimal",
    "is_calendar_month",
    "is_canonical_month_set",
]
