"""Screen: note labels whose wording changes between a modelo's designs.

A reviewed representation rule is grounded in a note, and a note is named by the
sheet that prints it and the label AEAT gave it. Those names are stable across a
modelo's revisions; the text behind them is not. Where it changes, anything that
carried a rule forward on the strength of the name is now grounded in wording
that no longer says what it said.

This is the last level of the same identity question the rest of this package
has worked through. A label does not identify a note on its own, because a
workbook numbers each page's notes from one. A sheet and label together do not
identify it either, because a modelo's designs are separate documents and the
note behind one name can be rewritten between them.

One condition is reported, and every row names it:

- ``note_text_differs_across_designs`` - one sheet and label carrying more than
  one distinct text across the designs of a single modelo. The row names the
  designs and the lengths, because the difference may be a rewrite, an
  extension, or a transcription artifact, and only reading tells them apart.

A key appearing in one design only is not reported: there is nothing to differ
from. A key whose text is identical everywhere it appears is not reported
either, and the census counts both so a quiet result is distinguishable from an
empty corpus.

The screen exits 0 whatever it finds. It reports; it does not gate. Rewording a
note between revisions is AEAT's to do and is often the point - a rule changed,
so its note changed. What must not happen is a rule carried forward without
anyone noticing that its grounding moved, and this is what makes that visible.
"""

from __future__ import annotations

import collections
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from .footnote_pointer_notes import sheet_note_definitions
from .note_label_scope import modelo_of, transcription_paths

#: Named once per module rather than repeated at each read site, where a typo
#: would be a silent decode change rather than an error.
_UTF_8: Final[str] = "utf-8"

__all__ = [
    "KINDS",
    "NoteTextDriftFinding",
    "note_texts_by_key",
    "screen_corpus",
]

#: Every condition this screen can report, declared once and used at its
#: emission site so the set cannot be recovered by reading the source wrong.
KINDS: tuple[str, ...] = ("note_text_differs_across_designs",)


@dataclass(frozen=True, slots=True)
class NoteTextDriftFinding:
    """One sheet and label whose wording is not the same in every design."""

    modelo: str
    sheet: str
    label: str
    kind: str
    designs: tuple[str, ...]
    lengths: tuple[int, ...]
    detail: str


def note_texts_by_key(
    root: Path | None = None,
) -> dict[tuple[str, str, str], dict[str, str]]:
    """Return ``{(modelo, sheet, label): {design: text}}`` across the corpus.

    Keyed on the design rather than the revision, because a note lives in a
    document and several revisions may share one. Returned whole rather than
    already reduced, so a caller can ask a different question of it without a
    second walk of the corpus.
    """
    found: dict[tuple[str, str, str], dict[str, str]] = collections.defaultdict(dict)
    for path in transcription_paths(root):
        modelo = modelo_of(path)
        for sheet, labels in sheet_note_definitions(path.read_text(encoding=_UTF_8)).items():
            for label, text in labels.items():
                found[(modelo, sheet, label)][path.name] = text
    return dict(found)


def screen_corpus(root: Path | None = None) -> tuple[NoteTextDriftFinding, ...]:
    """Return every sheet and label whose text differs between designs."""
    findings: list[NoteTextDriftFinding] = []
    for (modelo, sheet, label), by_design in sorted(note_texts_by_key(root).items()):
        if len(by_design) < 2 or len(set(by_design.values())) < 2:
            continue
        designs = tuple(sorted(by_design))
        findings.append(
            NoteTextDriftFinding(
                modelo=modelo,
                sheet=sheet,
                label=label,
                kind="note_text_differs_across_designs",
                designs=designs,
                lengths=tuple(len(by_design[name]) for name in designs),
                detail=f"{len(set(by_design.values()))} distinct texts across {len(by_design)} designs",
            )
        )
    return tuple(findings)


def main() -> int:
    """Print one greppable row per finding and a closing census; always exit 0."""
    by_key = note_texts_by_key()
    findings = screen_corpus()
    for item in findings:
        sys.stdout.write(
            f"note_text_drift modelo={item.modelo} sheet={item.sheet!r} label={item.label!r} "
            f"kind={item.kind} designs={len(item.designs)} "
            f"lengths={','.join(str(length) for length in item.lengths)} detail={item.detail!r}\n"
        )
    shared = sum(1 for by_design in by_key.values() if len(by_design) > 1)
    sys.stdout.write(
        f"summary keys={len(by_key)} keys_in_several_designs={shared} "
        f"findings={len(findings)} stable={shared - len(findings)}\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
