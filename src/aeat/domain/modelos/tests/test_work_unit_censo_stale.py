"""WorkUnit invariants for the censo-stale marker fields."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from ....core import Period
from .._work_unit import (
    ModeloCode,
    WorkUnit,
    derive_work_unit_id,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_P_2026_1T = Period.from_year_and_code(2026, "1T")


def _build(
    *,
    censo_stamped_stale_at: datetime | None = None,
    censo_stale_reason: str | None = None,
    created_at: datetime | None = None,
) -> WorkUnit:
    created = created_at or datetime(2026, 5, 1, tzinfo=UTC)
    work_unit_id = derive_work_unit_id(
        bucket_id="bucket-1",
        modelo=ModeloCode("303"),
        filing_year=2026,
        period=_P_2026_1T,
        revision_id="rev-v1",
    )
    return WorkUnit(
        work_unit_id=work_unit_id,
        bucket_id="bucket-1",
        modelo=ModeloCode("303"),
        filing_year=2026,
        period=_P_2026_1T,
        revision_id="rev-v1",
        name="303-2026-1T",
        created_at=created,
        updated_at=created,
        censo_stamped_stale_at=censo_stamped_stale_at,
        censo_stale_reason=censo_stale_reason,
    )


def test_censo_stale_fields_default_to_none() -> None:
    unit = _build()

    assert unit.censo_stamped_stale_at is None
    assert unit.censo_stale_reason is None


def test_censo_stale_fields_accepted_when_paired() -> None:
    stamped_at = datetime(2026, 5, 2, tzinfo=UTC)
    unit = _build(censo_stamped_stale_at=stamped_at, censo_stale_reason="snapshot abc123")

    assert unit.censo_stamped_stale_at == stamped_at
    assert unit.censo_stale_reason == "snapshot abc123"


def test_stale_at_without_reason_is_refused() -> None:
    with pytest.raises(ValidationError, match="set or unset together"):
        _build(
            censo_stamped_stale_at=datetime(2026, 5, 2, tzinfo=UTC),
            censo_stale_reason=None,
        )


def test_stale_reason_without_stamped_at_is_refused() -> None:
    with pytest.raises(ValidationError, match="set or unset together"):
        _build(censo_stamped_stale_at=None, censo_stale_reason="snapshot abc123")


def test_stale_at_before_created_at_is_refused() -> None:
    created = datetime(2026, 5, 1, tzinfo=UTC)
    with pytest.raises(ValidationError, match="precedes created_at"):
        _build(
            created_at=created,
            censo_stamped_stale_at=created - timedelta(days=1),
            censo_stale_reason="snapshot abc123",
        )
