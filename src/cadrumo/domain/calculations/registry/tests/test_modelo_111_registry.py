"""Modelo 111 registry behaviour for withholding filings."""

from __future__ import annotations

from datetime import date

import pytest

from .....core.resources.bundled_data import bundled_path
from ..authority import bundled_authority
from ..schema import ModeloDefinition, RegistryCatalogues
from ..snapshot import build_snapshot
from ..temporal import select_revision
from ._registry_schema_support import _committed_modelo

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

_MONTHLY_DEADLINES = {
    2022: (
        ("2022-02-21", "2022-02-16"),
        ("2022-03-21", "2022-03-16"),
        ("2022-04-20", "2022-04-15"),
        ("2022-05-20", "2022-05-15"),
        ("2022-06-20", "2022-06-15"),
        ("2022-07-20", "2022-07-15"),
        ("2022-08-22", "2022-08-17"),
        ("2022-09-20", "2022-09-15"),
        ("2022-10-20", "2022-10-15"),
        ("2022-11-21", "2022-11-16"),
        ("2022-12-20", "2022-12-15"),
        ("2023-01-20", "2023-01-15"),
    ),
    2023: (
        ("2023-02-20", "2023-02-15"),
        ("2023-03-20", "2023-03-15"),
        ("2023-04-20", "2023-04-15"),
        ("2023-05-22", "2023-05-17"),
        ("2023-06-20", "2023-06-15"),
        ("2023-07-20", "2023-07-15"),
        ("2023-08-21", "2023-08-16"),
        ("2023-09-20", "2023-09-15"),
        ("2023-10-20", "2023-10-15"),
        ("2023-11-20", "2023-11-15"),
        ("2023-12-20", "2023-12-15"),
        ("2024-01-22", "2024-01-17"),
    ),
    2024: (
        ("2024-02-20", "2024-02-15"),
        ("2024-03-20", "2024-03-15"),
        ("2024-04-22", "2024-04-17"),
        ("2024-05-20", "2024-05-15"),
        ("2024-06-20", "2024-06-17"),
        ("2024-07-22", "2024-07-17"),
        ("2024-08-20", "2024-08-15"),
        ("2024-09-20", "2024-09-17"),
        ("2024-10-21", "2024-10-16"),
        ("2024-11-20", "2024-11-15"),
        ("2024-12-20", "2024-12-17"),
        ("2025-01-20", "2025-01-15"),
    ),
    2025: (
        ("2025-02-20", "2025-02-17"),
        ("2025-03-20", "2025-03-17"),
        ("2025-04-21", "2025-04-15"),
        ("2025-05-20", "2025-05-15"),
        ("2025-06-20", "2025-06-17"),
        ("2025-07-21", "2025-07-16"),
        ("2025-08-20", "2025-08-15"),
        ("2025-09-22", "2025-09-17"),
        ("2025-10-20", "2025-10-15"),
        ("2025-11-20", "2025-11-17"),
        ("2025-12-22", "2025-12-17"),
        ("2026-01-20", "2026-01-15"),
    ),
    2026: (
        ("2026-02-20", "2026-02-17"),
        ("2026-03-20", "2026-03-16"),
        ("2026-04-20", "2026-04-15"),
        ("2026-05-20", "2026-05-15"),
        ("2026-06-22", "2026-06-17"),
        ("2026-07-20", "2026-07-15"),
        ("2026-08-20", "2026-08-17"),
        ("2026-09-21", "2026-09-16"),
        ("2026-10-20", "2026-10-15"),
        ("2026-11-20", "2026-11-17"),
        ("2026-12-21", "2026-12-16"),
        ("2027-01-20", None),
    ),
}

_QUARTERLY_DEADLINES = {
    2022: (
        ("2022-04-20", "2022-04-15"),
        ("2022-07-20", "2022-07-15"),
        ("2022-10-20", "2022-10-15"),
        ("2023-01-20", "2023-01-15"),
    ),
    2023: (
        ("2023-04-20", "2023-04-15"),
        ("2023-07-20", "2023-07-15"),
        ("2023-10-20", "2023-10-15"),
        ("2024-01-22", "2024-01-17"),
    ),
    2024: (
        ("2024-04-22", "2024-04-17"),
        ("2024-07-22", "2024-07-17"),
        ("2024-10-21", "2024-10-16"),
        ("2025-01-20", "2025-01-15"),
    ),
    2025: (
        ("2025-04-21", "2025-04-15"),
        ("2025-07-21", "2025-07-16"),
        ("2025-10-20", "2025-10-15"),
        ("2026-01-20", "2026-01-15"),
    ),
    2026: (
        ("2026-04-20", "2026-04-15"),
        ("2026-07-20", "2026-07-15"),
        ("2026-10-20", "2026-10-15"),
        ("2027-01-20", None),
    ),
}


@pytest.fixture(scope="module")
def modelo_111_registry():
    return _committed_modelo("111")


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
        filing_year=2026,
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
    revision = modelo.revisions["2019-y-siguientes"]
    windows = {(window.filing_year, window.period.registry_token): window for window in revision.deadline_windows}

    assert len(revision.deadline_windows) == len(windows) == 80
    assert set(revision.constructs[0].deadline_windows) == {window.id for window in revision.deadline_windows}

    for filing_year in range(2022, 2027):
        expected_periods = (*tuple(f"{month:02d}" for month in range(1, 13)), "1T", "2T", "3T", "4T")
        assert {period for year, period in windows if year == filing_year} == set(expected_periods)
        projected = bundled_authority().deadline_windows(filing_year, modelos=("111",))
        assert len(projected) == 16
        assert {window.period.registry_token for _, _, window in projected} == set(expected_periods)
        assert {selected.id for _, selected, _ in projected} == {"2019-y-siguientes"}

        expected = {
            **{f"{month:02d}": values for month, values in enumerate(_MONTHLY_DEADLINES[filing_year], start=1)},
            **{f"{quarter}T": values for quarter, values in enumerate(_QUARTERLY_DEADLINES[filing_year], start=1)},
        }
        for period, (close_text, payment_text) in expected.items():
            window = windows[(filing_year, period)]
            assert select_revision(modelo, filing_year=filing_year, period=period) is revision
            assert window.id == f"modelo-111-{filing_year}-{period.lower()}"
            assert window.filing_year == window.period.filing_year == filing_year
            assert window.closes_on == date.fromisoformat(close_text)
            assert window.payment_cutoff_on == (None if payment_text is None else date.fromisoformat(payment_text))
            expected_sources = {"aeat-modelo-111-instructions"}
            if window.closes_on.year <= 2026:
                expected_sources.add(f"aeat-calendario-contribuyente-{window.closes_on.year}")
            assert set(window.source_refs) == expected_sources

    assert windows[(2026, "12")].payment_cutoff_on is None
    assert windows[(2026, "4T")].payment_cutoff_on is None
