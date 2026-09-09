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

The projection itself and the predicates that decide a single field live here
too, with the resolver, rather than in the profile loader. Splitting them left
the loader calling back into this module while this module read the loader's
projection, and the only thing holding that cycle open was an import deferred to
call time. The seam is between "which fields are eligible" and "what a reviewed
profile says about them", so the whole eligibility question sits on this side of
it and the dependency runs one way: the profile loader reads this module, and
this module reads nothing of the loader's.
"""

from __future__ import annotations

import unicodedata
from collections.abc import Iterable
from typing import Final

from pydantic import BaseModel, ConfigDict

from cadrumo.domain.calculations.registry.record_design_pdf_rows import ABSENT_NATURALEZA_TYPE_CODE

from .record_design_intermediate import (
    RecordDesignIntermediateField,
    RecordDesignIntermediateSource,
)
from .source_defects import (
    NoteStatedApplicabilityDeclaration,
    note_stated_applicability_for,
    note_states_only_applicability,
    validate_note_stated_applicability_declarations,
)

__all__ = [
    "RenderProfileEligibility",
    "project_render_profile_eligibility",
    "resolve_render_profile_eligibility",
]

_RESERVED_DESCRIPTION_MARKER: Final[str] = "reservado"


class _StrictModel(BaseModel):
    """Frozen development-tool boundary model with no untyped extras."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class RenderProfileEligibility(_StrictModel):
    """Production-owned partition of otherwise-unrenderable fixed numeric fields."""

    all_fields: tuple[RecordDesignIntermediateField, ...]
    width_17_fields: tuple[RecordDesignIntermediateField, ...]
    smaller_fields: tuple[RecordDesignIntermediateField, ...]


def _is_source_reserved_field(field: RecordDesignIntermediateField) -> bool:
    """Report whether the official description marks this slot reserved.

    Reservation is read from the DESCRIPTION and never from the type column,
    because the type column is unreliable for exactly these slots.  When AEAT
    retires a numeric field it rewrites the description to mark the slot
    reserved and leaves the original numeric type in place, so a retired
    quantity keeps announcing itself as ``Num`` forever.  Modelo 303 shows both
    states of that edit within one modelo: its 2023 design types every reserved
    slot ``An``, while its 2025 design types five of thirteen ``Num``, and four
    of those five sit exactly where live employee-count quantities stood before
    they were retired.  The surviving ``Num`` is therefore a residue of the
    slot's former life, not a claim that a reserved run carries a number.

    The match is case-insensitive because official designs disagree on casing
    for the same marker.
    """
    return _RESERVED_DESCRIPTION_MARKER in field.normalized_description.casefold()


def _has_absent_naturaleza(field: RecordDesignIntermediateField) -> bool:
    """Whether AEAT printed this row's naturaleza cell EMPTY.

    The strongest case for a reviewed rule there is, and it was excluded. A
    numeric field at least tells the renderer it is numeric; a row AEAT printed
    with no naturaleza at all states nothing about its wire representation, and
    the shipped parser records exactly that by stamping the absent-naturaleza
    marker rather than guessing a type. Modelo 184's ``151-155 PORCENTAJE DE
    RENTA ATRIBUIBLE A MIEMBROS RESIDENTES`` is the worked case: its own prose
    says "campo numerico" and subdivides it into ENTERO and DECIMAL, so the wire
    fact is knowable and reviewable -- but it lives in the description, which is
    exactly the evidence a render profile exists to carry.

    Excluding these did not make the renderer safe: it made the field invisible
    to the profile's exhaustive-coverage check and then crashed the renderer on
    an unsupported type, so the gap surfaced as a late refusal instead of as the
    reviewable rule it should have demanded.
    """
    return field.aeat_type.strip() == ABSENT_NATURALEZA_TYPE_CODE


def _is_numeric_aeat_type(aeat_type: str) -> bool:
    """Whether ``aeat_type`` names a numeric naturaleza, however AEAT spelled it.

    A workbook prints the abbreviation (``Num``, and ``N`` for the signed form);
    a PDF design prints the word, which the shipped parser canonicalises to
    ``Numerico``. Selecting on the abbreviations alone made every PDF design's
    numeric fields ineligible, so no reviewed rule was ever demanded for them and
    an empty profile satisfied exhaustive coverage completely.

    Matched on an accent-stripped stem for the same reason
    ``naturaleza_or_none`` is: AEAT does not spell consistently, and every
    unmatched spelling is a field that silently escapes review.
    """
    normalised = unicodedata.normalize("NFKD", aeat_type.strip(" .")).encode("ascii", "ignore").decode("ascii").lower()
    return normalised in {"num", "n"} or normalised.startswith("numeric")


#: A Contenido cell that instructs the FILER and states nothing about the wire.
#: Modelo 200 prints "No cumplimentar" in six art. 11.12 LIS grid positions: the
#: slot is a 17-character amount like every sibling in its grid, and the note
#: withholds the VALUE rather than describing the representation.
#:
#: This is a third case the workbook branch above did not have. Its reasoning --
#: a non-blank Contenido is the design stating the fact -- holds for a cell that
#: DESCRIBES the slot and not for one that gives the filer an instruction. Read
#: as a wire fact the phrase is unparseable, and the renderer refused on it; read
#: as blank it becomes eligible for the reviewed rule the design's own note
#: already governs.
#:
#: Deliberately an exact phrase set, not a keyword search: "no" and
#: "cumplimentar" both appear inside legitimate descriptions of what a slot
#: carries, and a loose rule would make real wire facts invisible to review.
_FILING_INSTRUCTION_ONLY_CONTENTS: Final[frozenset[str]] = frozenset({"no cumplimentar"})


def _is_filing_instruction_only(content: str) -> bool:
    """Whether the Contenido cell instructs the filer instead of stating a wire fact."""
    return content.strip().rstrip(".").casefold() in _FILING_INSTRUCTION_ONLY_CONTENTS


def _states_no_wire_fact(
    field: RecordDesignIntermediateField,
    *,
    applicability_notes: tuple[NoteStatedApplicabilityDeclaration, ...] = (),
) -> bool:
    """Whether the design left this field's wire fact unstated at its anchor.

    A WORKBOOK field has a Contenido cell, so a non-blank one is the design
    stating the fact and the field needs no reviewed rule. A PDF design has no
    such column: the parser fills ``content`` with the field's DESCRIPTIVE PROSE,
    which states the fact sometimes, partially, or not at all. Modelo 347 carries
    all of those side by side -- one field giving sign and decimals in full, one
    giving only a width, a bare cross-reference, and a purely semantic
    description -- so no rule over the text can separate them and every numeric
    PDF anchor is put to a reviewed rule instead.

    The source shape is read off the field rather than threaded in: a workbook
    anchor carries a ``source_cell`` and a PDF anchor does not, which is the
    distinction :class:`RecordDesignIntermediateField` already documents.

    Where the prose DOES state a fact the reviewed rule must agree with it, which
    keeps the official design's veto intact; that agreement is checked where the
    rule's own evidence is validated, not here.

    ``applicability_notes`` is the third case, and it is the narrowest: a cell
    whose whole content is a pointer to a note SOMEBODY HAS READ and recorded as
    stating applicability rather than representation. AEAT's own vocabulary makes
    that cell equivalent to a blank one -- ``Contenido`` holds "aclaraciones
    relativas al formato del campo" and a ``Nota`` holds "aclaraciones al
    contenido", so a note about which periods a slot applies to states no format
    -- and the field goes where a blank cell goes. Read as a wire fact instead it
    is unparseable, and the numeric derivation falls through to an unscaled
    integer nobody reviewed.

    The gate is the DECLARATION and not the shape of the text, deliberately. A
    pointer-shaped cell whose note nobody has opened may still state the wire
    fact outright; admitting all of them on shape would make roughly 183 fields
    newly eligible at once, each owing a reviewed rule that does not exist, and
    would silently swallow the runs an adjudicated
    :class:`~dev.registry.pipeline.source_defects.NoteGovernedAmountDeclaration`
    already covers. So an unread pointer keeps the reading it has today and stays
    visible as outstanding work.
    """
    if field.source_cell is None:
        return True
    if field.content is None or not field.content.strip():
        return True
    if _is_filing_instruction_only(field.content):
        return True
    return note_states_only_applicability(
        applicability_notes,
        sheet=field.sheet,
        published_content=" ".join(field.content.split()),
    )


def project_render_profile_eligibility(
    fixed_fields: Iterable[RecordDesignIntermediateField],
    *,
    applicability_notes: tuple[NoteStatedApplicabilityDeclaration, ...] = (),
) -> RenderProfileEligibility:
    """Partition fixed joined fields eligible for reviewed absent-wire authority.

    A source-reserved slot is never eligible.  A render profile exists to state
    a wire fact the official design left unstated, and a reserved run has no
    wire fact beyond being filler, so admitting one would force an author to
    model numeric meaning onto a slot that carries none.

    ``applicability_notes`` reaches :func:`_states_no_wire_fact` unchanged.  It
    is threaded rather than resolved here so that this projection stays a pure
    function of the fields it is given, and so that eligibility and the
    renderer's own routing ask ONE predicate with ONE input set.

    A caller holding a parser-read source wants
    :func:`resolve_render_profile_eligibility` instead, which resolves and
    validates that source's declarations before projecting.  Calling this
    directly with a hand-assembled argument is how a consumer comes to answer a
    different question from the renderer.
    """
    eligible = tuple(
        field
        for field in fixed_fields
        if (_is_numeric_aeat_type(field.aeat_type) or _has_absent_naturaleza(field))
        and _states_no_wire_fact(field, applicability_notes=applicability_notes)
        and not _is_source_reserved_field(field)
    )
    return RenderProfileEligibility(
        all_fields=eligible,
        width_17_fields=tuple(field for field in eligible if field.length == 17),
        smaller_fields=tuple(field for field in eligible if field.length != 17),
    )


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
