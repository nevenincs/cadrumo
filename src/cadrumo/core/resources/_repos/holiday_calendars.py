"""Year-keyed holiday-calendar repository.

:class:`HolidayCalendarRepository` loads BOE holiday calendars through the
shared :class:`ResourceCacheRepository` cache behind :class:`ResourceRegistry`.
"""

from __future__ import annotations

from typing import override

from .._repository import ResourceCacheRepository


class HolidayCalendarRepository(ResourceCacheRepository[object, int]):
    """Year-keyed repository for BOE holiday calendars.

    Wraps :func:`cadrumo.domain.deadlines.load_holiday_calendar`
    behind the shared :class:`ResourceCacheRepository` cache.
    """

    @override
    def _load(self, key: int) -> object:
        from ....domain.deadlines.festivos import load_holiday_calendar

        return load_holiday_calendar(key)
