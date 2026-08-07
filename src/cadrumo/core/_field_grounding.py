"""What verification one extracted field's value actually passed.

The second half of the provenance pair. :class:`~core.FieldOrigin` records HOW a
value was obtained; this axis records WHAT CHECKING it survived afterwards.
Neither substitutes for the other: a value read by an exact structured parser
can still fail an arithmetic identity, and a value read by a vision model can
still be corroborated verbatim against the transcription it came from.

Declared as a :class:`enum.StrEnum` in ``core`` for the same reason
:class:`~core.FieldOrigin` is: the readers that ground values, the application
layer that projects them and the CLI that shows them to the operator sit in
three different packages, and ``core`` is the only home all three reach without
one depending on another.

Deliberately absent, again: any numeric score. A confidence number invites
threshold arithmetic over a quantity nobody measured, and the model's own
estimate of its output is not evidence about that output. Every member here is
the outcome of a check that either ran or did not, which is a fact.
"""

from __future__ import annotations

from enum import StrEnum

__all__ = ["FieldGroundingOutcome"]


class FieldGroundingOutcome(StrEnum):
    """The verification outcome attached to one extracted field value.

    Closed by construction. The members are ordered from strongest to weakest
    claim, but the ordering is documentation only -- nothing compares them, and
    a consumer that needs "at least anchored" must name the members it accepts
    rather than relying on declaration order.
    """

    RECONCILED = "reconciled"
    """Corroborated by an INDEPENDENT identity, not merely found in the source.

    An arithmetic closure (``base + cuota == total``), a tax-identifier control
    character, or a date that parses under the detected dialect. The strongest
    outcome available, because the corroborating check does not consult the same
    evidence the value was read from.
    """

    ANCHORED = "anchored"
    """Found verbatim in the source the value was read from.

    Bounds fabrication to transcription error rather than eliminating it: on a
    vision path the transcription is itself model-produced, so an anchored value
    survived two reads that agreed rather than one unchecked guess.
    """

    UNANCHORED = "unanchored"
    """No verbatim occurrence located in the source.

    Not an accusation and not a refusal -- a normalised value (a date rewritten
    to ISO form, a tax id stripped of separators) legitimately fails a verbatim
    search. It is a statement that this particular check did not pass, so the
    operator reviews the field rather than assuming it was corroborated.
    """

    AMBIGUOUS = "ambiguous"
    """Several readings competed and none was decidable.

    The value, if any, is one candidate among those recorded beside it. Never
    resolved by picking the first: an ambiguity silently collapsed is
    indistinguishable downstream from a fact.
    """

    CONTRADICTED = "contradicted"
    """An independent check disagreed with the value.

    The value is carried rather than dropped, because a contradiction the
    operator can see is worth more than an absence they cannot explain, and the
    disagreeing figure is itself evidence of what the document states.
    """
