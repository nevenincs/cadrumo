"""Screen: what authoritative wording exists for each field that needs a rule.

A field whose content cell states no wire fact needs a reviewed representation
rule, and a reviewed rule needs grounding in the official design's own words.
Sibling screens hold the pieces: one reports the fields, one reports the design
notes that state a convention for a whole AEAT type, and one reads the
unnumbered notes that govern a design rather than a sheet. This joins them and
answers the question the authoring task actually turns on - not how many fields
need a rule, but how many of them the design already speaks to.

The join is by AEAT type, because that is how the designs key these
conventions. A field does not cite the note governing its class; the note names
the class and the field belongs to it.

Four conditions are reported, and every row names one of them:

- ``grounded_by_own_note`` - the field's content cell cites a note, and that
  note is defined on the field's own sheet. The strongest grounding there is:
  the design pointed at this wording FOR THIS FIELD, so no argument is needed
  that the field falls under it. This condition was missing from the first
  version of this screen, which asked only what governed a field's class and
  never what the field itself cited - and every one of modelo 200's three
  oddly-sized fields turned out to be settled by exactly this, each by its own
  sheet's note: an accounting-statement code table at width one, a document-type
  enumeration at width one, and the rate filling rule at width four.
- ``grounded_by_type_convention`` - the field's design states a convention for
  the field's own type. The rule's author reads one note and it covers every
  field of that type in that design.
- ``grounded_by_design_note`` - no convention names the field's type, but the
  design carries an unnumbered note, which governs the design rather than the
  sheet it is printed on. This is weaker evidence and is kept separate for that
  reason: a type convention names the field's class, while a design note names
  nothing and may settle representation or may not. Modelo 200's states the
  integer width, sign carriage and decimal places of every amount it reports;
  another design's says only that the NIF is mandatory. Both produce this row,
  and only reading tells them apart, so collapsing it into the condition above
  would report a field as grounded on evidence that says nothing about it.
- ``ungrounded`` - neither. The grounding has to come from somewhere else, and
  the row exists so that "somewhere else" is a known quantity rather than a gap
  discovered halfway through authoring.

A grounded row is not an authored rule, and the gap is wider than it sounds. The
note still has to be read, and it may turn out to answer a different question
entirely: reading the eleven notes behind the forty-one fields, seven state
representation and cover twelve fields, while four state who must fill a field,
when it may carry content, or which period it applies to - and those four cover
twenty-nine. The single largest of them grounds twenty-six fields with a
sentence about which entities must complete them.

So this screen answers "is there official wording addressed to this field", not
"does that wording settle it". The second question is a reading of Spanish prose
and is deliberately left to the reader: a keyword list attempting it is the
instrument error this package has recorded repeatedly, most sharply when such a
list reported the plainest wire wording in the corpus as absent.

The screen exits 0 whatever it finds. It reports; it does not gate.
"""

from __future__ import annotations

import collections
import sys
from dataclasses import dataclass
from typing import Final

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.authority import ValidatedRegistryAuthority, bundled_authority

from ..pipeline.render_check import revision_render_inputs
from .footnote_only_wire_facts import revision_findings as fields_needing_rules
from .footnote_pointer_notes import design_transcription_path, sheet_unnumbered_notes
from .type_convention_notes import revision_findings as type_conventions

#: Named once per module rather than repeated at each read site, where a typo
#: would be a silent decode change rather than an error.
_UTF_8: Final[str] = "utf-8"

__all__ = [
    "KINDS",
    "GroundingFinding",
    "NoteWorkItem",
    "classify_grounding",
    "grounding_worklist",
    "revision_findings",
    "screen_authority",
]

#: Every condition this screen can report, declared once and used at each
#: emission site so the set cannot be recovered by reading the source wrong.
KINDS: tuple[str, ...] = (
    "grounded_by_own_note",
    "grounded_by_type_convention",
    "grounded_by_design_note",
    "ungrounded",
)


@dataclass(frozen=True, slots=True)
class GroundingFinding:
    """One field needing a reviewed rule, and the wording available for it."""

    modelo: str
    revision: str
    cell: str
    #: The transcription the field's notes are defined in. Carried because a
    #: note is located by DESIGN, not by revision: several revisions share one
    #: design, and looking a note up in the wrong revision of the right modelo
    #: returns nothing at all. That mistake was made while reading this screen's
    #: own output and briefly looked like three notes resolving to empty text.
    design: str
    aeat_type: str
    #: The field's declared width. Carried because it is what decides whether a
    #: note can settle the field at all: modelo 200's amounts note states a
    #: seventeen-character value and cannot govern a one-character one, which is
    #: how three fields credited to it turned out to be settled elsewhere.
    length: int
    kind: str
    notes: tuple[str, ...]
    detail: str


@dataclass(frozen=True, slots=True)
class NoteWorkItem:
    """One note to read, and the fields a rule grounded in it would cover."""

    modelo: str
    #: The transcription to open. Without it a reader has the note's sheet and
    #: label but no file, which is exactly enough information to look in the
    #: wrong place.
    design: str
    note: str
    grounding: str
    fields: tuple[str, ...]
    #: The declared widths among those fields, which is what decides whether one
    #: rule covers them all. A note stating an amount of fifteen integers and two
    #: decimals settles a seventeen-character field and cannot settle a
    #: one-character one, so a work item spanning several widths is a signal to
    #: read before assuming a single rule.
    widths: tuple[int, ...]
    types: tuple[str, ...]
    #: Whether this note's wording differs between the designs of its modelo.
    #: A rule grounded in a drifting note holds for the design it was read in
    #: and must be re-read for the others, so the flag belongs beside the note
    #: rather than in a screen an author would have to know to run.
    grounding_drifts: bool = False


def grounding_worklist(
    findings: tuple[GroundingFinding, ...],
    *,
    drifting: frozenset[tuple[str, str, str]] = frozenset(),
) -> tuple[NoteWorkItem, ...]:
    """Group grounded fields by the note that grounds them.

    The field count is not the size of the authoring task. One note read covers
    every field citing it, so the work is the number of DISTINCT notes, and the
    order to read them in is how many fields each covers. Grouping is by note
    rather than by field for that reason.

    Ungrounded fields are absent by construction: they have no note to group
    under, and the census reports them.

    ``drifting`` is the set of ``(modelo, sheet, label)`` keys whose wording is
    not the same in every design of their modelo, as the drift screen reports
    them. It is passed in rather than computed here so this stays a function of
    its arguments, and defaults to empty so a caller that has not measured drift
    gets no claim about it rather than a false negative.
    """
    grouped: dict[tuple[str, str, str, str], list[GroundingFinding]] = collections.defaultdict(list)
    for finding in findings:
        for note in finding.notes:
            grouped[(finding.modelo, finding.design, note, finding.kind)].append(finding)
    items = [
        NoteWorkItem(
            modelo=modelo,
            design=design,
            note=note,
            grounding=kind,
            fields=tuple(sorted(item.cell for item in members)),
            widths=tuple(sorted({item.length for item in members})),
            types=tuple(sorted({item.aeat_type for item in members})),
            grounding_drifts=(modelo, *note.split(":", 1)) in drifting,
        )
        for (modelo, design, note, kind), members in grouped.items()
    ]
    return tuple(sorted(items, key=lambda item: (-len(item.fields), item.modelo, item.design, item.note)))


def revision_findings(
    authority: ValidatedRegistryAuthority, *, modelo: str, revision: str
) -> tuple[GroundingFinding, ...]:
    """Return one revision's fields needing a rule, each with its grounding."""
    needed = fields_needing_rules(authority, modelo=modelo, revision=revision)
    if not needed:
        return ()
    by_type: dict[str, list[str]] = collections.defaultdict(list)
    for convention in type_conventions(authority, modelo=modelo, revision=revision):
        for code in convention.types:
            by_type[code].append(f"{convention.sheet}:{convention.label}")

    # Design-level, not sheet-level. These notes are read from the sheet that
    # prints them because that is where they are found, and the corpus is
    # unanimous that the design is what they govern: no design carries differing
    # ones on different sheets, and the one modelo 200 prints describes amount
    # fields that its own sheet does not contain. So every field of the design
    # is a candidate reader of every one of them, whatever sheet it sits on.
    inputs = revision_render_inputs(authority, modelo=modelo, revision=revision)
    corpus_path = bundled_path() / authority.catalogues.sources[inputs.joined.source.source_ref].corpus_path
    transcription = design_transcription_path(corpus_path)
    design_notes = (
        sheet_unnumbered_notes(transcription.read_text(encoding=_UTF_8)) if transcription.is_file() else {}
    )

    return classify_grounding(
        needed,
        by_type=dict(by_type),
        design_notes=tuple(sorted(design_notes)),
        modelo=modelo,
        revision=revision,
        design=transcription.name,
    )


def classify_grounding(
    needed: tuple[object, ...],
    *,
    by_type: dict[str, list[str]],
    design_notes: tuple[str, ...],
    modelo: str,
    revision: str,
    design: str = "",
) -> tuple[GroundingFinding, ...]:
    """Classify already-gathered fields and wording, separately from gathering them.

    Kept apart from :func:`revision_findings` because the classification is what
    decides which evidence a rule may rest on, and an instrument proven only
    against the live corpus is proven against whatever the corpus happens to
    say. Given the three inputs it can be shown to reach each condition on
    explicit input - which is also why no test here has to reach inside this
    module and replace what it imports.
    """
    findings: list[GroundingFinding] = []
    for field in needed:
        own = tuple(field.notes) if field.kind != "pointer_unresolved" else ()
        notes = tuple(by_type.get(field.aeat_type, ()))
        if own:
            kind = "grounded_by_own_note"
            notes = tuple(f"{field.cell.split('!', 1)[0]}:{note}" for note in own)
            detail = f"the field's own cell cites {', '.join(own)}, defined on its sheet"
        elif notes:
            kind = "grounded_by_type_convention"
            detail = f"{len(notes)} note(s) state a convention for type {field.aeat_type}"
        elif design_notes:
            kind = "grounded_by_design_note"
            notes = tuple(f"{sheet}:unnumbered" for sheet in design_notes)
            detail = (
                f"no convention names type {field.aeat_type}; the design carries "
                f"{len(design_notes)} unnumbered note(s), which have to be read"
            )
        else:
            kind = "ungrounded"
            detail = f"the design states no convention for type {field.aeat_type} and carries no design note"
        findings.append(
            GroundingFinding(
                modelo=modelo,
                revision=revision,
                cell=field.cell,
                design=design,
                aeat_type=field.aeat_type,
                length=field.length,
                kind=kind,
                notes=notes,
                detail=detail,
            )
        )
    return tuple(findings)


def screen_authority(
    authority: ValidatedRegistryAuthority, modelo_ids: tuple[str, ...]
) -> tuple[GroundingFinding, ...]:
    """Screen every revision that can produce render inputs."""
    findings: list[GroundingFinding] = []
    for modelo_id in modelo_ids:
        for revision_id in authority.modelo(modelo_id).revisions:
            try:
                findings.extend(revision_findings(authority, modelo=modelo_id, revision=str(revision_id)))
            except (ValueError, KeyError, FileNotFoundError, OSError):
                continue
    return tuple(findings)


def main() -> int:
    """Print one greppable row per field and a closing census; always exit 0."""
    from .corpus import bundled_modelo_ids

    authority = bundled_authority()
    findings = screen_authority(authority, bundled_modelo_ids())
    tally: collections.Counter[str] = collections.Counter(item.kind for item in findings)
    for item in findings:
        sys.stdout.write(
            f"rule_grounding modelo={item.modelo} revision={item.revision} cell={item.cell} "
            f"aeat_type={item.aeat_type!r} kind={item.kind} "
            f"notes={(','.join(item.notes) or 'none')!r} detail={item.detail!r}\n"
        )
    # The reading load, which is what the authoring task costs: one note read
    # covers every field citing it, so the distinct notes matter and the field
    # count does not.
    #
    # Counted as work items, not as (revision, note) pairs. Several revisions of
    # a modelo share one design, so a note common to them is ONE reading; the
    # earlier count keyed on the revision and reported thirteen readings for
    # eleven notes, which is the same concept measured two ways in one census.
    from .note_text_drift import screen_corpus as note_drift

    drifting = frozenset((item.modelo, item.sheet, item.label) for item in note_drift())
    work = grounding_worklist(findings, drifting=drifting)
    ungrounded_types = {(item.modelo, item.aeat_type) for item in findings if item.kind == "ungrounded"}
    for item in work:
        sys.stdout.write(
            f"rule_grounding_work modelo={item.modelo} design={item.design!r} note={item.note!r} "
            f"grounding={item.grounding} "
            f"fields={len(item.fields)} widths={','.join(str(width) for width in item.widths)} "
            f"types={','.join(item.types)!r} "
            f"grounding_drifts={str(item.grounding_drifts).lower()}\n"
        )
    kinds = " ".join(f"{kind}={tally[kind]}" for kind in KINDS)
    sys.stdout.write(
        f"summary fields={len(findings)} {kinds} distinct_notes_to_read={len(work)} "
        f"notes_whose_wording_drifts={sum(1 for item in work if item.grounding_drifts)} "
        f"fields_on_drifting_wording={sum(len(item.fields) for item in work if item.grounding_drifts)} "
        f"ungrounded_modelo_type_pairs={len(ungrounded_types)}\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
