"""Session-owned reuse of workbench capture work whose exact inputs have not changed.

A workbench generation is captured after every write and every return to Home.
Most of that work is a pure function of a few stored revisions and the
authority generation: the legal calendar, for example, changes only when the
profile, the work units, the filing records, the date or the authority does.
The capture memory keeps the last result of such work beside the exact
identity of its inputs, and hands it back only when every one of those
identities is unchanged. Anything whose identity cannot be stated is rebuilt.

One memory belongs to one authenticated session. It holds only projections
the session already publishes, never a decrypted catalogue, and the composition
that owns the session closes it on sign-out, handover or expiry.
"""

from __future__ import annotations

from collections.abc import Callable, Hashable
from dataclasses import dataclass
from datetime import date
from threading import Lock
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..domain.calculations.registry.authority_artifact import AuthorityGenerationPin
    from .overview.agenda import OverviewAgenda
    from .overview.calendar_models import OverviewCalendar

__all__ = [
    "WorkbenchCalendarMemoKey",
    "WorkbenchCalendarWork",
    "WorkbenchCaptureMemory",
    "WorkbenchMemoSlot",
]


class WorkbenchMemoSlot[KeyT: Hashable, ValueT]:
    """One reusable result and the input identity it was computed from.

    The key and value are swapped together under a lock, so a reader sees
    either the previous pair or the next one, never a mix. Two captures that
    compute the same work concurrently both build it; the later store wins,
    which loses nothing because both results belong to their own key.
    """

    def __init__(self) -> None:
        """Start empty."""
        self._lock = Lock()
        self._entry: tuple[KeyT, ValueT] | None = None
        self._closed = False

    def reuse(self, key: KeyT, build: Callable[[], ValueT]) -> ValueT:
        """Return the stored result for ``key``, or build, store and return it."""
        with self._lock:
            entry = self._entry
            closed = self._closed
        if entry is not None and entry[0] == key:
            return entry[1]
        value = build()
        if not closed:
            with self._lock:
                if not self._closed:
                    self._entry = (key, value)
        return value

    def close(self) -> None:
        """Drop the stored result and store nothing further."""
        with self._lock:
            self._closed = True
            self._entry = None


@dataclass(frozen=True, slots=True)
class WorkbenchCalendarMemoKey:
    """Everything the legal calendar and agenda of one capture are computed from."""

    profile_content_digest: str
    work_units_revision: str
    filings_revision: str
    as_of: date
    generation: AuthorityGenerationPin


@dataclass(frozen=True, slots=True)
class WorkbenchCalendarWork:
    """The registry-heavy calendar work of one capture.

    ``schedule_calendar`` scopes the filing evidence, ``calendar`` carries that
    evidence, and ``agenda`` is Home's upcoming window. Each carries the instant
    it was actually computed.
    """

    schedule_calendar: OverviewCalendar
    calendar: OverviewCalendar
    agenda: OverviewAgenda


class WorkbenchCaptureMemory:
    """The reusable work of one authenticated session's workbench captures."""

    def __init__(self) -> None:
        """Create the empty slots one session reuses."""
        self.calendar: WorkbenchMemoSlot[WorkbenchCalendarMemoKey, WorkbenchCalendarWork] = WorkbenchMemoSlot()

    def close(self) -> None:
        """Drop every stored result deterministically when the session ends."""
        self.calendar.close()
