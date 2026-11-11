"""Regression coverage for tax-year M100 work-unit deadline summaries."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest

from ....core.period import Period
from ....domain.calculations.registry.tests.authored_editions import filing_grade_exercises
from ....domain.calculations.registry.tests.published_authority import published_snapshot
from ....domain.modelos.codes import ModeloCode
from ....domain.modelos.work_unit import WorkUnit, derive_work_unit_id
from ..work_plazo import modelo_work_deadline_posture

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET_ID = "e" * 64

# The renta campaign of an exercise closes on 30 June of the following year
# (Reglamento del IRPF, art. 61.1 as the annual order applies it); a close that
# falls on a weekend runs to the next business day. The expectation is computed
# from that rule, so every exercise whose edition reaches filing grade is checked.


def _campaign_close(filing_year: int) -> date:
    nominal = date(filing_year + 1, 6, 30)
    weekend_days_to_monday = 7 - nominal.weekday() if nominal.weekday() >= 5 else 0
    return nominal + timedelta(days=weekend_days_to_monday)


@pytest.mark.parametrize("filing_year", filing_grade_exercises("100"))
def test_m100_tax_year_work_unit_resolves_its_following_campaign_deadline(filing_year: int) -> None:
    closes_on = _campaign_close(filing_year)
    reference_on = date(filing_year + 1, 5, 15)
    period = Period.from_year_and_code(filing_year, "0A")
    revision_id = published_snapshot(
        "100",
        filing_year=filing_year,
        period=period.registry_token,
    ).revision.id
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

    posture = modelo_work_deadline_posture(work_unit, reference_on=reference_on)

    assert posture is not None
    assert posture.closes_on == closes_on
    assert posture.days_remaining == (closes_on - reference_on).days
    assert posture.days_overdue is None
    assert posture.conditional_recargo_preview is None
