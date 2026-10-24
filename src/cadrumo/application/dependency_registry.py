"""The one registry of setup items and the rules that turn probe readings into item states.

Every surface -- ``aeat config check``, the health report, ``config provision
status``, the TUI, MCP and the desktop -- reads item status through
:class:`DependencyRegistry`, so the states, their order and their recovery
buttons are the same everywhere. The item set is closed: a registry is built
from one checker per declared item and refuses a missing, extra or redeclared
item, which is what keeps a new outside dependency from appearing on one
surface only.

The registry calls each item through the ports in
:mod:`~cadrumo.application.dependency_contracts`; it never imports an item's
implementation. The composition root binds the browser and local AI
provisioners to their declarations.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Iterable, Mapping, Sequence
from typing import Final

from cadrumo_client.contracts.failure_categories import DependencyFailureCategory

from ..core.errors.hierarchy import CadrumoError
from ..core.model_catalogue import ModelRole
from ..core.storage_taxonomy import StorageCategory
from .dependency_contracts import (
    DEPENDENCY_FULL_CHECK_ITEM_BUDGET_S,
    DEPENDENCY_QUICK_CHECK_BUDGET_S,
    DependencyActivity,
    DependencyBlockedReason,
    DependencyCheckMode,
    DependencyItemChecker,
    DependencyItemDeclaration,
    DependencyItemKind,
    DependencyItemProvisioner,
    DependencyPlanEntry,
    DependencyProbeOutcome,
    DependencyProbeReading,
    DependencyRecoveryAction,
    DependencySetupPlan,
    DependencySetupStep,
    DependencySpaceCheck,
    DependencyStaleReason,
    DependencyState,
    DependencyStatusRow,
    known_download_bytes_of,
    required_free_bytes,
)

__all__ = [
    "BROWSER_DECLARATION",
    "LOCAL_AI_DECLARATION",
    "DependencyReachability",
    "DependencyRegistry",
    "DependencySelectionError",
    "build_setup_plan",
    "dependency_item_declarations",
    "derive_dependency_row",
    "is_setup_complete",
    "recovery_action_for",
]

BROWSER_DECLARATION: Final = DependencyItemDeclaration(
    item_id=DependencyItemKind.BROWSER.value,
    kind=DependencyItemKind.BROWSER,
    display_key="provisioning.dependency.browser.name",
    network_host_group="browser",
    storage_category=StorageCategory.PLAYWRIGHT_BROWSERS,
    recovery_action_id="operator.provision.browser",
)

LOCAL_AI_DECLARATION: Final = DependencyItemDeclaration(
    item_id=DependencyItemKind.LOCAL_AI.value,
    kind=DependencyItemKind.LOCAL_AI,
    display_key="provisioning.dependency.local_ai.name",
    network_host_group="local_ai",
    storage_category=StorageCategory.OLLAMA_MODELS,
    recovery_action_id="operator.provision.local_ai",
    installs_outside_program=True,
    # The program and every role's model each get the bound one item has.
    full_check_budget_s=DEPENDENCY_FULL_CHECK_ITEM_BUDGET_S * (1 + len(ModelRole)),
)


def dependency_item_declarations() -> tuple[DependencyItemDeclaration, ...]:
    """Return every setup item in setup order: the browser, then the local AI.

    The setup operation runs them one at a time in this order.
    """
    return (BROWSER_DECLARATION, LOCAL_AI_DECLARATION)


class DependencySelectionError(CadrumoError):
    """A requested setup item is unknown."""

    def __init__(self, item_id: str, *, reason: str) -> None:
        """Name the refused item and why it cannot be selected."""
        super().__init__(f"setup item {item_id!r} cannot be selected: {reason}")
        self.item_id = item_id
        self.reason = reason


def _installable_here(row: DependencyStatusRow) -> bool:
    return row.blocked_reason not in {DependencyBlockedReason.HARDWARE, DependencyBlockedReason.NOT_IN_THIS_BUILD}


def derive_dependency_row(
    declaration: DependencyItemDeclaration,
    reading: DependencyProbeReading,
    *,
    activity: DependencyActivity | None = None,
    last_failure: DependencyFailureCategory | None = None,
) -> DependencyStatusRow:
    """Derive one item's state from its reading, any running setup step and its last settled failure.

    A running setup operation wins; then a probe that could not read gives
    ``unknown``; then the probe result. A settled failure, such as an
    interrupted download, shows only while the probe still finds the item
    absent: once the probe observes the item, the observation decides.
    """
    if reading.item_id != declaration.item_id:
        raise ValueError("probe reading belongs to another setup item")
    if activity is not None and activity.item_id != declaration.item_id:
        raise ValueError("setup activity belongs to another setup item")
    state, stale, blocked, failure = _derive_state(reading, activity=activity, last_failure=last_failure)
    usable = state in {DependencyState.READY, DependencyState.STALE}
    unsized = DependencyStatusRow(
        item_id=declaration.item_id,
        kind=declaration.kind,
        mode=reading.mode,
        state=state,
        stale_reason=stale,
        blocked_reason=blocked,
        failure_category=failure,
        note=reading.note if usable else None,
        version=reading.version,
        size_estimate_bytes=declaration.size_estimate_bytes,
    )
    recovery = recovery_action_for(unsized)
    if recovery is None:
        return unsized
    return unsized.model_copy(
        update={"recovery": recovery, "recovery_action_id": declaration.recovery_action_id},
    )


def _derive_state(
    reading: DependencyProbeReading,
    *,
    activity: DependencyActivity | None,
    last_failure: DependencyFailureCategory | None,
) -> tuple[
    DependencyState,
    DependencyStaleReason | None,
    DependencyBlockedReason | None,
    DependencyFailureCategory | None,
]:
    if activity is not None:
        if activity.step is DependencySetupStep.VERIFY:
            return DependencyState.VERIFYING, None, None, None
        return DependencyState.PROVISIONING, None, None, None
    match reading.outcome:
        case DependencyProbeOutcome.UNREADABLE:
            return DependencyState.UNKNOWN, None, None, None
        case DependencyProbeOutcome.PRESENT:
            return DependencyState.READY, None, None, None
        case DependencyProbeOutcome.DIFFERS:
            return DependencyState.STALE, reading.stale_reason, None, None
        case DependencyProbeOutcome.FAILED:
            return DependencyState.FAILED, None, None, reading.failure_category
        case DependencyProbeOutcome.BLOCKED:
            return DependencyState.BLOCKED, None, reading.blocked_reason, None
        case DependencyProbeOutcome.ABSENT:
            if last_failure is not None:
                return DependencyState.FAILED, None, None, last_failure
            return DependencyState.ABSENT, None, None, None


_NO_RECOVERY_FAILURES: Final = frozenset(
    {DependencyFailureCategory.NOT_IN_THIS_BUILD, DependencyFailureCategory.NOT_ENOUGH_MEMORY}
)


def recovery_action_for(row: DependencyStatusRow) -> DependencyRecoveryAction | None:
    """Return the one button an item's state offers, or ``None`` when the person has nothing to do.

    A computer below the model floor and a build without the item have no
    button: nothing the person does in Cadrumo changes them.
    """
    match row.state:
        case DependencyState.READY | DependencyState.PROVISIONING | DependencyState.VERIFYING:
            return None
        case DependencyState.UNKNOWN:
            return DependencyRecoveryAction.CHECK_AGAIN
        case DependencyState.ABSENT:
            return DependencyRecoveryAction.SET_UP
        case DependencyState.STALE:
            return DependencyRecoveryAction.UPDATE
        case DependencyState.BLOCKED:
            return _blocked_recovery(row.blocked_reason)
        case DependencyState.FAILED:
            return _failed_recovery(row.failure_category)


def _blocked_recovery(reason: DependencyBlockedReason | None) -> DependencyRecoveryAction | None:
    match reason:
        case DependencyBlockedReason.OFFLINE:
            return DependencyRecoveryAction.CHECK_AGAIN
        case DependencyBlockedReason.NEEDS_PERSON:
            return DependencyRecoveryAction.SET_UP
        case DependencyBlockedReason.HARDWARE | DependencyBlockedReason.NOT_IN_THIS_BUILD | None:
            return None


def _failed_recovery(category: DependencyFailureCategory | None) -> DependencyRecoveryAction | None:
    if category is None or category in _NO_RECOVERY_FAILURES:
        return None
    if category is DependencyFailureCategory.INTERRUPTED:
        return DependencyRecoveryAction.RESUME
    return DependencyRecoveryAction.TRY_AGAIN


def is_setup_complete(rows: Iterable[DependencyStatusRow]) -> bool:
    """Whether every item is usable; Cadrumo is set up when each is ready or stale."""
    return all(row.state in {DependencyState.READY, DependencyState.STALE} for row in rows)


def build_setup_plan(entries: Sequence[DependencyPlanEntry], *, free_bytes: int | None) -> DependencySetupPlan:
    """Assemble the plan a person approves from each item's entry and the measured free space."""
    known = known_download_bytes_of(entries)
    return DependencySetupPlan(
        entries=tuple(entries),
        space=DependencySpaceCheck(free_bytes=free_bytes, required_bytes=required_free_bytes(known)),
    )


class DependencyRegistry:
    """The composed registry: exactly one checker per declared item, in setup order."""

    def __init__(
        self,
        checkers: Iterable[DependencyItemChecker],
        *,
        reachability: DependencyReachability | None = None,
        hosts_for: Callable[[str], tuple[str, ...]] | None = None,
        full_checks: bool = True,
    ) -> None:
        """Enrol one checker per declared item, refusing a missing, extra or mismatched item.

        ``reachability`` and ``hosts_for`` bind the network preflight a full
        check applies once per host group; without them a full check reads
        only what the checkers themselves report. Without ``full_checks``, a
        request for a full check reads the quick check instead, and its rows
        say so, rather than claim an exercise of the item that never ran.
        """
        if (reachability is None) != (hosts_for is None):
            raise ValueError("the full-check preflight needs both the reachability check and the host groups")
        if not full_checks and reachability is not None:
            raise ValueError("a registry without full checks binds no full-check preflight")
        self._full_checks = full_checks
        self._reachability = reachability
        self._hosts_for = hosts_for
        by_id: dict[str, DependencyItemChecker] = {}
        for checker in checkers:
            item_id = checker.declaration.item_id
            if item_id in by_id:
                raise ValueError(f"setup item {item_id!r} is enrolled twice")
            by_id[item_id] = checker
        declarations = dependency_item_declarations()
        expected = {declaration.item_id for declaration in declarations}
        if set(by_id) != expected:
            missing = sorted(expected - set(by_id))
            extra = sorted(set(by_id) - expected)
            raise ValueError(f"setup registry must enrol every declared item: missing {missing}, unknown {extra}")
        for declaration in declarations:
            checker = by_id[declaration.item_id]
            if checker.declaration != declaration:
                raise ValueError(f"setup item {declaration.item_id!r} is enrolled with another declaration")
            if not isinstance(checker, DependencyItemProvisioner):
                raise ValueError(f"setup item {declaration.item_id!r} needs a provisioner")
        self._declarations = declarations
        self._checkers: Mapping[str, DependencyItemChecker] = by_id

    @property
    def declarations(self) -> tuple[DependencyItemDeclaration, ...]:
        """Every declared item, in setup order."""
        return self._declarations

    def declaration(self, item_id: str) -> DependencyItemDeclaration:
        """Return the declaration of ``item_id``, refusing an unknown item."""
        checker = self._checkers.get(item_id)
        if checker is None:
            raise DependencySelectionError(item_id, reason="not a setup item")
        return checker.declaration

    def provisioner(self, item_id: str) -> DependencyItemProvisioner:
        """Return the provisioner of a setup item."""
        checker = self._checkers.get(item_id)
        if checker is None or not isinstance(checker, DependencyItemProvisioner):
            raise DependencySelectionError(item_id, reason="not a setup item")
        return checker

    async def read_rows(
        self,
        mode: DependencyCheckMode,
        *,
        item_ids: Sequence[str] | None = None,
        activities: Iterable[DependencyActivity] = (),
        last_failures: Mapping[str, DependencyFailureCategory] | None = None,
    ) -> tuple[DependencyStatusRow, ...]:
        """Check the selected items (every item by default) and derive their rows, in setup order.

        Quick checks run together inside one shared bound; full checks run one
        item at a time, each inside its own bound. A check that does not answer
        in time reads as unknown rather than as absent. A check reports what it
        cannot read as ``unreadable`` itself; one that raises is a defect, and
        its error propagates.
        """
        selected = self._ordered_selection(item_ids)
        active = {activity.item_id: activity for activity in activities}
        failures = {} if last_failures is None else dict(last_failures)
        if mode is DependencyCheckMode.QUICK or not self._full_checks:
            readings = await self._quick_readings(selected)
        else:
            readings = await self._full_readings(selected, mode)
        return tuple(
            derive_dependency_row(
                declaration,
                reading,
                activity=active.get(declaration.item_id),
                last_failure=failures.get(declaration.item_id),
            )
            for declaration, reading in zip(selected, readings, strict=True)
        )

    async def preflight(self, hosts: tuple[str, ...]) -> DependencyFailureCategory | None:
        """Preflight ``hosts`` with the bound reachability check; ``None`` when they answer or none is bound."""
        if self._reachability is None:
            return None
        return await self._reachability(hosts)

    async def _full_readings(
        self, selected: Sequence[DependencyItemDeclaration], mode: DependencyCheckMode
    ) -> list[DependencyProbeReading]:
        """Run each full check, then hold every item that is not usable against its host group's preflight.

        The preflight runs once per host group however many items share it. A
        usable item stays usable offline: the network decides only what an
        item that still needs it can become.
        """
        network: dict[str, DependencyFailureCategory | None] = {}
        readings: list[DependencyProbeReading] = []
        for declaration in selected:
            reading = await _bounded_reading(declaration, self._checkers[declaration.item_id], mode)
            if self._reachability is not None and self._hosts_for is not None and reading.outcome not in _USABLE:
                group = declaration.network_host_group
                if group not in network:
                    network[group] = await self._reachability(self._hosts_for(group))
                reading = _held_by_network(reading, network[group])
            readings.append(reading)
        return readings

    def select_setup_items(
        self,
        rows: Iterable[DependencyStatusRow],
        *,
        requested: Sequence[str] | None = None,
    ) -> tuple[DependencyItemDeclaration, ...]:
        """Return the items a setup should cover, in setup order.

        With no request, that is every item that is not ready, is not already
        running, and is not held back by this computer or this build. A
        requested item must be a setup item.
        """
        if requested is not None:
            chosen = set(requested)
            for item_id in requested:
                self.provisioner(item_id)
            return tuple(declaration for declaration in self._declarations if declaration.item_id in chosen)
        settled = {DependencyState.READY, DependencyState.PROVISIONING, DependencyState.VERIFYING}
        wanted = {row.item_id for row in rows if row.state not in settled and _installable_here(row)}
        return tuple(declaration for declaration in self._declarations if declaration.item_id in wanted)

    def _ordered_selection(self, item_ids: Sequence[str] | None) -> tuple[DependencyItemDeclaration, ...]:
        if item_ids is None:
            return self._declarations
        chosen = set(item_ids)
        for item_id in chosen:
            self.declaration(item_id)
        return tuple(declaration for declaration in self._declarations if declaration.item_id in chosen)

    async def _quick_readings(self, selected: Sequence[DependencyItemDeclaration]) -> list[DependencyProbeReading]:
        tasks = [
            asyncio.ensure_future(self._checkers[declaration.item_id].check(DependencyCheckMode.QUICK))
            for declaration in selected
        ]
        if tasks:
            await asyncio.wait(tasks, timeout=DEPENDENCY_QUICK_CHECK_BUDGET_S)
        late = [task for task in tasks if not task.done()]
        for task in late:
            task.cancel()
        if late:
            await asyncio.gather(*late, return_exceptions=True)
        return [
            _unreadable(declaration, DependencyCheckMode.QUICK)
            if task.cancelled()
            else _matching_reading(declaration, DependencyCheckMode.QUICK, task.result())
            for declaration, task in zip(selected, tasks, strict=True)
        ]


async def _bounded_reading(
    declaration: DependencyItemDeclaration,
    checker: DependencyItemChecker,
    mode: DependencyCheckMode,
) -> DependencyProbeReading:
    try:
        async with asyncio.timeout(declaration.full_check_budget_s):
            reading = await checker.check(mode)
    except TimeoutError:
        return _unreadable(declaration, mode)
    return _matching_reading(declaration, mode, reading)


def _matching_reading(
    declaration: DependencyItemDeclaration,
    mode: DependencyCheckMode,
    reading: DependencyProbeReading,
) -> DependencyProbeReading:
    if reading.item_id != declaration.item_id or reading.mode is not mode:
        return _unreadable(declaration, mode)
    return reading


_USABLE: Final = frozenset({DependencyProbeOutcome.PRESENT, DependencyProbeOutcome.DIFFERS})

type DependencyReachability = Callable[[tuple[str, ...]], Awaitable[DependencyFailureCategory | None]]
"""Preflight of a host group: the failure category, or ``None`` when every host answered."""


def _held_by_network(
    reading: DependencyProbeReading, failure: DependencyFailureCategory | None
) -> DependencyProbeReading:
    if failure is None:
        return reading
    if failure is DependencyFailureCategory.OFFLINE:
        return DependencyProbeReading(
            item_id=reading.item_id,
            mode=reading.mode,
            outcome=DependencyProbeOutcome.BLOCKED,
            blocked_reason=DependencyBlockedReason.OFFLINE,
            facts=reading.facts,
        )
    return DependencyProbeReading(
        item_id=reading.item_id,
        mode=reading.mode,
        outcome=DependencyProbeOutcome.FAILED,
        failure_category=failure,
        facts=reading.facts,
    )


def _unreadable(declaration: DependencyItemDeclaration, mode: DependencyCheckMode) -> DependencyProbeReading:
    return DependencyProbeReading(item_id=declaration.item_id, mode=mode, outcome=DependencyProbeOutcome.UNREADABLE)
