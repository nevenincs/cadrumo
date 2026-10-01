"""Modelo 182's ejercicios 2022 and 2023 are filed on the design Orden HFP/1351/2021 fixed.

BOE's analysis of Orden EHA/3021/2007 lists no amendment of its anexo II between
Orden HFP/1351/2021 (first applied to the 2021 declarations) and Orden HAC/1504/2024
(first applied to ejercicio 2024). That design prints every field the 2024 one does
at the same position; the only textual difference is the 150 euros the % DE
DEDUCCION description names, which HAC/1504/2024 raises to 250. The 2022-2023
edition therefore states the modelo's payload once, with its own design and
deadline windows, and the 2024 edition stores against it.
"""

from __future__ import annotations

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

_DESIGN = "aeat-dr-182-2021-2023"
_NEXT_DESIGN = "aeat-dr-182-2024"
# Record fields the casillas and donor-row bindings stand for (tipo 1 EJERCICIO,
# tipo 2 NIF, name, % deduccion, importe, recurrencia).
_BOUND_FIELDS = (
    "5-8 numerico ejercicio",
    "18-26 alfanumerico n.i.f. del declarado",
    "36-75 alfanumerico apellidos",
    "79-83 numerico % de deduccion",
    "84-96 numerico importe",
    "132 numerico recurrencia donativos",
)


@cache
def _modelo() -> tuple[ModeloDefinition, RegistryCatalogues]:
    return committed_modelo("182")


def _design_years() -> tuple[int, ...]:
    """The supported ejercicios the 2021-2023 design governs, read from its catalogue window."""
    _, catalogues = _modelo()
    source = catalogues.sources[_DESIGN]
    assert source.applies_from is not None
    assert source.applies_to is not None
    return tuple(
        year
        for year in catalogues.supported_filing_years.years
        if source.applies_from <= date(year, 1, 1) and date(year, 12, 31) <= source.applies_to
    )


def _selected(year: int) -> ModeloRevision:
    modelo, catalogues = _modelo()
    return select_revision(modelo, filing_year=year, period="0A", support=catalogues.supported_filing_years)


def _corpus_text(source_id: str) -> str:
    _, catalogues = _modelo()
    corpus_path = catalogues.sources[source_id].corpus_path
    assert corpus_path is not None
    sidecar = bundled_path("manual_corpus_text", *corpus_path.removeprefix("corpus/").split("/"))
    sidecar = sidecar.with_name(sidecar.name + ".corpus_text.json")
    return json.loads(sidecar.read_text(encoding="utf-8"))["normalised_text"]


def test_each_design_year_is_authored_on_its_own_design() -> None:
    _, catalogues = _modelo()
    years = _design_years()
    assert years, "the 2021-2023 design no longer covers a supported ejercicio"
    for year in years:
        revision = _selected(year)
        resolution = revision_temporal_resolution(
            revision, filing_year=year, period="0A", support=catalogues.supported_filing_years
        )
        assert revision.id == "2022-2023"
        assert resolution.projection_direction is TemporalProjectionDirection.AUTHORED
        assert _DESIGN in revision.source_refs
        assert _NEXT_DESIGN not in revision.source_refs
        assert "orden-hfp-1351-2021:df-unica" in revision.legal_refs
        (window,) = [window for window in revision.deadline_windows if window.filing_year == year]
        assert (window.opens_on, window.closes_on) == (date(year + 1, 1, 1), date(year + 1, 1, 31))


def test_the_design_years_state_the_members_2024_states() -> None:
    later = _selected(max(_design_years()) + 1)
    assert later.id == "2024"
    for year in _design_years():
        revision = _selected(year)
        assert [(c.id, c.number, c.data_type) for c in revision.casillas] == [
            (c.id, c.number, c.data_type) for c in later.casillas
        ]
        assert [binding.id for binding in revision.bindings] == [binding.id for binding in later.bindings]
        assert revision.constructs[0].bindings == later.constructs[0].bindings
    assert _NEXT_DESIGN in later.source_refs
    assert _DESIGN not in later.source_refs
    assert {window.filing_year for window in later.deadline_windows} == {later.valid_from.year}


def test_the_design_prints_every_bound_field_where_2024_does() -> None:
    design = _corpus_text(_DESIGN)
    later = _corpus_text(_NEXT_DESIGN)
    for field in _BOUND_FIELDS:
        assert field in design and field in later, field
    assert "150 euros" in design and "250 euros" not in design
    assert "250 euros" in later
