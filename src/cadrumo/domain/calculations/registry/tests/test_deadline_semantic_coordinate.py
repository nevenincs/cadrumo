"""Canonical deadline semantic-coordinate tests."""

from __future__ import annotations

from datetime import date

import pytest

from .....core import Period, ResultDisposition
from cadrumo.domain.calculations.registry.deadline_coordinate import DeadlineSemanticCoordinate, deadline_semantic_coordinate, deadline_window_semantic_coordinates
from cadrumo.domain.calculations.registry.schema import DeadlineWindowDefinition

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_deadline_coordinate_uses_typed_period_and_qualifier_axes_only() -> None:
    period = Period.from_year_and_code(2025, "0A")

    coordinate = deadline_semantic_coordinate(
        "210",
        period,
        ResultDisposition.INGRESO,
        "35",
    )

    assert coordinate == DeadlineSemanticCoordinate("210", 2025, "0A", ResultDisposition.INGRESO, "35")


def test_deadline_coordinate_ignores_non_identity_window_metadata() -> None:
    shared: dict[str, object] = {
        "filing_year": 2025,
        "period": "2025 0A",
        "period_kind": "annual",
        "resultado_scope": "I",
        "tipo_renta_scope": ("01", "35"),
        "legal_refs": ("legal.test",),
        "source_refs": ("source-test",),
    }
    first = DeadlineWindowDefinition.model_validate(
        shared | {"id": "first", "opens_on": date(2026, 1, 1), "closes_on": date(2026, 1, 20)},
    )
    second = DeadlineWindowDefinition.model_validate(
        shared | {"id": "second", "opens_on": date(2026, 4, 1), "closes_on": date(2026, 4, 20)},
    )

    assert deadline_window_semantic_coordinates("210", first) == deadline_window_semantic_coordinates("210", second)


def test_deadline_coordinate_distinguishes_each_approved_qualifier_axis() -> None:
    period = Period.from_year_and_code(2025, "0A")
    base = deadline_semantic_coordinate("210", period, None, None)

    assert deadline_semantic_coordinate("210", period, ResultDisposition.INGRESO, None) != base
    assert deadline_semantic_coordinate("210", period, None, "01") != base
    assert deadline_semantic_coordinate("211", period, None, None) != base
    assert deadline_semantic_coordinate("210", Period.from_year_and_code(2025, "1T"), None, None) != base


def test_deadline_coordinates_expand_bundled_tipo_scope_to_atomic_codes() -> None:
    shared: dict[str, object] = {
        "filing_year": 2025,
        "period": "2025 0A",
        "period_kind": "annual",
        "opens_on": date(2026, 1, 1),
        "closes_on": date(2026, 1, 20),
        "resultado_scope": "I",
        "legal_refs": ("legal.test",),
        "source_refs": ("source-test",),
    }
    bundled = DeadlineWindowDefinition.model_validate(
        shared | {"id": "bundled", "tipo_renta_scope": ("01", "35")},
    )
    subset = DeadlineWindowDefinition.model_validate(
        shared | {"id": "subset", "tipo_renta_scope": ("01",)},
    )

    bundled_coordinates = set(deadline_window_semantic_coordinates("210", bundled))
    subset_coordinates = set(deadline_window_semantic_coordinates("210", subset))
    assert bundled_coordinates & subset_coordinates == {
        DeadlineSemanticCoordinate("210", 2025, "0A", ResultDisposition.INGRESO, "01"),
    }


def test_unqualified_window_overlaps_every_qualified_request_it_can_match() -> None:
    shared: dict[str, object] = {
        "filing_year": 2025,
        "period": "2025 0A",
        "period_kind": "annual",
        "opens_on": date(2026, 1, 1),
        "closes_on": date(2026, 1, 20),
        "legal_refs": ("legal.test",),
        "source_refs": ("source-test",),
    }
    unqualified = DeadlineWindowDefinition.model_validate(shared | {"id": "unqualified"})
    qualified = DeadlineWindowDefinition.model_validate(
        shared | {"id": "qualified", "resultado_scope": "I", "tipo_renta_scope": ("01",)},
    )

    assert set(deadline_window_semantic_coordinates("210", unqualified)) & set(
        deadline_window_semantic_coordinates("210", qualified),
    ) == {DeadlineSemanticCoordinate("210", 2025, "0A", ResultDisposition.INGRESO, "01")}
