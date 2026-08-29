"""The bounded-text shapes that recur across every layer, stated once.

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
from typing import Annotated

from pydantic import Field, StringConstraints

NonEmptyStr = Annotated[str, StringConstraints(min_length=1)]
"""A string that carries something. The weakest useful claim about text."""

PositiveCount = Annotated[int, Field(ge=1)]
"""A count of at least one, keeping the inclusive bound the wire contract shows."""

NonNegativeDecimal = Annotated[Decimal, Field(ge=Decimal("0"))]
"""A decimal quantity that cannot go below zero."""

type NonEmptyList[T] = Annotated[list[T], Field(min_length=1)]
"""A list that carries at least one element.

The container is part of a payload's wire shape, so this keeps the list rather
than quietly promoting it to a tuple: the strict models refuse the coercion,
and a projection has no business changing what a caller may hand it.
"""

__all__ = ["NonEmptyList", "NonEmptyStr", "NonNegativeDecimal", "PositiveCount"]
