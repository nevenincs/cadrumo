"""Regression coverage for tax-year M100 work-unit deadline summaries."""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from ....core import Period
from ....domain.calculations.registry.authority import bundled_authority
from ....domain.modelos import ModeloCode, WorkUnit, derive_work_unit_id
from .._work_plazo import modelo_work_deadline_posture

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET_ID = "e" * 64


@pytest.mark.parametrize(
    ("filing_year", "opens_on", "closes_on"),
    (
        (2020, date(2021, 4, 7), date(2021, 6, 30)),
        (2021, date(2022, 4, 6), date(2022, 6, 30)),
    ),
)
def test_m100_tax_year_work_unit_resolves_its_following_campaign_deadline(
    filing_year: int,
    opens_on: date,
    closes_on: date,
) -> None:
    period = Period.from_year_and_code(filing_year, "0A")
    revision_id = (
        bundled_authority()
        .snapshot(
            "100",
            filing_year=filing_year,
            period=period.registry_token,
        )
        .revision.id
    )
    created_at = datetime(filing_year, 12, 31, tzinfo=UTC)
    work_unit = WorkUnit(
        work_unit_id=derive_work_unit_id(
            bucket_id=_BUCKET_ID,
            modelo="100",
            filing_year=filing_year,
            period=period,
            revision_id=revision_id,
        ),
        bucket_id=_BUCKET_ID,
        modelo=ModeloCode("100"),
        filing_year=filing_year,
        period=period,
        revision_id=revision_id,
        name=f"100-{filing_year}-0A",
        created_at=created_at,
        updated_at=created_at,
    )

    posture = modelo_work_deadline_posture(work_unit, reference_on=opens_on)

    assert posture is not None
    assert posture.closes_on == closes_on
    assert posture.days_remaining == (closes_on - opens_on).days
    assert posture.days_overdue is None
    assert posture.conditional_recargo_preview is None
