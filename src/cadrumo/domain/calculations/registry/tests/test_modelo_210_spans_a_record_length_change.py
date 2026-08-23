"""Modelo 210's single revision spans a record-length change its designs do not advertise.

Revision ``2025`` is valid from 2025-01-01 with no end date and DECLARES BOTH of
this modelo's current designs -- ``aeat-dr-210-2022`` (devengos 2022-06-01 to
2025-12-31) and ``aeat-dr-210-2026`` (devengos from 2026-01-01). Between them
AEAT did not move a single data field: all 127 positions on ``Página 01`` are
byte-identical and nothing straddles. What changed is the RECORD LENGTH.
``Reservado para la Administración`` grows from 532 bytes to 1832, and the
``Indicador de fin de registro`` moves from 2692 to 3992, taking the record from
2700 positions to 4000.

WHY THIS IS INVISIBLE TO THE RELAYOUT GATE. That gate pairs a revision's designs
by the ejercicios they cover, and modelo 210's designs state DEVENGO spans
rather than ejercicios -- deliberately, since enumerating a devengo span into
years would invent them. So the pair never forms and modelo 210 appears on no
spanning row, while 200, 322 and 347 do.

WHY IT IS INVISIBLE TO THE STRADDLE SIGNAL TOO. Straddling detects a field
DISPLACED across another's boundary. Here nothing is displaced; a reserved run
was extended at the tail. Both instruments are silent on a change that alters
every emitted line's length.

WHAT THIS MODULE ASSERTS, AND WHAT IT DELIBERATELY DOES NOT. It pins the inputs
that make a split necessary: both designs readable, their data fields nesting,
their record lengths differing, and the revision declaring both. It does NOT
assert the length the committed layout currently emits. That figure is the
defect -- a filing for a 2026 devengo goes out at the 2022 geometry -- and
freezing it here would turn a defect into the contract.
"""

from __future__ import annotations

import pytest

from .....core.resources import bundled_path
from .. import extract_record_design
from ._registry_schema_support import _committed_registry_tree

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_EARLIER = "aeat-dr-210-2022"
_LATER = "aeat-dr-210-2026"
_PAGE_ONE_SUFFIX = "01"


def _tree():
    modelos, catalogues = _committed_registry_tree()
    modelo = next(candidate for candidate in modelos if candidate.id == "210")
    return modelo, catalogues


def _designs():
    _modelo, catalogues = _tree()
    return {
        ref: extract_record_design(bundled_path() / catalogues.sources[ref].corpus_path)
        for ref in (_EARLIER, _LATER)
    }


def _page_one(design):
    return next(sheet for sheet in design.sheets if sheet.name.strip().endswith(_PAGE_ONE_SUFFIX))


def test_both_designs_read_cleanly() -> None:
    for ref, design in _designs().items():
        assert not design.skipped, (ref, [(s.name, s.reason) for s in design.skipped])
        assert design.sheets, ref


def test_one_revision_declares_both_designs() -> None:
    """The span itself: a single revision standing across two record geometries."""
    modelo, catalogues = _tree()

    assert set(modelo.revisions) == {"2025"}, sorted(modelo.revisions)
    revision = modelo.revisions["2025"]
    declared = {
        str(ref) for ref in revision.source_refs
        if catalogues.sources[str(ref)].kind == "record_design"
    }

    assert {_EARLIER, _LATER} <= declared, sorted(declared)
    assert revision.valid_to is None, revision.valid_to


def test_the_data_fields_are_unchanged_between_the_designs() -> None:
    """This is a length change, not a re-layout -- which is why straddling is silent."""
    designs = _designs()
    earlier, later = _page_one(designs[_EARLIER]), _page_one(designs[_LATER])

    assert len(earlier.fields) == len(later.fields), (len(earlier.fields), len(later.fields))

    straddles = []
    for a in earlier.fields:
        a_start, a_end = a.offset, a.offset + a.length - 1
        for b in later.fields:
            b_start, b_end = b.offset, b.offset + b.length - 1
            if a_end < b_start or b_end < a_start:
                continue
            if (a_start >= b_start and a_end <= b_end) or (b_start >= a_start and b_end <= a_end):
                continue
            straddles.append((a_start, a_end, b_start, b_end))
    assert not straddles, straddles


def test_the_record_length_differs_and_the_difference_is_the_reserved_run() -> None:
    """The consequence a split has to resolve: one revision, two record lengths."""
    designs = _designs()
    earlier, later = _page_one(designs[_EARLIER]), _page_one(designs[_LATER])

    assert earlier.total_positions != later.total_positions, earlier.total_positions
    assert later.total_positions > earlier.total_positions

    def _reserved(sheet):
        """The TAIL reserved run -- the sheet carries several, and only the last one grows."""
        matches = sorted(
            (f for f in sheet.fields if "reservado" in (f.description or "").casefold()),
            key=lambda field: field.offset,
        )
        assert matches, "the sheet declares no reserved run at all"
        return matches[-1]

    earlier_reserved, later_reserved = _reserved(earlier), _reserved(later)

    assert earlier_reserved.offset == later_reserved.offset, "the reserved run moved, so this is not a pure tail extension"
    growth = later_reserved.length - earlier_reserved.length
    assert growth > 0
    assert growth == later.total_positions - earlier.total_positions, (
        "the record grew by more than its reserved run, so data positions changed too"
    )
