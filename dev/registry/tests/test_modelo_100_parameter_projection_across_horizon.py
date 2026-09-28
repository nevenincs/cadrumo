"""Modelo 100 parameter rows stay in force across projected years and never outlive their edition.

A year the registry authors no edition for is served by the nearest edition
through temporal projection. That only works when a parameter row the law
leaves unchanged stays open: a row that closes at its edition's own year end
drops the value from every projected year and fails the filing. A row may
still close on a genuine legal end, but then a later row carries on or the
parameter has no value to project, and the rows in force at the newest
edition's last day are exactly the rows the projected years must see.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date
from functools import cache

import pytest

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.schema import ModeloRevision
from cadrumo.domain.calculations.registry.schema_base import DateAxis
from cadrumo.domain.calculations.registry.schema_formula import (
    BracketEntry,
    DatedValue,
    KeyedBracketEntry,
    ParameterDefinition,
)

from ..compiler.loader import load_modelo_directory, load_shared_catalogues

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_Row = DatedValue | BracketEntry | KeyedBracketEntry


@cache
def _newest_edition() -> ModeloRevision:
    modelo = load_modelo_directory(bundled_path("registry", "aeat", "modelos", "100"))
    return max(modelo.revisions.values(), key=lambda revision: (revision.valid_from, str(revision.id)))


@cache
def _projected_years() -> tuple[int, ...]:
    support = load_shared_catalogues(bundled_path("registry", "aeat")).supported_filing_years
    assert support is not None, "the registry declares no supported filing years"
    newest = _newest_edition()
    return tuple(year for year in support.years if year > newest.valid_from.year)


def _filing_period_rows(parameter: ParameterDefinition) -> Iterable[_Row]:
    yield from (row for row in parameter.values if row.date_axis is DateAxis.FILING_PERIOD)
    yield from parameter.brackets
    yield from parameter.keyed_brackets


def _in_force(parameter: ParameterDefinition, on: date) -> tuple[_Row, ...]:
    return tuple(
        row
        for row in _filing_period_rows(parameter)
        if row.valid_from <= on and (row.valid_to is None or row.valid_to >= on)
    )


def _years_losing_rows(parameter: ParameterDefinition, *, edition_end: date, years: Iterable[int]) -> tuple[int, ...]:
    """Projected years whose year end sees fewer of the rows in force when the edition ends."""
    last = set(_in_force(parameter, edition_end))
    return tuple(year for year in years if not last <= set(_in_force(parameter, date(year, 12, 31))))


def _rows_closed_before(parameter: ParameterDefinition, edition_start: date) -> tuple[_Row, ...]:
    """Rows an edition states whose window ended before the edition begins."""
    return tuple(
        row for row in _filing_period_rows(parameter) if row.valid_to is not None and row.valid_to < edition_start
    )


@cache
def _editions() -> tuple[ModeloRevision, ...]:
    modelo = load_modelo_directory(bundled_path("registry", "aeat", "modelos", "100"))
    return tuple(sorted(modelo.revisions.values(), key=lambda revision: (revision.valid_from, str(revision.id))))


def test_the_envelope_projects_past_the_newest_edition() -> None:
    assert _projected_years(), "no supported year lies beyond the newest authored Modelo 100 edition"


def test_every_parameter_in_force_at_the_newest_edition_end_reaches_every_projected_year() -> None:
    newest = _newest_edition()
    edition_end = newest.valid_to or date(newest.valid_from.year, 12, 31)
    lost = {
        parameter.id: years
        for parameter in newest.parameters
        if (years := _years_losing_rows(parameter, edition_end=edition_end, years=_projected_years()))
    }
    assert lost == {}, lost


def test_no_edition_states_a_row_that_closed_before_it_begins() -> None:
    """An edition carries the rows in force for it; a closed row belongs only to the editions it covered.

    Consumers read a table's rows as the table (its brackets, its top rung), so a
    stale row left in a later edition reads as part of that edition's law even
    though a dated lookup would skip it.
    """
    stale = {
        (str(revision.id), parameter.id): len(rows)
        for revision in _editions()
        for parameter in revision.parameters
        if (rows := _rows_closed_before(parameter, revision.valid_from))
    }
    assert stale == {}, stale


def test_a_row_closed_at_its_edition_end_is_detected() -> None:
    edition_year = _newest_edition().valid_from.year
    closed = ParameterDefinition.model_validate(
        {
            "id": "renta-detector-parameter",
            "data_type": "money",
            "unit": "EUR",
            "legal_refs": ("ley-35-2006:art-81",),
            "source_refs": ("aeat-renta-manual-parte1",),
            "values": (
                {
                    "value": "100",
                    "date_axis": "filing_period",
                    "valid_from": date(edition_year, 1, 1),
                    "valid_to": date(edition_year, 12, 31),
                },
            ),
        },
    )
    opened = closed.model_copy(update={"values": (closed.values[0].model_copy(update={"valid_to": None}),)})
    years = (edition_year + 1,)
    edition_end = date(edition_year, 12, 31)

    assert _years_losing_rows(closed, edition_end=edition_end, years=years) == years
    assert _years_losing_rows(opened, edition_end=edition_end, years=years) == ()
    later_edition_start = date(edition_year + 1, 1, 1)
    assert _rows_closed_before(closed, later_edition_start) == closed.values
    assert _rows_closed_before(opened, later_edition_start) == ()
