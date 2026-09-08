"""The one question the renderer and its screens must ask about a pinned design.

Which fields of a parser-read record design are eligible for a reviewed render
profile is not a fact of the profile loader; it is a shared contract. The
generator asks it before emitting, the profile validator asks it to check
exhaustive coverage, and the pointer-only screen asks it to decide whether a
content cell is still outstanding work. Those callers sit in different packages,
so the contract has a public defining module of its own rather than living
inside the profile loader's private one.

That placement is not bookkeeping. While this function was private to
``_render_profile``, the screen reached past it into the bare projection and
passed none of the design's declarations, so it answered a different question
from the renderer and reported a cell whose note had been read, recorded and
acted on as a reference nobody had opened. A screen that disagrees with the
thing it screens is worse than no screen, because its rows read as work.

The pin is VALIDATED here, not merely read: a declaration naming this source but
carrying another digest ends the call rather than being silently ignored. A
caller that classifies that refusal as "this revision declares nothing I can
read" has collapsed two different states, and the refusal is the one that means
somebody's reviewed reading has stopped covering the file in hand.
"""

from __future__ import annotations

from collections.abc import Iterable

from ._record_design_ir import RecordDesignIntermediateField, RecordDesignIntermediateSource
from ._render_profile import RenderProfileEligibility, project_render_profile_eligibility
from .source_defects import note_stated_applicability_for, validate_note_stated_applicability_declarations

__all__ = ["resolve_render_profile_eligibility"]


def resolve_render_profile_eligibility(
    fixed_fields: Iterable[RecordDesignIntermediateField],
    source: RecordDesignIntermediateSource,
) -> RenderProfileEligibility:
    """Partition fields of one PARSER-READ design, resolving its declarations here.

    The declaration set is resolved from the source the parser read rather than
    accepted from the caller, for the same reason ``render_complete_export_tree``
    resolves the note-governed amounts there: every consumer -- the generator,
    the drift check, a screen, a test -- must read ONE declaration set for one
    pinned design and cannot disagree about which cells have been read.

    This exists as a named function because a caller that assembles the argument
    itself is a caller that can forget to. Routing through one function removes
    the argument a caller could get wrong rather than correcting the callers that
    got it wrong.

    Raises:
        RegistryValidationError: when a declaration names this source but is
            pinned to another digest. That is a refusal, distinct from a design
            this eligibility question does not apply to, and a caller must keep
            the two apart.
    """
    applicability_notes = note_stated_applicability_for(source.source_ref)
    validate_note_stated_applicability_declarations(applicability_notes, source)
    return project_render_profile_eligibility(fixed_fields, applicability_notes=applicability_notes)
