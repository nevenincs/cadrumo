"""Contracts for the one identifier naming a validated registry snapshot.

These are deliberately registry-free: they pin the identifier's collision
behaviour without loading the bundled authority, so the contract stays
measurable independently of corpus state.
"""

from __future__ import annotations

import pytest

from .._snapshot_coordinate import registry_snapshot_id

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_same_revision_in_two_filing_years_gets_distinct_identifiers() -> None:
    """The reported collision: one revision serving two years must not share an id.

    Modelo 130 for 2025/1T and 2026/1T both resolve revision
    ``2019-y-siguientes``. A modelo-plus-revision identifier named them
    identically, silently merging the provenance of two separate filings.
    """
    first = registry_snapshot_id(modelo="130", revision_id="2019-y-siguientes", filing_year=2025, period="1T")
    second = registry_snapshot_id(modelo="130", revision_id="2019-y-siguientes", filing_year=2026, period="1T")

    assert first != second


def test_same_revision_in_two_periods_gets_distinct_identifiers() -> None:
    """Period is load-bearing too, not only the filing year."""
    first = registry_snapshot_id(modelo="130", revision_id="2019-y-siguientes", filing_year=2025, period="1T")
    second = registry_snapshot_id(modelo="130", revision_id="2019-y-siguientes", filing_year=2025, period="2T")

    assert first != second


@pytest.mark.parametrize(
    ("field", "changed"),
    [
        ("modelo", {"modelo": "131"}),
        ("revision_id", {"revision_id": "2024-y-siguientes"}),
        ("filing_year", {"filing_year": 2026}),
        ("period", {"period": "4T"}),
    ],
)
def test_every_coordinate_changes_the_identifier(field: str, changed: dict[str, object]) -> None:
    """No coordinate may be decorative.

    Asserting only that two known-different snapshots differ would still pass
    if one coordinate were dropped from the format, so each is varied alone.
    """
    baseline = {"modelo": "130", "revision_id": "2019-y-siguientes", "filing_year": 2025, "period": "1T"}

    assert registry_snapshot_id(**baseline) != registry_snapshot_id(**{**baseline, **changed}), field


def test_identifier_is_the_four_coordinates_in_order() -> None:
    """Pin the exact rendering the persisted observations and reports carry."""
    assert (
        registry_snapshot_id(modelo="130", revision_id="2019-y-siguientes", filing_year=2025, period="1T")
        == "130:2019-y-siguientes:2025:1T"
    )
