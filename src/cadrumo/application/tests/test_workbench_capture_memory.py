"""A session's capture memory reuses calendar work only while its exact inputs are unchanged.

The door under test is the production one; the stores are the in-memory
repository doubles the generation contract tests already use, because the
question here is what the door recomputes, not how a store persists. Calendar
builds are counted by observing the real builder, never by replacing it.
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any, cast

import pytest

from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.modelos.calculation_revision import CalculationRevisionCatalogue
from ...domain.modelos.filing_record import ModeloRecordCatalogue
from ...domain.modelos.work_unit import WorkUnitCatalogue
from ...domain.user_profile.values import ProfileSetupState, UserProfileRecord, create_user_profile_record
from ..overview.home import HomeAccountSession, HomeSessionPosture
from ..workbench_capture_memory import WorkbenchCaptureMemory, WorkbenchCaptureMemoryOwner, WorkbenchMemoSlot
from ..workbench_generation import (
    InstalledWorkbenchGenerationProviderV1,
)
from ..workbench_generation_contracts import WorkbenchGenerationV1
from ..workbench_generation_reader import SecureProfileWorkbenchGenerationReadDoorV1
from .workbench_generation_support import calendar_builds

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFILE_ID = "11111111-1111-4111-8111-111111111111"
_NOW = datetime(2026, 9, 3, 10, 30, tzinfo=UTC)


@dataclass
class _Store[ValueT]:
    """A store whose revision the test advances to model a committed write."""

    value: ValueT
    revision: str = "revision-1"

    def load(self, *_args: object) -> ValueT:
        return self.value

    def load_revisioned(self, *, operation: object | None = None) -> tuple[ValueT, str]:
        return self.value, self.revision


def _record(operation: PinnedAuthorityOperation, *, name: str = "Ada") -> UserProfileRecord:
    from ...domain.user_profile.values import UserProfileFact

    return create_user_profile_record(
        context=operation.profile_create_context(),
        profile_id=_PROFILE_ID,
        setup_state=ProfileSetupState.INCOMPLETE,
        facts=(UserProfileFact(path="identity.name", value=name),),
    )


@dataclass
class _Session:
    operation: PinnedAuthorityOperation
    profile: _Store[UserProfileRecord]
    work_units: _Store[WorkUnitCatalogue]
    filings: _Store[ModeloRecordCatalogue]
    now: datetime = _NOW

    def door(self, memory: WorkbenchCaptureMemory | None) -> SecureProfileWorkbenchGenerationReadDoorV1:
        return SecureProfileWorkbenchGenerationReadDoorV1(
            profile_id=_PROFILE_ID,
            operation=self.operation,
            profile_repository=cast(Any, self.profile),
            work_unit_repository=cast(Any, self.work_units),
            calculation_repository=cast(Any, _Store(CalculationRevisionCatalogue())),
            filing_repository=cast(Any, self.filings),
            clock=lambda: self.now,
            account_session_reader=lambda: HomeAccountSession(
                posture=HomeSessionPosture.ACTIVE,
                profile_label="Perfil local",
                expires_at=self.now + timedelta(hours=1),
            ),
            capture_memory=memory,
        )

    def capture(self, memory: WorkbenchCaptureMemory | None) -> WorkbenchGenerationV1:
        return InstalledWorkbenchGenerationProviderV1(self.door(memory))()


def _session(operation: PinnedAuthorityOperation) -> _Session:
    return _Session(
        operation=operation,
        profile=_Store(_record(operation)),
        work_units=_Store(WorkUnitCatalogue()),
        filings=_Store(ModeloRecordCatalogue()),
    )


def _without_compute_instants(value: object) -> object:
    """Drop the instants a calendar records for when it was computed; nothing else."""
    if isinstance(value, dict):
        return {key: _without_compute_instants(item) for key, item in value.items() if key != "generated_at"}
    if isinstance(value, list):
        return [_without_compute_instants(item) for item in value]
    return value


def _comparable(generation: WorkbenchGenerationV1) -> object:
    return _without_compute_instants(generation.model_dump(mode="json"))


def test_an_unchanged_session_reuses_its_calendar_and_publishes_the_same_generation(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    session = _session(authority_operation)
    memory = WorkbenchCaptureMemory()

    first_builds = calendar_builds(lambda: session.capture(memory))
    reused: list[WorkbenchGenerationV1] = []
    reuse_builds = calendar_builds(lambda: reused.append(session.capture(memory)))
    fresh = session.capture(None)

    assert first_builds > 0
    assert reuse_builds == 0, "an unchanged capture must not rebuild the calendar"
    assert _comparable(reused[0]) == _comparable(fresh)


def test_the_counter_detects_rebuilding_on_every_capture(authority_operation: PinnedAuthorityOperation) -> None:
    session = _session(authority_operation)

    first = calendar_builds(lambda: session.capture(None))
    second = calendar_builds(lambda: session.capture(None))

    assert first > 0
    assert second == first, "without a memory every capture rebuilds, and the counter sees it"


@pytest.mark.parametrize("change", ["profile", "work_units", "filings", "date"])
def test_any_changed_input_rebuilds_the_calendar(authority_operation: PinnedAuthorityOperation, change: str) -> None:
    session = _session(authority_operation)
    memory = WorkbenchCaptureMemory()
    session.capture(memory)

    if change == "profile":
        session.profile.value = _record(authority_operation, name="Babbage")
    elif change == "work_units":
        session.work_units.revision = "revision-2"
    elif change == "filings":
        session.filings.revision = "revision-2"
    else:
        session.now = _NOW + timedelta(days=1)
    changed: list[WorkbenchGenerationV1] = []
    builds = calendar_builds(lambda: changed.append(session.capture(memory)))

    assert builds > 0, f"a changed {change} must not be served from memory"
    assert _comparable(changed[0]) == _comparable(session.capture(None))


def test_a_closed_memory_serves_and_keeps_nothing(authority_operation: PinnedAuthorityOperation) -> None:
    session = _session(authority_operation)
    memory = WorkbenchCaptureMemory()
    session.capture(memory)
    memory.close()

    after_close = calendar_builds(lambda: session.capture(memory))
    again = calendar_builds(lambda: session.capture(memory))

    assert after_close > 0
    assert again == after_close, "a closed memory must not start storing again"


def test_a_slot_never_hands_one_key_another_keys_value() -> None:
    slot: WorkbenchMemoSlot[int, tuple[int, int]] = WorkbenchMemoSlot()
    mismatches: list[tuple[int, tuple[int, int]]] = []

    def worker(offset: int) -> None:
        for step in range(2000):
            key = (offset + step) % 7
            value = slot.reuse(key, lambda key=key: (key, key * key))
            if value != (key, key * key):
                mismatches.append((key, value))

    threads = [threading.Thread(target=worker, args=(offset,)) for offset in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert mismatches == []


def test_a_slot_builds_once_per_unchanged_key() -> None:
    slot: WorkbenchMemoSlot[date, str] = WorkbenchMemoSlot()
    builds: list[date] = []

    def build(day: date) -> Callable[[], str]:
        def run() -> str:
            builds.append(day)
            return day.isoformat()

        return run

    today, tomorrow = date(2026, 9, 3), date(2026, 9, 4)
    assert slot.reuse(today, build(today)) == "2026-09-03"
    assert slot.reuse(today, build(today)) == "2026-09-03"
    assert slot.reuse(tomorrow, build(tomorrow)) == "2026-09-04"
    assert slot.reuse(today, build(today)) == "2026-09-03"
    assert builds == [today, tomorrow, today]


def test_a_slot_names_the_key_of_the_result_it_keeps() -> None:
    slot: WorkbenchMemoSlot[str, str] = WorkbenchMemoSlot()
    assert slot.kept_key() is None
    slot.reuse("first", lambda: "a")
    assert slot.kept_key() == "first"
    slot.reuse("second", lambda: "b")
    assert slot.kept_key() == "second"
    slot.clear()
    assert slot.kept_key() is None


def test_a_refreshed_result_is_served_without_building_again() -> None:
    slot: WorkbenchMemoSlot[str, str] = WorkbenchMemoSlot()
    builds: list[str] = []

    def build() -> str:
        builds.append("next")
        return "built"

    assert slot.refresh("next", lambda: "refreshed", current=lambda: True)
    assert slot.reuse("next", build) == "refreshed"
    assert builds == []
    assert not slot.refresh("next", lambda: "again", current=lambda: True), "a kept key was refreshed again"


def test_a_refresh_overtaken_by_a_newer_input_keeps_nothing() -> None:
    slot: WorkbenchMemoSlot[str, str] = WorkbenchMemoSlot()

    assert not slot.refresh("next", lambda: "stale", current=lambda: False)
    assert slot.kept_key() is None
    assert slot.reuse("next", lambda: "built") == "built"


def test_a_read_for_the_key_being_refreshed_joins_the_refresh() -> None:
    slot: WorkbenchMemoSlot[str, str] = WorkbenchMemoSlot()
    started, release = threading.Event(), threading.Event()
    builds: list[str] = []

    def refreshing() -> str:
        started.set()
        release.wait()
        builds.append("refresh")
        return "refreshed"

    def read() -> str:
        builds.append("read")
        return "built"

    refresh = threading.Thread(target=lambda: slot.refresh("next", refreshing, current=lambda: True))
    refresh.start()
    started.wait()
    served: list[str] = []
    joining = threading.Thread(target=lambda: served.append(slot.reuse("next", read)))
    joining.start()
    release.set()
    joining.join()
    refresh.join()

    assert served == ["refreshed"]
    assert builds == ["refresh"]


def test_a_read_for_another_key_never_waits_for_a_refresh() -> None:
    slot: WorkbenchMemoSlot[str, str] = WorkbenchMemoSlot()
    started, release = threading.Event(), threading.Event()

    def refreshing() -> str:
        started.set()
        release.wait()
        return "refreshed"

    refresh = threading.Thread(target=lambda: slot.refresh("next", refreshing, current=lambda: True))
    refresh.start()
    started.wait()
    try:
        assert slot.reuse("other", lambda: "built") == "built"
        assert not slot.refresh("other", lambda: "second", current=lambda: True), "two refreshes ran at once"
    finally:
        release.set()
        refresh.join()


def test_a_read_joining_a_failed_refresh_builds_itself() -> None:
    slot: WorkbenchMemoSlot[str, str] = WorkbenchMemoSlot()
    started, release = threading.Event(), threading.Event()

    def failing() -> str:
        started.set()
        release.wait()
        raise RuntimeError("refresh failed")

    def refresh() -> None:
        with pytest.raises(RuntimeError):
            slot.refresh("next", failing, current=lambda: True)

    refreshing = threading.Thread(target=refresh)
    refreshing.start()
    started.wait()
    served: list[str] = []
    joining = threading.Thread(target=lambda: served.append(slot.reuse("next", lambda: "built")))
    joining.start()
    release.set()
    joining.join()
    refreshing.join()

    assert served == ["built"]


def test_a_closed_slot_keeps_no_refresh() -> None:
    slot: WorkbenchMemoSlot[str, str] = WorkbenchMemoSlot()
    slot.close()

    assert not slot.refresh("next", lambda: "refreshed", current=lambda: True)
    assert slot.kept_key() is None


def test_an_ended_or_replaced_session_starts_no_form_refresh() -> None:
    owner = WorkbenchCaptureMemoryOwner()
    ran: list[str] = []
    owner.for_profile("first").keep_form_refresh(lambda: ran.append("first"))
    owner.for_profile("second")
    assert owner.refresh_settled_form() is None

    owner.for_profile("second").keep_form_refresh(lambda: ran.append("second"))
    owner.close()
    assert owner.refresh_settled_form() is None

    memory = owner.for_profile("third")
    memory.keep_form_refresh(lambda: ran.append("third"))
    started = owner.refresh_settled_form()
    assert started is not None
    started.join()
    memory.close()
    memory.keep_form_refresh(lambda: ran.append("after close"))
    assert memory.refresh_form() is None
    assert ran == ["third"]


def _kept(memory: WorkbenchCaptureMemory) -> bool:
    """Whether the memory still stores and serves work: a second reuse of one key builds nothing."""
    key = cast(Any, object())
    builds: list[int] = []

    def build() -> Any:
        builds.append(1)
        return cast(Any, object())

    memory.calendar.reuse(key, build)
    memory.calendar.reuse(key, build)
    return len(builds) == 1


def test_an_owner_hands_one_profile_the_same_open_memory() -> None:
    owner = WorkbenchCaptureMemoryOwner()

    memory = owner.for_profile(_PROFILE_ID)

    assert owner.for_profile(_PROFILE_ID) is memory
    assert _kept(memory)


def test_form_memory_cannot_be_filled_after_session_close_or_reused_after_handover() -> None:
    owner = WorkbenchCaptureMemoryOwner()
    memory = owner.for_profile(_PROFILE_ID)
    builds: list[str] = []

    def end_session_during_build() -> None:
        builds.append("closed-during-build")
        owner.close()

    memory.form_projection.reuse("same-input", end_session_during_build)
    memory.form_projection.clear()
    memory.form_projection.reuse("same-input", lambda: builds.append("closed-reader"))
    assert builds == ["closed-during-build", "closed-reader"]
    fresh = owner.for_profile(_PROFILE_ID)
    fresh.form_projection.reuse("same-input", lambda: builds.append("fresh"))
    fresh.form_projection.reuse("same-input", lambda: builds.append("must-not-build"))
    assert builds[-1] == "fresh"
    owner.for_profile("22222222-2222-4222-8222-222222222222")
    fresh.form_projection.reuse("same-input", lambda: builds.append("handed-over"))
    assert builds[-1] == "handed-over"


def test_another_profile_closes_the_memory_the_first_kept() -> None:
    owner = WorkbenchCaptureMemoryOwner()
    first = owner.for_profile(_PROFILE_ID)

    second = owner.for_profile("22222222-2222-4222-8222-222222222222")

    assert second is not first
    assert not _kept(first), "a closed memory stores nothing for the previous profile"
    assert _kept(second)


def test_a_session_end_closes_the_memory_and_the_next_read_starts_empty() -> None:
    owner = WorkbenchCaptureMemoryOwner()
    before = owner.for_profile(_PROFILE_ID)
    key = cast(Any, object())
    kept = cast(Any, object())
    before.calendar.reuse(key, lambda: kept)

    owner.close()

    after = owner.for_profile(_PROFILE_ID)
    assert after is not before
    assert not _kept(before), "a capture still holding the closed memory stores nothing"
    assert after.calendar.reuse(key, lambda: cast(Any, object())) is not kept, "nothing kept before the end is served"
    owner.close()
    owner.close()
