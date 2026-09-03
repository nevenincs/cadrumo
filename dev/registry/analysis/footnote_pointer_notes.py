"""Resolve a footnote pointer in a design's Contenido cell to the note it points at.

A workbook design states a field's wire fact in its Contenido column, and the
render-profile eligibility predicate reads a non-blank cell as the design having
stated it. Some cells hold only a pointer - ``Nota 4.`` - which states nothing on
its own, so the field is treated as governed by a fact that was never given.

Correcting that predicate makes 183 fields newly eligible, and every eligible
field needs a reviewed representation rule. That figure was measured once, by
applying the corrected predicate to the whole corpus, and nothing in this tree
reproduces it: the predicate it corrects still reads the old way, so re-running
the measurement means correcting it first. Treat the number as the order of the
work rather than a current count, and re-measure it as part of the correction
rather than trusting it afterwards. An author writing those rules needs
to know what each pointer actually points at, because the answer decides the
rule: a note that gives the numeric convention constrains the rule, and a note
about applicability leaves the wire fact still unstated.

This resolves the pointer against the design's own extracted text and prints the
note beside the field. It authors nothing and decides nothing. Modelo 353's
``Nota 4`` reads "Solo para periodos 02 y siguientes" - an applicability
statement carrying no scale, no decimals and no sign - which is the evidence
that the pointer states no wire fact, quoted from the design rather than
asserted about it.

The extracted markdown is a transcription of the workbook, so a pointer this
cannot resolve is reported as unresolved rather than skipped: an author who sees
nothing cannot tell a note that says little from a note that was not found.
"""

from __future__ import annotations

import re
import sys
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

__all__ = [
    "FootnotePointerNote",
    "PointerEvidence",
    "design_transcription_path",
    "note_definitions",
    "pointer_evidence_for_design",
    "resolve_pointer_notes",
]

#: A Contenido cell holding only a footnote pointer: "Nota 4", "Notas 1 y 2",
#: optionally preceded by "Véase". Anything more is the design saying something.
POINTER = re.compile(r"^(?:v[eé]ase\s+)?notas?\s*[\d\s,y]*$", re.IGNORECASE)
_DEFINITION = re.compile(r"^\s*\|?\s*(nota\s*\d+)\s*:\s*(.*)$", re.IGNORECASE)
_ROW = re.compile(r"^\s*\|?\s*(nota\s*\d+)\b", re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class FootnotePointerNote:
    """One footnote pointer and the note text it resolves to, if any."""

    pointer: str
    note: str
    text: str

    @property
    def resolved(self) -> bool:
        """Whether the design carried a definition for this pointer."""
        return bool(self.text)


def note_definitions(extracted: str) -> dict[str, str]:
    """Return each note label in a design's extracted text mapped to its wording.

    A definition is a row whose first cell is ``Nota N:``. The wording may sit on
    that row or on the rows beneath it, so continuation lines are gathered until
    the next note or a row that starts a table again.
    """
    definitions: dict[str, list[str]] = {}
    current: str | None = None
    for line in extracted.splitlines():
        match = _DEFINITION.match(line)
        if match is not None:
            current = _normalise(match.group(1))
            definitions.setdefault(current, [])
            if match.group(2).strip():
                definitions[current].append(match.group(2).strip())
            continue
        if current is None:
            continue
        stripped = line.strip().lstrip("|").strip()
        if not stripped or stripped.startswith("#") or _ROW.match(line):
            current = None
            continue
        definitions[current].append(stripped)
    return {label: " ".join(parts).strip() for label, parts in definitions.items()}


def _normalise(label: str) -> str:
    return re.sub(r"\s+", " ", label.strip().lower())


def resolve_pointer_notes(content: str, definitions: dict[str, str]) -> tuple[FootnotePointerNote, ...]:
    """Resolve every note a pointer cell names against the design's definitions.

    A cell may name several notes ("Notas 1 y 2"), and each is resolved on its
    own, because one may state a numeric convention while another does not.
    """
    if not POINTER.match(content.strip().rstrip(".")):
        return ()
    return tuple(
        FootnotePointerNote(
            pointer=content.strip(),
            note=f"nota {number}",
            text=definitions.get(f"nota {number}", ""),
        )
        for number in re.findall(r"\d+", content)
    )


#: Vocabulary a note uses when it constrains how a value is written. Its presence
#: is a READING AID and not a verdict: a note mentioning decimals may still not
#: settle the field, and the rule's author decides. It exists so an author can
#: see which notes are worth opening first among many.
_WIRE_VOCABULARY = ("decimal", "signo", "coma", "alinead", "ceros", "derecha", "izquierda")


@dataclass(frozen=True, slots=True)
class PointerEvidence:
    """One Contenido cell holding only a pointer, and what the design says behind it."""

    cell: str
    pointer: str
    notes: tuple[FootnotePointerNote, ...]

    @property
    def unresolved(self) -> tuple[str, ...]:
        """Notes the pointer names that the design never defines."""
        return tuple(item.note for item in self.notes if not item.resolved)

    @property
    def mentions_wire_vocabulary(self) -> bool:
        """Whether any resolved note uses the vocabulary of how a value is written.

        A reading aid, not a verdict. A note that mentions decimals still has to
        be read; this only says it is worth reading first.
        """
        text = " ".join(item.text for item in self.notes if item.resolved).casefold()
        return any(word in text for word in _WIRE_VOCABULARY)


def design_transcription_path(corpus_path: Path) -> Path:
    """Return the extracted-text path for one design file.

    Derived from the design the source reference names rather than by searching
    its directory. Several modelos bundle many designs - one bundles fifteen -
    so a directory search returns an arbitrary sibling, and a note resolved
    against the wrong year's design is worse evidence than none.
    """
    return Path(str(corpus_path) + ".extracted.md")


def pointer_evidence_for_design(contents: Iterable[str], transcription: Path) -> tuple[PointerEvidence, ...]:
    """Return the pointer cells among ``contents`` with the notes they name resolved.

    A design with no transcription yields nothing, and the caller is expected to
    report that separately: thirteen bundled designs ship without one, and
    silently returning an empty result would read as "this design has no
    pointers".
    """
    if not transcription.exists():
        return ()
    definitions = note_definitions(transcription.read_text(encoding="utf-8"))
    evidence: list[PointerEvidence] = []
    for content in contents:
        cell = content.strip()
        notes = resolve_pointer_notes(cell, definitions)
        if notes:
            evidence.append(PointerEvidence(cell=cell, pointer=cell, notes=notes))
    return tuple(evidence)


def main(argv: list[str] | None = None) -> int:
    """Print each pointer in one design's extracted text with the note it resolves to."""
    argv = sys.argv[1:] if argv is None else argv
    if not argv:
        sys.stdout.write("usage: python -m dev.registry.analysis.footnote_pointer_notes <extracted.md>\n")
        return 2
    # Read strictly. The corpus transcriptions are UTF-8, and silencing a
    # decode error here would drop accented characters from Spanish note text
    # that an author is about to rely on - a note that quietly lost a word is
    # worse evidence than a note that failed to load.
    extracted = Path(argv[0]).read_text(encoding="utf-8")
    definitions = note_definitions(extracted)
    for label, text in sorted(definitions.items()):
        sys.stdout.write(f"note_definition label={label!r} text={text!r}\n")
    sys.stdout.write(f"summary definitions={len(definitions)}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
