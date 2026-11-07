"""Modelo 111 registry behaviour for withholding filings."""

from __future__ import annotations

from datetime import date

import pytest

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.schema import ModeloDefinition
from cadrumo.domain.calculations.registry.schema_catalogues import RegistryCatalogues
from cadrumo.domain.calculations.registry.temporal import select_revision
from cadrumo.domain.calculations.registry.tests.authored_editions import filing_year_envelope, open_ended_revision
from cadrumo.domain.calculations.registry.tests.snapshot_support import build_snapshot
from dev.registry.compiler.authority import compiled_bundled_authority

from ..conformance.registry_schema_support import committed_modelo
from .monthly_deadline_support import MONTHLY_RETENCION_DEADLINES
from .quarterly_deadline_support import QUARTERLY_RETENCION_DEADLINES

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_OPEN_ENDED_REVISION = str(open_ended_revision("111").id)

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
    modelo, _ = modelo_111_registry
    revision = modelo.revisions[_OPEN_ENDED_REVISION]
    horizon = filing_year_envelope().horizon
    windows = {(window.filing_year, window.period.registry_token): window for window in revision.deadline_windows}

    assert len(revision.deadline_windows) == len(windows) == 80
    assert set(revision.constructs[0].deadline_windows) == {window.id for window in revision.deadline_windows}

    for filing_year in filing_year_envelope().years:
        expected_periods = (*tuple(f"{month:02d}" for month in range(1, 13)), "1T", "2T", "3T", "4T")
        assert {period for year, period in windows if year == filing_year} == set(expected_periods)
        projected = compiled_bundled_authority().deadline_windows(filing_year, modelos=("111",))
        assert len(projected) == 16
        assert {window.period.registry_token for _, _, window in projected} == set(expected_periods)
        assert {selected.id for _, selected, _ in projected} == {_OPEN_ENDED_REVISION}

        expected = {
            **{
                f"{month:02d}": values for month, values in enumerate(MONTHLY_RETENCION_DEADLINES[filing_year], start=1)
            },
            **{
                f"{quarter}T": values
                for quarter, values in enumerate(QUARTERLY_RETENCION_DEADLINES[filing_year], start=1)
            },
        }
        for period, (close_text, payment_text) in expected.items():
            window = windows[(filing_year, period)]
            assert select_revision(modelo, filing_year=filing_year, period=period) is revision
            assert window.id == f"modelo-111-{filing_year}-{period.lower()}"
            assert window.filing_year == window.period.filing_year == filing_year
            assert window.closes_on == date.fromisoformat(close_text)
            assert window.payment_cutoff_on == (None if payment_text is None else date.fromisoformat(payment_text))
            expected_sources = {"aeat-modelo-111-instructions"}
            if window.closes_on.year <= horizon:
                expected_sources.add(f"aeat-calendario-contribuyente-{window.closes_on.year}")
            assert set(window.source_refs) == expected_sources

    assert windows[(horizon, "12")].payment_cutoff_on is None
    assert windows[(horizon, "4T")].payment_cutoff_on is None
