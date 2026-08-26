"""Modelo 115 registry behaviour for quarterly rental withholding filings."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from cadrumo.domain.calculations.registry.authority import bundled_authority
from cadrumo.domain.calculations.registry.bindings import resolve_available_bound_inputs_by_casilla_id
from cadrumo.domain.calculations.registry.schema_input_kind import InputKind
from cadrumo.domain.calculations.registry.snapshot import build_snapshot
from cadrumo.domain.calculations.registry.validate import RegistryValidator

from .....core.resources import bundled_path
from ..formula_runtime import calculate_registry_snapshot
from ..temporal import select_revision
from ._registry_schema_support import _committed_modelo

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_SUPPORTED_DEADLINES = {
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


def test_modelo_115_validated_snapshot_owns_workflow_surfaces() -> None:
    modelo, catalogues = _committed_modelo("115")

    RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(modelo)
    snapshot = build_snapshot(
        modelo,
        catalogues,
        source_root=bundled_path(),
        filing_year=2026,
        period="1T",
    )

    assert snapshot.revision.orden_aplicabilidad == ("orden-2000-11-20:apartado-primero",)
    construct = snapshot.revision.constructs[0]
    linked_by_surface = {
        link.surface: link for link in snapshot.revision.application_links if link.id in construct.application_links
    }
    assert {
        "calculation",
        "filing",
        "export",
        "review",
        "approval",
        "reconciliation",
        "extractor",
        "portal",
        "deadline",
        "workflow",
    } <= set(linked_by_surface)
    assert all(link.requires_snapshot for link in linked_by_surface.values())


def test_modelo_115_binds_retenciones_aggregation_and_calculates_rent_withholding() -> None:
    """M115 count/base come from retenciones aggregation; retención remains the registry formula."""

    modelo, catalogues = _committed_modelo("115")
    snapshot = build_snapshot(
        modelo,
        catalogues,
        source_root=bundled_path(),
        filing_year=2026,
        period="1T",
    )
    casillas = {casilla.id: casilla for casilla in snapshot.revision.casillas}
    bindings = {binding.id: binding for binding in snapshot.revision.bindings}

    assert casillas["01"].input_kind is InputKind.BOUND
    assert casillas["01"].binding == "modelo-115-perceptores"
    assert bindings["modelo-115-perceptores"].source == "retenciones_aggregation"
    assert casillas["02"].input_kind is InputKind.BOUND
    assert casillas["02"].binding == "modelo-115-base-retenciones"
    assert bindings["modelo-115-base-retenciones"].source == "retenciones_aggregation"

    binding_values = {
        "modelo-115-perceptores": Decimal("1"),
        "modelo-115-base-retenciones": Decimal("2700.00"),
    }
    inputs = {
        **resolve_available_bound_inputs_by_casilla_id(snapshot.revision, binding_values),
        "04": Decimal("0"),
    }
    result = calculate_registry_snapshot(
        snapshot,
        inputs=inputs,
        date_context={"filing_period": date(2026, 3, 31)},
        binding_values=binding_values,
    )

    assert result.values["01"] == Decimal("1")
    assert result.values["02"] == Decimal("2700.00")
    assert result.values["03"] == Decimal("513.00")
    assert result.values["05"] == Decimal("513.00")


def test_modelo_115_supported_year_deadline_census_dates_sources_and_ownership() -> None:
    modelo, _ = _committed_modelo("115")
    revision = modelo.revisions["2019-y-siguientes"]
    windows = {(window.filing_year, window.period.registry_token): window for window in revision.deadline_windows}

    assert len(revision.deadline_windows) == len(windows) == 20
    assert set(revision.constructs[0].deadline_windows) == {window.id for window in revision.deadline_windows}

    for filing_year, expected_year in _SUPPORTED_DEADLINES.items():
        expected_periods = {"1T", "2T", "3T", "4T"}
        assert {period for year, period in windows if year == filing_year} == expected_periods
        projected = bundled_authority().deadline_windows(filing_year, modelos=("115",))
        assert len(projected) == 4
        assert {window.period.registry_token for _, _, window in projected} == expected_periods
        assert {selected.id for _, selected, _ in projected} == {"2019-y-siguientes"}

        for quarter, (close_text, payment_text) in enumerate(expected_year, start=1):
            period = f"{quarter}T"
            window = windows[(filing_year, period)]
            assert select_revision(modelo, filing_year=filing_year, period=period) is revision
            assert window.id == f"modelo-115-{filing_year}-{period.lower()}"
            assert window.filing_year == window.period.filing_year == filing_year
            assert window.opens_on == date(window.closes_on.year, window.closes_on.month, 1)
            assert window.closes_on == date.fromisoformat(close_text)
            assert window.payment_cutoff_on == (None if payment_text is None else date.fromisoformat(payment_text))
            expected_sources = {"aeat-modelo-115-guia-censal"}
            if window.closes_on.year <= 2026:
                expected_sources.add(f"aeat-calendario-contribuyente-{window.closes_on.year}")
            else:
                expected_sources.update(
                    {"aeat-modelo-115-180-folleto-actividades", "boe-rirpf-art-108-retencion-deadline"}
                )
            assert set(window.source_refs) == expected_sources
            assert len(window.applicability_conditions) == 1
            assert window.applicability_conditions[0].field == "pays_rent_with_retencion"

    assert windows[(2026, "4T")].payment_cutoff_on is None
