"""Modelo 111 registry behaviour for withholding filings."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority
from cadrumo.domain.calculations.registry.schema import ModeloDefinition
from cadrumo.domain.calculations.registry.schema_catalogues import RegistryCatalogues
from cadrumo.domain.calculations.registry.temporal import select_revision
from cadrumo.domain.calculations.registry.tests.authored_editions import filing_year_envelope, open_ended_revision
from cadrumo.domain.calculations.registry.tests.snapshot_support import build_snapshot
from dev.registry.compiler.authority import compiled_bundled_authority

from ..conformance.registry_schema_support import committed_modelo
from .retencion_deadline_support import (
    RETENCION_PERIODS,
    calendar_is_bundled,
    expected_close,
    expected_cutoff,
)

if TYPE_CHECKING:
    from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_REQUIRED_SURFACES = {
    "approval",
    "calculation",
    "deadline",
    "export",
    "extractor",
    "filing",
    "portal",
    "reconciliation",
    "review",
    "workflow",
}


@pytest.fixture(scope="module")
def modelo_111_registry():
    return committed_modelo("111")


@pytest.mark.parametrize("period", ["1T", "01"])
def test_modelo_111_validated_snapshot_owns_workflow_surfaces(
    modelo_111_registry: tuple[ModeloDefinition, RegistryCatalogues],
    period: str,
) -> None:
    modelo, catalogues = modelo_111_registry
    snapshot = build_snapshot(
        modelo,
        catalogues,
        source_root=bundled_path(),
        filing_year=filing_year_envelope().horizon,
        period=period,
    )

    construct = snapshot.revision.constructs[0]
    linked_by_surface = {
        link.surface: link for link in snapshot.revision.application_links if link.id in construct.application_links
    }
    assert set(linked_by_surface) >= _REQUIRED_SURFACES
    assert all(link.requires_snapshot for link in linked_by_surface.values())


def test_modelo_111_supported_year_deadline_census_dates_sources_and_ownership(
    modelo_111_registry: tuple[ModeloDefinition, RegistryCatalogues],
) -> None:
    with bundled_indexed_authority().operation() as operation:
        _check_supported_year_deadlines(modelo_111_registry, operation)


def _check_supported_year_deadlines(
    modelo_111_registry: tuple[ModeloDefinition, RegistryCatalogues],
    operation: PinnedAuthorityOperation,
) -> None:
    modelo, _ = modelo_111_registry
    revision = modelo.revisions[open_ended_revision("111").id]
    windows = {(window.filing_year, window.period.registry_token): window for window in revision.deadline_windows}

    assert len(revision.deadline_windows) == len(windows) == len(RETENCION_PERIODS) * len(filing_year_envelope().years)
    assert set(revision.constructs[0].deadline_windows) == {window.id for window in revision.deadline_windows}

    for filing_year in filing_year_envelope().years:
        expected_periods = RETENCION_PERIODS
        assert {period for year, period in windows if year == filing_year} == set(expected_periods)
        projected = compiled_bundled_authority().deadline_windows(filing_year, modelos=("111",))
        assert len(projected) == 16
        assert {window.period.registry_token for _, _, window in projected} == set(expected_periods)
        assert {selected.id for _, selected, _ in projected} == {revision.id}

        for period in RETENCION_PERIODS:
            window = windows[(filing_year, period)]
            assert select_revision(modelo, filing_year=filing_year, period=period) is revision
            assert window.id == f"modelo-111-{filing_year}-{period.lower()}"
            assert window.filing_year == window.period.filing_year == filing_year
            assert window.closes_on == expected_close(operation, "111", filing_year, period)
            assert window.payment_cutoff_on == expected_cutoff(filing_year, period)
            expected_sources = {"aeat-modelo-111-instructions"}
            if calendar_is_bundled(window.closes_on.year):
                expected_sources.add(f"aeat-calendario-contribuyente-{window.closes_on.year}")
            assert set(window.source_refs) == expected_sources

    horizon = filing_year_envelope().horizon
    assert windows[(horizon, "12")].payment_cutoff_on is None
    assert windows[(horizon, "4T")].payment_cutoff_on is None
