"""Screen: design notes that state a wire convention for a whole AEAT type.

A record design mostly does not tell each field how it is written. It says it
once, for a type, in a general note - modelo 202 settles alphanumeric fields
("alineados a la izquierda, rellenando con blancos por la derecha"), numeric
fields ("alineados a la derecha rellenando con ceros por la izquierda") and
signed numeric fields in three notes covering every field in the design.

This matters because the reviewed representation rules a render profile needs
have been treated as per-field research: read the field's content cell, follow
its footnote pointer, ground a rule in what the note says. On that route the
grounding is empty - no pointer in this corpus resolves to representation
wording - and the emptiness was nearly reported as the designs being silent.
They are not silent. They state the convention once and key it to the type, and
no field cites it, because a field does not need to cite what governs its whole
class.

A note is reported when it names one of the AEAT type codes that the design's
own fields actually carry, written in parentheses as the designs write them.
The type set is read from the parsed fields rather than from a list kept here:
a list would be a second declaration of the type vocabulary, and it would be
the copy that stopped matching when a design introduced a code nobody had seen.
Parentheses are required because a bare code is a letter that occurs in
ordinary Spanish; the designs that state these conventions all parenthesise.

One condition is reported, and every row names it:

- ``type_convention_stated`` - a note naming at least one type the design uses.
  The row carries the types named and the note's wording, because the decision
  the row exists to support is which fields the convention governs, and that is
  read from the text and not from the match.

Whether a matched note really states a convention is the rule author's call.
The screen finds the notes worth reading and says which types they mention; it
does not classify their wording, having watched a keyword classifier report the
plainest wire wording in the corpus as absent.

The screen exits 0 whatever it finds. It reports; it does not gate.
"""

from __future__ import annotations

import collections
import re
import sys
from dataclasses import dataclass

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.authority import ValidatedRegistryAuthority, bundled_authority

from ..pipeline.render_check import revision_render_inputs
from .footnote_pointer_notes import design_transcription_path, sheet_note_definitions

__all__ = [
    "KINDS",
    "TypeConventionFinding",
    "revision_findings",
    "screen_authority",
    "types_named_in",
]

#: Every condition this screen can report, declared once and used at its
#: emission site so the set cannot be recovered by reading the source wrong.
KINDS: tuple[str, ...] = ("type_convention_stated",)

_UTF_8 = "utf-8"


@dataclass(frozen=True, slots=True)
class TypeConventionFinding:
    """One design note that names an AEAT type its own fields carry."""

    modelo: str
    design: str
    sheet: str
    label: str
    kind: str
    types: tuple[str, ...]
    #: One ``(type, field count)`` pair per named type. Kept per type rather
    #: than pre-summed so a consumer can count a type once per design instead
    #: of once per note that mentions it.
    field_counts: tuple[tuple[str, int], ...]
    text: str

    @property
    def fields_governed(self) -> int:
        """Fields of every type this note names, within this design."""
        return sum(count for _, count in self.field_counts)


def types_named_in(text: str, types: frozenset[str]) -> tuple[str, ...]:
    """Return the design's own type codes this note names, in parentheses.

    The candidate set is the design's, so this cannot drift from the type
    vocabulary in use. Parentheses are required: an AEAT type code is a short
    token - ``N``, ``An``, ``Num`` - and matching one bare would fire on
    ordinary Spanish. ``(Num)`` does not match ``(N)`` because the pattern is
    anchored on both sides of the exact code.
    """
    return tuple(sorted(code for code in types if code and re.search(rf"\({re.escape(code)}\)", text)))


def revision_findings(
    authority: ValidatedRegistryAuthority, *, modelo: str, revision: str
) -> tuple[TypeConventionFinding, ...]:
    """Return one revision's design notes that state a type-level convention."""
    inputs = revision_render_inputs(authority, modelo=modelo, revision=revision)
    corpus_path = bundled_path() / authority.catalogues.sources[inputs.joined.source.source_ref].corpus_path
    transcription = design_transcription_path(corpus_path)
    if not transcription.is_file():
        return ()

    per_type: collections.Counter[str] = collections.Counter(
        field.parser_field.aeat_type.strip() for field in inputs.joined.fields
    )
    types = frozenset(per_type)
    findings: list[TypeConventionFinding] = []
    for sheet, labels in sorted(sheet_note_definitions(transcription.read_text(encoding=_UTF_8)).items()):
        for label, text in sorted(labels.items()):
            named = types_named_in(text, types)
            if not named:
                continue
            findings.append(
                TypeConventionFinding(
                    modelo=modelo,
                    design=transcription.name,
                    sheet=sheet,
                    label=label,
                    kind="type_convention_stated",
                    types=named,
                    field_counts=tuple((code, per_type[code]) for code in named),
                    text=text,
                )
            )
    return tuple(findings)


def screen_authority(
    authority: ValidatedRegistryAuthority, modelo_ids: tuple[str, ...]
) -> tuple[TypeConventionFinding, ...]:
    """Screen every revision that can produce render inputs, once per design.

    Deduplicated by design rather than by revision: several revisions of a
    modelo share one transcription, and reporting the same note once per
    revision would multiply the population by how often a design was reused
    rather than by how much wording it carries.
    """
    findings: list[TypeConventionFinding] = []
    seen: set[str] = set()
    for modelo_id in modelo_ids:
        for revision_id in authority.modelo(modelo_id).revisions:
            try:
                found = revision_findings(authority, modelo=modelo_id, revision=str(revision_id))
            except (ValueError, KeyError, FileNotFoundError, OSError):
                continue
            if found and found[0].design in seen:
                continue
            if found:
                seen.add(found[0].design)
            findings.extend(found)
    return tuple(findings)


def main() -> int:
    """Print one greppable row per finding and a closing census; always exit 0."""
    from .corpus import bundled_modelo_ids

    authority = bundled_authority()
    findings = screen_authority(authority, bundled_modelo_ids())
    for item in findings:
        sys.stdout.write(
            f"type_convention modelo={item.modelo} design={item.design!r} sheet={item.sheet!r} "
            f"label={item.label!r} kind={item.kind} types={','.join(item.types)!r} "
            f"fields_governed={item.fields_governed} text={item.text[:200]!r}\n"
        )
    designs = len({item.design for item in findings})
    modelos = len({item.modelo for item in findings})
    governed = sum(item.fields_governed for item in findings)
    sys.stdout.write(
        f"summary findings={len(findings)} designs={designs} modelos={modelos} "
        f"field_citations_covered={governed}\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
