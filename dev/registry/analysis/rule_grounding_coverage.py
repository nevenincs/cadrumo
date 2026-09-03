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

Three conditions are reported, and every row names one of them:

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

A grounded row is not an authored rule. The note still has to be read, and it
may turn out to settle less than the field needs. What the row establishes is
that there is official wording to read, which is exactly what the per-field
pointer route failed to produce.

The screen exits 0 whatever it finds. It reports; it does not gate.
"""

from __future__ import annotations

import collections
import sys
from dataclasses import dataclass

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.authority import ValidatedRegistryAuthority, bundled_authority

from ..pipeline.render_check import revision_render_inputs
from .footnote_only_wire_facts import revision_findings as fields_needing_rules
from .footnote_pointer_notes import design_transcription_path, sheet_unnumbered_notes
from .type_convention_notes import revision_findings as type_conventions

__all__ = [
    "KINDS",
    "GroundingFinding",
    "classify_grounding",
    "revision_findings",
    "screen_authority",
]

#: Every condition this screen can report, declared once and used at each
#: emission site so the set cannot be recovered by reading the source wrong.
KINDS: tuple[str, ...] = (
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
    aeat_type: str
    kind: str
    notes: tuple[str, ...]
    detail: str


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
        sheet_unnumbered_notes(transcription.read_text(encoding="utf-8")) if transcription.is_file() else {}
    )

    return classify_grounding(
        needed, by_type=dict(by_type), design_notes=tuple(sorted(design_notes)), modelo=modelo, revision=revision
    )


def classify_grounding(
    needed: tuple[object, ...],
    *,
    by_type: dict[str, list[str]],
    design_notes: tuple[str, ...],
    modelo: str,
    revision: str,
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
        notes = tuple(by_type.get(field.aeat_type, ()))
        if notes:
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
                aeat_type=field.aeat_type,
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
    # covers every field of its type in its design, so the distinct notes matter
    # and the field count does not.
    reads = {(item.modelo, item.revision, note) for item in findings for note in item.notes}
    ungrounded_types = {(item.modelo, item.aeat_type) for item in findings if item.kind == "ungrounded"}
    kinds = " ".join(f"{kind}={tally[kind]}" for kind in KINDS)
    sys.stdout.write(
        f"summary fields={len(findings)} {kinds} distinct_notes_to_read={len(reads)} "
        f"ungrounded_modelo_type_pairs={len(ungrounded_types)}\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
