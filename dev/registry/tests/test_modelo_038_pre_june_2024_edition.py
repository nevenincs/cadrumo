"""Modelo 038 is filed on AEAT's 2012 design until the June 2024 IRUS amendment.

Orden HAC/646/2024 adds the IRUS field to the tipo 2 record and applies it first to
the June 2024 declaration. Every earlier month in the support envelope is filed on
the 2012 design, which prints every other field of the 2024 design, so the
2022-hasta-2024-05 edition is the modelo's storage baseline and the June 2024
edition keys only its design, deadline windows and export source against it.
"""

from __future__ import annotations

import calendar
import json
from datetime import date
from functools import cache

import pytest

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.schema import ModeloDefinition, ModeloRevision, RegistryCatalogues
from cadrumo.domain.calculations.registry.schema_references import TemporalProjectionDirection
from cadrumo.domain.calculations.registry.temporal import revision_temporal_resolution, select_revision

from ..conformance.registry_schema_support import committed_modelo

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_OLD_DESIGN = "aeat-dr-038-2012"
_NEW_DESIGN = "aeat-dr-038-2024"


@cache
def _modelo() -> tuple[ModeloDefinition, RegistryCatalogues]:
    return committed_modelo("038")


def _months_before_amendment() -> list[tuple[int, str]]:
    """Every (year, month) from the support floor to the 2012 design's last month."""
    _, catalogues = _modelo()
    applies_to = catalogues.sources[_OLD_DESIGN].applies_to
    assert applies_to is not None
    floor = min(catalogues.supported_filing_years.years)
    return [
        (year, f"{month:02d}")
        for year in range(floor, applies_to.year + 1)
        for month in range(1, 13)
        if date(year, month, 1) <= applies_to
    ]


def _selected(year: int, period: str) -> ModeloRevision:
    modelo, catalogues = _modelo()
    return select_revision(modelo, filing_year=year, period=period, support=catalogues.supported_filing_years)


def _corpus_text(source_id: str) -> str:
    _, catalogues = _modelo()
    corpus_path = catalogues.sources[source_id].corpus_path
    assert corpus_path is not None
    sidecar = bundled_path("manual_corpus_text", *corpus_path.removeprefix("corpus/").split("/"))
    sidecar = sidecar.with_name(sidecar.name + ".corpus_text.json")
    return json.loads(sidecar.read_text(encoding="utf-8"))["normalised_text"]


def test_every_month_before_the_amendment_is_authored_on_the_2012_design() -> None:
    _, catalogues = _modelo()
    for year, period in _months_before_amendment():
        revision = _selected(year, period)
        resolution = revision_temporal_resolution(
            revision, filing_year=year, period=period, support=catalogues.supported_filing_years
        )
        assert revision.id == "2022-hasta-2024-05", (year, period)
        assert resolution.projection_direction is TemporalProjectionDirection.AUTHORED
        assert _OLD_DESIGN in revision.source_refs
        assert _NEW_DESIGN not in revision.source_refs
        (export_link,) = [link for link in revision.application_links if link.id == "modelo-038-export"]
        assert export_link.source_refs == (_OLD_DESIGN,)


def test_each_month_carries_its_own_art_6_deadline_window() -> None:
    for year, period in _months_before_amendment():
        revision = _selected(year, period)
        month = int(period)
        next_year, next_month = (year + 1, 1) if month == 12 else (year, month + 1)
        (window,) = [
            window
            for window in revision.deadline_windows
            if window.filing_year == year and window.period.registry_token.endswith(period)
        ]
        assert window.opens_on == date(next_year, next_month, 1)
        assert window.closes_on == date(next_year, next_month, calendar.monthrange(next_year, next_month)[1])
        construct = revision.constructs[0]
        assert window.id in construct.deadline_windows


def test_june_2024_onward_keeps_the_irus_design_and_its_own_windows() -> None:
    _, catalogues = _modelo()
    first = catalogues.sources[_NEW_DESIGN].applies_from
    assert first is not None
    revision = _selected(first.year, f"{first.month:02d}")
    assert revision.id == "2024-desde-06"
    assert _NEW_DESIGN in revision.source_refs
    assert _OLD_DESIGN not in revision.source_refs
    (export_link,) = [link for link in revision.application_links if link.id == "modelo-038-export"]
    assert export_link.source_refs == (_NEW_DESIGN,)
    assert {window.filing_year for window in revision.deadline_windows} == {first.year}
    assert revision.constructs[0].deadline_windows == tuple(
        f"modelo-038-{first.year}-{month:02d}" for month in range(first.month, 13)
    )
    assert [casilla.id for casilla in revision.casillas] == [
        casilla.id for casilla in _selected(first.year, "01").casillas
    ]


def test_the_2012_design_prints_every_2024_field_but_irus() -> None:
    old = _corpus_text(_OLD_DESIGN)
    new = _corpus_text(_NEW_DESIGN)
    assert "identificador registral unico de la sociedad (irus)" in new
    assert "irus" not in old
    for field in ("ejercicio", "dec. complementaria", "dec. sustitutiva", "n.i.f. de la entidad", "clave operacion"):
        assert field in old and field in new
