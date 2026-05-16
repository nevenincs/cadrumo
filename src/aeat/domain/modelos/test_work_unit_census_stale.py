"""WorkUnit invariants for the census-stale marker fields."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from pydantic import ValidationError

from aeat.domain.modelos._work_unit import (
    ModeloCode,
    WorkUnit,
    derive_work_unit_id,
)


pytestmark = [pytest.mark.unit, pytest.mark.domain_model]


def _build(
    *,
    census_stamped_stale_at: datetime | None = None,
    census_stale_reason: str | None = None,
    created_at: datetime | None = None,
) -> WorkUnit:
    created = created_at or datetime(2026, 5, 1, tzinfo=UTC)
    work_unit_id = derive_work_unit_id(
        bucket_id="bucket-1",
        modelo=ModeloCode("303"),
        filing_year=2026,
        period="Q1",
        revision_id="rev-v1",
    )
    return WorkUnit(
        work_unit_id=work_unit_id,
        bucket_id="bucket-1",
        modelo=ModeloCode("303"),
        filing_year=2026,
        period="Q1",
        revision_id="rev-v1",
        name="303-2026-Q1",
        created_at=created,
        updated_at=created,
        census_stamped_stale_at=census_stamped_stale_at,
        census_stale_reason=census_stale_reason,
    )


def test_census_stale_fields_default_to_none() -> None:
    unit = _build()

    assert unit.census_stamped_stale_at is None
    assert unit.census_stale_reason is None


def test_census_stale_fields_accepted_when_paired() -> None:
    stamped_at = datetime(2026, 5, 2, tzinfo=UTC)
    unit = _build(census_stamped_stale_at=stamped_at, census_stale_reason="snapshot abc123")

    assert unit.census_stamped_stale_at == stamped_at
    assert unit.census_stale_reason == "snapshot abc123"


def test_stale_at_without_reason_is_refused() -> None:
    with pytest.raises(ValidationError, match="set or unset together"):
        _build(
            census_stamped_stale_at=datetime(2026, 5, 2, tzinfo=UTC),
            census_stale_reason=None,
        )


def test_stale_reason_without_stamped_at_is_refused() -> None:
    with pytest.raises(ValidationError, match="set or unset together"):
        _build(census_stamped_stale_at=None, census_stale_reason="snapshot abc123")


def test_stale_at_before_created_at_is_refused() -> None:
    created = datetime(2026, 5, 1, tzinfo=UTC)
    with pytest.raises(ValidationError, match="precedes created_at"):
        _build(
            created_at=created,
            census_stamped_stale_at=created - timedelta(days=1),
            census_stale_reason="snapshot abc123",
        )
