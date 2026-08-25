"""Fleet invariants for the canonical deadline-window authority projection."""

from __future__ import annotations

from collections import Counter, defaultdict

import pytest

from .. import (
    DeadlineWindowDefinition,
    ModeloRevision,
    bundled_authority,
    deadline_window_semantic_coordinates,
    select_revision,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _projection_identity(item: tuple[str, ModeloRevision, DeadlineWindowDefinition]) -> tuple[str, str, str]:
    modelo_id, revision, window = item
    return modelo_id, revision.id, window.id


def test_fleet_deadline_projection_is_canonically_owned_exact_and_filter_invariant() -> None:
    """The authority projects every owned row once without masking corpus defects.

    This deliberately measures only authored rows. Completeness is
    a separate registry invariant, so future-year gaps cannot weaken or block the
    ownership and projection contract proved here.
    """
    authority = bundled_authority()
    assert authority.catalogues.supported_filing_years is not None

    for filing_year in authority.catalogues.supported_filing_years.years:
        projected = authority.deadline_windows(filing_year)
        assert projected, f"fleet projection for {filing_year} must exercise real bundled rows"
        assert projected == authority.deadline_windows(filing_year), "projection order changed between calls"

        expected = []
        for modelo in authority.modelos:
            for containing_revision in modelo.revisions.values():
                for window in containing_revision.deadline_windows:
                    if window.filing_year != filing_year:
                        continue
                    owner = select_revision(
                        modelo,
                        filing_year=window.period.filing_year,
                        period=window.period.registry_token,
                    )
                    if owner is containing_revision:
                        expected.append((modelo.id, owner, window))

        assert Counter(map(_projection_identity, projected)) == Counter(map(_projection_identity, expected))
        assert len(projected) == len(expected), "authority must retain authored row multiplicity"

        atomic_coordinates = [
            coordinate
            for modelo_id, _revision, window in projected
            for coordinate in deadline_window_semantic_coordinates(modelo_id, window)
        ]
        assert len(atomic_coordinates) == len(set(atomic_coordinates))

        for modelo_id in {item[0] for item in projected}:
            filtered = authority.deadline_windows(filing_year, modelos=(modelo_id,))
            assert filtered == tuple(item for item in projected if item[0] == modelo_id)
            for projected_modelo, revision, window in filtered:
                modelo = authority.modelo(projected_modelo)
                assert revision is select_revision(
                    modelo,
                    filing_year=window.period.filing_year,
                    period=window.period.registry_token,
                )


def test_fleet_projection_preserves_distinct_qualified_variants() -> None:
    authority = bundled_authority()
    projected = authority.deadline_windows(2025, modelos=("210",))
    by_base_coordinate = defaultdict(list)
    for modelo_id, revision, window in projected:
        by_base_coordinate[(modelo_id, window.period.filing_year, window.period.registry_token)].append(
            (revision, window),
        )

    qualified_variants = max(by_base_coordinate.values(), key=len)
    assert len(qualified_variants) > 1, "bundled fleet must exercise qualifier-distinct plazo variants"
    assert len(qualified_variants) == len(
        {(window.resultado_scope, window.tipo_renta_scope) for _revision, window in qualified_variants},
    )
    assert len(
        {
            coordinate
            for _revision, window in qualified_variants
            for coordinate in deadline_window_semantic_coordinates("210", window)
        },
    ) == sum(len(deadline_window_semantic_coordinates("210", window)) for _revision, window in qualified_variants)


def _window_by_period(
    filing_year: int,
    modelo: str,
) -> dict[str, DeadlineWindowDefinition]:
    return {
        window.period.registry_token: window
        for _modelo, _revision, window in bundled_authority().deadline_windows(filing_year, modelos=(modelo,))
    }


def test_shared_iva_group_year_end_rule_stays_relationally_consistent_over_supported_horizon() -> None:
    """Equivalent monthly IVA obligations must not drift by modelo.

    Exact source tests own the external calendar dates. This fleet invariant
    instead compares models that AEAT declares to share Modelo 303's monthly
    presentation timetable, so it remains meaningful when the supported-year
    catalogue advances.
    """
    authority = bundled_authority()
    assert authority.catalogues.supported_filing_years is not None
    compared_years = 0

    for filing_year in authority.catalogues.supported_filing_years.years:
        projected = {modelo: _window_by_period(filing_year, modelo) for modelo in ("303", "322", "353")}
        if not all("12" in windows for windows in projected.values()):
            continue
        compared_years += 1
        year_end = {modelo: windows["12"] for modelo, windows in projected.items()}
        expected = year_end["303"]
        for modelo, window in year_end.items():
            assert (window.opens_on, window.closes_on) == (
                expected.opens_on,
                expected.closes_on,
            ), f"modelo {modelo} diverges from the shared monthly IVA year-end rule for {filing_year}"
        declared_cutoffs = [window.payment_cutoff_on for window in year_end.values() if window.payment_cutoff_on]
        assert len(set(declared_cutoffs)) <= 1
    assert compared_years > 0


@pytest.mark.parametrize("modelo", ("303", "349"))
def test_monthly_and_quarterly_year_end_variants_share_their_endpoint(modelo: str) -> None:
    """December and Q4 variants governed by one January rule cannot disagree."""
    authority = bundled_authority()
    assert authority.catalogues.supported_filing_years is not None
    compared_years = 0

    for filing_year in authority.catalogues.supported_filing_years.years:
        windows = _window_by_period(filing_year, modelo)
        if not {"12", "4T"}.issubset(windows):
            continue
        compared_years += 1
        assert windows["12"].closes_on == windows["4T"].closes_on
    assert compared_years > 0
