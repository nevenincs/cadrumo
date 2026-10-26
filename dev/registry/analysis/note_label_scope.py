"""Screen: record designs whose note labels repeat across sheets.

A workbook record design prints one sheet per page and numbers each page's
notes from one, so a label like ``Nota 1`` identifies a note only together with
the sheet that prints it. Where a label repeats, any design-wide reading of that
label is unsound: it must either merge notes that are not the same note, pick
one arbitrarily, or refuse. The reader this corpus shipped merged them, and a
field citing the label received every page's note run together.

This screen reports where that ambiguity exists, so a reader can tell a design
whose labels happen to be unique - where a design-wide lookup is harmless - from
one where the sheet is load-bearing.

One condition is reported, and every row names it:

- ``label_repeats_across_sheets`` - one label defined on more than one sheet of
  the same design. The row carries how many sheets define it, which is also how
  many notes a design-wide reading would have merged into one.

A design carrying no note definition at all is counted in the census and not
reported as a row. It is the majority state across the corpus, and most of
those designs simply have no notes, so a row per design would bury the ones
that carry work under the ones that carry none. The count stays visible
because a design whose notes failed to transcribe looks exactly like one that
has none, and that distinction needs a pointer to chase, not a design to list.

The census reports the surplus - the number of definitions past the first for
every repeated label - because that is the count of notes a design-wide reader
silently absorbed, and it is not recoverable from the number of affected
designs.

The screen exits 0 whatever it finds. It reports; it does not gate. A repeated
label is the official design's own numbering and is not a defect in the corpus:
the defect was reading it without its sheet, and that is fixed at the reader
rather than by demanding AEAT renumber its pages.
"""

from __future__ import annotations

import collections
import sys
from dataclasses import dataclass
from pathlib import Path

from cadrumo.core.resources.bundled_data import bundled_path

from .footnote_pointer_notes import sheet_note_definitions

__all__ = [
    "KINDS",
    "NoteLabelScopeFinding",
    "design_findings",
    "screen_corpus",
    "transcription_paths",
]

#: Every condition this screen can report, declared once and used at each
#: emission site so the set cannot be recovered by reading the source wrong.
KINDS: tuple[str, ...] = ("label_repeats_across_sheets",)

_UTF_8 = "utf-8"
_DESIGN_SUFFIX = ".extracted.md"
_CORPUS_SEGMENTS = ("corpus", "aeat_official", "disenos_registro")


@dataclass(frozen=True, slots=True)
class NoteLabelScopeFinding:
    """One design whose note labels do not identify a note on their own."""

    modelo: str
    design: str
    kind: str
    label: str
    sheets: tuple[str, ...]
    detail: str

    @property
    def merged(self) -> int:
        """How many notes a design-wide reading of this label would absorb."""
        return max(len(self.sheets) - 1, 0)


_MODELO_PREFIX = "modelo_"


def modelo_of(path: Path) -> str:
    """Return the modelo whose corpus directory holds this transcription.

    Walked up rather than taken at a fixed depth: most designs sit under
    ``modelo_NNN/files/``, and one sits directly under ``modelo_210/``. A fixed
    parent count would return "disenos_registro" for that one, which is not a
    modelo and would be reported as though it were.
    """
    for parent in path.parents:
        if parent.name.startswith(_MODELO_PREFIX):
            return parent.name.removeprefix(_MODELO_PREFIX)
    raise ValueError(f"transcription outside any modelo directory: {path}")


def transcription_paths(root: Path | None = None) -> tuple[Path, ...]:
    """Return every extracted design transcription in the bundled corpus.

    Resolved from the bundled data root rather than a checkout-relative literal,
    so the screen reads the same corpus the authority does.
    """
    base = bundled_path().joinpath(*_CORPUS_SEGMENTS) if root is None else root
    return tuple(sorted(base.rglob(f"*{_DESIGN_SUFFIX}")))


def design_findings(path: Path) -> tuple[NoteLabelScopeFinding, ...]:
    """Return one design transcription's note-label scope findings."""
    by_sheet = sheet_note_definitions(path.read_text(encoding=_UTF_8))
    name = path.name
    sheets_by_label: dict[str, list[str]] = collections.defaultdict(list)
    for sheet, labels in by_sheet.items():
        for label in labels:
            sheets_by_label[label].append(sheet)
    return tuple(
        NoteLabelScopeFinding(
            modelo=modelo_of(path),
            design=name,
            kind="label_repeats_across_sheets",
            label=label,
            sheets=tuple(sorted(sheets)),
            detail=f"{len(sheets)} sheets define this label",
        )
        for label, sheets in sorted(sheets_by_label.items())
        if len(sheets) > 1
    )


def screen_corpus(root: Path | None = None) -> tuple[NoteLabelScopeFinding, ...]:
    """Screen every bundled design transcription."""
    findings: list[NoteLabelScopeFinding] = []
    for path in transcription_paths(root):
        findings.extend(design_findings(path))
    return tuple(findings)


def main() -> int:
    """Print one greppable row per finding and a closing census; always exit 0."""
    paths = transcription_paths()
    findings = screen_corpus()
    without_notes = sum(1 for path in paths if not sheet_note_definitions(path.read_text(encoding=_UTF_8)))
    tally: collections.Counter[str] = collections.Counter(item.kind for item in findings)
    for item in findings:
        sys.stdout.write(
            f"note_label_scope modelo={item.modelo} design={item.design!r} kind={item.kind} "
            f"label={item.label!r} "
            f"sheets={len(item.sheets)} merged={item.merged} detail={item.detail!r}\n"
        )
    merged = sum(item.merged for item in findings)
    designs = len({item.design for item in findings if item.kind == "label_repeats_across_sheets"})
    kinds = " ".join(f"{kind}={tally[kind]}" for kind in KINDS)
    sys.stdout.write(
        f"summary transcriptions={len(paths)} findings={len(findings)} "
        f"designs_with_repeated_label={designs} "
        f"definitions_a_design_wide_read_would_merge={merged} "
        f"transcriptions_defining_no_note={without_notes} {kinds}\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
