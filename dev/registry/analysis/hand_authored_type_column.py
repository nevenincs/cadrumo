"""Screen: hand-authored export fields that contradict their official type column.

A generated export tree carries a derivation record for every field, and the
type-column gate reads the official AEAT type straight out of it. A hand-authored
``export_layouts`` tree carries no derivation record, so that gate cannot see it
at all: its fields are not explained, not pinned and not failing. They are simply
never compared. This screen compares them.

The comparison needs each shipped record joined to the right sheet of the
revision's own pinned record design. The join is made on a record's whole wire
geometry: a record aligns to a sheet only when every one of its ``(offset,
length)`` slots is a slot of that sheet, and of exactly one sheet. Matching a
single slot proves nothing, because the same offsets recur on every page of a
design and a single-slot match cross-matches them. A record that fits no sheet,
or more than one, is reported as UNCHECKED rather than silently passed; so is a
revision that pins no record design, or more than one.

The join is only ever made within one revision. Across editions a slot can keep
its record, ordinal, offset and width while the concept in it changes, and a
cross-edition geometric match would certify that reassignment instead of
catching it.

For an aligned field, the official type ``N`` means the design allows a negative
amount, written with a leading ``N``. A field shipped ``signed = false`` there
cannot represent one. Two shapes cannot simply be signed, because the export
schema refuses them: a field carrying a closed value domain, since the schema
holds no signed domain, and a field whose data type is not ``money``, since the
schema signs money only and re-typing an integer as money would add implied
decimals the design never stated. Those are reported as blocked, with the
reason, rather than as plain contradictions.

The screen exits 0 whatever it finds. It reports; the gate beside it decides.
"""

from __future__ import annotations

import sys
import tomllib
from collections.abc import Iterator
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.authority import ValidatedRegistryAuthority, bundled_authority
from cadrumo.domain.calculations.registry.record_design import extract_record_design

__all__ = [
    "Alignment",
    "RecordAlignment",
    "TypeColumnContradiction",
    "hand_authored_revisions",
    "revision_findings",
    "screen_authority",
]

_SIGNED_TYPE = "N"
_RECORD_DESIGN_KIND = "record_design"
_GENERATION_MANIFEST = "_generation.provenance.json"


class Alignment(StrEnum):
    """How one shipped record was joined to its revision's official design."""

    ALIGNED = "aligned"
    """Exactly one design sheet covers every slot of the record."""
    AMBIGUOUS = "ambiguous"
    """More than one sheet covers every slot, so the record's sheet is not determined."""
    UNMATCHED = "unmatched"
    """No sheet covers every slot."""
    NO_DESIGN = "no_design"
    """The revision pins no record design, or more than one."""


@dataclass(frozen=True, slots=True)
class RecordAlignment:
    """One shipped record and the outcome of joining it to the official design."""

    modelo: str
    revision: str
    layout_file: str
    record_id: str
    alignment: Alignment
    sheet: str | None

    @property
    def subject(self) -> str:
        """Return the canonical ``modelo/revision`` identity."""
        return f"{self.modelo}/{self.revision}"


@dataclass(frozen=True, slots=True)
class TypeColumnContradiction:
    """One aligned field the official design types signed and the layout ships unsigned."""

    modelo: str
    revision: str
    layout_file: str
    record_id: str
    field_id: str
    offset: int
    length: int
    sheet: str
    blocked_reason: str | None
    """Why the schema cannot carry a sign on this field, or ``None`` when it can."""

    @property
    def subject(self) -> str:
        """Return the canonical ``modelo/revision`` identity."""
        return f"{self.modelo}/{self.revision}"


def hand_authored_revisions(authority: ValidatedRegistryAuthority) -> Iterator[tuple[str, str, Path]]:
    """Yield ``(modelo, revision, revision_root)`` for every hand-authored export revision."""
    for modelo in sorted(authority.modelos, key=lambda item: str(item.id)):
        for revision in sorted(modelo.revisions.values(), key=lambda item: str(item.id)):
            root = bundled_path("registry", "aeat", "modelos", str(modelo.id), "revisions", str(revision.id))
            if (root / "export" / _GENERATION_MANIFEST).is_file() or not (root / "export_layouts").is_dir():
                continue
            yield str(modelo.id), str(revision.id), root


def _design_slots(
    authority: ValidatedRegistryAuthority, modelo: str, revision: str
) -> dict[str, dict[tuple[int, int], str]] | None:
    definition = authority.modelo(modelo).revisions[revision]
    sources = authority.catalogues.sources
    refs = [ref for ref in definition.source_refs if str(sources[ref].kind) == _RECORD_DESIGN_KIND]
    if len(refs) != 1:
        return None
    extraction = extract_record_design(bundled_path() / sources[refs[0]].corpus_path)
    return {
        sheet.name: {(field.offset, field.length): field.type_code.strip() for field in sheet.fields}
        for sheet in extraction.sheets
    }


def _blocked_reason(field: dict[str, object]) -> str | None:
    if field.get("value_policy") or field.get("allowed_values"):
        return "carries a closed value domain, which a signed field cannot"
    if field.get("data_type") != "money":
        return f"data type {field.get('data_type')!r} cannot be signed; only money can"
    return None


def _shipped_records(revision_root: Path) -> Iterator[tuple[str, dict[str, object]]]:
    for layout_file in sorted((revision_root / "export_layouts").glob("*.toml")):
        document = tomllib.loads(layout_file.read_text(encoding="utf-8"))
        for body in document.get("revisions", {}).values():
            for layout in body.get("export_layouts", []):
                for record in layout.get("records", []):
                    yield layout_file.name, record


def revision_findings(
    authority: ValidatedRegistryAuthority, *, modelo: str, revision: str, revision_root: Path
) -> tuple[tuple[RecordAlignment, ...], tuple[TypeColumnContradiction, ...]]:
    """Return one revision's record alignments and its type-column contradictions."""
    design = _design_slots(authority, modelo, revision)
    alignments: list[RecordAlignment] = []
    contradictions: list[TypeColumnContradiction] = []
    for layout_file, record in _shipped_records(revision_root):
        fields = [item for item in record.get("fields", ()) if item.get("offset") and item.get("length")]
        if not fields:
            continue
        record_id = str(record.get("id", ""))
        if design is None:
            alignments.append(RecordAlignment(modelo, revision, layout_file, record_id, Alignment.NO_DESIGN, None))
            continue
        slots = {(int(item["offset"]), int(item["length"])) for item in fields}
        covering = sorted(name for name, sheet_slots in design.items() if slots <= sheet_slots.keys())
        if len(covering) != 1:
            outcome = Alignment.AMBIGUOUS if covering else Alignment.UNMATCHED
            alignments.append(RecordAlignment(modelo, revision, layout_file, record_id, outcome, None))
            continue
        sheet = covering[0]
        alignments.append(RecordAlignment(modelo, revision, layout_file, record_id, Alignment.ALIGNED, sheet))
        for item in fields:
            slot = (int(item["offset"]), int(item["length"]))
            if design[sheet][slot] == _SIGNED_TYPE and not item.get("signed", False):
                contradictions.append(
                    TypeColumnContradiction(
                        modelo=modelo,
                        revision=revision,
                        layout_file=layout_file,
                        record_id=record_id,
                        field_id=str(item["id"]),
                        offset=slot[0],
                        length=slot[1],
                        sheet=sheet,
                        blocked_reason=_blocked_reason(item),
                    )
                )
    return tuple(alignments), tuple(contradictions)


def screen_authority(
    authority: ValidatedRegistryAuthority,
) -> tuple[tuple[RecordAlignment, ...], tuple[TypeColumnContradiction, ...]]:
    """Return every hand-authored record alignment and contradiction across the registry."""
    alignments: list[RecordAlignment] = []
    contradictions: list[TypeColumnContradiction] = []
    for modelo, revision, root in hand_authored_revisions(authority):
        found_alignments, found_contradictions = revision_findings(
            authority, modelo=modelo, revision=revision, revision_root=root
        )
        alignments.extend(found_alignments)
        contradictions.extend(found_contradictions)
    return tuple(alignments), tuple(contradictions)


def main() -> int:
    """Print the alignment census and every contradiction, one greppable row each."""
    alignments, contradictions = screen_authority(bundled_authority())
    for outcome in Alignment:
        print(f"{outcome.value:10s} {sum(1 for item in alignments if item.alignment is outcome)}")
    for item in alignments:
        if item.alignment is not Alignment.ALIGNED:
            print(f"UNCHECKED {item.subject} {item.layout_file} {item.record_id} {item.alignment.value}")
    for item in contradictions:
        state = f"blocked ({item.blocked_reason})" if item.blocked_reason else "contradiction"
        print(f"{state} {item.subject} {item.layout_file} {item.field_id} {item.sheet} @{item.offset}+{item.length}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
