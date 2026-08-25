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

_SUPPORTED_DEADLINE_YEARS = range(2022, 2027)


def _projection_identity(item: tuple[str, ModeloRevision, DeadlineWindowDefinition]) -> tuple[str, str, str]:
    modelo_id, revision, window = item
    return modelo_id, revision.id, window.id


def test_fleet_deadline_projection_is_canonically_owned_exact_and_filter_invariant() -> None:
    """The authority projects every owned row once without masking corpus defects.

    This deliberately measures only rows that are authored today. Completeness is
    a separate registry invariant, so future-year gaps cannot weaken or block the
    ownership and projection contract proved here.
    """
    authority = bundled_authority()

    for filing_year in _SUPPORTED_DEADLINE_YEARS:
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
