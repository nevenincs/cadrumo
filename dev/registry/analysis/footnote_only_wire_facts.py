"""Screen: workbook content cells that state a wire fact only by pointing at a note.

A workbook record design has a ``Contenido`` column, and the render-profile
eligibility predicate reads a non-blank cell there as the design stating the
field's wire fact - so the field needs no reviewed rule. Some of those cells
state nothing themselves: they hold a bare footnote pointer, and the fact lives
in the note the pointer names. Treating the pointer as the fact admits a field
to the renderer on the strength of a cross-reference nobody followed.

This screen reports that population and follows the reference. For each cell it
names the modelo, the revision, the record, the exact source cell, the field's
offset and length, the pointer as written, the
notes it resolves to, and whether the resolved wording uses the vocabulary of
how a value is written. That last is a reading aid and not a verdict: a note
mentioning decimals may still not settle the field. It exists so an author
facing many fields can see which notes are worth opening first.

Three conditions are reported, and every row names one of them:

- ``pointer_resolves_to_wire_wording`` - the note the cell points at does use
  that vocabulary, so there is authored wording to ground a reviewed rule in.
- ``pointer_resolves_without_wire_wording`` - the note is defined and says
  nothing about representation. The field still needs a rule; the design just
  does not supply its text, which is a different research task and must not be
  mistaken for the case above.
- ``pointer_unresolved`` - the pointer names a note the design never defines.
  Reported separately because the remedy is a transcription, not a rule: the
  evidence is missing rather than silent.

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

from ..pipeline._record_design_ir import RecordDesignIntermediateField
from ..pipeline._render_profile import project_render_profile_eligibility
from ..pipeline.render_check import revision_render_inputs
from .footnote_pointer_notes import (
    PointerEvidence,
    design_transcription_path,
    note_definitions,
    resolve_pointer_notes,
)

__all__ = [
    "KINDS",
    "PointerWireFactFinding",
    "revision_findings",
    "screen_authority",
]

#: Every condition this screen can report, declared once and used at each
#: emission site, so the set cannot be recovered by reading the source wrong.
KINDS: tuple[str, ...] = (
    "pointer_resolves_to_wire_wording",
    "pointer_resolves_without_wire_wording",
    "pointer_unresolved",
)

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


def revision_findings(
    authority: ValidatedRegistryAuthority, *, modelo: str, revision: str
) -> tuple[PointerWireFactFinding, ...]:
    """Return one revision's pointer-only content cells with their notes resolved."""
    inputs = revision_render_inputs(authority, modelo=modelo, revision=revision)
    source_ref = inputs.joined.source.source_ref
    corpus_path = bundled_path() / authority.catalogues.sources[source_ref].corpus_path
    transcription = design_transcription_path(corpus_path)
    definitions = note_definitions(transcription.read_text(encoding=_UTF_8)) if transcription.is_file() else {}

    findings: list[PointerWireFactFinding] = []
    for joined_field in inputs.joined.fields:
        field = joined_field.parser_field
        content = field.content
        if field.source_cell is None or content is None or not content.strip():
            continue
        resolved = resolve_pointer_notes(content, definitions)
        if not resolved or not would_become_eligible(field):
            continue
        # Asked through the module that owns the reading aid rather than by
        # keeping a second copy of its vocabulary here.
        evidence = PointerEvidence(cell=content, pointer=content.strip(), notes=resolved)
        if evidence.unresolved:
            kind = "pointer_unresolved"
            detail = f"design defines no {', '.join(evidence.unresolved)}"
        elif evidence.mentions_wire_vocabulary:
            kind = "pointer_resolves_to_wire_wording"
            detail = f"{len(resolved)} note(s) resolved, wire vocabulary present"
        else:
            kind = "pointer_resolves_without_wire_wording"
            detail = f"{len(resolved)} note(s) resolved, wire vocabulary absent"
        findings.append(
            PointerWireFactFinding(
                modelo=modelo,
                revision=revision,
                record=field.record_identity,
                cell=f"{field.sheet}!{field.source_cell}",
                offset=field.offset,
                length=field.length,
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
    findings: list[PointerWireFactFinding] = []
    for modelo_id in modelo_ids:
        definition = authority.modelo(modelo_id)
        for revision_id in definition.revisions:
            try:
                findings.extend(revision_findings(authority, modelo=modelo_id, revision=str(revision_id)))
            except (ValueError, KeyError, FileNotFoundError, OSError):
                continue
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
    sys.stdout.write(f"summary findings={len(findings)} modelos={modelos} {kinds}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
