"""Modelo 322's 2022 and 2023 designs STRADDLE, so its split cannot be derived on bytes.

Modelo 347's two designs nest exactly -- no field of either partially overlaps a
field of the other -- which is what makes its split's semantics carryable
without a per-box reading. That result invites a generalisation, and this module
exists because the generalisation is false.

Modelo 322's remaining boundary is the 2022/2023 one, and there the designs do
not nest. AEAT inserted fields into ``DR32201`` (84 fields becoming 99) and
shifted everything after them, so ``Liquidación. IVA DEVENGADO`` at 267-283 in
2022 sits at 272-288 in 2023: a five-byte displacement that leaves the two
overlapping without either containing the other. Eighty-two such straddles on
that sheet, three more on ``DR32202``.

WHY THAT MATTERS FOR THE SPLIT. Where a field is wholly inside another, the
narrower is a subdivision of the wider and its meaning is bounded by it. Where
two fields straddle, each covers bytes the other does not, and nothing about
their relationship can be asserted from position -- the only remaining route is
reading AEAT's prose box by box. So modelo 322's recorded blocker ("no key pairs
the two designs totally") is CORRECT, and unlike modelo 347's it is not an
artefact of the key chosen.

THE SHAPE IS LOCALISED, WHICH IS THE USEFUL PART. Three of the five sheets --
``DR32200``, ``DR32203``, ``DR32204`` -- nest cleanly and are untouched by the
re-layout. Only two need the manual reading.
"""

from __future__ import annotations

import pytest

from .....core.resources.bundled_data import bundled_path
from ..record_design import extract_record_design
from ._registry_schema_support import _committed_registry_tree

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_EARLIER = "aeat-dr-322-2022"
_LATER = "aeat-dr-322-2023"

#: Sheets the 2022/2023 re-layout leaves byte-compatible.
_NESTING_SHEETS = frozenset({"DR32200", "DR32203", "DR32204"})
#: Sheets where fields straddle, so semantics cannot be carried on position.
_STRADDLING_SHEETS = frozenset({"DR32201", "DR32202"})


def _designs():
    _modelos, catalogues = _committed_registry_tree()
    return {
        ref: extract_record_design(bundled_path() / catalogues.sources[ref].corpus_path) for ref in (_EARLIER, _LATER)
    }


def _straddles(sheet_name: str) -> list[str]:
    designs = _designs()
    earlier = next(s for s in designs[_EARLIER].sheets if s.name == sheet_name)
    later = next(s for s in designs[_LATER].sheets if s.name == sheet_name)
    found: list[str] = []
    for a in earlier.fields:
        a_start, a_end = a.offset, a.offset + a.length - 1
        for b in later.fields:
            b_start, b_end = b.offset, b.offset + b.length - 1
            if a_end < b_start or b_end < a_start:
                continue
            if (a_start >= b_start and a_end <= b_end) or (b_start >= a_start and b_end <= a_end):
                continue
            found.append(f"{sheet_name}: 2022 @{a_start}-{a_end} >< 2023 @{b_start}-{b_end}")
    return found


def test_both_designs_read_cleanly_and_declare_the_same_sheets() -> None:
    """Non-vacuity: a skipped read or a renamed sheet would fake either verdict."""
    designs = _designs()
    for ref, design in designs.items():
        assert not design.skipped, (ref, [(s.name, s.reason) for s in design.skipped])

    earlier = {s.name for s in designs[_EARLIER].sheets}
    later = {s.name for s in designs[_LATER].sheets}
    assert earlier == later, (sorted(earlier - later), sorted(later - earlier))
    assert earlier == _NESTING_SHEETS | _STRADDLING_SHEETS, sorted(earlier)


@pytest.mark.parametrize("sheet_name", sorted(_STRADDLING_SHEETS))
def test_the_re_laid_sheets_straddle(sheet_name: str) -> None:
    """The finding: position cannot carry semantics across this boundary.

    Asserted as presence rather than as a count -- the exact number of straddles
    is an artefact of how many fields sit after the insertion point, and pinning
    it would make an unrelated design correction look like a regression.
    """
    assert _straddles(sheet_name), (
        f"{sheet_name} no longer straddles. If AEAT's designs really became byte-compatible "
        "this module's premise is gone; more likely the two designs stopped being compared."
    )


@pytest.mark.parametrize("sheet_name", sorted(_NESTING_SHEETS))
def test_the_untouched_sheets_nest_cleanly(sheet_name: str) -> None:
    """The other half: the re-layout is localised, so only two sheets need reading."""
    assert _straddles(sheet_name) == []


def test_the_straddling_is_not_merely_a_field_count_difference() -> None:
    """Distinguishes a genuine displacement from fields simply being added.

    Adding fields into reserved space would change the count while leaving every
    surviving field where it was, and would NOT straddle. DR32201 both gains
    fields and moves the survivors, which is what makes it a re-layout.
    """
    designs = _designs()
    earlier = next(s for s in designs[_EARLIER].sheets if s.name == "DR32201")
    later = next(s for s in designs[_LATER].sheets if s.name == "DR32201")

    assert len(earlier.fields) != len(later.fields), "DR32201 field counts now agree"

    earlier_starts = {f.offset for f in earlier.fields}
    later_starts = {f.offset for f in later.fields}
    assert earlier_starts - later_starts, (
        "every 2022 field start survives in 2023, so nothing was displaced and the straddles "
        "above would need another explanation"
    )
