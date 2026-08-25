"""Modelo 200's 2024-y-siguientes revision spans two incompatible layouts, and files at one.

The revision is valid from 2024-01-01 with no end date and cites TWO record
designs, ``aeat-dr-200-2024`` and ``aeat-dr-200-2025``. AEAT re-laid the form
out between them: the standing relayout gate measures 1140 of 3194 shared boxes
moving, and the two designs do not even carry the same number of sheets (75
against 77).

The committed export tree implements the 2025 geometry -- its generation
provenance stamps ``design_epoch: 2025`` -- so an ejercicio 2024 filing made
under this revision is written at the 2025 layout. That is the concrete
consequence of the span, and it is what makes splitting the revision a filing
correctness matter rather than a tidiness one.

WHAT THIS MODULE IS FOR. The relayout gate already reports that the span exists,
in terms of casilla movement. This one records which layout the TREE currently
implements and how far the other design is from it, because a split has to
re-render one side and needs to know which side is already correct.

HOW IT WAS GOT WRONG FIRST. These same eight records were previously read as
writing data into AEAT-reserved positions and overrunning their record length.
That reading came from comparing them against ``aeat-dr-200-2024`` -- the first
record_design the revision happens to list -- while the tree was generated from
``aeat-dr-200-2025``. Against the design the generator actually used, all eight
tile exactly and intrude on nothing. Where a revision cites more than one
design, "the design" is not well defined, and picking the first is not picking
the right one.
"""

from __future__ import annotations

import pytest

from .....core.resources import bundled_path
from .. import extract_record_design
from .._export import derive_export_layouts_from_bindings
from ._registry_schema_support import _committed_registry_tree

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_REVISION = "2024-y-siguientes"
_RENDERED_AGAINST = "aeat-dr-200-2025"
_OTHER_DESIGN = "aeat-dr-200-2024"

#: The continuation records whose geometry differs between the two designs.
_RECORDS = (
    "m200-page-015b",
    "m200-page-016b",
    "m200-page-018b",
    "m200-page-020b",
    "m200-page-020c",
    "m200-page-020d",
    "m200-page-022b",
    "m200-page-026b",
)


def _tree():
    modelos, catalogues = _committed_registry_tree()
    modelo = next(candidate for candidate in modelos if candidate.id == "200")
    return modelo.revisions[_REVISION], catalogues


def _design(ref: str):
    _revision, catalogues = _tree()
    return extract_record_design(bundled_path() / catalogues.sources[ref].corpus_path)


def _records():
    revision, _catalogues = _tree()
    return {record.id: record for layout in derive_export_layouts_from_bindings(revision) for record in layout.records}


def _sheet_for(record_id: str, design):
    name = "DP200" + record_id.split("page-")[1].upper()
    return next((sheet for sheet in design.sheets if sheet.name == name), None)


def test_the_revision_cites_both_designs() -> None:
    """The span itself, stated from the registry rather than from the gate's message."""
    revision, catalogues = _tree()

    designs = [ref for ref in revision.source_refs if catalogues.sources[ref].kind == "record_design"]

    assert set(designs) == {_OTHER_DESIGN, _RENDERED_AGAINST}, designs


def test_both_designs_read_cleanly_so_the_comparison_means_something() -> None:
    """A skipped or holed read would make every coordinate below untrustworthy."""
    for ref in (_OTHER_DESIGN, _RENDERED_AGAINST):
        design = _design(ref)
        assert not design.skipped, (ref, [(s.name, s.reason) for s in design.skipped])
        assert design.sheets, ref


def test_the_committed_tree_implements_the_2025_geometry_exactly() -> None:
    """Which side of the span is already correct, and needs no re-rendering."""
    design = _design(_RENDERED_AGAINST)
    records = _records()
    checked = 0

    for record_id in _RECORDS:
        record = records[record_id]
        sheet = _sheet_for(record_id, design)
        assert sheet is not None, f"{record_id}: sheet absent from {_RENDERED_AGAINST}"
        extent = max(field.offset + field.length - 1 for field in record.fields if field.offset)
        assert extent == sheet.total_positions, (
            f"{record_id} spans {extent} but {_RENDERED_AGAINST} declares {sheet.total_positions}"
        )
        checked += 1

    assert checked == len(_RECORDS)


def test_the_other_design_declares_a_different_length_for_every_one_of_them() -> None:
    """The span is material, not cosmetic -- these records cannot serve both years.

    Asserted as inequality rather than by pinning the 2024 numbers: the point is
    that the two designs disagree, and pinning both sides would turn a split
    into a test edit for no gain.
    """
    other = _design(_OTHER_DESIGN)
    rendered = _design(_RENDERED_AGAINST)
    differing = 0

    for record_id in _RECORDS:
        other_sheet = _sheet_for(record_id, other)
        rendered_sheet = _sheet_for(record_id, rendered)
        assert other_sheet is not None and rendered_sheet is not None, record_id
        if other_sheet.total_positions != rendered_sheet.total_positions:
            differing += 1

    assert differing == len(_RECORDS), (
        f"only {differing} of {len(_RECORDS)} records differ between the two designs; "
        "the set this module tracks no longer describes the divergence"
    )
