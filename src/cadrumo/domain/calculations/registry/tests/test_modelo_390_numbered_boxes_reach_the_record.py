"""Every numbered box on Modelo 390's pages 5 and 7 reaches the fixed-width record.

WHAT THIS PINS. Page 05 carries the ``6. Operaciones Reg. Simplificado`` block
and page 07 the prorrata and regularizacion blocks. For every 390 revision that
ships an export layout, every box AEAT prints a number for on those sheets must
be covered by the record's fields -- otherwise a numbered figure is computed and
then never written, which a reader of the file cannot distinguish from a zero.

THE MEASUREMENT MUST SPAN EVERY FIELD KIND, AND THAT IS THE POINT. Page 05
declares ``binding_record``, so most of its coordinates are not authored in TOML
at all: :func:`derive_export_layouts_from_bindings` resolves them from the
binding selectors at snapshot build. A count restricted to ``kind == "casilla"``
sees almost none of them and reports a large phantom gap -- nine boxes on page
05 alone, every one of them in fact already written as a ``binding`` field. This
module therefore measures against the DERIVED layout and counts coverage by
BYTE, across all kinds.

That is not a hypothetical failure mode. It is the one this file exists to stop:
the phantom gap was measured, believed, and "closed" by authoring nine duplicate
casilla fields onto occupied offsets, which broke referential integrity across
the whole registry package before the control below was run.

WHAT IS NOT ASSERTED. Untagged positions are out of scope. AEAT numbers a box
once and repeats the row -- ``[66]`` heads Actividad 1 of five, ``[114]``-``[118]``
head Prorrata 1 of five -- so an untagged position is usually a further row of a
tagged group rather than an unnumbered datum. Box numbers, offsets and lengths
are read from the bundled design; nothing is transcribed here.
"""

from __future__ import annotations

import re

import pytest

from .....core.resources import bundled_path
from ..authority import bundled_authority
from ..export import derive_export_layouts_from_bindings
from ..record_design import extract_record_design
from ._registry_schema_support import _committed_registry_tree

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

#: A bracketed casilla number as AEAT prints it in a design description.
_TAG = re.compile(r"\[(\d+)\]")
_PAGES = (("page-05", "5"), ("page-07", "7"))
#: Below this the sheet was not read and the walk would pass vacuously.
_MINIMUM_BOXES = 10


def _revisions_with_a_layout():
    modelo = next(m for m in bundled_authority().modelos if str(m.id) == "390")
    return [
        (revision_id, revision) for revision_id, revision in sorted(modelo.revisions.items()) if revision.export_layouts
    ]


def _design_sheet_boxes(revision, suffix: str) -> dict[str, tuple[int, int]]:
    """Return ``box number -> (offset, length)`` from the revision's own design."""
    _, catalogues = _committed_registry_tree()
    source_ref = next(r for r in revision.export_layouts[0].source_refs if "dr-390" in r)
    extraction = extract_record_design(bundled_path() / catalogues.sources[source_ref].corpus_path)
    sheet = next(s for s in extraction.sheets if s.name.endswith(suffix))
    boxes: dict[str, tuple[int, int]] = {}
    for field in sheet.fields:
        for tag in _TAG.findall(field.description or ""):
            boxes.setdefault(tag, (field.offset, field.length))
    return boxes


def _written_bytes(revision, page: str) -> set[int]:
    """Return every byte the DERIVED record writes, across all field kinds."""
    derived = derive_export_layouts_from_bindings(revision)
    record = next((r for r in derived[0].records if str(r.id).endswith(page)), None)
    if record is None:
        return set()
    written: set[int] = set()
    for field in record.fields:
        assert field.offset is not None and field.length is not None, f"unpositioned derived field {field.id}"
        written |= set(range(field.offset, field.offset + field.length))
    return written


def test_every_numbered_box_on_pages_five_and_seven_is_written() -> None:
    checked = 0
    for revision_id, revision in _revisions_with_a_layout():
        for page, suffix in _PAGES:
            boxes = _design_sheet_boxes(revision, suffix)
            assert len(boxes) >= _MINIMUM_BOXES, (
                f"{revision_id} {page}: only {len(boxes)} numbered boxes read from the "
                "design; the sheet was not read and this walk would be vacuous"
            )
            written = _written_bytes(revision, page)
            missing = {
                number: span for number, span in boxes.items() if not set(range(span[0], span[0] + span[1])) <= written
            }
            checked += len(boxes)

            assert not missing, (
                f"modelo 390 revision {revision_id} {page} never writes these numbered "
                "boxes: "
                + ", ".join(f"[{n}] @{o}+{ln}" for n, (o, ln) in sorted(missing.items(), key=lambda kv: int(kv[0])))
            )

    assert checked, "no revision carried a page-05 or page-07 record; nothing was checked"


def test_counting_only_casilla_fields_would_report_a_phantom_gap() -> None:
    """The kind-blind measurement is load-bearing, so its necessity is asserted.

    If page 05 ever became fully casilla-authored this would fail, and that is
    the right moment to revisit the module: the reason for spanning every kind
    would have gone away. Until then this stops the walk above from being
    quietly narrowed back to one kind, which is the specific error that made a
    fully-written page look nine boxes short.
    """
    revision_id, revision = _revisions_with_a_layout()[0]
    boxes = _design_sheet_boxes(revision, "5")
    derived = derive_export_layouts_from_bindings(revision)
    record = next(r for r in derived[0].records if str(r.id).endswith("page-05"))

    casilla_only: set[int] = set()
    for field in record.fields:
        if field.kind == "casilla":
            assert field.offset is not None and field.length is not None, f"unpositioned casilla field {field.id}"
            casilla_only |= set(range(field.offset, field.offset + field.length))

    unseen = [
        number for number, (offset, length) in boxes.items() if not set(range(offset, offset + length)) <= casilla_only
    ]

    assert len(unseen) >= 5, (
        f"{revision_id}: a casilla-only measurement now misses only {sorted(unseen)} "
        "page-05 boxes. If page 05 became casilla-authored, retire this module "
        "rather than loosening it"
    )
    assert not [n for n in unseen if not set(range(*_span(boxes[n]))) <= _written_bytes(revision, "page-05")], (
        "every box a casilla-only count misses must still be written by another kind"
    )


def _span(box: tuple[int, int]) -> tuple[int, int]:
    offset, length = box
    return offset, offset + length
