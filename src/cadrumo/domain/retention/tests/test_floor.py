"""Pure tests for the tax-record retention-floor assessment.

Expected safe-erase dates are derived from the LGT four-year prescription
floor (Ley 58/2003 art. 66/70), the external legal authority — never from the
assessment code under test, so a wrong floor would fail these tests.
"""

from __future__ import annotations

from calendar import isleap
from dataclasses import dataclass
from datetime import UTC, date, datetime

import pytest

from ....core.calendar_shift import shift_by_calendar_years
from ...calculations.registry.tests.published_authority import published_supported_filing_years
from ..floor import RetainableFilingRecord, RetentionFloorAssessment, assess_retention_floor

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain, pytest.mark.usefixtures("operation")]

#: The LGT art. 66 prescription floor. Duplicated here as the independent
#: specification the assessment must satisfy, not imported from the code path
#: it exercises.
_LGT_FLOOR_YEARS = 4
_FILING_ID_1 = "1" * 64
_FILING_ID_2 = "2" * 64
_FILING_ID_3 = "3" * 64


@dataclass(frozen=True)
class _FiledRecord:
    """Minimal record satisfying :class:`RetainableFilingRecord` for tests."""

    filing_record_id: str
    modelo: str
    filing_year: int
    filed_at: datetime


def _dt(year: int, month: int = 6, day: int = 15) -> datetime:
    return datetime(year, month, day, 12, 0, tzinfo=UTC)


def test_record_satisfies_protocol() -> None:
    record = _FiledRecord(_FILING_ID_1, "303", 2020, _dt(2021))
    assert isinstance(record, RetainableFilingRecord)


def _safe_erase_date(filed_at: datetime) -> datetime:
    """Read one record's safe-erase instant back off the real assessment.

    The assessment is the production surface that applies the floor, so the
    instant is observed where a caller observes it rather than through a
    second entry point that only restates the calendar shift.
    """
    record = _FiledRecord(_FILING_ID_1, "303", filed_at.year - 1, filed_at)
    assessment = assess_retention_floor((record,), as_of=filed_at)
    return assessment.retained[0].earliest_safe_erase_date


def _supported_years() -> tuple[int, ...]:
    support = published_supported_filing_years()
    assert support is not None, "the bundled registry declares no supported filing years"
    return support.years


def test_safe_erase_date_adds_four_year_floor() -> None:
    year = _supported_years()[0]
    assert _safe_erase_date(_dt(year, 6, 30)) == _dt(year + _LGT_FLOOR_YEARS, 6, 30)


def test_leap_day_filed_at_clamps_to_28_february() -> None:
    # A leap day plus four years lands on another leap year, so no clamp.
    leap_year = next(year for year in _supported_years() if isleap(year) and isleap(year + _LGT_FLOOR_YEARS))
    assert _safe_erase_date(_dt(leap_year, 2, 29)) == _dt(leap_year + _LGT_FLOOR_YEARS, 2, 29)
    # A one-year floor from a leap day into a non-leap year clamps to 28 Feb.
    assert shift_by_calendar_years(_dt(2020, 2, 29), 1) == _dt(2021, 2, 28)


def test_prescription_year_addition_preserves_date_or_datetime_kind() -> None:
    assert shift_by_calendar_years(date(2020, 2, 29), 1) == date(2021, 2, 28)
    assert shift_by_calendar_years(_dt(2020, 2, 29), 1) == _dt(2021, 2, 28)


def test_record_inside_window_blocks_erase() -> None:
    filed_at = _dt(2023, 6, 15)
    record = _FiledRecord(_FILING_ID_1, "130", 2022, filed_at)
    # Two years after filing: well inside the four-year floor.
    assessment = assess_retention_floor((record,), as_of=_dt(2025, 6, 15))
    assert isinstance(assessment, RetentionFloorAssessment)
    assert assessment.blocks_erase is True
    assert len(assessment.retained) == 1
    blocking = assessment.retained[0]
    assert blocking.filing_record_id == _FILING_ID_1
    assert blocking.earliest_safe_erase_date == _dt(2027, 6, 15)
    assert assessment.latest_safe_erase_date == _dt(2027, 6, 15)


def test_record_past_floor_is_erasable() -> None:
    filed_at = _dt(2019, 6, 15)
    record = _FiledRecord(_FILING_ID_1, "100", 2018, filed_at)
    # Six years after filing: the four-year window elapsed in 2023.
    assessment = assess_retention_floor((record,), as_of=_dt(2025, 6, 15))
    assert assessment.blocks_erase is False
    assert assessment.retained == ()
    assert assessment.latest_safe_erase_date is None


def test_boundary_exactly_at_floor_is_erasable() -> None:
    filed_at = _dt(2021, 6, 15)
    record = _FiledRecord(_FILING_ID_1, "303", 2020, filed_at)
    # as_of == the safe-erase instant: the window has elapsed (strict <).
    assessment = assess_retention_floor((record,), as_of=_dt(2025, 6, 15))
    assert assessment.blocks_erase is False


def test_mixed_set_reports_latest_safe_erase_date() -> None:
    old = _FiledRecord(_FILING_ID_1, "100", 2016, _dt(2017))
    recent = _FiledRecord(_FILING_ID_2, "303", 2023, _dt(2024, 1, 20))
    newest = _FiledRecord(_FILING_ID_3, "130", 2024, _dt(2025, 3, 10))
    assessment = assess_retention_floor((old, recent, newest), as_of=_dt(2025, 6, 15))
    # Only the two records filed within the last four years block.
    retained_ids = {record.filing_record_id for record in assessment.retained}
    assert retained_ids == {_FILING_ID_2, _FILING_ID_3}
    # Latest safe-erase date is the max across retained: newest + 4 years.
    assert assessment.latest_safe_erase_date == _dt(2029, 3, 10)
    # Retained records are ordered by their safe-erase date (ascending).
    assert [record.filing_record_id for record in assessment.retained] == [_FILING_ID_2, _FILING_ID_3]


def test_empty_record_set_never_blocks() -> None:
    assessment = assess_retention_floor((), as_of=_dt(2025, 6, 15))
    assert assessment.blocks_erase is False
    assert assessment.latest_safe_erase_date is None
    assert assessment.floor_years == _LGT_FLOOR_YEARS
