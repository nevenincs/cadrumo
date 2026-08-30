"""Deadline-posture and unassessed Article 27 preview regression coverage.

The calculate path has a work unit and an as-of reference date, but not the
provenance-bearing facts needed to assess Article 27 LGT.  Its overdue output is
therefore an explicit deadline posture plus a conditional rate preview, never a
determined recargo or interest liability.  These tests derive the close date and
band from the live registry-backed deadline engine, rather than inventing rates.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest

from ....core.period import Period
from ....domain.deadlines.plazo import resolve_filing_closes_on
from ....domain.deadlines.recargo import build_recovery_for_overdue
from ....domain.modelos.codes import ModeloCode
from ....domain.modelos.work_unit import WorkUnit, derive_work_unit_id
from .._work_plazo import modelo_work_deadline_posture

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET_ID = "d" * 64
_REVISION_ID = "130-2019-y-siguientes"
_MODELO = "130"
_PERIOD_CODE = "1T"
_FILING_YEAR = 2026


def _work_unit(period: Period) -> WorkUnit:
    work_unit_id = derive_work_unit_id(
        bucket_id=_BUCKET_ID,
        modelo=_MODELO,
        filing_year=_FILING_YEAR,
        period=period,
        revision_id=_REVISION_ID,
    )
    now = datetime(_FILING_YEAR, 1, 1, tzinfo=UTC)
    return WorkUnit(
        work_unit_id=work_unit_id,
        bucket_id=_BUCKET_ID,
        modelo=ModeloCode(_MODELO),
        filing_year=_FILING_YEAR,
        period=period,
        revision_id=_REVISION_ID,
        name=f"{_MODELO}-{_FILING_YEAR}-{_PERIOD_CODE}",
        created_at=now,
        updated_at=now,
    )


def _overdue_context() -> tuple[WorkUnit, Period, date, date]:
    """Return (work_unit, period, closes_on, reference_on) for late M130 1T."""
    period = Period.from_year_and_code(_FILING_YEAR, _PERIOD_CODE)
    closes_on = resolve_filing_closes_on(_MODELO, _FILING_YEAR, period)
    assert closes_on is not None, "registry must carry an M130 1T 2026 deadline window"
    reference_on = closes_on + timedelta(days=40)
    return _work_unit(period), period, closes_on, reference_on


def test_overdue_deadline_posture_exposes_unassessed_rate_preview() -> None:
    """A past deadline yields posture plus advisory rate, never an assessment."""
    work_unit, period, closes_on, reference_on = _overdue_context()

    posture = modelo_work_deadline_posture(work_unit, reference_on=reference_on)

    assert posture is not None
    assert posture.closes_on == closes_on
    assert posture.days_overdue == (reference_on - closes_on).days
    preview = posture.conditional_recargo_preview
    assert preview is not None, "an overdue posture should expose the governed conditional rate"
    assert preview.assessment_status == "unassessed"
    assert preview.rate_reference_on == reference_on
    assert not hasattr(preview, "presentation_date"), "the as-of reference must not become a filing date"

    expected = build_recovery_for_overdue(
        closes_on=closes_on,
        reference_today=reference_on,
        modelo=_MODELO,
        period=period,
    )
    assert preview.band_id == expected.recargo_band.id
    assert preview.surcharge_pct == expected.recargo_band.surcharge_pct
    assert preview.interest_applies is expected.recargo_band.interest_applies


def test_preview_preserves_exact_twelve_month_rate_boundary_without_assessment() -> None:
    """The governed 12-month band remains correct while status stays unassessed."""
    work_unit, period, closes_on, _reference_on = _overdue_context()
    anniversary = closes_on.replace(year=closes_on.year + 1)
    day_after = anniversary + timedelta(days=1)

    anniversary_posture = modelo_work_deadline_posture(work_unit, reference_on=anniversary)
    day_after_posture = modelo_work_deadline_posture(work_unit, reference_on=day_after)

    assert anniversary_posture is not None
    assert day_after_posture is not None
    anniversary_preview = anniversary_posture.conditional_recargo_preview
    day_after_preview = day_after_posture.conditional_recargo_preview
    assert anniversary_preview is not None
    assert day_after_preview is not None
    assert anniversary_preview.assessment_status == "unassessed"
    assert day_after_preview.assessment_status == "unassessed"

    anniversary_recovery = build_recovery_for_overdue(
        closes_on=closes_on,
        reference_today=anniversary,
        modelo=_MODELO,
        period=period,
    )
    day_after_recovery = build_recovery_for_overdue(
        closes_on=closes_on,
        reference_today=day_after,
        modelo=_MODELO,
        period=period,
    )
    assert anniversary_preview.band_id == anniversary_recovery.recargo_band.id
    assert anniversary_preview.interest_applies is anniversary_recovery.recargo_band.interest_applies
    assert day_after_preview.band_id == day_after_recovery.recargo_band.id
    assert day_after_preview.interest_applies is day_after_recovery.recargo_band.interest_applies


def test_in_time_deadline_posture_has_no_conditional_rate_preview() -> None:
    """An open voluntary window has only days remaining, with no rate guidance."""
    period = Period.from_year_and_code(_FILING_YEAR, _PERIOD_CODE)
    closes_on = resolve_filing_closes_on(_MODELO, _FILING_YEAR, period)
    assert closes_on is not None
    reference_on = closes_on - timedelta(days=5)

    posture = modelo_work_deadline_posture(_work_unit(period), reference_on=reference_on)

    assert posture is not None
    assert posture.days_remaining == 5
    assert posture.days_overdue is None
    assert posture.conditional_recargo_preview is None
