"""Modelo 347 spans a SECOND re-layout the boundary detector does not report.

The relayout gate reports one boundary for revision ``2008-2024`` -- 2009/2010 --
and its own message warns that "splitting at only the ones one signal saw leaves
the rest live". That warning applies here, because there is a second boundary it
does not see.

Between the 2010 and 2011 designs AEAT widened ``IMPORTE TOTAL ANUAL DE LAS
OPERACIONES`` on the declarante record from 15 bytes to 16 and shifted
everything after it by one: ``NUMERO TOTAL DE INMUEBLES`` moves from 160 to 161.
The declarado record shifts the same way, ``IMPORTE PERCIBIDO EN METALICO``
moving from 100 to 101. Eleven fields straddle across the two designs.

WHY THE DETECTOR IS BLIND TO IT. Its signals key on box numbers moving and on
the field SET changing. Modelo 347's designs print no bracketed box numbers at
all, so the movement signal has nothing to key on; and a one-byte widening
changes no field's description, so the set signal sees the same fields before
and after. The gate flags this class itself -- "unnumbered slot(s) re-described
at an unchanged position and width ... INSTRUMENT LIMIT: this is the weakest
signal in this module". This is that limit reached, with a real displacement
behind it.

WHY IT MATTERS. Revision ``2008-2024`` is valid from 2008-01-01 to 2024-12-31
and cites the 2011 design, so it covers filing years the 2010 design governs and
writes them at 2011 offsets -- one byte out from position 145 onward. Splitting
it only at 2009/2010 would leave that live inside the resulting ``2010-2024``.

STRADDLING IS THE SIGNAL THE MODULE LACKS, and it works precisely where the
others fail: it reads bytes, so it needs no box number and no description
change.
"""

from __future__ import annotations

import pytest

from .....core.resources import bundled_path
from .. import extract_record_design
from ._registry_schema_support import _committed_registry_tree

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_2010 = "aeat-dr-347-2010"
_2011 = "aeat-dr-347-2011"

_DISPLACED_SHEETS = ("Tipo 1 - Registro De Declarante", "Tipo 2 - Registro De Declarado")
_STABLE_SHEET = "Tipo 2 - Registro De Inmueble"


def _designs():
    _modelos, catalogues = _committed_registry_tree()
    return {
        ref: extract_record_design(bundled_path() / catalogues.sources[ref].corpus_path)
        for ref in (_2010, _2011)
    }


def _straddles(sheet_name: str) -> list[str]:
    designs = _designs()
    earlier = next(s for s in designs[_2010].sheets if s.name == sheet_name)
    later = next(s for s in designs[_2011].sheets if s.name == sheet_name)
    found: list[str] = []
    for a in earlier.fields:
        a_start, a_end = a.offset, a.offset + a.length - 1
        for b in later.fields:
            b_start, b_end = b.offset, b.offset + b.length - 1
            if a_end < b_start or b_end < a_start:
                continue
            if (a_start >= b_start and a_end <= b_end) or (b_start >= a_start and b_end <= a_end):
                continue
            found.append(f"{sheet_name}: 2010 @{a_start}-{a_end} >< 2011 @{b_start}-{b_end}")
    return found


def test_both_designs_read_cleanly() -> None:
    for ref, design in _designs().items():
        assert not design.skipped, (ref, [(s.name, s.reason) for s in design.skipped])
        assert design.sheets, ref


@pytest.mark.parametrize("sheet_name", _DISPLACED_SHEETS)
def test_the_2010_and_2011_designs_straddle(sheet_name: str) -> None:
    """The undetected boundary, on the two records that carry it."""
    assert _straddles(sheet_name), (
        f"{sheet_name} no longer straddles between the 2010 and 2011 designs. Either AEAT's "
        "layouts converged or the two designs stopped being compared."
    )


def test_the_third_record_is_untouched_so_the_displacement_is_localised() -> None:
    """Non-vacuity from the other side: not everything straddles everything."""
    assert _straddles(_STABLE_SHEET) == []


def test_the_displacement_is_a_one_byte_widening_not_a_new_field() -> None:
    """Names the mechanism, which is what makes it invisible to a set-difference signal.

    The declarante record has the SAME number of fields in both designs, and the
    field at 145 is one byte wider in 2011. A signal watching for fields added
    or removed sees nothing here; a signal watching box numbers has none to
    watch.
    """
    designs = _designs()
    earlier = next(s for s in designs[_2010].sheets if s.name == _DISPLACED_SHEETS[0])
    later = next(s for s in designs[_2011].sheets if s.name == _DISPLACED_SHEETS[0])

    assert len(earlier.fields) == len(later.fields), (
        "the declarante field counts now differ, so a set-difference signal would catch this "
        "and the blindness this module documents no longer applies"
    )

    earlier_at_145 = next(f for f in earlier.fields if f.offset == 145)
    later_at_145 = next(f for f in later.fields if f.offset == 145)
    assert later_at_145.length == earlier_at_145.length + 1, (
        f"expected a one-byte widening at 145; got {earlier_at_145.length} -> {later_at_145.length}"
    )


def test_the_revision_really_covers_both_designs_years() -> None:
    """The consequence: this is a live span, not an abstract difference."""
    modelos, catalogues = _committed_registry_tree()
    modelo = next(m for m in modelos if m.id == "347")
    revision = modelo.revisions["2008-2024"]

    cited = [r for r in revision.source_refs if catalogues.sources[r].kind == "record_design"]
    assert cited == [_2011], cited
    assert revision.valid_from.year <= 2010, revision.valid_from
    assert revision.valid_to is None or revision.valid_to.year >= 2011, revision.valid_to
