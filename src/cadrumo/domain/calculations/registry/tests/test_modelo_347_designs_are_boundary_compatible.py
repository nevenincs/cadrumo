"""Modelo 347's 2008 and 2010 designs nest cleanly, so the split boundary is pairable.

The split-progress record says these two designs are "NOT derivable: their box
numbers agree with 2010's on 11 of 43, so a derivation would carry semantics
onto the wrong boxes". The measurement is right and the conclusion drawn from it
is too narrow: these designs print NO bracketed box numbers at all, so a
number-keyed pairing was never going to work on them, and its failure says
nothing about whether the two layouts correspond.

They correspond exactly. Read on bytes rather than on numbers, the 2009/2010
re-layout is four merges and one addition, with every position accounted for:

* ``PERSONA TELEFONO`` (59+9) and ``CON QUIEN RELACIONARSE`` (68+40) become one
  ``PERSONA CON QUIEN RELACIONARSE`` (59+49);
* ``DEC. COMPLEMENTARIA`` (121+1) and ``DEC. SUSTITUTIVA`` (122+1) become
  ``DECLARACION COMPLEMENTARIA O SUSTITUTIVA`` (121+2);
* ``CODIGO PROVINCIA`` (77+2) and ``CODIGO PAIS`` (79+2) become
  ``CODIGO PROVINCIA/PAIS`` (77+4);
* two ``IMPORTE ... `` + ``DECIMAL`` pairs (100+13 / 113+2 and 115+13 / 128+2)
  become 15-byte amounts;
* and 2010 carves a 4-byte ``EJERCICIO`` (130+4) out of the trailing BLANCOS.

WHAT THIS ASSERTS, AND WHY IT IS THE RIGHT PROPERTY. Not a field-to-field map,
which would be a similarity judgement and is exactly what the grounding rule
forbids as a route to box identity. The weaker, checkable, structural fact:
NO FIELD OF EITHER DESIGN PARTIALLY OVERLAPS A FIELD OF THE OTHER. Every overlap
is total containment in one direction or the other.

That is the property that makes a split authorable, and it is the same
containment-versus-partial-overlap distinction the record-design contiguity
rules already turn on. Where one design's field sits wholly inside another's,
the narrower one is a subdivision of the wider and its meaning is bounded by it.
Where fields straddle, nothing can be said without reading AEAT's prose. These
two never straddle.
"""

from __future__ import annotations

import pytest

from .....core.resources.bundled_data import bundled_path
from ..record_design import extract_record_design
from ..record_design_schema import RecordDesignField
from ._registry_schema_support import _committed_registry_tree

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_EARLIER = "aeat-dr-347-2008"
_LATER = "aeat-dr-347-2010"

_SHEETS = (
    "Tipo 1 - Registro De Declarante",
    "Tipo 2 - Registro De Declarado",
    "Tipo 2 - Registro De Inmueble",
)


def _designs():
    _modelos, catalogues = _committed_registry_tree()
    return {
        ref: extract_record_design(bundled_path() / catalogues.sources[ref].corpus_path) for ref in (_EARLIER, _LATER)
    }


def _span(field: RecordDesignField) -> tuple[int, int]:
    assert field.offset is not None
    assert field.length is not None
    return field.offset, field.offset + field.length - 1


def test_both_designs_read_cleanly_and_cover_the_same_record_length() -> None:
    """Non-vacuity, and the precondition for comparing positions at all."""
    designs = _designs()
    for ref, design in designs.items():
        assert not design.skipped, (ref, [(s.name, s.reason) for s in design.skipped])
        for name in _SHEETS:
            sheet = next((s for s in design.sheets if s.name == name), None)
            assert sheet is not None, f"{ref} has no sheet {name!r}"
            assert sheet.total_positions == 500, (ref, name, sheet.total_positions)


def test_neither_design_carries_a_box_number_so_number_pairing_was_never_possible() -> None:
    """The measurement behind the 'not derivable' verdict, and its real cause.

    A number-keyed pairing cannot succeed on designs that print no numbers, so
    its low agreement rate is a fact about the key, not about the layouts.
    """
    designs = _designs()
    tagged = [
        (ref, sheet.name, field.offset)
        for ref, design in designs.items()
        for sheet in design.sheets
        if sheet.name in _SHEETS
        for field in sheet.fields
        if "[" in (field.description or "")
    ]

    assert tagged == [], f"these designs do print box numbers after all: {tagged[:5]}"


@pytest.mark.parametrize("sheet_name", _SHEETS)
def test_no_field_partially_overlaps_a_field_of_the_other_design(sheet_name: str) -> None:
    """The property that makes the split authorable: containment, never straddling."""
    designs = _designs()
    earlier = next(s for s in designs[_EARLIER].sheets if s.name == sheet_name)
    later = next(s for s in designs[_LATER].sheets if s.name == sheet_name)

    straddles = []
    for a in earlier.fields:
        a_start, a_end = _span(a)
        for b in later.fields:
            b_start, b_end = _span(b)
            if a_end < b_start or b_end < a_start:
                continue  # disjoint
            contained = (a_start >= b_start and a_end <= b_end) or (b_start >= a_start and b_end <= a_end)
            if not contained:
                straddles.append(
                    f"{sheet_name}: 2008 @{a_start}-{a_end} {(a.description or '')[:28]!r} "
                    f"straddles 2010 @{b_start}-{b_end} {(b.description or '')[:28]!r}",
                )

    assert not straddles, straddles


@pytest.mark.parametrize("sheet_name", _SHEETS)
def test_the_two_layouts_are_genuinely_different(sheet_name: str) -> None:
    """Containment would hold trivially if the designs were identical.

    They are not: this is a real re-layout, which is why the revision spanning
    it has to be split at all.
    """
    designs = _designs()
    earlier = {_span(f) for f in next(s for s in designs[_EARLIER].sheets if s.name == sheet_name).fields}
    later = {_span(f) for f in next(s for s in designs[_LATER].sheets if s.name == sheet_name).fields}

    assert earlier != later, f"{sheet_name}: the two designs declare identical field spans"
