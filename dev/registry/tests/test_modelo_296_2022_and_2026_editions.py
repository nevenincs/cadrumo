"""Modelo 296 editions at the two ends of the envelope follow their own record layouts.

2022 is governed by Anexo III of Orden EHA/3290/2008 as Orden HFP/1351/2021 left it,
before Orden HFP/1284/2023 added the identificador field at 77-84 and the Anexo de
desglose; 2026 by the redaction Orden HAC/623/2026 made. AEAT publishes a diseno de
registro for neither year, so both editions claim applicability only and carry no
generated export, while 2024 and 2025 keep the filing-grade edition of their design.
"""

from __future__ import annotations

from functools import cache

import pytest

from cadrumo.core.authority_grade import RegistryAuthorityGrade
from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.modelo_inception import UnauthoredBefore
from cadrumo.domain.calculations.registry.schema import ModeloDefinition, ModeloRevision, RegistryCatalogues
from cadrumo.domain.calculations.registry.schema_references import TemporalProjectionDirection
from cadrumo.domain.calculations.registry.temporal import revision_temporal_resolution, select_revision

from ..compiler.authority import compiled_bundled_authority
from ..conformance.registry_schema_support import committed_modelo

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_LAYOUT_2022 = "boe-modelo-296-2021-2022-layout"
_LAYOUT_2026 = "boe-modelo-296-2026-layout"
_IDENTIFIER = "IDENTIFICADOR DE REGISTRO"
_NEW_2026_FIELD = "CLAVE DE PERSONALIDAD DEL TITULAR REGISTRAL"


@cache
def _modelo() -> tuple[ModeloDefinition, RegistryCatalogues]:
    return committed_modelo("296")


def _selected(year: int) -> ModeloRevision:
    modelo, catalogues = _modelo()
    return select_revision(modelo, filing_year=year, period="0A", support=catalogues.supported_filing_years)


def _source_text(source_ref: str) -> str:
    _, catalogues = _modelo()
    return bundled_path(*catalogues.sources[source_ref].corpus_path.split("/")).read_text(encoding="utf-8")


def _window_years(source_ref: str) -> tuple[int, int | None]:
    _, catalogues = _modelo()
    source = catalogues.sources[source_ref]
    assert source.applies_from is not None
    return source.applies_from.year, None if source.applies_to is None else source.applies_to.year


def _assert_applicability_without_export(revision: ModeloRevision, layout: str) -> None:
    assert revision.authority_grade is RegistryAuthorityGrade.APPLICABILITY
    assert revision.export_layouts == ()
    assert revision.projection_endpoints == ()
    assert "modelo-296-export" not in {str(link.id) for link in revision.application_links}
    assert layout in revision.source_refs
    assert revision.completeness_manifest is not None
    assert str(revision.completeness_manifest.source_ref) == layout


def test_the_2022_layout_predates_the_identifier_and_the_desglose_annex() -> None:
    _, last = _window_years(_LAYOUT_2022)
    assert last is not None
    text = _source_text(_LAYOUT_2022)
    assert "77-90" in text
    assert _IDENTIFIER not in text
    assert "Anexo de desglose" not in text

    revision = _selected(last)
    _, catalogues = _modelo()
    resolution = revision_temporal_resolution(
        revision, filing_year=last, period="0A", support=catalogues.supported_filing_years
    )
    assert resolution.projection_direction is TemporalProjectionDirection.AUTHORED
    _assert_applicability_without_export(revision, _LAYOUT_2022)
    assert _selected(last + 1).export_layouts, "the following year keeps its generated export"


def test_the_2026_layout_adds_the_titular_registral_field() -> None:
    first, _ = _window_years(_LAYOUT_2026)
    assert _NEW_2026_FIELD in _source_text(_LAYOUT_2026)

    revision = _selected(first)
    _assert_applicability_without_export(revision, _LAYOUT_2026)
    previous = _selected(first - 1)
    assert previous.authority_grade is RegistryAuthorityGrade.FILING
    assert previous.export_layouts
    assert previous.id == _selected(first - 2).id, "2024 and 2025 share one filing-grade edition"
    assert previous.valid_to is not None and previous.valid_to.year == first - 1


def test_each_year_window_sits_in_the_edition_that_governs_it() -> None:
    modelo, catalogues = _modelo()
    support = catalogues.supported_filing_years
    assert support is not None
    for year in support.years:
        revision = _selected(year)
        assert year in {window.filing_year for window in revision.deadline_windows}, (year, revision.id)
    for revision in modelo.revisions.values():
        for window in revision.deadline_windows:
            assert revision.period_selector.includes_year(window.filing_year), (revision.id, window.id)


def test_every_supported_year_snapshots_at_its_edition_grade() -> None:
    _, catalogues = _modelo()
    support = catalogues.supported_filing_years
    assert support is not None
    authority = compiled_bundled_authority()
    for year in support.years:
        revision = _selected(year)
        assert revision.authority_grade is not None, f"selected edition for {year} has no declared authority grade"
        snapshot = authority.snapshot("296", filing_year=year, period="0A", grade=revision.authority_grade)
        assert snapshot.revision.id == revision.id, year


def test_the_earliest_authored_statement_matches_the_editions() -> None:
    modelo, catalogues = _modelo()
    support = catalogues.supported_filing_years
    assert support is not None
    assert isinstance(modelo.inception, UnauthoredBefore), "Modelo 296 declares earlier years as unauthored"
    first_authored = min(
        year
        for year in support.years
        if revision_temporal_resolution(
            _selected(year), filing_year=year, period="0A", support=support
        ).projection_direction
        is TemporalProjectionDirection.AUTHORED
    )
    assert modelo.inception.earliest_authored == first_authored
