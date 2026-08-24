"""Canonical deadline semantic-coordinate tests."""

from __future__ import annotations

from datetime import date

import pytest

from cadrumo.core import Period, ResultDisposition

from .. import (
    DeadlineSemanticCoordinate,
    DeadlineWindowDefinition,
    deadline_semantic_coordinate,
    deadline_window_semantic_coordinate,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_deadline_coordinate_uses_typed_period_and_qualifier_axes_only() -> None:
    period = Period.from_year_and_code(2025, "0A")

    coordinate = deadline_semantic_coordinate(
        "210",
        period,
        ResultDisposition.INGRESO,
        ("35", "01"),
    )

    assert coordinate == DeadlineSemanticCoordinate("210", 2025, "0A", ResultDisposition.INGRESO, ("01", "35"))


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

    assert deadline_window_semantic_coordinate("210", first) == deadline_window_semantic_coordinate("210", second)


def test_deadline_coordinate_distinguishes_each_approved_qualifier_axis() -> None:
    period = Period.from_year_and_code(2025, "0A")
    base = deadline_semantic_coordinate("210", period, None, None)

    assert deadline_semantic_coordinate("210", period, ResultDisposition.INGRESO, None) != base
    assert deadline_semantic_coordinate("210", period, None, ("01",)) != base
    assert deadline_semantic_coordinate("211", period, None, None) != base
    assert deadline_semantic_coordinate("210", Period.from_year_and_code(2025, "1T"), None, None) != base
