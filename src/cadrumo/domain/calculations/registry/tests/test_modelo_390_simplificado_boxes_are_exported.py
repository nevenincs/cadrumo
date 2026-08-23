"""Every Modelo 390 Regimen Simplificado box AEAT numbers is written to the file.

WHAT WAS WRONG. Page 05 of the 390 record carries the ``6. Operaciones Reg.
Simplificado`` block: ten numbered boxes, ``[74]`` through ``[83]``, each a
17-byte money field. The registry declared a casilla for all ten, and the export
layout emitted exactly ONE of them -- box ``[79]``. The other nine were computed,
carried a legal grounding, and then never reached the fixed-width file, in all
four revisions that ship a layout (2022, 2023, 2024, 2025).

A blank money slot is a valid zero to a reader of the file, so this understated
the simplified-regime result silently rather than failing. That is the shape the
``no-silent-under-declaration`` rule exists for.

WHAT IS ASSERTED, AND AGAINST WHAT. For every 390 revision carrying an export
layout, every box number the BUNDLED design prints on its page-05 sheet that the
revision also declares as a casilla must be emitted by the page-05 record, at the
offset and length the design gives it. Nothing is transcribed: the box numbers,
offsets and lengths are read from AEAT's own design, and the casilla set from the
revision, so this compares two authorities rather than checking a list typed here.

WHY POSITION IS ASSERTED, NOT ONLY PRESENCE. A field emitted at the wrong offset
still tiles into a plausible record. Box ``[79]`` was already shipping at
``@1118+17`` before this change and independently confirms the convention the
other nine now follow.

WHAT IS DELIBERATELY OUT OF SCOPE. Box ``[66]`` (Epigrafe I.A.E.) is excluded by
the same rule that admits the rest -- it has no casilla -- and that is correct
rather than an omission: the design repeats it per Actividad, five rows deep, and
this registry models a repeating row table as a binding-row record. Modelo 390
has no such record yet. The assertion is therefore scoped to boxes the revision
declares a casilla for, which is exactly the population an export layout can
write today.
"""

from __future__ import annotations

import re

import pytest

from .....core.resources import bundled_path
from .. import bundled_authority, extract_record_design
from ._registry_schema_support import _committed_registry_tree

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

#: A bracketed casilla number as AEAT prints it in a design description.
_TAG = re.compile(r"\[(\d+)\]")
#: Below this the sheet was not read and every assertion would pass vacuously.
_MINIMUM_BOXES = 10


def _revisions_with_a_layout():
    modelo = next(m for m in bundled_authority().modelos if str(m.id) == "390")
    return [
        (revision_id, revision) for revision_id, revision in sorted(modelo.revisions.items()) if revision.export_layouts
    ]


def _design_boxes(revision) -> dict[str, tuple[int, int]]:
    """Return ``box number -> (offset, length)`` from the revision's own design."""
    _, catalogues = _committed_registry_tree()
    layout = revision.export_layouts[0]
    source_ref = next(ref for ref in layout.source_refs if "dr-390" in ref)
    extraction = extract_record_design(bundled_path() / catalogues.sources[source_ref].corpus_path)
    sheet = next(s for s in extraction.sheets if s.name.endswith("5"))
    boxes: dict[str, tuple[int, int]] = {}
    for field in sheet.fields:
        for tag in _TAG.findall(field.description or ""):
            boxes.setdefault(tag, (field.offset, field.length))
    return boxes


def test_every_numbered_simplificado_box_with_a_casilla_is_emitted() -> None:
    checked = 0
    for revision_id, revision in _revisions_with_a_layout():
        boxes = _design_boxes(revision)
        assert len(boxes) >= _MINIMUM_BOXES, (
            f"{revision_id}: only {len(boxes)} boxes read from the page-05 sheet; "
            "the design was not read and this assertion would be vacuous"
        )
        declared = {str(c.number) for c in revision.casillas if str(c.number).isdigit()}
        record = next(r for r in revision.export_layouts[0].records if str(r.id).endswith("page-05"))
        emitted = {(f.offset, f.length) for f in record.fields if f.kind == "casilla"}

        expected = {n: span for n, span in boxes.items() if n in declared}
        missing = {n: span for n, span in expected.items() if span not in emitted}
        checked += len(expected)

        assert not missing, (
            f"modelo 390 revision {revision_id} declares a casilla for these page-05 "
            "boxes but never writes them to the file: "
            + ", ".join(f"[{n}] @{o}+{ln}" for n, (o, ln) in sorted(missing.items(), key=lambda kv: int(kv[0])))
        )

    assert checked, "no revision carried a page-05 layout; nothing was checked"


def test_the_scope_rule_still_admits_the_simplificado_block() -> None:
    """The population must not shrink to nothing by the casilla filter.

    Without this, deleting the ten casillas would make the check above pass while
    the file lost every simplified-regime figure -- the exact failure it exists to
    prevent, arrived at from the other side.
    """
    for revision_id, revision in _revisions_with_a_layout():
        boxes = _design_boxes(revision)
        declared = {str(c.number) for c in revision.casillas if str(c.number).isdigit()}
        in_scope = sorted(set(boxes) & declared, key=int)

        assert len(in_scope) >= _MINIMUM_BOXES, (
            f"{revision_id}: only {in_scope} page-05 boxes are backed by a casilla; "
            "the simplified-regime block has lost its casillas"
        )
