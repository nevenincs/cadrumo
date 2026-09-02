"""The verdict a live identity check returns for one tax identifier.

One vocabulary, previously declared three times: twice inline in the sede checkers
that produce it, and once as an alias in the live verification surface that consumes
it. The three agreed only because nobody had changed one of them.

The producers and the consumer sit in different layers, so the definition lives here
where both may reach it rather than in either of them.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

__all__ = ["IdentityCheckVerdict", "IdentityCheckVerdictValue"]


class IdentityCheckVerdict(StrEnum):
    """What a live AEAT or VIES lookup said about one identifier."""

    VALID = "valid"
    """The registry the check consulted recognises the identifier."""

    INVALID = "invalid"
    """The registry answered, and the identifier is not recognised."""

    UNKNOWN = "unknown"
    """No answer was obtained, so nothing may be inferred either way.

    Structurally unanswerable rather than negative: a transport failure mid-query
    reads as unknown, and collapsing it into ``INVALID`` would report an outage as a
    rejected identifier.
    """


IdentityCheckVerdictValue = Literal[
    IdentityCheckVerdict.VALID,
    IdentityCheckVerdict.INVALID,
    IdentityCheckVerdict.UNKNOWN,
]
"""The same vocabulary in the form a strict payload boundary accepts.

A bare enum under strict validation refuses the plain token a serialised observation
carries, and a coercing annotation cannot be used where a customised core schema is
forbidden. A literal over this enum's own members accepts the token and adds no hook.
Rooted in the vocabulary above rather than restated.
"""
