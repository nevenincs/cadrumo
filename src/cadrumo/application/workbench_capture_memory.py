"""Session-owned reuse of workbench capture work whose exact inputs have not changed.

A workbench generation is captured after every write and every return to Home.
Most of that work is a pure function of a few stored revisions and the
authority generation: the legal calendar, for example, changes only when the
profile, the work units, the filing records, the date or the authority does.
The capture memory keeps the last result of such work beside the exact
identity of its inputs, and hands it back only when every one of those
identities is unchanged. Anything whose identity cannot be stated is rebuilt.

The census is kept differently: its reading classifies every operation
journal record, and a record's definition never changes, so the memory keeps
the last classification and the next capture brings it up to date from the
records created or removed since instead of classifying every record again.

One memory belongs to one authenticated session. It holds only projections
the session already publishes and journal record identifiers, never a
decrypted catalogue, and the composition that owns the session closes it on
sign-out, handover or expiry.
"""

from __future__ import annotations

from collections.abc import Callable, Hashable
from dataclasses import dataclass
from datetime import date
from threading import Lock
from typing import TYPE_CHECKING
from uuid import UUID

if TYPE_CHECKING:
    from ..domain.calculations.registry.authority_artifact import AuthorityGenerationPin
    from .overview.agenda import OverviewAgenda
    from .overview.calendar_models import OverviewCalendar
    from .user_profile.censal_readback import CensalHistoryRead

__all__ = [
    "WorkbenchCalendarMemoKey",
    "WorkbenchCalendarWork",
    "WorkbenchCaptureMemory",
    "WorkbenchCaptureMemoryOwner",
    "WorkbenchCensusMemo",
    "WorkbenchCensusMemoKey",
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
    aeat_evidence_revision: str = "unbound"
    invoice_catalogue_revision: str = "unbound"
    """The invoice catalogue the ledger obligation signals are derived from."""


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


@dataclass(frozen=True, slots=True)
class WorkbenchCensusMemoKey:
    """The exact census lookup a kept classification answers: one profile over one journal."""

    profile_id: UUID
    journal_root: str


class WorkbenchCensusMemo:
    """The census classification the next capture of one session starts from.

    It is never served as an answer. A capture that finds one brings it up to
    date from the journal before using it, and that brings back exactly what a
    full read would, because a record's definition never changes and an
    identifier is never reused; any classification that was once current is
    therefore a sound start, and two captures storing out of order lose
    nothing but work. A classification is handed back only for the exact key
    it was kept under.
    """

    def __init__(self) -> None:
        """Start empty."""
        self._lock = Lock()
        self._entry: tuple[WorkbenchCensusMemoKey, CensalHistoryRead] | None = None
        self._closed = False

    def recall(self, key: WorkbenchCensusMemoKey) -> CensalHistoryRead | None:
        """Return the classification kept for ``key``, or nothing."""
        with self._lock:
            entry = self._entry
        return entry[1] if entry is not None and entry[0] == key else None

    def keep(self, key: WorkbenchCensusMemoKey, history: CensalHistoryRead) -> None:
        """Keep ``history`` for ``key``, unless the memo is closed."""
        with self._lock:
            if not self._closed:
                self._entry = (key, history)

    def close(self) -> None:
        """Drop the kept classification and keep nothing further."""
        with self._lock:
            self._closed = True
            self._entry = None


class WorkbenchCaptureMemory:
    """The reusable work of one authenticated session's workbench captures."""

    def __init__(self) -> None:
        """Create the empty slots one session reuses."""
        self.calendar: WorkbenchMemoSlot[WorkbenchCalendarMemoKey, WorkbenchCalendarWork] = WorkbenchMemoSlot()
        self.census = WorkbenchCensusMemo()

    def close(self) -> None:
        """Drop every stored result deterministically when the session ends."""
        self.calendar.close()
        self.census.close()


class WorkbenchCaptureMemoryOwner:
    """Hand out one profile's capture memory until a session that read through it ends.

    The owner keeps at most one memory, for the exact profile last asked for,
    and closes it before handing out another profile's. :meth:`close` drops it
    when a session ends (a lock, a sign-out, a lapsed lease or the worker's
    close), and the next read starts an empty memory: a capture still running
    with the closed one stores nothing, so nothing computed before a session
    ended is served after it.
    """

    def __init__(self) -> None:
        """Start holding no memory."""
        self._lock = Lock()
        self._held: tuple[str, WorkbenchCaptureMemory] | None = None

    def for_profile(self, profile_id: str) -> WorkbenchCaptureMemory:
        """Return the open memory of ``profile_id``, closing another profile's first."""
        with self._lock:
            held = self._held
            if held is not None and held[0] == profile_id:
                return held[1]
            memory = WorkbenchCaptureMemory()
            self._held = (profile_id, memory)
        if held is not None:
            held[1].close()
        return memory

    def close(self) -> None:
        """Drop the held memory; the next read starts an empty one."""
        with self._lock:
            held, self._held = self._held, None
        if held is not None:
            held[1].close()
