"""Modelo 100 escala rows the law leaves unchanged stay keyed from their first day.

When a reform changes only some tranches of a progressive scale, the later
edition closes and replaces only those tranches; the untouched ones stay the open
rows of the edition that first stated them. The in-force table of a year then
mixes rows keyed from different first days, and read as a whole it must still be
one progressive scale: it starts at zero with no accumulated cuota, each rung
begins where the one beneath it ends, and the top rung is open.

The accumulated cuota of each rung and the re-keying of a numerically unchanged
row are judged registry-wide, by the bracket accumulated-cuota gate and the
open-row gate, which read every in-force table whole and compare rows by typed
value.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date, timedelta
from decimal import Decimal
from functools import cache
from itertools import pairwise

import pytest

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.schema import ModeloDefinition, ModeloRevision
from cadrumo.domain.calculations.registry.schema_formula import BracketEntry, ParameterDefinition
from cadrumo.domain.calculations.registry.temporal import select_revision_for_year

from ..compiler.loader import load_modelo_directory, load_shared_catalogues

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


@cache
def _modelo() -> ModeloDefinition:
    return load_modelo_directory(bundled_path("registry", "aeat", "modelos", "100"))


@cache
def _supported_years() -> tuple[int, ...]:
    support = load_shared_catalogues(bundled_path("registry", "aeat")).require_supported_filing_years()
    return tuple(support.years)


def _edition_for(year: int) -> ModeloRevision:
    support = load_shared_catalogues(bundled_path("registry", "aeat")).require_supported_filing_years()
    return select_revision_for_year(_modelo(), filing_year=year, support=support)


def _scales(revision: ModeloRevision) -> Iterable[ParameterDefinition]:
    return (parameter for parameter in revision.parameters if parameter.data_type == "bracket_table")


def _in_force(parameter: ParameterDefinition, on: date) -> tuple[BracketEntry, ...]:
    rows = (row for row in parameter.brackets if row.valid_from <= on and (row.valid_to is None or on <= row.valid_to))
    return tuple(sorted(rows, key=lambda row: row.lower_bound))


def _scale_defects(rows: tuple[BracketEntry, ...]) -> list[str]:
    """Report every break in the shape of one in-force table read as a single scale."""
    if not rows:
        return ["no rung in force"]
    defects: list[str] = []
    if rows[0].lower_bound != 0 or rows[0].fixed_addition != 0:
        defects.append(f"first rung starts at {rows[0].lower_bound} with cuota {rows[0].fixed_addition}")
    if rows[-1].upper_bound is not None:
        defects.append(f"top rung closes at {rows[-1].upper_bound}")
    defects.extend(
        f"rung {lower.lower_bound} ends at {lower.upper_bound}, next starts {upper.lower_bound}"
        for lower, upper in pairwise(rows)
        if lower.upper_bound != upper.lower_bound
    )
    return defects


def test_every_supported_year_reads_each_scale_as_one_progressive_table() -> None:
    """Rows keyed from different first days still form one contiguous scale in every supported year."""
    defects: dict[tuple[str, int], list[str]] = {}
    split_tables: set[tuple[str, int]] = set()
    for year in _supported_years():
        for parameter in _scales(_edition_for(year)):
            for on in (date(year, 1, 1), date(year, 12, 31)):
                rows = _in_force(parameter, on)
                if len({row.valid_from for row in rows}) > 1:
                    split_tables.add((parameter.id, year))
                if found := _scale_defects(rows):
                    defects[parameter.id, year] = found

    assert split_tables, "no supported year reads a scale whose unchanged rungs kept their first day"
    assert defects == {}, defects


def _rung(lower: str, upper: str | None, fixed: str, rate: str, valid_from: date) -> BracketEntry:
    return BracketEntry(
        lower_bound=Decimal(lower),
        upper_bound=None if upper is None else Decimal(upper),
        fixed_addition=Decimal(fixed),
        marginal_rate=Decimal(rate),
        valid_from=valid_from,
    )


def test_a_scale_split_across_windows_with_a_broken_shape_is_detected() -> None:
    """The whole-table read catches a gap, a closed top and a late start between rungs keyed from different days."""
    first = date(2020, 1, 1)
    second = first + timedelta(days=366)
    continuous = (_rung("0", "6000", "0", "0.095", first), _rung("6000", None, "570", "0.105", second))
    gapped = (_rung("0", "6000", "0", "0.095", first), _rung("6500", None, "617.50", "0.105", second))
    closed = (_rung("0", "6000", "0", "0.095", first), _rung("6000", "9000", "570", "0.105", second))
    late = (_rung("100", "6000", "0", "0.095", first), _rung("6000", None, "560.50", "0.105", second))

    assert _scale_defects(continuous) == []
    assert _scale_defects(gapped) == ["rung 0 ends at 6000, next starts 6500"]
    assert _scale_defects(closed) == ["top rung closes at 9000"]
    assert _scale_defects(late) == ["first rung starts at 100 with cuota 0"]
    assert _scale_defects(()) == ["no rung in force"]
