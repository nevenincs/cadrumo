"""Year-keyed holiday-calendar repository.

:class:`HolidayCalendarRepository` loads BOE holiday calendars through the
shared :class:`ResourceCacheRepository` cache behind :class:`ResourceRegistry`.
"""

from __future__ import annotations

from collections.abc import Iterable

from ...calculations.registry.authority import PinnedAuthorityOperation


class HolidayCalendarRepository:
    """Year-keyed repository for BOE holiday calendars.

    Wraps :func:`cadrumo.domain.deadlines.load_holiday_calendar`
    without adding a second cache to the published authority.
    """

    def get(self, key: int, *, operation: PinnedAuthorityOperation) -> object:
        """Resolve through the caller's pinned authority operation."""
        return self._load(key, operation=operation)

    def _load(self, key: int, *, operation: PinnedAuthorityOperation) -> object:
        from ...deadlines.festivos import load_holiday_calendar

        return load_holiday_calendar(key, operation=operation)

    def all(self) -> Iterable[object]:
        """Preserve the repository contract's non-enumerable behavior."""
        raise NotImplementedError(f"{type(self).__name__} does not implement all(); override per repository")

    def clear_cache(self) -> None:
        """Do nothing; the published authority owns runtime freshness."""
