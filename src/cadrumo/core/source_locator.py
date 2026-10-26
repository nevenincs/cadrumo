"""The URL a captured AEAT snapshot came from, bounded once.

The same value was declared three ways. The live-capture records that PERSIST it
set a minimum and no maximum; the overview calendar entry that PROJECTS them
capped it at five hundred and twelve; the corpus fetch record and its ORM column
agree on a thousand and twenty-four.

The first two are the pair that matters, because the calendar copies the
snapshot's value straight across. A persisted URL longer than the projection's
cap does not truncate -- it refuses, and it refuses the whole calendar entry, so
one long sede link would take out the overview for that taxpayer rather than that
one field.

The bound is the generous one deliberately. A sede URL carries session and
procedure parameters and is long by nature; the tighter cap was the arbitrary
half of the disagreement, and tightening the persisted side to match it would
refuse links the portal really issues. A thousand and twenty-four is what this
codebase already gives a stored URL elsewhere.
"""

from __future__ import annotations

from typing import Annotated, Final

from pydantic import StringConstraints

#: Longest source URL any surface stores or projects.
SOURCE_URL_MAX_LENGTH: Final[int] = 1024

SourceUrl = Annotated[
    str,
    StringConstraints(min_length=1, max_length=SOURCE_URL_MAX_LENGTH),
]
"""The URL a capture came from. Present by definition -- a capture has a source."""

OptionalSourceUrl = Annotated[
    str,
    StringConstraints(max_length=SOURCE_URL_MAX_LENGTH),
]
"""The same bound where the surface may legitimately have no URL to show.

Separate rather than ``SourceUrl | None`` because the projection spells an absent
value as the empty string on the wire, and a minimum of one would refuse it.
"""

__all__ = ["SOURCE_URL_MAX_LENGTH", "OptionalSourceUrl", "SourceUrl"]
