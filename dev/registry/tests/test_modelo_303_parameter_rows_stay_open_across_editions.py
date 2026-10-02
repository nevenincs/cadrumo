"""Modelo 303 statutory figures are one open row, inherited by every later edition.

The simplified regime's one-percent deduction for cuotas of difficult
justification is restated verbatim by every annual modulos Orden, and the
capital-goods regularisation threshold of ten points is LIVA art. 107.Uno. Each
later edition only refreshes the evidence that cites the figure, so each supported
year resolves the figure from the single row the first edition stated. The
deduction row closes only where the newest annual Orden held stops applying.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from functools import cache

import pytest

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.schema import ModeloDefinition, ModeloRevision
from cadrumo.domain.calculations.registry.schema_base import DateAxis
from cadrumo.domain.calculations.registry.schema_formula import DatedValue, ParameterDefinition
from cadrumo.domain.calculations.registry.temporal import select_revision_for_year

from ..compiler.loader import load_modelo_directory, load_shared_catalogues

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_FORFAIT = "m303-modulos-iva-dificil-justificacion-forfait"
_UMBRAL = "m303-bien-inversion-regularizacion-umbral-puntos"
_EXPECTED = {_FORFAIT: Decimal("1"), _UMBRAL: Decimal("10")}


@cache
def _modelo() -> ModeloDefinition:
    return load_modelo_directory(bundled_path("registry", "aeat", "modelos", "303"))


@cache
def _supported_years() -> tuple[int, ...]:
    return tuple(load_shared_catalogues(bundled_path("registry", "aeat")).require_supported_filing_years().years)


def _edition_for(on: date) -> ModeloRevision:
    support = load_shared_catalogues(bundled_path("registry", "aeat")).require_supported_filing_years()
    return select_revision_for_year(_modelo(), filing_year=on.year, on=on, support=support)


def _parameter(revision: ModeloRevision, parameter_id: str) -> ParameterDefinition:
    return next(parameter for parameter in revision.parameters if parameter.id == parameter_id)


def _in_force(parameter: ParameterDefinition, on: date) -> tuple[DatedValue, ...]:
    return tuple(
        row
        for row in parameter.values
        if row.date_axis is DateAxis.FILING_PERIOD
        and row.valid_from <= on
        and (row.valid_to is None or on <= row.valid_to)
    )


def _quarter_starts(year: int) -> tuple[date, ...]:
    return tuple(date(year, month, 1) for month in (1, 4, 7, 10))


@cache
def _first_edition() -> ModeloRevision:
    return min(_modelo().revisions.values(), key=lambda revision: (revision.valid_from, str(revision.id)))


@pytest.mark.parametrize("parameter_id", sorted(_EXPECTED))
def test_every_supported_quarter_resolves_the_figure_from_the_first_editions_row(parameter_id: str) -> None:
    """Each supported quarter sees exactly one row, stated by the first edition and keyed from its first day."""
    first_day = _first_edition().valid_from
    seen: dict[date, tuple[tuple[Decimal, date], ...]] = {}
    for year in _supported_years():
        for on in _quarter_starts(year):
            rows = _in_force(_parameter(_edition_for(on), parameter_id), on)
            seen[on] = tuple((row.value, row.valid_from) for row in rows)

    assert seen, "no supported quarter was read"
    assert {on: rows for on, rows in seen.items() if rows != ((_EXPECTED[parameter_id], first_day),)} == {}


def test_the_threshold_row_never_closes() -> None:
    """LIVA art. 107.Uno sets the ten points without a period, so no edition closes the row."""
    closed = {
        str(revision.id): [row.valid_to for row in _parameter(revision, _UMBRAL).values if row.valid_to is not None]
        for revision in _modelo().revisions.values()
    }

    assert {revision_id: ends for revision_id, ends in closed.items() if ends} == {}


def test_the_deduction_row_closes_only_where_the_newest_annual_orden_stops_applying() -> None:
    """Every edition but the newest inherits the open row; the newest closes it where its cited Orden stops."""
    editions = sorted(_modelo().revisions.values(), key=lambda revision: (revision.valid_from, str(revision.id)))
    newest = editions[-1]
    ends = {str(revision.id): {row.valid_to for row in _parameter(revision, _FORFAIT).values} for revision in editions}
    sources = load_shared_catalogues(bundled_path("registry", "aeat")).sources
    orden_ends = {sources[source_id].applies_to for source_id in _parameter(newest, _FORFAIT).source_refs}

    assert {
        revision_id: end for revision_id, end in ends.items() if revision_id != str(newest.id) and end != {None}
    } == {}
    assert None not in orden_ends
    assert ends[str(newest.id)] == orden_ends
