"""Modelo 100 escala rows the law leaves unchanged stay keyed from their first day.

When a reform changes only some tranches of a progressive scale, the later
edition closes and replaces only those tranches; the untouched ones stay the open
rows of the edition that first stated them. The in-force table of a year then
mixes rows keyed from different first days, so two properties must hold of it as
a whole rather than per window:

- it is still one progressive scale: contiguous from zero to an open top rung,
  each rung's accumulated cuota equal to what the rungs beneath it accumulate;
- no row in it is a numerically unchanged restatement of a row its predecessor
  edition left open, whatever decimal representation the restatement uses.
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

#: Official scales print the accumulated cuota rounded to cents; see the
#: registry-wide accumulated-cuota gate for why a two-cent band is not a budget.
_TOLERANCE = Decimal("0.02")

#: Murcia's 2022 top rung is enacted discontinuous (Decreto-ley 4/2022); the
#: registry-wide accumulated-cuota gate pins it to the bundled manual.
_ENACTED_DISCONTINUITY = frozenset({("renta-escala-autonomica-murcia-base-general", 2022)})


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


def _numeric(row: BracketEntry) -> tuple[Decimal | None, ...]:
    bounds = (row.lower_bound, row.upper_bound, row.fixed_addition, row.marginal_rate)
    return tuple(None if value is None else value.normalize() for value in bounds)


def _scale_defects(rows: tuple[BracketEntry, ...]) -> list[str]:
    """Report every break in one in-force table read as a single progressive scale."""
    if not rows:
        return ["no rung in force"]
    defects: list[str] = []
    if rows[0].lower_bound != 0 or rows[0].fixed_addition != 0:
        defects.append(f"first rung starts at {rows[0].lower_bound} with cuota {rows[0].fixed_addition}")
    if rows[-1].upper_bound is not None:
        defects.append(f"top rung closes at {rows[-1].upper_bound}")
    for lower, upper in pairwise(rows):
        if lower.upper_bound != upper.lower_bound:
            defects.append(f"rung {lower.lower_bound} ends at {lower.upper_bound}, next starts {upper.lower_bound}")
        accumulated = lower.fixed_addition + lower.marginal_rate * (upper.lower_bound - lower.lower_bound)
        if abs(accumulated - upper.fixed_addition) > _TOLERANCE:
            defects.append(f"rung {upper.lower_bound} carries {upper.fixed_addition}, rungs beneath give {accumulated}")
    return defects


def _rekeyed_rows(earlier: ModeloRevision, later: ModeloRevision) -> dict[str, list[str]]:
    """Rows in force when ``later`` starts that numerically repeat an open row of ``earlier`` from another day."""
    following = {parameter.id: parameter for parameter in _scales(later)}
    found: dict[str, list[str]] = {}
    for parameter in _scales(earlier):
        successor = following.get(parameter.id)
        if successor is None:
            continue
        first_days: dict[tuple[Decimal | None, ...], set[date]] = {}
        for row in _in_force(parameter, later.valid_from):
            first_days.setdefault(_numeric(row), set()).add(row.valid_from)
        hits = [
            f"{row.lower_bound}..{row.upper_bound} from {row.valid_from}"
            for row in _in_force(successor, later.valid_from)
            if _numeric(row) in first_days and row.valid_from not in first_days[_numeric(row)]
        ]
        if hits:
            found[parameter.id] = hits
    return found


def _editions() -> list[ModeloRevision]:
    return sorted(_modelo().revisions.values(), key=lambda revision: (revision.valid_from, str(revision.id)))


def test_every_supported_year_reads_each_scale_as_one_progressive_table() -> None:
    """Rows keyed from different first days still form one continuous scale in every supported year."""
    defects: dict[tuple[str, int], list[str]] = {}
    split_tables: set[tuple[str, int]] = set()
    for year in _supported_years():
        for parameter in _scales(_edition_for(year)):
            for on in (date(year, 1, 1), date(year, 12, 31)):
                rows = _in_force(parameter, on)
                if len({row.valid_from for row in rows}) > 1:
                    split_tables.add((parameter.id, year))
                if (parameter.id, year) not in _ENACTED_DISCONTINUITY and (found := _scale_defects(rows)):
                    defects[parameter.id, year] = found

    assert split_tables, "no supported year reads a scale whose unchanged rungs kept their first day"
    assert defects == {}, defects


def test_no_edition_rekeys_a_numerically_unchanged_rung() -> None:
    """A rung the law left unchanged is inherited, not restated from the later edition's first day."""
    rekeyed = {
        (str(earlier.id), str(later.id)): found
        for earlier, later in pairwise(_editions())
        if (found := _rekeyed_rows(earlier, later))
    }

    assert rekeyed == {}, rekeyed


def _synthetic(*rows: BracketEntry) -> ParameterDefinition:
    return ParameterDefinition(
        id="renta-escala-detector",
        data_type="bracket_table",
        unit="EUR",
        bracket_axis="filing_period",
        legal_refs=("ley-35-2006:art-63",),
        source_refs=("aeat-renta-2024-manual-parte1",),
        brackets=rows,
    )


def _rung(lower: str, upper: str | None, fixed: str, rate: str, valid_from: date) -> BracketEntry:
    return BracketEntry(
        lower_bound=Decimal(lower),
        upper_bound=None if upper is None else Decimal(upper),
        fixed_addition=Decimal(fixed),
        marginal_rate=Decimal(rate),
        valid_from=valid_from,
    )


def test_a_rung_restated_in_another_representation_is_detected() -> None:
    """Writing 12450.00 for 12450 does not hide a re-keyed rung; a changed rate is not reported."""
    earlier, later = _editions()[-2:]
    start = earlier.valid_from
    inherited = (_rung("0", "12450", "0", "0.095", start), _rung("12450", None, "1182.75", "0.12", start))
    predecessor = earlier.model_copy(update={"parameters": (_synthetic(*inherited),)})
    rekeyed = later.model_copy(
        update={
            "parameters": (
                _synthetic(
                    _rung("0", "12450.00", "0.00", "0.0950", later.valid_from),
                    _rung("12450.00", None, "1182.75", "0.13", later.valid_from),
                ),
            )
        }
    )
    kept = later.model_copy(
        update={"parameters": (_synthetic(inherited[0], _rung("12450", None, "1182.75", "0.13", later.valid_from)),)}
    )

    assert _rekeyed_rows(predecessor, rekeyed) == {"renta-escala-detector": [f"0..12450.00 from {later.valid_from}"]}
    assert _rekeyed_rows(predecessor, kept) == {}


def test_a_scale_split_across_windows_with_a_broken_seam_is_detected() -> None:
    """The whole-table read catches a seam between rungs keyed from different days."""
    first = date(2020, 1, 1)
    second = first + timedelta(days=366)
    continuous = (_rung("0", "6000", "0", "0.095", first), _rung("6000", None, "570", "0.105", second))
    broken = (_rung("0", "6000", "0", "0.095", first), _rung("6000", None, "575", "0.105", second))
    gapped = (_rung("0", "6000", "0", "0.095", first), _rung("6500", None, "617.50", "0.105", second))

    assert _scale_defects(continuous) == []
    assert len(_scale_defects(broken)) == 1
    assert len(_scale_defects(gapped)) == 1
