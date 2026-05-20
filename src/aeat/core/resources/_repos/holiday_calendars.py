"""HolidayCalendarRepository: int-year-keyed holiday calendar."""

from __future__ import annotations

from .._repository import ResourceCacheRepository


class HolidayCalendarRepository(ResourceCacheRepository[object, int]):
    """Year-keyed repository for BOE holiday calendars.

    Wraps :func:`aeat.domain.deadlines.load_holiday_calendar`.
    """

    def _load(self, key: int) -> object:
        from ....domain.deadlines import load_holiday_calendar

        return load_holiday_calendar(key)
