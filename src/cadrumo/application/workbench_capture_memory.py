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

One memory belongs to one authenticated session. In addition to calendar
projections and journal identifiers, it retains decrypted derived taxpayer
form values in a public subtree, its strictly validated canonical inverse and
an exact copied value key, and the last served form keyed by a digest of
every stored row it was read from. It does not retain a repository catalogue
or an issued baseline: the form reader admits the edit baseline afresh on
every read and serves the kept form with that new baseline. It also keeps how
to read that last served form again: once an export that wrote has settled,
the session reads it again in the background under its new key, keeping the
result only in this memory and only if nothing the form reads moved meanwhile.
The owning composition clears this private session memory, and the refresh
with it, on sign-out, lock, handover, expiry and shutdown.
"""

from __future__ import annotations

from collections.abc import Callable, Hashable
from dataclasses import dataclass
from datetime import date
from threading import Event, Lock, Thread
from typing import TYPE_CHECKING
from uuid import UUID

if TYPE_CHECKING:
    from ..domain.calculations.registry.authority_artifact import AuthorityGenerationPin
    from .modelo.workbench_form_read_memo import WorkbenchFormReadKey
    from .modelo.workbench_projection import ModeloWorkbenchFormProjectionV1
    from .modelo.workbench_projection_memory import FormProjectionPair
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


class _Flight[KeyT: Hashable, ValueT]:
    """One background build of a slot's result, which a read for the same key waits for."""

    __slots__ = ("built", "done", "key")

    def __init__(self, key: KeyT) -> None:
        self.key = key
        self.done = Event()
        # The built result, boxed so that a result which is itself ``None`` still counts as built.
        self.built: tuple[ValueT] | None = None


class WorkbenchMemoSlot[KeyT: Hashable, ValueT]:
    """One reusable result and the input identity it was computed from.

    The key and value are swapped together under a lock, so a reader sees
    either the previous pair or the next one, never a mix. Two reads that
    compute the same work concurrently both build it; the later store wins,
    which loses nothing because both results belong to their own key.

    A :meth:`refresh` builds ahead of the read that will ask for it. One runs
    at a time, and a read asking for the key it is building waits for that
    build instead of starting its own; a read for any other key never waits.
    """

    def __init__(self) -> None:
        """Start empty."""
        self._lock = Lock()
        self._entry: tuple[KeyT, ValueT] | None = None
        self._flight: _Flight[KeyT, ValueT] | None = None
        self._closed = False

    def kept_key(self) -> KeyT | None:
        """The key of the result kept now, or ``None`` when nothing is kept."""
        with self._lock:
            entry = self._entry
        return None if entry is None else entry[0]

    def reuse(self, key: KeyT, build: Callable[[], ValueT]) -> ValueT:
        """Return the stored result for ``key``, the one being refreshed for it, or build, store and return it."""
        with self._lock:
            entry = self._entry
            flight = self._flight
            closed = self._closed
        if entry is not None and entry[0] == key:
            return entry[1]
        if flight is not None and flight.key == key:
            flight.done.wait()
            if flight.built is not None:
                return flight.built[0]
        value = build()
        if not closed:
            with self._lock:
                if not self._closed:
                    self._entry = (key, value)
        return value

    def refresh(self, key: KeyT, build: Callable[[], ValueT], *, current: Callable[[], bool]) -> bool:
        """Build and keep the result for ``key`` ahead of the read that will ask for it.

        Nothing is built when the slot is closed, already keeps ``key`` or is
        refreshing already. The result is kept only if ``current`` still holds
        once it is built, so a refresh overtaken by a newer input keeps nothing.
        Answers whether it kept a result.
        """
        flight: _Flight[KeyT, ValueT] = _Flight(key)
        with self._lock:
            entry = self._entry
            if self._closed or self._flight is not None or (entry is not None and entry[0] == key):
                return False
            self._flight = flight
        kept = False
        try:
            value = build()
            flight.built = (value,)
            fresh = current()
            with self._lock:
                if fresh and not self._closed:
                    self._entry = (key, value)
                    kept = True
        finally:
            with self._lock:
                if self._flight is flight:
                    self._flight = None
            flight.done.set()
        return kept

    def close(self) -> None:
        """Drop the stored result and store nothing further."""
        with self._lock:
            self._closed = True
            self._entry = None

    def clear(self) -> None:
        """Discard a result without reopening a closed slot or ending its session."""
        with self._lock:
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
    related_party_revision: str = "unbound"
    """The Modelo 232 statements the related-party obligation fact is derived from."""


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
        self.form_projection: WorkbenchMemoSlot[Hashable, FormProjectionPair | None] = WorkbenchMemoSlot()
        self.form_read: WorkbenchMemoSlot[WorkbenchFormReadKey, ModeloWorkbenchFormProjectionV1] = WorkbenchMemoSlot()
        self._refresh_lock = Lock()
        self._form_refresh: Callable[[], None] | None = None
        self._closed = False

    def keep_form_refresh(self, refresh: Callable[[], None]) -> None:
        """Keep how to read again the form this session was last served, for :meth:`refresh_form`."""
        with self._refresh_lock:
            if not self._closed:
                self._form_refresh = refresh

    def refresh_form(self) -> Thread | None:
        """Read the last served form again in the background, so the read that returns to it finds it kept.

        Returns the started thread, or ``None`` when this session was served no
        form or has ended. The refresh keeps its result only in this memory.
        """
        with self._refresh_lock:
            refresh = None if self._closed else self._form_refresh
        if refresh is None:
            return None
        thread = Thread(target=refresh, name="workbench-form-refresh", daemon=True)
        thread.start()
        return thread

    def close(self) -> None:
        """Drop every stored result deterministically when the session ends."""
        with self._refresh_lock:
            self._closed = True
            self._form_refresh = None
        self.calendar.close()
        self.census.close()
        self.form_projection.close()
        self.form_read.close()


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

    def refresh_settled_form(self) -> Thread | None:
        """Refresh the held session's last served form after an operation changed what it is read from."""
        with self._lock:
            held = self._held
        return None if held is None else held[1].refresh_form()

    def close(self) -> None:
        """Drop the held memory; the next read starts an empty one."""
        with self._lock:
            held, self._held = self._held, None
        if held is not None:
            held[1].close()
