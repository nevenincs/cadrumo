"""Screen: shipped fields whose governing note cannot be resolved to one text.

A record design states some of a field's meaning in its ``Contenido`` cell and
the rest in a NOTE the cell points at. Modelo 390's expired-rate slots say only
"Nota 2", and that note carries the mandate - "estas casillas deben estar
rellenas a 0" - which decides the only value those slots may hold.

A pointer is only as good as the label it names. Where one design defines the
same label on several sheets with DIFFERENT text, the pointer has more than one
plausible reading, and nothing in the artefact records which was taken. Both
readings look like valid notes, so a wrong resolution is silent - the same shape
as the sign defect, where a convention sat in a note that nothing had joined to
the fields it governs and a stable wrong answer shipped for years.

This screen performs that join. It reports a field whose note label resolves to
several texts, because such a field's derivation cannot be PROVEN from its
design however plausible it looks.

It judges no reading and cannot: choosing between two texts is the reviewer's
call, and the point is that the artefact does not record one having been made.

The screen exits 0 whatever it finds. It reports; it does not gate.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from cadrumo.core.resources.bundled_data import bundled_path

from .note_label_scope import screen_corpus as note_label_scope

#: How a design cites a note from a field's content cell: the word, optional
#: punctuation, then the number. Matched loosely because AEAT does not spell
#: consistently, and every unmatched spelling is a pointer that escapes review.
_NOTE_POINTER: Final[re.Pattern[str]] = re.compile(r"\bnota\s*\.?\s*(\d+)", re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class UnresolvableNotePointer:
    """One shipped field whose governing note label carries several texts."""

    modelo: str
    revision: str
    export_field_id: str
    note_label: str
    distinct_texts: int

    @property
    def is_resolvable(self) -> bool:
        """Whether exactly one text stands behind the label this field cites."""
        return self.distinct_texts <= 1


def _ambiguous_labels() -> dict[tuple[str, str], int]:
    counts: dict[tuple[str, str], int] = {}
    for finding in note_label_scope():
        key = (finding.modelo, re.sub(r"\s+", "", finding.label.lower()))
        counts[key] = max(counts.get(key, 0), finding.merged)
    return counts


def unresolvable_note_pointers(modelos_root: Path | None = None) -> Iterator[UnresolvableNotePointer]:
    """Yield every shipped field whose cited note label resolves to several texts."""
    root = modelos_root if modelos_root is not None else bundled_path("registry", "aeat", "modelos")
    labels = _ambiguous_labels()
    for manifest_path in sorted(root.glob("*/revisions/*/export/_generation.provenance.json")):
        parts = manifest_path.parts
        modelo, revision = parts[-5], parts[-3]
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        for entry in manifest.get("field_derivations") or ():
            content = (entry.get("parser_field") or {}).get("content") or ""
            pointer = _NOTE_POINTER.search(content)
            if pointer is None:
                continue
            label = f"nota{pointer.group(1)}"
            distinct = labels.get((modelo, label))
            if distinct is None or distinct <= 1:
                continue
            field_id = (entry.get("field") or {}).get("id")
            yield UnresolvableNotePointer(
                modelo=modelo,
                revision=revision,
                export_field_id=str(field_id),
                note_label=label,
                distinct_texts=distinct,
            )


def screen_authority(_authority: object = None, _modelo_ids: Sequence[str] = ()) -> Sequence[UnresolvableNotePointer]:
    """Entry point matching the screens register's calling convention."""
    return tuple(unresolvable_note_pointers())


def main() -> int:
    """Report the fields whose governing note has more than one plausible reading."""
    rows = tuple(unresolvable_note_pointers())
    by_pointer: dict[str, int] = {}
    for row in rows:
        by_pointer[f"{row.modelo}:{row.note_label}"] = by_pointer.get(f"{row.modelo}:{row.note_label}", 0) + 1
    for pointer, count in sorted(by_pointer.items(), key=lambda item: -item[1]):
        print(f"{pointer:24} {count:5} field(s)")
    print(
        f"\n{len(rows)} shipped field(s) cite a note label that carries several texts. Their derivation\n"
        f"is not provable from the design alone, and the artefact records no reading having been chosen.",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
