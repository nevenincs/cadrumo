"""Proofs for the setup registry: closed enrolment, state derivation, recovery buttons and bounded checks."""

from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import override

import pytest

from cadrumo_client.contracts.failure_categories import DependencyFailureCategory

from ...core.model_catalogue import ModelRole
from ..dependency_contracts import (
    DEPENDENCY_FULL_CHECK_ITEM_BUDGET_S,
    DEPENDENCY_QUICK_CHECK_BUDGET_S,
    DependencyActivity,
    DependencyBlockedReason,
    DependencyCheckMode,
    DependencyItemDeclaration,
    DependencyNote,
    DependencyPlanEntry,
    DependencyProbeOutcome,
    DependencyProbeReading,
    DependencyProvisionResult,
    DependencyRecoveryAction,
    DependencySetupEvents,
    DependencySetupStep,
    DependencyStaleReason,
    DependencyState,
)
from ..dependency_registry import (
    BROWSER_DECLARATION,
    LOCAL_AI_DECLARATION,
    DependencyRegistry,
    DependencySelectionError,
    build_setup_plan,
    dependency_item_declarations,
    derive_dependency_row,
    is_setup_complete,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


class _Checker:
    """Checker answering a fixed outcome, with no way to set its item up."""

    def __init__(
        self,
        declaration: DependencyItemDeclaration,
        outcome: DependencyProbeOutcome = DependencyProbeOutcome.PRESENT,
        *,
        delay_s: float = 0.0,
    ) -> None:
        self._declaration = declaration
        self._outcome = outcome
        self._delay_s = delay_s
        self.modes: list[DependencyCheckMode] = []

    @property
    def declaration(self) -> DependencyItemDeclaration:
        return self._declaration

    async def check(self, mode: DependencyCheckMode) -> DependencyProbeReading:
        self.modes.append(mode)
        if self._delay_s:
            await asyncio.sleep(self._delay_s)
        return DependencyProbeReading(item_id=self._declaration.item_id, mode=mode, outcome=self._outcome)


class _Provisioner(_Checker):
    async def plan(self, *, model_name: str | None) -> DependencyPlanEntry:
        del model_name
        return DependencyPlanEntry(
            item_id=self.declaration.item_id,
            download_bytes=10,
            source_hosts=("example.org",),
            destination=self.declaration.storage_category,
        )

    async def provision(self, entry: DependencyPlanEntry, events: DependencySetupEvents) -> DependencyProvisionResult:
        await events.step(DependencySetupStep.DOWNLOAD)
        return DependencyProvisionResult(item_id=entry.item_id, changed=True)


class _Events:
    def __init__(self) -> None:
        self.steps: list[DependencySetupStep] = []

    async def step(self, step: DependencySetupStep) -> None:
        self.steps.append(step)

    async def transferred(self, *, completed: int, total: int | None) -> None:
        del completed, total

    async def retrying(self, *, attempt: int, delay_s: float) -> None:
        del attempt, delay_s

    @property
    def cancellation_requested(self) -> bool:
        return False

    @asynccontextmanager
    async def irreversible(self) -> AsyncGenerator[None]:
        yield


def _provisioners() -> list[_Checker]:
    return [_Provisioner(declaration) for declaration in dependency_item_declarations()]


def _reading(item_id: str, outcome: DependencyProbeOutcome, **fields: object) -> DependencyProbeReading:
    return DependencyProbeReading.model_validate(
        {"item_id": item_id, "mode": DependencyCheckMode.QUICK, "outcome": outcome, **fields}
    )


def test_declarations_are_the_browser_then_the_local_ai_and_nothing_of_the_profile() -> None:
    declarations = dependency_item_declarations()
    assert [declaration.item_id for declaration in declarations] == ["browser", "local_ai"]
    assert LOCAL_AI_DECLARATION.installs_outside_program is True
    assert LOCAL_AI_DECLARATION.display_key == "provisioning.dependency.local_ai.name"
    # The local AI's full check covers its program and every role's model.
    assert LOCAL_AI_DECLARATION.full_check_budget_s == DEPENDENCY_FULL_CHECK_ITEM_BUDGET_S * (1 + len(ModelRole))
    assert BROWSER_DECLARATION.full_check_budget_s == DEPENDENCY_FULL_CHECK_ITEM_BUDGET_S
    assert {declaration.recovery_action_id for declaration in declarations} == {
        "operator.provision.browser",
        "operator.provision.local_ai",
    }


def test_registry_enrols_exactly_one_matching_provisioner_per_declared_item() -> None:
    registry = DependencyRegistry(_provisioners())
    assert registry.declarations == dependency_item_declarations()
    assert isinstance(registry.provisioner("browser"), _Provisioner)

    full = _provisioners()
    with pytest.raises(ValueError, match="missing"):
        DependencyRegistry(full[1:])
    with pytest.raises(ValueError, match="twice"):
        DependencyRegistry([*full, full[0]])
    with pytest.raises(ValueError, match="another declaration"):
        DependencyRegistry(
            [_Provisioner(BROWSER_DECLARATION.model_copy(update={"network_host_group": "other"})), *full[1:]]
        )
    with pytest.raises(ValueError, match="needs a provisioner"):
        DependencyRegistry([_Checker(BROWSER_DECLARATION), *full[1:]])


def test_registry_refuses_items_it_does_not_declare() -> None:
    registry = DependencyRegistry(_provisioners())
    for unknown in ("chromium", "google", "model_runtime"):
        with pytest.raises(DependencySelectionError, match="not a setup item"):
            registry.declaration(unknown)
        with pytest.raises(DependencySelectionError):
            registry.provisioner(unknown)
    with pytest.raises(DependencySelectionError):
        registry.select_setup_items((), requested=("google",))


def test_running_work_wins_then_unknown_then_the_probe() -> None:
    absent = _reading("browser", DependencyProbeOutcome.ABSENT)
    for step in DependencySetupStep:
        row = derive_dependency_row(
            BROWSER_DECLARATION, absent, activity=DependencyActivity(item_id="browser", step=step)
        )
        expected = DependencyState.VERIFYING if step is DependencySetupStep.VERIFY else DependencyState.PROVISIONING
        assert row.state is expected
        assert row.recovery is None

    unreadable = derive_dependency_row(BROWSER_DECLARATION, _reading("browser", DependencyProbeOutcome.UNREADABLE))
    assert unreadable.state is DependencyState.UNKNOWN
    assert unreadable.recovery is DependencyRecoveryAction.CHECK_AGAIN

    unreadable_after_failure = derive_dependency_row(
        BROWSER_DECLARATION,
        _reading("browser", DependencyProbeOutcome.UNREADABLE),
        last_failure=DependencyFailureCategory.INTERRUPTED,
    )
    assert unreadable_after_failure.state is DependencyState.UNKNOWN


def test_settled_failure_shows_only_while_the_probe_still_finds_nothing() -> None:
    interrupted = derive_dependency_row(
        BROWSER_DECLARATION,
        _reading("browser", DependencyProbeOutcome.ABSENT),
        last_failure=DependencyFailureCategory.INTERRUPTED,
    )
    assert interrupted.state is DependencyState.FAILED
    assert interrupted.failure_category is DependencyFailureCategory.INTERRUPTED
    assert interrupted.recovery is DependencyRecoveryAction.RESUME
    assert interrupted.recovery_action_id == "operator.provision.browser"

    observed = derive_dependency_row(
        LOCAL_AI_DECLARATION,
        _reading("local_ai", DependencyProbeOutcome.PRESENT, note=DependencyNote.DOWNLOADED_NOT_LOADED),
        last_failure=DependencyFailureCategory.INTERRUPTED,
    )
    assert observed.state is DependencyState.READY
    assert observed.failure_category is None
    assert observed.note is DependencyNote.DOWNLOADED_NOT_LOADED
    assert observed.recovery is None


def test_recovery_buttons_follow_state_and_reason() -> None:
    cases = (
        (BROWSER_DECLARATION, _reading("browser", DependencyProbeOutcome.ABSENT), DependencyRecoveryAction.SET_UP),
        (
            BROWSER_DECLARATION,
            _reading("browser", DependencyProbeOutcome.DIFFERS, stale_reason=DependencyStaleReason.OLDER_REVISION),
            DependencyRecoveryAction.UPDATE,
        ),
        (
            LOCAL_AI_DECLARATION,
            _reading("local_ai", DependencyProbeOutcome.DIFFERS, stale_reason=DependencyStaleReason.PROGRAM_TOO_OLD),
            DependencyRecoveryAction.UPDATE,
        ),
        (
            BROWSER_DECLARATION,
            _reading("browser", DependencyProbeOutcome.BLOCKED, blocked_reason=DependencyBlockedReason.OFFLINE),
            DependencyRecoveryAction.CHECK_AGAIN,
        ),
        (
            LOCAL_AI_DECLARATION,
            _reading("local_ai", DependencyProbeOutcome.BLOCKED, blocked_reason=DependencyBlockedReason.NEEDS_PERSON),
            DependencyRecoveryAction.SET_UP,
        ),
        (
            LOCAL_AI_DECLARATION,
            _reading("local_ai", DependencyProbeOutcome.BLOCKED, blocked_reason=DependencyBlockedReason.HARDWARE),
            None,
        ),
        (
            BROWSER_DECLARATION,
            _reading(
                "browser", DependencyProbeOutcome.BLOCKED, blocked_reason=DependencyBlockedReason.NOT_IN_THIS_BUILD
            ),
            None,
        ),
        (
            BROWSER_DECLARATION,
            _reading("browser", DependencyProbeOutcome.FAILED, failure_category=DependencyFailureCategory.DISK_FULL),
            DependencyRecoveryAction.TRY_AGAIN,
        ),
        (
            LOCAL_AI_DECLARATION,
            _reading(
                "local_ai", DependencyProbeOutcome.FAILED, failure_category=DependencyFailureCategory.NOT_ENOUGH_MEMORY
            ),
            None,
        ),
        (
            LOCAL_AI_DECLARATION,
            _reading(
                "local_ai", DependencyProbeOutcome.FAILED, failure_category=DependencyFailureCategory.NEEDS_SIGN_IN
            ),
            DependencyRecoveryAction.TRY_AGAIN,
        ),
    )
    for declaration, reading, expected in cases:
        row = derive_dependency_row(declaration, reading)
        assert row.recovery is expected, (declaration.item_id, reading.outcome)
        assert (row.recovery_action_id is None) == (expected is None)


def test_setup_is_complete_when_every_item_is_ready_or_stale() -> None:
    ready = derive_dependency_row(BROWSER_DECLARATION, _reading("browser", DependencyProbeOutcome.PRESENT))
    stale = derive_dependency_row(
        LOCAL_AI_DECLARATION,
        _reading(
            "local_ai", DependencyProbeOutcome.DIFFERS, stale_reason=DependencyStaleReason.DIFFERENT_MODEL_VERSION
        ),
    )
    unknown = derive_dependency_row(BROWSER_DECLARATION, _reading("browser", DependencyProbeOutcome.UNREADABLE))
    assert is_setup_complete((ready, stale)) is True
    assert is_setup_complete((ready, unknown)) is False


def test_default_selection_skips_ready_running_and_unfixable_items() -> None:
    registry = DependencyRegistry(_provisioners())
    absent = derive_dependency_row(BROWSER_DECLARATION, _reading("browser", DependencyProbeOutcome.ABSENT))
    stale = derive_dependency_row(
        LOCAL_AI_DECLARATION,
        _reading(
            "local_ai", DependencyProbeOutcome.DIFFERS, stale_reason=DependencyStaleReason.DIFFERENT_MODEL_VERSION
        ),
    )
    running = derive_dependency_row(
        LOCAL_AI_DECLARATION,
        _reading("local_ai", DependencyProbeOutcome.ABSENT),
        activity=DependencyActivity(item_id="local_ai", step=DependencySetupStep.DOWNLOAD),
    )
    hardware = derive_dependency_row(
        LOCAL_AI_DECLARATION,
        _reading("local_ai", DependencyProbeOutcome.BLOCKED, blocked_reason=DependencyBlockedReason.HARDWARE),
    )
    selected = registry.select_setup_items
    assert [declaration.item_id for declaration in selected((absent, stale))] == ["browser", "local_ai"]
    assert [declaration.item_id for declaration in selected((absent, running))] == ["browser"]
    assert [declaration.item_id for declaration in selected((absent, hardware))] == ["browser"]

    requested = registry.select_setup_items((absent, hardware), requested=("local_ai", "browser"))
    assert [declaration.item_id for declaration in requested] == ["browser", "local_ai"]


def test_quick_rows_answer_inside_the_budget_and_a_late_probe_reads_unknown() -> None:
    checkers = _provisioners()
    checkers[0] = _Provisioner(BROWSER_DECLARATION, delay_s=30.0)
    registry = DependencyRegistry(checkers)

    started = time.monotonic()
    rows = asyncio.run(registry.read_rows(DependencyCheckMode.QUICK))
    elapsed = time.monotonic() - started

    assert elapsed < DEPENDENCY_QUICK_CHECK_BUDGET_S + 1.0
    assert rows[0].item_id == "browser"
    assert rows[0].state is DependencyState.UNKNOWN
    assert all(row.state is DependencyState.READY for row in rows[1:])
    assert all(row.mode is DependencyCheckMode.QUICK for row in rows)


def test_full_rows_check_selected_items_in_order_and_apply_running_work() -> None:
    checkers = _provisioners()
    registry = DependencyRegistry(checkers)
    rows = asyncio.run(
        registry.read_rows(
            DependencyCheckMode.FULL,
            item_ids=("local_ai", "browser"),
            activities=(DependencyActivity(item_id="browser", step=DependencySetupStep.VERIFY),),
        )
    )
    assert [row.item_id for row in rows] == ["browser", "local_ai"]
    assert rows[0].state is DependencyState.VERIFYING
    assert rows[1].state is DependencyState.READY
    assert checkers[0].modes == [DependencyCheckMode.FULL]
    assert checkers[1].modes == [DependencyCheckMode.FULL]
    with pytest.raises(DependencySelectionError):
        asyncio.run(registry.read_rows(DependencyCheckMode.FULL, item_ids=("chromium",)))


def test_a_reading_for_another_item_or_mode_reads_unknown() -> None:
    class _Mislabelled(_Provisioner):
        @override
        async def check(self, mode: DependencyCheckMode) -> DependencyProbeReading:
            del mode
            return DependencyProbeReading(
                item_id="browser", mode=DependencyCheckMode.QUICK, outcome=DependencyProbeOutcome.PRESENT
            )

    checkers = _provisioners()
    checkers[0] = _Mislabelled(BROWSER_DECLARATION)
    rows = asyncio.run(DependencyRegistry(checkers).read_rows(DependencyCheckMode.FULL, item_ids=("browser",)))
    assert rows[0].state is DependencyState.UNKNOWN


def test_built_plan_follows_entry_order_and_the_space_rule() -> None:
    registry = DependencyRegistry(_provisioners())
    events = _Events()
    provisioner = registry.provisioner("browser")
    entry = asyncio.run(provisioner.plan(model_name=None))
    result = asyncio.run(provisioner.provision(entry, events))
    assert result.changed is True
    assert events.steps == [DependencySetupStep.DOWNLOAD]
    assert isinstance(events, DependencySetupEvents)

    plan = build_setup_plan((entry,), free_bytes=None)
    assert plan.space.required_bytes == 12 + 1024**3
    assert plan.space.sufficient is False


def test_full_checks_hold_unusable_items_against_one_preflight_per_host_group() -> None:
    asked: list[tuple[str, ...]] = []

    async def offline(hosts: tuple[str, ...]) -> DependencyFailureCategory | None:
        asked.append(hosts)
        return DependencyFailureCategory.OFFLINE

    checkers: list[_Checker] = [
        _Provisioner(BROWSER_DECLARATION, DependencyProbeOutcome.PRESENT),
        _Provisioner(LOCAL_AI_DECLARATION, DependencyProbeOutcome.ABSENT),
    ]
    registry = DependencyRegistry(checkers, reachability=offline, hosts_for=lambda group: (f"{group}.example.org",))
    rows = asyncio.run(registry.read_rows(DependencyCheckMode.FULL))
    by_id = {row.item_id: row for row in rows}

    assert by_id["browser"].state is DependencyState.READY
    assert by_id["local_ai"].state is DependencyState.BLOCKED
    assert by_id["local_ai"].blocked_reason is DependencyBlockedReason.OFFLINE
    assert asked == [("local_ai.example.org",)]
    with pytest.raises(ValueError, match="both"):
        DependencyRegistry(_provisioners(), reachability=offline)


def test_a_reachable_failure_marks_the_item_failed_with_the_network_category() -> None:
    async def blocked(hosts: tuple[str, ...]) -> DependencyFailureCategory | None:
        del hosts
        return DependencyFailureCategory.BLOCKED_BY_NETWORK

    checkers = _provisioners()
    checkers[0] = _Provisioner(BROWSER_DECLARATION, DependencyProbeOutcome.ABSENT)
    registry = DependencyRegistry(checkers, reachability=blocked, hosts_for=lambda group: (f"{group}.example.org",))
    (row,) = asyncio.run(registry.read_rows(DependencyCheckMode.FULL, item_ids=("browser",)))
    assert row.state is DependencyState.FAILED
    assert row.failure_category is DependencyFailureCategory.BLOCKED_BY_NETWORK
    assert row.recovery is DependencyRecoveryAction.TRY_AGAIN
