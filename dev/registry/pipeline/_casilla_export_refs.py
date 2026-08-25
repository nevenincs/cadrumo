"""Write the back-reference a generated export layout implies onto its casillas.

``export_refs`` is DERIVED data, not authored meaning: the generator has just
computed which casilla each export field addresses, and the back-reference is
that same fact written the other way. Registry validation requires both
directions, so a generated layout cannot validate while the casillas it
addresses stay silent about it.

Hand-authoring it would mean copying generated field ids into casilla files by
hand -- dual maintenance of one fact, which rots the moment a layout is
regenerated. So the generator owns this field, and ONLY this field, on exactly
the casillas its layout addresses.

The write is deliberately textual rather than a load-and-reserialise. A
round-trip through the TOML compiler would rewrite every casilla in the file,
reordering keys and normalising formatting, and the generator has no mandate
over any of that. Editing the one line keeps every other byte identical, which
the caller can and does verify.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from pathlib import Path

from cadrumo.core.directory_scan import scan_directory
from cadrumo.domain.calculations.registry import RegistryValidationError

from ._export_tree import RenderedExportTree

__all__ = ["export_refs_by_casilla", "write_generated_casilla_export_refs"]

_BLOCK_START = re.compile(r"^\[\[revisions\.")
_ID_LINE = re.compile(r'^id = "(?P<id>[^"]*)"\s*$')
_EXPORT_REFS_LINE = re.compile(r"^export_refs = ")
_SOURCE_REFS_LINE = re.compile(r"^source_refs = ")


def _render(field_ids: tuple[str, ...]) -> str:
    return "export_refs = [" + ", ".join(f'"{field_id}"' for field_id in field_ids) + "]"


def _block_bounds(lines: list[str]) -> list[tuple[int, int]]:
    """Return the [start, end) line span of every casilla table in the file."""
    starts = [index for index, line in enumerate(lines) if _BLOCK_START.match(line)]
    return [
        (start, starts[position + 1] if position + 1 < len(starts) else len(lines))
        for position, start in enumerate(starts)
    ]


def export_refs_by_casilla(rendered: RenderedExportTree) -> dict[str, tuple[str, ...]]:
    """Derive ``{casilla_id: (export_field_id, ...)}`` from the rendered tree.

    Every derivation whose semantic entry addresses a casilla contributes its
    export field id, in derivation order -- the same order the layout emits.
    """
    by_casilla: dict[str, list[str]] = {}
    for derivation in rendered.field_derivations:
        casilla_id = derivation.semantic_entry.casilla_id
        if casilla_id is None:
            continue
        by_casilla.setdefault(casilla_id, []).append(derivation.semantic_entry.export_field_id)
    return {casilla: tuple(field_ids) for casilla, field_ids in by_casilla.items()}


def write_generated_casilla_export_refs(
    revision_root: Path,
    *,
    export_refs_by_casilla: Mapping[str, tuple[str, ...]],
) -> tuple[Path, ...]:
    """Write ``export_refs`` onto the addressed casillas, touching nothing else.

    Returns every file changed. An addressed casilla that already declares
    ``export_refs`` is RECONCILED, never merged: an identical declaration is
    left untouched, and a differing one raises, because two disagreeing answers
    to "which field addresses this casilla" is a finding rather than something
    to silently union.
    """
    casillas_root = revision_root / "casillas"
    if not casillas_root.is_dir():
        raise RegistryValidationError(f"generated export_refs write found no casillas directory: {casillas_root}")

    written: list[Path] = []
    seen: set[str] = set()
    for path in scan_directory(casillas_root, pattern="*.toml"):
        original = path.read_text(encoding="utf-8")
        lines = original.splitlines(keepends=True)
        changed = False
        for start, end in reversed(_block_bounds(lines)):
            casilla_id = next(
                (match.group("id") for line in lines[start:end] if (match := _ID_LINE.match(line))),
                None,
            )
            if casilla_id is None or casilla_id not in export_refs_by_casilla:
                continue
            seen.add(casilla_id)
            expected = export_refs_by_casilla[casilla_id]
            # Confine the write to the casilla's OWN keys. A casilla may carry
            # nested sub-tables (`[...casillas.constraints]`, aliases) which
            # declare their own `source_refs`; anchoring on the last one in the
            # whole block would place export_refs inside the sub-table, where it
            # is a different -- and rejected -- field.
            body_end = next(
                (index for index in range(start + 1, end) if lines[index].lstrip().startswith("[")),
                end,
            )
            existing = next(
                (index for index in range(start, body_end) if _EXPORT_REFS_LINE.match(lines[index])),
                None,
            )
            if existing is not None:
                if lines[existing].strip() != _render(expected):
                    raise RegistryValidationError(
                        f"{path}: casilla {casilla_id!r} already declares {lines[existing].strip()!r} but the "
                        f"generated layout addresses it as {_render(expected)!r}. Two disagreeing answers to "
                        "which field addresses this casilla is a finding; reconcile it deliberately rather "
                        "than letting generation overwrite an authored declaration",
                    )
                continue
            anchor = next(
                (index for index in range(body_end - 1, start - 1, -1) if _SOURCE_REFS_LINE.match(lines[index])),
                None,
            )
            if anchor is None:
                anchor = max(index for index in range(start, body_end) if lines[index].strip())
            ending = "\r\n" if lines[anchor].endswith("\r\n") else "\n"
            lines.insert(anchor + 1, _render(expected) + ending)
            changed = True
        if changed:
            path.write_text("".join(lines), encoding="utf-8", newline="\n")
            written.append(path)

    missing = sorted(set(export_refs_by_casilla) - seen)
    if missing:
        raise RegistryValidationError(
            f"generated layout addresses casillas the revision does not declare: {missing!r}",
        )
    return tuple(written)
