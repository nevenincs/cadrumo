"""An export record may leave a position unwritten only where the design says blank.

A fixed-width record is padded to its full span, so a position the layout never
writes still reaches AEAT -- as spaces. When the design marks that slot
``BLANCOS`` that is exactly right. When the design puts a DATA field there, the
filing silently under-declares it: the file is the correct length, the digest is
valid, and nothing downstream can tell the difference between "this taxpayer
declared nothing" and "the layout has no anchor for it".

That is the same failure the export completeness rule names for a blank required
casilla, one layer lower: completeness asks whether a casilla carries a value,
this asks whether the byte range that value belongs in is written at all.

**Enrollment is by declared correspondence, not by inference.** Reconciling a
record against a design needs to know WHICH design sheet it renders, and the
tree supplies no such link: the sheet naming is heterogeneous across modelos
(``Tipo 1 - Registro De Declarante``, ``M11100``, ``DR 11500``, ``Pág. 1``,
``DPA``), and keying on ``record_type`` plus a ``Tipo N`` prefix resolves 0 of
the tree's 403 export records. Until that correspondence has a declared home in
registry data, each enrolled row names its sheet here, having been read out of
the design rather than guessed. A modelo absent from this table is UNMEASURED by
this gate, never proven clean.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest

from .....core.resources import bundled_path
from .._export import derive_export_layouts_from_bindings
from .._record_design_coverage import _extract_record_design
from ._registry_schema_support import _committed_modelo

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

#: A design field whose description marks the slot as deliberately unwritten.
#: Matched against the description with trailing punctuation stripped, so a DATA
#: field that merely MENTIONS blanks in its prose cannot clear itself. Every
#: enrolled gap below is covered by a field whose whole description is one of
#: these, which is what makes the strict form sufficient.
_BLANK_DESCRIPTIONS = frozenset({"BLANCO", "BLANCOS", "RESERVADO", "RESERVADOS", "SIN CONTENIDO"})


@dataclass(frozen=True)
class _EnrolledRecord:
    """One export record and the design sheet it renders."""

    modelo_id: str
    revision_id: str
    record_id: str
    sheet_name: str


_ENROLLED: tuple[_EnrolledRecord, ...] = (
    # Modelo 193's three records against Orden HAC/56/2024 and the 2025 design.
    # The sheet for each was read from the design: the declarante record renders
    # the Tipo 1 sheet, the perceptor record the Tipo 2 sheet, and the gastos
    # record the separate Tipo 2 "Relación de Gastos" sheet, which is a distinct
    # sheet with its own 10 fields rather than a continuation of the perceptor's.
    _EnrolledRecord("193", "2024", "modelo-193-declarante", "Tipo 1 - Registro De Declarante"),
    _EnrolledRecord("193", "2024", "modelo-193-perceptor", "Tipo 2 - Registro De Perceptor"),
    _EnrolledRecord("193", "2024", "modelo-193-gastos", "Tipo 2 - Registro De Perceptor  Relación De Gastos"),
    _EnrolledRecord("193", "2025-y-siguientes", "modelo-193-declarante", "Tipo 1 - Registro De Declarante"),
    _EnrolledRecord("193", "2025-y-siguientes", "modelo-193-perceptor", "Tipo 2 - Registro De Perceptor"),
    _EnrolledRecord(
        "193", "2025-y-siguientes", "modelo-193-gastos", "Tipo 2 - Registro De Perceptor  Relación De Gastos"
    ),
    # Modelo 720's two records against Orden HAP/72/2013. Both are
    # binding-derived: their TOML declares one reserved-tail filler each and the
    # remaining coordinates come from the bindings, which is why they must be
    # read through the resolver. Resolved, they write all 500 bytes and leave no
    # gap at all -- a stronger state than a reconciled one, and the reason the
    # anti-vacuity check below does not demand a blank slot from every sheet.
    _EnrolledRecord("720", "2013-y-siguientes", "modelo-720-type-1", "Tipo 1 - Registro De Declarante"),
    _EnrolledRecord("720", "2013-y-siguientes", "modelo-720-type-2", "Tipo 2 - Registro De Detalle"),
)


def _is_blank_slot(description: str | None) -> bool:
    return (description or "").strip().rstrip(".").upper() in _BLANK_DESCRIPTIONS


def _design_sheet(enrolled: _EnrolledRecord):
    modelo, catalogues = _committed_modelo(enrolled.modelo_id)
    revision = modelo.revisions[enrolled.revision_id]
    # Through the binding resolver, never the raw layout. A record declaring
    # ``binding_record`` carries its wire coordinates on the BINDINGS, and its
    # raw ``fields`` hold only what TOML states directly -- for modelo 720 that
    # is a single reserved-tail filler, so the raw view shows 320 of 500 bytes
    # written where the resolved view shows all 500. Reconciling the raw view
    # reports a 180-byte hole in a record that has none.
    layout = derive_export_layouts_from_bindings(revision)[0]

    design_refs = [
        ref
        for ref in layout.source_refs
        if (source := catalogues.sources.get(ref)) is not None and source.kind == "record_design"
    ]
    assert design_refs, f"{enrolled.modelo_id}/{enrolled.revision_id} layout cites no record design"

    source = catalogues.sources[design_refs[0]]
    path = Path(source.corpus_path)
    if not path.exists():
        path = bundled_path() / source.corpus_path
    assert path.exists(), f"{source.id} is not readable at {path}"

    sheets = {sheet.name: sheet for sheet in _extract_record_design(path)}
    sheet = sheets.get(enrolled.sheet_name)
    assert sheet is not None, (
        f"{enrolled.record_id} is enrolled against sheet {enrolled.sheet_name!r}, "
        f"which {source.id} does not carry: {sorted(sheets)}"
    )
    record = next(r for r in layout.records if r.id == enrolled.record_id)
    return record, sheet


@pytest.mark.parametrize("enrolled", _ENROLLED, ids=lambda e: f"{e.modelo_id}-{e.revision_id}-{e.record_id}")
def test_every_unwritten_position_is_a_design_blank(enrolled: _EnrolledRecord) -> None:
    record, sheet = _design_sheet(enrolled)

    written = {
        position
        for field in record.fields
        for position in range(field.offset, field.offset + field.length)
    }
    span = max(field.offset + field.length - 1 for field in record.fields)

    data_at: dict[int, str] = {}
    blank_at: set[int] = set()
    for field in sheet.fields:
        if field.offset is None:
            continue
        for position in range(field.offset, field.offset + (field.length or 1)):
            if _is_blank_slot(field.description):
                blank_at.add(position)
            else:
                data_at[position] = field.description or ""

    unwritten = [position for position in range(1, span + 1) if position not in written]
    over_data = [position for position in unwritten if position in data_at]
    unmapped = [position for position in unwritten if position not in data_at and position not in blank_at]

    assert not over_data, (
        f"{enrolled.record_id} leaves DATA positions unwritten, so a filing pads them with "
        f"spaces and under-declares them: "
        f"{sorted({(position, data_at[position]) for position in over_data})[:6]}"
    )
    assert not unmapped, (
        f"{enrolled.record_id} leaves positions unwritten that the design maps to no field at all "
        f"-- neither data nor a declared blank: {unmapped[:12]}"
    )


@pytest.mark.parametrize("enrolled", _ENROLLED, ids=lambda e: f"{e.modelo_id}-{e.revision_id}-{e.record_id}")
def test_the_reconciliation_is_measuring_a_real_record(enrolled: _EnrolledRecord) -> None:
    """A record that wrote everything, or nothing, would pass the gate vacuously.

    The sibling assertion is satisfied by an empty unwritten set, which is also
    what a record with no fields would produce. This pins that each enrolled row
    really does have both written bytes and design-declared blanks to reconcile.
    """
    record, sheet = _design_sheet(enrolled)

    assert record.fields, f"{enrolled.record_id} declares no fields"
    assert sheet.fields, f"{enrolled.sheet_name} carries no fields"
    assert any(not _is_blank_slot(field.description) for field in sheet.fields), (
        f"{enrolled.sheet_name} is entirely blank slots, so this row cannot catch a DATA gap"
    )

    written = {p for field in record.fields for p in range(field.offset, field.offset + field.length)}
    span = max(field.offset + field.length - 1 for field in record.fields)
    unwritten = [p for p in range(1, span + 1) if p not in written]

    # A record that writes every byte needs no blank to reconcile against, and
    # demanding one would red modelo 720 for being MORE complete than modelo
    # 193. Only a record that does leave a gap has to be measured against a
    # design that declares blanks at all.
    if unwritten:
        assert any(_is_blank_slot(field.description) for field in sheet.fields), (
            f"{enrolled.record_id} leaves {len(unwritten)} positions unwritten but "
            f"{enrolled.sheet_name} declares no blank slot to justify any of them"
        )


def test_a_data_gap_is_actually_detected() -> None:
    """Drop a record's field and the gate must report the design DATA it exposed.

    Without this the assertions above could hold because the reconciliation never
    finds anything, rather than because the records are correct.
    """
    enrolled = _ENROLLED[0]
    record, sheet = _design_sheet(enrolled)

    data_fields = [field for field in sheet.fields if field.offset is not None and not _is_blank_slot(field.description)]
    assert data_fields, "the enrolled sheet must carry a DATA field for this proof to mean anything"
    target = data_fields[0]

    written = {
        position
        for field in record.fields
        for position in range(field.offset, field.offset + field.length)
        if not (target.offset <= position < target.offset + (target.length or 1))
    }
    span = max(field.offset + field.length - 1 for field in record.fields)

    data_at = {
        position: field.description or ""
        for field in sheet.fields
        if field.offset is not None and not _is_blank_slot(field.description)
        for position in range(field.offset, field.offset + (field.length or 1))
    }
    exposed = [p for p in range(1, span + 1) if p not in written and p in data_at]

    assert exposed, (
        "removing a DATA field's coverage exposed no design DATA position, so the "
        "reconciliation cannot detect the defect it exists to catch"
    )
