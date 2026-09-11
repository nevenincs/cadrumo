"""Find money fields that start on a sign byte their official design reserves.

Some AEAT record designs subdivide an amount into a leading alphabetic SIGNO
position and a magnitude that carries no sign of its own. Such a field must
declare ``sign_position``: without it the codec applies the general convention,
where a non-negative amount writes a digit into the byte the design reserves
for a space or an 'N'.

The design text is the evidence. A SIGNO subdivision is printed as a position
number followed by the word SIGNO ("145 SIGNO: campo alfabetico ...",
"176. SIGNO: ..."), and the screen reads those positions from the text of
every record design the revision pins. A position is joined to a
shipped field by its starting offset, and only money fields are compared.

Where this stops: positions are read per document, not per record type, so a
money field on one record that starts at a SIGNO position printed for another
record would be reported too, and must then be ruled explicitly rather than
passed. A SIGNO position falling INSIDE a wider field, rather than at its
start, is not screened: surveyed once, every such case in the corpus was a
position printed for a different record type.
"""

from __future__ import annotations

import functools
import re
import sys
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.authority import ValidatedRegistryAuthority
from ..compiler.record_design import extract_record_design
from ..compiler.record_design_pdf_visual import extract_pdf_text_lines
from cadrumo.domain.calculations.registry.schema import ModeloRevision
from dev.registry.compiler.authority import compiled_bundled_authority

__all__ = [
    "UndeclaredSignPosition",
    "design_sign_positions",
    "screen_authority",
    "sign_positions_in_design_text",
    "undeclared_sign_positions",
    "unreadable_designs",
]

_RECORD_DESIGN_KIND = "record_design"
_WORKBOOK_SUFFIXES = frozenset({".xls", ".xlsx", ".xlsm"})
_SIGNO_POSITION = re.compile(r"(?<![\d-])(\d{1,4})\s*[.:-]?\s*SIGNO\b", re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class UndeclaredSignPosition:
    """One money field starting on a design SIGNO position without a declared sign_position."""

    modelo: str
    revision: str
    record_id: str
    field_id: str
    offset: int

    @property
    def subject(self) -> str:
        """Return the canonical ``modelo/revision`` identity."""
        return f"{self.modelo}/{self.revision}"


def sign_positions_in_design_text(text: str) -> frozenset[int]:
    """Return every position the design text prints as a SIGNO subdivision."""
    return frozenset(int(match.group(1)) for match in _SIGNO_POSITION.finditer(text))


def undeclared_sign_positions(
    fields: Iterable[tuple[str, int | None, str, object]], positions: frozenset[int]
) -> list[tuple[str, int]]:
    """Return ``(field_id, offset)`` for money fields on a SIGNO position lacking sign_position.

    Each field is ``(field_id, offset, data_type, sign_position)``.
    """
    return [
        (field_id, offset)
        for field_id, offset, data_type, sign_position in fields
        if offset in positions and data_type == "money" and sign_position is None
    ]


@functools.cache
def _document_text(document: Path, ref: str) -> str | None:
    """Return one design document's text, or ``None`` when it cannot be read.

    Cached because every revision pinning the same design, and every caller
    in one run, would otherwise re-parse the same PDF or workbook.
    """
    extracted = document.with_name(document.name + ".extracted.md")
    if extracted.is_file():
        return extracted.read_text(encoding="utf-8", errors="replace")
    if not document.is_file():
        return None
    if document.suffix.lower() == ".pdf":
        return "\n".join(extract_pdf_text_lines(document.read_bytes(), source_label=ref))
    if document.suffix.lower() in _WORKBOOK_SUFFIXES:
        # A workbook design prints each slot as its own row, so a SIGNO slot
        # reads as its position followed by its description.
        extraction = extract_record_design(document)
        return "\n".join(f"{field.offset} {field.description}" for sheet in extraction.sheets for field in sheet.fields)
    return None


def _design_texts(authority: ValidatedRegistryAuthority, revision: ModeloRevision) -> tuple[list[str], list[str]]:
    """Return the text of every pinned record design, and the refs whose text cannot be read.

    The extracted text beside a design is used when present; a PDF without one
    is read through the record-design PDF text reader. Any other design with no
    readable text is returned as unreadable, so a revision is never passed on
    evidence the screen did not see.
    """
    sources = authority.catalogues.sources
    texts: list[str] = []
    unreadable: list[str] = []
    for ref in map(str, revision.source_refs):
        source = sources[ref]
        if str(source.kind) != _RECORD_DESIGN_KIND:
            continue
        text = _document_text(bundled_path() / source.corpus_path, ref)
        if text is None:
            unreadable.append(ref)
        else:
            texts.append(text)
    return texts, unreadable


def design_sign_positions(authority: ValidatedRegistryAuthority, revision: ModeloRevision) -> frozenset[int]:
    """Return the SIGNO positions printed by every record design the revision pins."""
    texts, _unreadable = _design_texts(authority, revision)
    return sign_positions_in_design_text("\n".join(texts))


def unreadable_designs(authority: ValidatedRegistryAuthority) -> tuple[str, ...]:
    """Return ``modelo/revision ref`` for each pinned design of an exporting revision with no readable text."""
    return tuple(
        f"{modelo.id}/{revision.id} {ref}"
        for modelo in sorted(authority.modelos, key=lambda item: str(item.id))
        for revision in sorted(modelo.revisions.values(), key=lambda item: str(item.id))
        if revision.export_layouts
        for ref in _design_texts(authority, revision)[1]
    )


def _screen(authority: ValidatedRegistryAuthority) -> Iterator[UndeclaredSignPosition]:
    for modelo in sorted(authority.modelos, key=lambda item: str(item.id)):
        for revision in sorted(modelo.revisions.values(), key=lambda item: str(item.id)):
            if not revision.export_layouts:
                continue
            positions = design_sign_positions(authority, revision)
            if not positions:
                continue
            for layout in revision.export_layouts:
                for record in layout.records:
                    fields = [
                        (str(field.id), field.offset, str(field.data_type), field.sign_position)
                        for field in record.fields
                    ]
                    for field_id, offset in undeclared_sign_positions(fields, positions):
                        yield UndeclaredSignPosition(
                            modelo=str(modelo.id),
                            revision=str(revision.id),
                            record_id=str(record.id),
                            field_id=field_id,
                            offset=offset,
                        )


def screen_authority(authority: ValidatedRegistryAuthority) -> tuple[UndeclaredSignPosition, ...]:
    """Return every money field on a design SIGNO position that declares no sign_position."""
    return tuple(_screen(authority))


def main() -> int:
    """Print one greppable row per undeclared sign position."""
    for item in screen_authority(compiled_bundled_authority()):
        print(f"{item.subject} {item.record_id} {item.field_id} @{item.offset}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
