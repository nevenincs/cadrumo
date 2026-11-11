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
from ...domain.calculations.registry.tests.authored_editions import filing_year_envelope
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
_YEAR = filing_year_envelope().horizon
_NOW = datetime(_YEAR, 9, 3, 10, 30, tzinfo=UTC)


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
        for step in range(1024):
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

    today, tomorrow = date(_YEAR, 9, 3), date(_YEAR, 9, 4)
    assert slot.reuse(today, build(today)) == today.isoformat()
    assert slot.reuse(today, build(today)) == today.isoformat()
    assert slot.reuse(tomorrow, build(tomorrow)) == tomorrow.isoformat()
    assert slot.reuse(today, build(today)) == today.isoformat()
    assert builds == [today, tomorrow, today]


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
