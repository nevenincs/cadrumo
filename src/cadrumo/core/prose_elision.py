"""Canonical elision primitive for length-capped operator-facing prose.

A diagnostic, finding, or issue whose message is assembled from taxpayer data
has a length nobody authored: fixed prose plus interpolated terms sized by the
household rather than by the writer. When such a message crosses its field's
cap the model raises, and a NON-BLOCKING advisory becomes a blocking failure --
the filing stops at exactly the moment the advisory had something to say. Cap
enforcement on system-assembled prose therefore cuts rather than refuses.

Making that a property of the TYPE is the point. A clamp applied at the call
site is only as complete as the author's memory: the next builder added to the
module raises, and nothing catches it until a real household is large enough.
A type that elides is total by construction, so no present or future author
carries a character budget in their head.

Three homes grew this same clamp independently, with three different markers
and three different behaviours -- a word-boundary-aware type validator using
``" [...]"``, a mid-word call-site clamp using ``"…"``, and a third
hard-cut call-site clamp using ``"..."``. Nothing made them agree, and two of
the three were partial (a construction site that forgot the wrapper still
raised). This module is their single home, so an operator meets one elision
convention rather than three and a new capped prose field inherits the
behaviour instead of reimplementing it.

The elision is deliberately VISIBLE. A silently shortened advisory is its own
defect: these messages carry remedies, and an operator cannot tell a terse
message from a cut one. The marker costs six characters to make the difference
legible.

Eliding is a floor, not a licence. A message that reaches the validator has
already lost words an operator was meant to read, so authoring-time headroom
assertions still belong on messages whose length scales with taxpayer data.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Annotated, Final

from pydantic import BeforeValidator, StringConstraints

__all__ = ["PROSE_ELISION_MARKER", "ElidedProse", "elide_to_cap", "elided_prose"]

#: Appended to prose the cap truncated, so the elision is visible to a reader.
PROSE_ELISION_MARKER: Final[str] = " [...]"


def elide_to_cap(value: str, *, cap: int) -> str:
    """Return *value* shortened to at most *cap* characters, marking any cut.

    Total: every input produces a string of at most *cap* characters, so a
    caller can rely on the result satisfying the bound whatever the data.

    Cuts on a word boundary where one is reasonably placed rather than
    mid-word, because a message ending in half an identifier reads as
    corruption rather than as truncation. "Reasonably placed" means past the
    halfway mark of the available room; a boundary earlier than that would
    discard more than it saves, so the cut falls mid-word instead.

    A *cap* too small to hold the marker leaves no room to signal anything, so
    the value is hard-cut to the bound. That case does not arise for prose
    fields in this tree -- the tightest declared cap is an order of magnitude
    larger -- but the function stays total rather than producing a string
    longer than the cap it was asked to satisfy.

    Args:
        value: The prose to bound.
        cap: The maximum length of the result, in characters.

    Returns:
        *value* unchanged when it already fits, otherwise a shortened form
        ending in :data:`PROSE_ELISION_MARKER`.
    """
    if len(value) <= cap:
        return value
    if cap <= len(PROSE_ELISION_MARKER):
        return value[:cap]
    keep = cap - len(PROSE_ELISION_MARKER)
    head = value[:keep].rstrip()
    boundary = head.rfind(" ")
    if boundary > keep // 2:
        head = head[:boundary].rstrip()
    return head + PROSE_ELISION_MARKER


def elided_prose(
    cap: int,
    *,
    min_length: int = 1,
    strip_whitespace: bool = False,
) -> object:
    """Return a ``str`` annotation that elides to *cap* instead of refusing.

    The returned annotation carries the cap as a real constraint, so the bound
    stays readable on the model and discoverable by anything that inspects
    field metadata; the eliding validator runs first, so the constraint sees an
    already-bounded value and never fires on length.

    Use this for prose the SYSTEM assembles. Operator-supplied text -- a note
    typed at the CLI, an imported feedback package -- should keep a raising
    cap: the operator can shorten what they wrote, and silently swallowing
    half of it would be the worse failure.

    Args:
        cap: The field's maximum length, in characters.
        min_length: Minimum length after elision; the default rejects empty
            prose, which is a real defect rather than a short message.
        strip_whitespace: Whether to strip surrounding whitespace, for fields
            that already declared that constraint.

    Returns:
        An :data:`~typing.Annotated` ``str`` suitable as a field annotation.
    """

    def _elide(value: object) -> object:
        if not isinstance(value, str):
            return value
        return elide_to_cap(value, cap=cap)

    return Annotated[
        str,
        StringConstraints(
            strip_whitespace=strip_whitespace,
            min_length=min_length,
            max_length=cap,
        ),
        BeforeValidator(_elide),
    ]


if TYPE_CHECKING:  # pragma: no cover - import cycle only matters to type checkers
    from pydantic import GetCoreSchemaHandler
    from pydantic_core import CoreSchema


@dataclass(frozen=True, slots=True)
class ElidedProse:
    """Annotated metadata declaring an eliding prose cap.

    Carries the same constraint set as :func:`elided_prose` but as *metadata*
    rather than as a returned annotation, so a field can be written
    ``Annotated[str, ElidedProse(512)]``. That form is a literal type
    expression, which a static type checker can follow; assigning the result of
    a call to a name and using the name as an annotation is not, and leaves the
    field's type unknown along with every value read from it.

    Args:
        cap: The field's maximum length, in characters.
        min_length: Minimum length after elision.
        strip_whitespace: Whether to strip surrounding whitespace.
    """

    cap: int
    min_length: int = 1
    strip_whitespace: bool = False

    @property
    def max_length(self) -> int:
        """Return the cap under the name field-metadata inspectors look for.

        :func:`elided_prose` placed a :class:`~pydantic.StringConstraints` in the
        field metadata, and callers read ``max_length`` off it to size their own
        buffers. Exposing the same name here keeps that contract intact: the
        bound stays discoverable by anything inspecting metadata, which is the
        property the eliding annotation documents.
        """
        return self.cap

    def __get_pydantic_core_schema__(self, source_type: object, handler: GetCoreSchemaHandler) -> CoreSchema:
        """Return the schema of the equivalent :func:`elided_prose` annotation."""
        return handler.generate_schema(
            elided_prose(
                self.cap,
                min_length=self.min_length,
                strip_whitespace=self.strip_whitespace,
            )
        )

#: The traceable-exclusion ``detail`` annotation: elides rather than refusing.
#:
#: Homed here rather than beside its first consumer because BOTH the ledger
#: preflight surface and the aggregation income ledgers annotate a field with
#: it, and the ledger-side home made that a cycle: preflight imports the
#: aggregation package, whose modules imported this name back out of a
#: half-initialised preflight.
#:
#: These issues explain why a ledger row was excluded, so refusing one over its
#: length would drop the explanation for the exclusion AND fail the aggregation
#: that produced it -- a silent under-declaration dressed as a validation error.
#: Shortening the sentence is strictly the lesser loss.
IssueDetail = Annotated[str, ElidedProse(512)]
