"""Screen: workbook content cells that state a wire fact only by pointing at a note.

A workbook record design has a ``Contenido`` column, and the render-profile
eligibility predicate reads a non-blank cell there as the design stating the
field's wire fact - so the field needs no reviewed rule. Some of those cells
state nothing themselves: they hold a bare footnote pointer, and the fact lives
in the note the pointer names. Treating the pointer as the fact admits a field
to the renderer on the strength of a cross-reference nobody followed.

This screen reports that population and follows the reference. For each cell it
names the modelo, the revision, the record, the exact source cell, the field's
offset and length, the pointer as written, the notes it resolves to, and
whether the resolved wording uses the vocabulary of how a value is written.

That last is a reading aid and not a verdict, in BOTH directions. It is a fixed
keyword list, so it recognises one wording of the concept and misses others: it
misses modelo 200's nota 1, which states a filling rule outright. A vocabulary
miss therefore orders the reading queue and settles nothing, and no count of
misses may be reported as a count of notes that state no wire fact.

Four conditions are reported, and every row names one of them. Three of them
are outstanding work - a reference nobody has followed yet - and the fourth is
not:

- ``pointer_resolves_vocabulary_hit`` - the note the cell points at is defined
  and uses the reading aid's vocabulary, so it is worth opening first.
- ``pointer_resolves_vocabulary_miss`` - the note is defined and does not use
  that vocabulary. This is NOT a finding that the note states no wire fact, and
  must not be read as one. Modelo 200's nota 1 is the standing counterexample:
  it says "se rellenaran los dos primeros digitos con el tipo, y los dos
  ultimos con 00. Ej: 25% se rellenara como 2500", which is a filling rule in
  full, and the vocabulary misses it because the note says digitos and
  rellenaran rather than decimal or ceros. Every row in this condition still
  has to be read by the rule's author.
- ``pointer_unresolved`` - the pointer names a note the design never defines.
  Reported separately because the remedy is a transcription, not a rule: the
  evidence is missing rather than silent.
- ``pointer_adjudicated`` - somebody DID follow this reference. A
  :class:`~dev.registry.pipeline.source_defects.NoteGovernedAmountDeclaration`
  covers the cell: pinned to this design by digest, to this sheet by name, and
  to this exact published pointer, carrying the note text that was read and the
  representation adjudicated from it. The renderer decides eligibility on that
  same identity, so a row here is a cell the renderer already treats as read
  rather than as a bare pointer.

  A row in this condition proves the reference was FOLLOWED. It is not a claim
  that the reading was correct, that the note settles the field, or that the
  adjudicated representation is right - only that a reviewed, re-checkable
  declaration exists where previously there was a cross-reference nobody had
  opened. Re-reading a declaration remains ordinary review work; this screen
  simply stops counting it as unopened.

The rows are kept and reclassified rather than dropped, so the covered
population stays visible and a reader can see the mechanism working. The
outstanding population is therefore ``OUTSTANDING_KINDS``, not every row: a
consumer counting work to be done must filter on it, and the summary line
reports the two totals separately so a covered row is never read as a pending
one.

An adjudication does not outrank ``pointer_unresolved``. A design that never
defines the note still owes a transcription whatever has been adjudicated for
it, so that condition is decided first and is unchanged by this table.

Only fields the eligibility predicate would newly admit are reported. A field
already eligible needs no pointer argument, and a reserved slot never becomes
eligible, so including either would inflate the population with rows carrying
no work.

The screen exits 0 whatever it finds. It reports; it does not gate. The gate
belongs with the predicate correction, which cannot land until the reviewed
rules that correction makes due exist - and this screen is what those rules
are grounded in.
"""

from __future__ import annotations

import collections
import sys
from dataclasses import dataclass

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.authority import ValidatedRegistryAuthority, bundled_authority

from ..pipeline._record_design_ir import RecordDesignIntermediateField, RecordDesignIntermediateSource
from ..pipeline._render_profile import project_render_profile_eligibility
from ..pipeline.render_check import revision_render_inputs
from ..pipeline.source_defects import (
    NoteGovernedAmountDeclaration,
    note_governed_amount_scale_for,
    note_governed_amounts_for,
)
from .footnote_pointer_notes import (
    PointerEvidence,
    design_transcription_path,
    resolve_pointer_notes,
    sheet_note_definitions,
)

__all__ = [
    "KINDS",
    "OUTSTANDING_KINDS",
    "PointerWireFactFinding",
    "cell_adjudication",
    "classify_pointer",
    "pinned_adjudications",
    "revision_findings",
    "screen_authority",
]

#: Every condition this screen can report, declared once and used at each
#: emission site, so the set cannot be recovered by reading the source wrong.
KINDS: tuple[str, ...] = (
    "pointer_resolves_vocabulary_hit",
    "pointer_resolves_vocabulary_miss",
    "pointer_unresolved",
    "pointer_adjudicated",
)

#: The conditions that are work still to be done. Declared beside ``KINDS`` and
#: derived from it, so a condition added later is outstanding unless somebody
#: says otherwise - the safe default for a screen whose population is a queue.
OUTSTANDING_KINDS: tuple[str, ...] = tuple(kind for kind in KINDS if kind != "pointer_adjudicated")

_UTF_8 = "utf-8"


@dataclass(frozen=True, slots=True)
class PointerWireFactFinding:
    """One content cell whose wire fact lives behind a footnote pointer."""

    modelo: str
    revision: str
    record: str
    cell: str
    offset: int
    length: int
    #: The AEAT type the design gives this field. Carried because the grounding
    #: for a reviewed rule is keyed to the type, not to the field.
    aeat_type: str
    kind: str
    pointer: str
    notes: tuple[str, ...]
    description: str
    detail: str


def would_become_eligible(field: RecordDesignIntermediateField) -> bool:
    """Whether dropping the pointer-as-fact reading would admit this field.

    Asked through the shipped predicate rather than by restating its clauses.
    The field is put through :func:`project_render_profile_eligibility` twice,
    once as it stands and once with its content cleared, and only a field the
    predicate rejects now and admits then is reported. Restating the numeric,
    absent-naturaleza and reserved clauses here would be a second copy of the
    eligibility rule, and the copy would be the one that stopped agreeing.
    """
    if project_render_profile_eligibility([field]).all_fields:
        return False
    cleared = field.model_copy(update={"content": None})
    return bool(project_render_profile_eligibility([cleared]).all_fields)


def pinned_adjudications(source: RecordDesignIntermediateSource) -> tuple[NoteGovernedAmountDeclaration, ...]:
    """Return the adjudications declared for, and pinned to, this parser-read design.

    Resolved from the source the parser read - its reference and its SHA-256 -
    and never from a caller-supplied list, so this screen and the renderer are
    reading one table for one document.

    A declaration naming this source but pinned to another digest is dropped
    here rather than raised on. The renderer refuses outright in that case, and
    refusing is right where a document is about to be emitted; this screen has
    the whole corpus to report on, and a stale pin means the adjudication does
    not cover the file in hand - which is exactly a cell nobody has followed the
    reference for. Dropping it therefore leaves the cell outstanding, which is
    the conservative answer, rather than crediting it or ending the run.
    """
    return tuple(
        declaration
        for declaration in note_governed_amounts_for(source.source_ref)
        if declaration.source_ref == source.source_ref and declaration.source_sha256 == source.source_sha256
    )


def cell_adjudication(
    declarations: tuple[NoteGovernedAmountDeclaration, ...], *, sheet: str, content: str
) -> NoteGovernedAmountDeclaration | None:
    """Return the declaration covering this content cell, or ``None``.

    The verdict is taken from :func:`note_governed_amount_scale_for`, the same
    matcher the renderer admits a cell by, so the two cannot disagree about what
    is covered. The declaration is looked up afterwards only to quote the note
    that was read into the row's detail line.

    ``content`` is whitespace-normalised the way the renderer normalises it
    before matching. The renderer additionally peels a clause wrapped whole in
    brackets; a bracketed cell is not a bare pointer and never reaches this
    screen, so there is nothing here for that peel to do.
    """
    published = " ".join(content.split())
    if note_governed_amount_scale_for(declarations, sheet=sheet, published_content=published) is None:
        return None
    return next(
        declaration
        for declaration in declarations
        if declaration.sheet == sheet and declaration.published_content == published
    )


def classify_pointer(
    evidence: PointerEvidence, *, resolved: int, adjudication: NoteGovernedAmountDeclaration | None
) -> tuple[str, str]:
    """Return the condition a resolved pointer falls under, and its detail line.

    Separated from the walk so all four conditions are reachable from a test
    with input written in it. One of them - ``pointer_resolves_vocabulary_hit`` -
    has no instance anywhere in the corpus, so while this decision lived inline
    it had neither a live member nor a proof, which is the state this package
    treats as a condition that has stopped reporting without anyone noticing.

    ``adjudication`` is required rather than defaulted. A default would let a
    caller that never looked report a covered cell as outstanding work by
    omission, which is the reading this condition exists to end.

    The order is the precedence. An unresolved pointer is unresolved whatever
    vocabulary the notes it did resolve happen to use, and whatever has been
    adjudicated for it, because a design that never defines the note owes a
    transcription either way. An adjudicated pointer outranks the vocabulary
    reading, which is a queue order for notes still to be opened and has nothing
    to say about a note somebody has already read.
    """
    if evidence.unresolved:
        return "pointer_unresolved", f"design defines no {', '.join(evidence.unresolved)}"
    if adjudication is not None:
        return "pointer_adjudicated", (
            f"{resolved} note(s) resolved, read at {adjudication.sheet}!{adjudication.note_cell}: "
            f"{adjudication.note_statement!r}"
        )
    if evidence.mentions_wire_vocabulary:
        return "pointer_resolves_vocabulary_hit", f"{resolved} note(s) resolved, read these first"
    return "pointer_resolves_vocabulary_miss", f"{resolved} note(s) resolved, still to be read"


def revision_findings(
    authority: ValidatedRegistryAuthority, *, modelo: str, revision: str
) -> tuple[PointerWireFactFinding, ...]:
    """Return one revision's pointer-only content cells with their notes resolved."""
    inputs = revision_render_inputs(authority, modelo=modelo, revision=revision)
    source_ref = inputs.joined.source.source_ref
    corpus_path = bundled_path() / authority.catalogues.sources[source_ref].corpus_path
    transcription = design_transcription_path(corpus_path)
    by_sheet = sheet_note_definitions(transcription.read_text(encoding=_UTF_8)) if transcription.is_file() else {}
    adjudications = pinned_adjudications(inputs.joined.source)

    findings: list[PointerWireFactFinding] = []
    for joined_field in inputs.joined.fields:
        field = joined_field.parser_field
        content = field.content
        if field.source_cell is None or content is None or not content.strip():
            continue
        # Resolved against the field's OWN sheet. A design numbers each page's
        # notes from one, so a design-wide lookup hands back another page's note.
        resolved = resolve_pointer_notes(content, by_sheet.get(field.sheet, {}))
        if not resolved or not would_become_eligible(field):
            continue
        # Asked through the module that owns the reading aid rather than by
        # keeping a second copy of its vocabulary here.
        evidence = PointerEvidence(cell=content, pointer=content.strip(), notes=resolved)
        kind, detail = classify_pointer(
            evidence,
            resolved=len(resolved),
            adjudication=cell_adjudication(adjudications, sheet=field.sheet, content=content),
        )
        findings.append(
            PointerWireFactFinding(
                modelo=modelo,
                revision=revision,
                record=field.record_identity,
                cell=f"{field.sheet}!{field.source_cell}",
                offset=field.offset,
                length=field.length,
                aeat_type=field.aeat_type.strip(),
                description=field.normalized_description,
                kind=kind,
                pointer=content.strip(),
                notes=tuple(item.note for item in resolved),
                detail=detail,
            )
        )
    return tuple(findings)


def screen_authority(
    authority: ValidatedRegistryAuthority, modelo_ids: tuple[str, ...]
) -> tuple[PointerWireFactFinding, ...]:
    """Screen every revision that can produce render inputs.

    A revision that cannot produce them - no layout, no authored map, no
    enrolled profile - is skipped rather than reported: this screen is about
    what a content cell says, and a revision with no render inputs has no
    content cells to say it with.
    """
    inapplicable: list[tuple[str, str, str]] = []
    attempted = 0
    findings: list[PointerWireFactFinding] = []
    for modelo_id in modelo_ids:
        definition = authority.modelo(modelo_id)
        for revision_id in definition.revisions:
            attempted += 1
            try:
                findings.extend(revision_findings(authority, modelo=modelo_id, revision=str(revision_id)))
            except (ValueError, KeyError, FileNotFoundError, OSError) as error:
                # Inapplicable, not broken: these revisions declare no export
                # layout or cite no record design, so the screen genuinely cannot
                # examine them. The skip is correct; its INVISIBILITY was not.
                # Measured over the bundled authority: 94 of 128 revisions land
                # here, so a clean count was reading as corpus-wide coverage when
                # it covered close to a quarter of the corpus.
                inapplicable.append((modelo_id, str(revision_id), str(error)))
                continue
    if inapplicable:
        sys.stderr.write(
            f"footnote_only_wire_facts: examined {attempted - len(inapplicable)} of {attempted} revision(s); "
            f"{len(inapplicable)} declared nothing this screen can read and were not "
            "examined, so the count below is not corpus-wide" + chr(10)
        )
    return tuple(findings)


def main() -> int:
    """Print one greppable row per finding and a closing census; always exit 0."""
    from .corpus import bundled_modelo_ids

    authority = bundled_authority()
    findings = screen_authority(authority, bundled_modelo_ids())
    tally: collections.Counter[str] = collections.Counter(item.kind for item in findings)
    for item in findings:
        sys.stdout.write(
            f"pointer_wire_fact modelo={item.modelo} revision={item.revision} "
            f"record={item.record!r} cell={item.cell} offset={item.offset} length={item.length} "
            f"kind={item.kind} pointer={item.pointer!r} notes={(','.join(item.notes) or 'none')!r} "
            f"description={item.description!r} "
            f"detail={item.detail!r}\n"
        )
    kinds = " ".join(f"{kind}={tally[kind]}" for kind in KINDS)
    modelos = len({item.modelo for item in findings})
    # Both totals, on the one line. `findings` is every pointer-only cell this
    # screen sees; `outstanding` is the queue. Reporting only the first would let
    # a covered row be counted as pending work, which is the whole reason this
    # screen could never reach zero.
    outstanding = sum(tally[kind] for kind in OUTSTANDING_KINDS)
    sys.stdout.write(
        f"summary findings={len(findings)} outstanding={outstanding} "
        f"adjudicated={len(findings) - outstanding} modelos={modelos} {kinds}\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
