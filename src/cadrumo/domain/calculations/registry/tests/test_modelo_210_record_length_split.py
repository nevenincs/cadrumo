"""Modelo 210 files each devengo era at the record length AEAT declares for it.

AEAT kept every data field where it stood between its 2022 and 2026 designs and
lengthened the record: the tail ``Reservado para la Administración`` grows from
532 bytes to 1832 and ``Indicador de fin de registro`` moves from 2692 to 3992,
taking ``Página 01`` from 2700 declared positions to 4000. ``Página 02`` is
unchanged at 1400.

BEFORE THE SPLIT one revision spanned both, valid from 2025-01-01 with no end
and citing both designs, and its single export layout emitted 2700. Every 2026
devengo would have gone out 1300 bytes short with its end-of-record marker
1300 positions early -- a malformed fichero that no gate caught, because the
relayout detector pairs designs by ejercicio and modelo 210's state DEVENGO
spans, and the straddle signal sees only displacement, not a lengthened tail.

WHAT THIS PINS. The property, not the arithmetic: each revision emits exactly
the positions its OWN cited design declares. Read from the design rather than
compared against 2700 and 4000 written here, so a future AEAT re-issue moves
both sides together instead of turning a corrected registry red.
"""

from __future__ import annotations

import pytest

from .....core.resources import bundled_path
from .. import extract_record_design
from ._registry_schema_support import _committed_registry_tree

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_AUTOLIQUIDACION = "m210-autoliquidacion"
_PAGE_ONE_SUFFIX = "01"


def _modelo_210():
    modelos, catalogues = _committed_registry_tree()
    return next(m for m in modelos if m.id == "210"), catalogues


def _cited_design(revision, catalogues) -> str:
    designs = [
        str(ref) for ref in revision.source_refs
        if catalogues.sources[str(ref)].kind == "record_design"
    ]
    assert len(designs) == 1, designs
    return designs[0]


def test_the_modelo_carries_one_revision_per_record_geometry() -> None:
    """Two revisions, tiling without gap or overlap at the design boundary."""
    modelo, _catalogues = _modelo_210()

    assert set(modelo.revisions) == {"2025", "2026-y-siguientes"}, sorted(modelo.revisions)

    earlier, later = modelo.revisions["2025"], modelo.revisions["2026-y-siguientes"]
    assert earlier.valid_to is not None, "the earlier revision is still open-ended"
    assert (earlier.valid_to.year, earlier.valid_to.month, earlier.valid_to.day) == (2025, 12, 31)
    assert (later.valid_from.year, later.valid_from.month, later.valid_from.day) == (2026, 1, 1)


def test_each_revision_cites_exactly_one_design() -> None:
    """A revision carrying one export layout may stand on only one geometry."""
    modelo, catalogues = _modelo_210()

    cited = {rid: _cited_design(rev, catalogues) for rid, rev in modelo.revisions.items()}

    assert cited == {"2025": "aeat-dr-210-2022", "2026-y-siguientes": "aeat-dr-210-2026"}, cited


def test_each_revision_emits_the_positions_its_own_design_declares() -> None:
    """The defect this split closed, asserted against the design rather than a constant."""
    modelo, catalogues = _modelo_210()
    checked = 0

    for revision_id, revision in modelo.revisions.items():
        design = extract_record_design(
            bundled_path() / catalogues.sources[_cited_design(revision, catalogues)].corpus_path,
        )
        page_one = next(s for s in design.sheets if s.name.strip().endswith(_PAGE_ONE_SUFFIX))
        record = next(
            rec
            for layout in revision.export_layouts
            for rec in layout.records
            if rec.id == _AUTOLIQUIDACION
        )
        extent = max(f.offset + f.length - 1 for f in record.fields if f.offset)
        assert extent == page_one.total_positions, (
            f"210/{revision_id} emits {extent} positions but its cited design declares "
            f"{page_one.total_positions}"
        )
        checked += 1

    assert checked == 2, checked


def test_the_two_geometries_really_differ() -> None:
    """Non-vacuity: the check above would hold trivially if both designs agreed."""
    modelo, catalogues = _modelo_210()

    spans = set()
    for revision in modelo.revisions.values():
        design = extract_record_design(
            bundled_path() / catalogues.sources[_cited_design(revision, catalogues)].corpus_path,
        )
        page_one = next(s for s in design.sheets if s.name.strip().endswith(_PAGE_ONE_SUFFIX))
        spans.add(page_one.total_positions)

    assert len(spans) == 2, spans
