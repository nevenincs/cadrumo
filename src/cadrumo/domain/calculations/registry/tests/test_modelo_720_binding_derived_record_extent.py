"""Modelo 720's binding-derived records tile their design sheet exactly.

Modelo 720 declares its two records by INTENT -- ``binding_record = "type_1"``
-- and lets the resolver derive every field coordinate from the binding
selectors. That is why the committed layout carries a single declared field per
record: a reserved tail. Without it the records went out 180 and 480 bytes long
where AEAT reads 500, because the emitted length is
``max(offset + length - 1)`` over whatever fields the record ends up with, and
a derived set that stops early produces a short line rather than an error.

WHAT THIS PINS. Not the tail's presence, which would restate the layout back to
itself. The finished geometry, against the AEAT Diseño as the independent
authority: each record spans exactly the positions its sheet declares, and the
derived fields plus the tail tile that span with NO unwritten position at all.

Zero holes is the strong form and it is the one that holds here, unlike modelo
193, whose records legitimately leave AEAT's own ``BLANCOS`` runs unwritten. A
hole appearing in 720 would mean a derived field went missing between the
binding table and the record, which is invisible in a rendered line because
every unclaimed position emits as a space.
"""

from __future__ import annotations

import pytest

from .....core.resources import bundled_path
from .. import extract_record_design
from ..export import derive_export_layouts_from_bindings
from ._registry_schema_support import _committed_registry_tree

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

#: Record id -> the design sheet that governs it.
_SHEET_FOR_RECORD = {
    "modelo-720-type-1": "Tipo 1 - Registro De Declarante",
    "modelo-720-type-2": "Tipo 2 - Registro De Detalle",
}


def _modelo_720_cases():
    modelos, catalogues = _committed_registry_tree()
    modelo = next(candidate for candidate in modelos if candidate.id == "720")
    for revision_id, revision in modelo.revisions.items():
        design_ref = next(ref for ref in revision.source_refs if catalogues.sources[ref].kind == "record_design")
        design = extract_record_design(bundled_path() / catalogues.sources[design_ref].corpus_path)
        sheets = {sheet.name: sheet for sheet in design.sheets}
        for layout in derive_export_layouts_from_bindings(revision):
            for record in layout.records:
                yield revision_id, record, sheets[_SHEET_FOR_RECORD[record.id]]


def test_derivation_actually_produces_fields_beyond_the_declared_tail() -> None:
    """The committed layout declares one field per record; the rest are derived.

    Asserted first because every check below would pass vacuously on a record
    that still carried only its tail.
    """
    checked = 0
    for revision_id, record, _sheet in _modelo_720_cases():
        positioned = [field for field in record.fields if field.offset and field.length]
        assert len(positioned) > 1, (
            f"720/{revision_id} record {record.id} resolved to {len(positioned)} positioned "
            "field(s), so binding derivation produced nothing"
        )
        checked += 1
    assert checked, "no modelo 720 records were examined"


def test_each_record_spans_exactly_the_positions_its_design_declares() -> None:
    """Short-line truncation is the defect the reserved tail exists to close."""
    for revision_id, record, sheet in _modelo_720_cases():
        extent = max(field.offset + field.length - 1 for field in record.fields if field.offset)
        assert extent == sheet.total_positions, (
            f"720/{revision_id} record {record.id} spans {extent} positions but its design sheet "
            f"{sheet.name!r} declares {sheet.total_positions}"
        )


def test_the_derived_fields_leave_no_position_unwritten() -> None:
    """A derived field lost between binding table and record emits as spaces, not as an error."""
    for revision_id, record, sheet in _modelo_720_cases():
        occupied: set[int] = set()
        for field in record.fields:
            if field.offset and field.length:
                occupied |= set(range(field.offset, field.offset + field.length))
        unwritten = sorted(set(range(1, sheet.total_positions + 1)) - occupied)
        assert not unwritten, (
            f"720/{revision_id} record {record.id} leaves {len(unwritten)} position(s) unwritten, "
            f"first at {unwritten[0]}"
        )


def test_the_derived_field_count_agrees_with_the_design() -> None:
    """Two independent authorities counting the same record.

    The registry derives fields from binding selectors; AEAT's Diseño lists them
    directly. Agreement is evidence the derivation reproduced the published
    record rather than merely covering its bytes -- a single wide field would
    satisfy the tiling check above and fail this one.
    """
    for revision_id, record, sheet in _modelo_720_cases():
        positioned = [field for field in record.fields if field.offset and field.length]
        assert len(positioned) == len(sheet.fields), (
            f"720/{revision_id} record {record.id} resolved {len(positioned)} fields but its "
            f"design sheet lists {len(sheet.fields)}"
        )
