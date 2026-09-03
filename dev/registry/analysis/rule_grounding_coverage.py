"""Screen: what authoritative wording exists for each field that needs a rule.

A field whose content cell states no wire fact needs a reviewed representation
rule, and a reviewed rule needs grounding in the official design's own words.
Two screens each hold half of that: one reports the fields, the other reports
the design notes that state a convention for a whole AEAT type. This joins them
and answers the question the authoring task actually turns on - not how many
fields need a rule, but how many of them the design already speaks to.

The join is by AEAT type, because that is how the designs key these
conventions. A field does not cite the note governing its class; the note names
the class and the field belongs to it.

Two conditions are reported, and every row names one of them:

- ``grounded_by_type_convention`` - the field's design states a convention for
  the field's own type. The rule's author reads one note and it covers every
  field of that type in that design.
- ``ungrounded`` - the design states no convention for this field's type. The
  grounding has to come from somewhere else, and the row exists so that
  "somewhere else" is a known quantity rather than a gap discovered halfway
  through authoring.

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

from cadrumo.domain.calculations.registry.authority import ValidatedRegistryAuthority, bundled_authority

from .footnote_only_wire_facts import revision_findings as fields_needing_rules
from .type_convention_notes import revision_findings as type_conventions

__all__ = [
    "KINDS",
    "GroundingFinding",
    "revision_findings",
    "screen_authority",
]

#: Every condition this screen can report, declared once and used at each
#: emission site so the set cannot be recovered by reading the source wrong.
KINDS: tuple[str, ...] = (
    "grounded_by_type_convention",
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

    findings: list[GroundingFinding] = []
    for field in needed:
        notes = tuple(by_type.get(field.aeat_type, ()))
        findings.append(
            GroundingFinding(
                modelo=modelo,
                revision=revision,
                cell=field.cell,
                aeat_type=field.aeat_type,
                kind="grounded_by_type_convention" if notes else "ungrounded",
                notes=notes,
                detail=(
                    f"{len(notes)} note(s) state a convention for type {field.aeat_type}"
                    if notes
                    else f"the design states no convention for type {field.aeat_type}"
                ),
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
