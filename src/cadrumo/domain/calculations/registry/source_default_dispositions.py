"""An edition's authored statement that a family default cannot be derived.

The edition-level ``source_refs`` defaults -- ``casilla_source_refs``,
``binding_source_refs``, ``formula_source_refs`` -- lift a family's shared
grounding onto the revision manifest once instead of restating it on every row.
The lift is derivable only when a leading run of references opens at least two
statements. An edition whose rows share no such run has nothing to lift, and
absence of the key cannot say which of the two it is: not yet lifted, or
nothing to lift.

A disposition is the second reading, authored. It carries the reason somebody
established, so a later reader disagrees with a claim rather than with silence,
and the screen that reports underivable defaults closes on the authored
statement instead of on a guess about why the key is missing.
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from .schema_base import RegistryModel

__all__ = ("SourceDefaultDisposition",)


class SourceDefaultDisposition(RegistryModel):
    """One family's authored reason that its edition default is underivable.

    ``kind`` is a single member today because ``underivable`` is the only
    statement an edition can make that absence does not already carry: a family
    whose default IS derivable declares the default itself, and a family with no
    rows declares nothing. It is spelled as an enumerated field rather than
    assumed so a later, differently-grounded disposition is an added member
    rather than a reinterpretation of every existing reason string.
    """

    kind: Literal["underivable"]
    reason: str = Field(min_length=1, max_length=1024)
