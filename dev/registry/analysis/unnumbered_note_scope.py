"""Screen: the structural evidence for what an unnumbered design note governs.

An unnumbered ``NOTA`` carries no label, so nothing points at it and its reach
has to be inferred from where it is printed. The reader that finds these returns
them keyed by the sheet they appear on, because that is where they were found -
not because the sheet is their scope. This screen reports the evidence that
bears on the scope, so a consumer keying a reviewed rule to one of these notes
does it from the design's own structure rather than from where the text happened
to sit.

Three conditions are reported, and every row names one of them:

- ``one_note_many_sheets`` - the design prints exactly one such note while
  carrying several sheets. The note cannot be a statement about the sheet it
  sits on unless that sheet is the only one it concerns, and the worked case
  refutes that: modelo 200's note settles how *importes* are written, its own
  sheet carries no amount field at all, and the 5,665 fields it describes are
  spread over 74 other sheets. Reading the printing sheet as the scope would put
  such a note out of reach of everything it governs.
- ``note_on_several_sheets_identical`` - several sheets carry one, all with the
  same text. One statement printed repeatedly, which is what a design-level fact
  looks like when the page template repeats it.
- ``note_on_several_sheets_differing`` - several sheets carry one and the texts
  differ. Here the sheet does distinguish, because two sheets are being told
  different things.

The conditions name what was observed, not what was concluded. A design can
carry the first shape and still intend a sheet-local note; what the row says is
that the design's structure gives no support for reading it that way.

The screen exits 0 whatever it finds. It reports; it does not gate, and it does
not decide a scope on the reader's behalf.
"""

from __future__ import annotations

import collections
import sys
from dataclasses import dataclass
from pathlib import Path

from .footnote_pointer_notes import sheet_note_definitions, sheet_unnumbered_notes
from .note_label_scope import modelo_of, transcription_paths

__all__ = [
    "KINDS",
    "UnnumberedNoteScopeFinding",
    "design_finding",
    "screen_corpus",
]

#: Every condition this screen can report, declared once and used at each
#: emission site so the set cannot be recovered by reading the source wrong.
KINDS: tuple[str, ...] = (
    "one_note_many_sheets",
    "note_on_several_sheets_identical",
    "note_on_several_sheets_differing",
)

_UTF_8 = "utf-8"


@dataclass(frozen=True, slots=True)
class UnnumberedNoteScopeFinding:
    """One design's unnumbered notes and the structure around them."""

    modelo: str
    design: str
    kind: str
    sheets_with_note: int
    distinct_texts: int
    sheets_seen: int
    detail: str


def _sheets_in(extracted: str) -> int:
    """Count the design's sheets.

    Counted from the same headings the note reader splits on, so the two cannot
    disagree about what a sheet is. A design with notes on every sheet and one
    with a single note read identically without this denominator.
    """
    seen = {sheet for sheet in sheet_note_definitions(extracted)}
    seen |= set(sheet_unnumbered_notes(extracted))
    return len(seen)


def design_finding(path: Path, *, sheets_seen: int | None = None) -> UnnumberedNoteScopeFinding | None:
    """Return one design's unnumbered-note scope evidence, or None if it has none."""
    extracted = path.read_text(encoding=_UTF_8)
    notes = sheet_unnumbered_notes(extracted)
    if not notes:
        return None
    texts = {text for text in notes.values()}
    total_sheets = _sheets_in(extracted) if sheets_seen is None else sheets_seen
    if len(notes) == 1:
        kind = "one_note_many_sheets"
        detail = f"one note, and the design carries {total_sheets} sheet(s) carrying notes"
    elif len(texts) == 1:
        kind = "note_on_several_sheets_identical"
        detail = f"{len(notes)} sheets repeat one text"
    else:
        kind = "note_on_several_sheets_differing"
        detail = f"{len(notes)} sheets carry {len(texts)} distinct texts"
    return UnnumberedNoteScopeFinding(
        modelo=modelo_of(path),
        design=path.name,
        kind=kind,
        sheets_with_note=len(notes),
        distinct_texts=len(texts),
        sheets_seen=total_sheets,
        detail=detail,
    )


def screen_corpus(root: Path | None = None) -> tuple[UnnumberedNoteScopeFinding, ...]:
    """Screen every bundled design transcription carrying an unnumbered note."""
    found = (design_finding(path) for path in transcription_paths(root))
    return tuple(item for item in found if item is not None)


def main() -> int:
    """Print one greppable row per design and a closing census; always exit 0."""
    findings = screen_corpus()
    tally: collections.Counter[str] = collections.Counter(item.kind for item in findings)
    for item in findings:
        sys.stdout.write(
            f"unnumbered_note_scope modelo={item.modelo} design={item.design!r} kind={item.kind} "
            f"sheets_with_note={item.sheets_with_note} distinct_texts={item.distinct_texts} "
            f"sheets_seen={item.sheets_seen} detail={item.detail!r}\n"
        )
    kinds = " ".join(f"{kind}={tally[kind]}" for kind in KINDS)
    sys.stdout.write(f"summary designs={len(findings)} {kinds}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
