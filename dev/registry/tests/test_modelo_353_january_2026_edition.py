"""Modelo 353's January 2026 autoliquidacion belongs to the design that preceded the 2026 one.

Orden HAC/27/2026 applies its new modelo 353 for the first time to the
autoliquidacion of February 2026, so January of that year is still filed on the
earlier design. The registry states that month as an authored coordinate of the
earlier edition, with its own presentation window, rather than carrying the
earlier edition forward from 2025 and shifting January 2026's dates back a year.
"""

from __future__ import annotations

import re
from datetime import date
from functools import cache
from html import unescape

import pytest

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.errors import AmbiguousRevisionSelectionError
from cadrumo.domain.calculations.registry.schema import ModeloDefinition, RegistryCatalogues
from cadrumo.domain.calculations.registry.schema_references import TemporalProjectionDirection
from cadrumo.domain.calculations.registry.temporal import (
    revision_temporal_resolution,
    select_revision,
    select_revision_for_year,
)

from ..conformance.registry_schema_support import committed_modelo
from .authored_edition_support import legal_text_match

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_OUTGOING = "2021-hasta-2026-01"
_INCOMING = "2026-desde-02"
_MONTHS = {"enero": 1, "febrero": 2, "marzo": 3}
_JANUARY = "01"


@cache
def _modelo() -> tuple[ModeloDefinition, RegistryCatalogues]:
    return committed_modelo("353")


@cache
def _transition_year() -> int:
    """The year whose February first carries the new design, read from the Orden itself."""
    return int(legal_text_match("orden-hac-27-2026:disposicion-final-unica", r"al mes de febrero de (\d{4})").group(1))


@cache
def _calendar_dates() -> tuple[date, date, date]:
    """Opening, closing and domiciliation dates AEAT publishes for that January's 353."""
    raw = (
        bundled_path("corpus", "aeat_official", "calendars", "files")
        / "calendario-contribuyente-2026-domiciliacion.html"
    ).read_text(encoding="utf-8")
    text = " ".join(unescape(re.sub(r"<[^>]+>", " ", raw)).split())
    section = text[text.index("Modelos 303 y 353") :]
    year = _transition_year()
    short = f"1M {year % 100:02d}"
    presentation = re.search(rf"{short}: 1 de (\w+) al (\d+) de (\w+)", section)
    domiciliation = re.search(rf"{short}: 1 al (\d+) de (\w+)", section)
    assert presentation is not None and domiciliation is not None
    opens = date(year, _MONTHS[presentation.group(1)], 1)
    closes = date(year, _MONTHS[presentation.group(3)], int(presentation.group(2)))
    cutoff = date(year, _MONTHS[domiciliation.group(2)], int(domiciliation.group(1)))
    return opens, closes, cutoff


def test_january_of_the_transition_year_is_authored_on_the_outgoing_design() -> None:
    modelo, catalogues = _modelo()
    support = catalogues.supported_filing_years
    year = _transition_year()

    revision = select_revision(modelo, filing_year=year, period="01", support=support)
    resolution = revision_temporal_resolution(revision, filing_year=year, period="01", support=support)

    assert revision.id == _OUTGOING
    assert resolution.projection_direction is TemporalProjectionDirection.AUTHORED
    assert revision.valid_to == date(year, 1, 31)
    assert select_revision(modelo, filing_year=year, period="02", support=support).id == _INCOMING


def test_the_outgoing_design_still_serves_every_earlier_supported_month() -> None:
    modelo, catalogues = _modelo()
    support = catalogues.supported_filing_years
    assert support is not None
    for year in range(support.floor, _transition_year()):
        for month in range(1, 13):
            assert select_revision(modelo, filing_year=year, period=f"{month:02d}", support=support).id == _OUTGOING


def test_the_january_window_carries_the_calendar_dates_and_admits_its_last_day() -> None:
    modelo, catalogues = _modelo()
    support = catalogues.supported_filing_years
    year = _transition_year()
    opens, closes, cutoff = _calendar_dates()

    (window,) = (
        window
        for window in modelo.revisions[_OUTGOING].deadline_windows
        if window.filing_year == year and str(window.period.code) == _JANUARY
    )
    assert (window.opens_on, window.closes_on, window.payment_cutoff_on) == (opens, closes, cutoff)
    assert not any(
        window.filing_year == year
        for window in modelo.revisions[_INCOMING].deadline_windows
        if str(window.period.code) == _JANUARY
    )
    # The last legal day falls in March of the transition year; a window carried
    # forward from the previous year would have refused it.
    assert select_revision(modelo, filing_year=year, period="01", on=closes, support=support).id == _OUTGOING


def test_a_year_only_question_about_the_transition_year_is_refused() -> None:
    modelo, catalogues = _modelo()
    with pytest.raises(AmbiguousRevisionSelectionError):
        select_revision_for_year(modelo, filing_year=_transition_year(), support=catalogues.supported_filing_years)


def test_the_outgoing_design_source_reaches_january_of_the_transition_year() -> None:
    _, catalogues = _modelo()
    design = catalogues.sources["aeat-dr-353-2021-2025"]
    successor = catalogues.sources["aeat-dr-353-2026"]
    year = _transition_year()
    assert design.applies_to == date(year, 1, 31)
    assert successor.applies_from == date(year, 2, 1)
