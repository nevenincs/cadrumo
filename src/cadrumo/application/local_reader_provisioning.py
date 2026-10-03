"""Execution of supervised local-reader provisioning requests."""

from __future__ import annotations

import asyncio
import threading
from dataclasses import dataclass, field
from typing import Protocol

from ..core.model_catalogue import ModelRole
from ..core.operations import OperationEffect
from ..core.time.clock import now
from .local_reader import RoleModelTarget, TextExtractionFitnessProbe, role_model_targets, verify_role_target
from .local_reader_contracts import (
    LOCAL_READER_EXECUTE_PHASE,
    LOCAL_READER_OPERATION_SUBJECT,
    LOCAL_READER_PREFLIGHT_PHASE,
    LOCAL_READER_PULL_PROGRESS_UNIT,
    LOCAL_READER_SETTLEMENT_PHASE,
    LocalReaderInstallOutcome,
    LocalReaderModelOutcome,
    LocalReaderProvisionAction,
    LocalReaderProvisionOutcome,
    LocalReaderProvisionRequest,
    LocalReaderSetupStep,
    LocalReaderSetupStepOutcome,
    LocalReaderSetupStepState,
    local_reader_setup_phase,
)
from .operations.models import OperationRequest
from .operations.owner import OperationEventEmitter, OperationExecutorContext
from .provisioning_host import (
    InstallerRunner,
    RuntimeSpawner,
    install_runtime,
    read_runtime_version,
    start_runtime,
)
from .provisioning_runtime import (
    PullProgress,
    load_runtime_model,
    pull_runtime_model,
    read_installed_models,
    remove_runtime_model,
    runtime_model_names_match,
)

__all__ = [
    "LocalReaderProvisionEvents",
    "LocalReaderProvisionExecutor",
    "local_reader_provision_effect",
    "provision_local_reader",
]

_PREFLIGHT = LOCAL_READER_PREFLIGHT_PHASE
_EXECUTE = LOCAL_READER_EXECUTE_PHASE
_SETTLEMENT = LOCAL_READER_SETTLEMENT_PHASE
_PROGRESS_POLL_S = 0.5


def _refused_target(target: RoleModelTarget, step: LocalReaderSetupStep | None) -> LocalReaderModelOutcome:
    return LocalReaderModelOutcome(
        roles=target.roles,
        succeeded=False,
        step=step,
        facts=dict(target.selection_facts),
        precondition_verdict=target.selection_verdict,
    )


class LocalReaderProvisionEvents(Protocol):
    """Where a provisioning run reports its progress; the supervised operation journals it."""

    async def step(self, step: LocalReaderSetupStep) -> None:
        """Report that a setup step begins."""
        ...

    async def progress(self, *, completed: int, total: int) -> None:
        """Report fetched bytes of the model being pulled."""
        ...


class _UnobservedEvents:
    """Progress nobody watches: a direct caller reads only the settled outcome."""

    async def step(self, step: LocalReaderSetupStep) -> None:
        del step

    async def progress(self, *, completed: int, total: int) -> None:
        del completed, total


class _ProgressRelay:
    """Carries the latest fetch progress from the worker thread to the event loop."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._latest: PullProgress | None = None
        self._published: tuple[int, int] | None = None

    def record(self, progress: PullProgress) -> None:
        with self._lock:
            self._latest = progress

    async def publish(self, events: LocalReaderProvisionEvents) -> None:
        with self._lock:
            latest = self._latest
        if latest is None or latest.total_bytes is None or latest.completed_bytes is None:
            return
        reading = (min(latest.completed_bytes, latest.total_bytes), latest.total_bytes)
        if reading == self._published or reading[1] == 0:
            return
        self._published = reading
        await events.progress(completed=reading[0], total=reading[1])


def _targets(role: ModelRole | None, model: str | None = None) -> tuple[RoleModelTarget, ...]:
    return role_model_targets(None if role is None else (role,), explicit_model=model)


@dataclass
class _LocalReaderSetupProgress:
    steps: list[LocalReaderSetupStepOutcome] = field(default_factory=list)
    models: list[LocalReaderModelOutcome] = field(default_factory=list)
    install: LocalReaderInstallOutcome | None = None
    runtime_started: bool = False
    stopped: LocalReaderSetupStep | None = None
    refusal: LocalReaderProvisionOutcome | None = None

    def record(self, step: LocalReaderSetupStep, state: LocalReaderSetupStepState, failed: str | None = None) -> None:
        self.steps.append(LocalReaderSetupStepOutcome(step=step, state=state, failed_condition_id=failed))
        if state is LocalReaderSetupStepState.FAILED:
            self.stopped = step

    def record_models(self, step: LocalReaderSetupStep, items: list[LocalReaderModelOutcome]) -> None:
        self.models.extend(items)
        failed = next((item for item in items if not item.succeeded), None)
        if failed is not None:
            self.record(step, LocalReaderSetupStepState.FAILED, failed.failed_condition_id)
        elif all(item.already_satisfied for item in items):
            self.record(step, LocalReaderSetupStepState.UNCHANGED)
        else:
            self.record(step, LocalReaderSetupStepState.CHANGED)

    def record_verification(self, items: list[LocalReaderModelOutcome]) -> None:
        self.models.extend(items)
        failed = next((item for item in items if not item.succeeded), None)
        if failed is not None:
            self.record(LocalReaderSetupStep.VERIFY, LocalReaderSetupStepState.FAILED, failed.failed_condition_id)
        else:
            # Verification observes; a pass changes nothing.
            self.record(LocalReaderSetupStep.VERIFY, LocalReaderSetupStepState.UNCHANGED)

    def outcome(self) -> LocalReaderProvisionOutcome:
        reached = {step.step for step in self.steps}
        self.steps.extend(
            LocalReaderSetupStepOutcome(step=step, state=LocalReaderSetupStepState.NOT_REACHED)
            for step in LocalReaderSetupStep
            if step not in reached
        )
        return LocalReaderProvisionOutcome(
            action=LocalReaderProvisionAction.SETUP,
            succeeded=self.stopped is None,
            runtime_started=self.runtime_started,
            install=self.install,
            models=tuple(self.models),
            steps=tuple(self.steps),
            stopped_step=self.stopped,
            facts={} if self.refusal is None else dict(self.refusal.facts),
            precondition_verdict=None if self.refusal is None else self.refusal.precondition_verdict,
        )


def _settled_effect(changed: int, failed: int) -> OperationEffect:
    if changed == 0:
        return OperationEffect.NONE
    return OperationEffect.PARTIAL if failed else OperationEffect.UPDATED


def local_reader_provision_effect(outcome: LocalReaderProvisionOutcome) -> OperationEffect:
    """Return the committed extent a settled provisioning outcome represents."""
    if outcome.action is LocalReaderProvisionAction.SETUP:
        return _setup_effect(outcome)
    if outcome.action is LocalReaderProvisionAction.INSTALL:
        return _install_effect(outcome)
    if outcome.action is LocalReaderProvisionAction.START:
        return OperationEffect.UPDATED if outcome.runtime_started else OperationEffect.NONE
    if outcome.action is LocalReaderProvisionAction.VERIFY:
        return OperationEffect.NONE
    return _model_action_effect(outcome)


def _setup_effect(outcome: LocalReaderProvisionOutcome) -> OperationEffect:
    changed = sum(step.state is LocalReaderSetupStepState.CHANGED for step in outcome.steps)
    return _settled_effect(changed, 0 if outcome.succeeded else 1)


def _install_effect(outcome: LocalReaderProvisionOutcome) -> OperationEffect:
    install = outcome.install
    changed = install is not None and install.installed and not install.already_installed
    return OperationEffect.UPDATED if changed else OperationEffect.NONE


def _model_action_effect(outcome: LocalReaderProvisionOutcome) -> OperationEffect:
    changed = sum(item.succeeded and not item.already_satisfied for item in outcome.models)
    failed = sum(not item.succeeded for item in outcome.models)
    return _settled_effect(changed, failed)


class _LocalReaderProvisioner:
    """Every provisioning action, over the injected process and fitness ports."""

    def __init__(
        self,
        *,
        spawn: RuntimeSpawner,
        run_installer: InstallerRunner,
        text_probe: TextExtractionFitnessProbe,
        events: LocalReaderProvisionEvents,
    ) -> None:
        self._spawn = spawn
        self._run_installer = run_installer
        self._text_probe = text_probe
        self._events = events

    async def run(self, payload: LocalReaderProvisionRequest) -> LocalReaderProvisionOutcome:
        match payload.action:
            case LocalReaderProvisionAction.INSTALL:
                return await self._install(consent=payload.consent)
            case LocalReaderProvisionAction.START:
                return await self._start()
            case LocalReaderProvisionAction.PULL:
                return _settled(LocalReaderProvisionAction.PULL, await self._pull(_targets(payload.role)))
            case LocalReaderProvisionAction.LOAD:
                return _settled(
                    LocalReaderProvisionAction.LOAD, await self._load(_targets(payload.role, payload.model))
                )
            case LocalReaderProvisionAction.VERIFY:
                return await self._verify(payload.role)
            case LocalReaderProvisionAction.REMOVE:
                return _settled(
                    LocalReaderProvisionAction.REMOVE, await self._remove(_targets(payload.role, payload.model))
                )
            case LocalReaderProvisionAction.SETUP:
                return await self._setup(consent=payload.consent)

    async def _install(self, *, consent: bool) -> LocalReaderProvisionOutcome:
        installed = await asyncio.to_thread(install_runtime, consent=consent, run=self._run_installer)
        return LocalReaderProvisionOutcome(
            action=LocalReaderProvisionAction.INSTALL,
            succeeded=installed.installed,
            install=LocalReaderInstallOutcome(
                installed=installed.installed,
                already_installed=installed.already_installed,
                installer=installed.installer,
                consented=installed.consented,
                installer_exit_code=installed.installer_exit_code,
            ),
            facts=dict(installed.facts),
            precondition_verdict=installed.precondition_verdict,
        )

    async def _start(self) -> LocalReaderProvisionOutcome:
        started = await asyncio.to_thread(start_runtime, spawn=self._spawn)
        return LocalReaderProvisionOutcome(
            action=LocalReaderProvisionAction.START,
            succeeded=started.running,
            runtime_started=started.running and not started.already_running,
            already_running=started.already_running,
            started_pid=started.started_pid,
            facts=dict(started.facts),
            precondition_verdict=started.precondition_verdict,
        )

    async def _pull(
        self,
        targets: tuple[RoleModelTarget, ...],
        *,
        step: LocalReaderSetupStep | None = None,
        skip_installed: bool = False,
    ) -> list[LocalReaderModelOutcome]:
        inventory = await asyncio.to_thread(read_installed_models) if skip_installed else None
        items: list[LocalReaderModelOutcome] = []
        for target in targets:
            if target.model is None or target.requirement_bytes is None:
                items.append(_refused_target(target, step))
                continue
            if inventory is not None and any(runtime_model_names_match(target.model, row.name) for row in inventory):
                items.append(
                    LocalReaderModelOutcome(
                        model=target.model,
                        roles=target.roles,
                        succeeded=True,
                        already_satisfied=True,
                        step=step,
                        facts={"model": target.model, "model_installed": True},
                    )
                )
                continue
            relay = _ProgressRelay()
            task = asyncio.create_task(
                asyncio.to_thread(pull_runtime_model, target.model, target.requirement_bytes, on_progress=relay.record)
            )
            while not task.done():
                await asyncio.wait({task}, timeout=_PROGRESS_POLL_S)
                await relay.publish(self._events)
            pulled = task.result()
            items.append(
                LocalReaderModelOutcome(
                    model=pulled.model,
                    roles=target.roles,
                    succeeded=pulled.pulled,
                    step=step,
                    bytes_fetched=pulled.bytes_fetched,
                    facts=dict(pulled.facts),
                    precondition_verdict=pulled.precondition_verdict,
                )
            )
        return items

    async def _load(
        self, targets: tuple[RoleModelTarget, ...], *, step: LocalReaderSetupStep | None = None
    ) -> list[LocalReaderModelOutcome]:
        items: list[LocalReaderModelOutcome] = []
        for target in targets:
            if target.model is None or target.requirement_bytes is None:
                items.append(_refused_target(target, step))
                continue
            loaded = await asyncio.to_thread(load_runtime_model, target.model, target.requirement_bytes)
            items.append(
                LocalReaderModelOutcome(
                    model=loaded.model,
                    roles=target.roles,
                    succeeded=loaded.loaded,
                    already_satisfied=loaded.already_loaded,
                    step=step,
                    resident=loaded.loaded,
                    elapsed_ms=loaded.elapsed_ms,
                    facts=dict(loaded.facts),
                    precondition_verdict=loaded.precondition_verdict,
                )
            )
        return items

    async def _verify(self, role: ModelRole | None) -> LocalReaderProvisionOutcome:
        return _settled(LocalReaderProvisionAction.VERIFY, await self._verify_targets(_targets(role)))

    async def _verify_targets(
        self, targets: tuple[RoleModelTarget, ...], *, step: LocalReaderSetupStep | None = None
    ) -> list[LocalReaderModelOutcome]:
        items: list[LocalReaderModelOutcome] = []
        for target in targets:
            if target.model is None:
                items.append(_refused_target(target, step))
                continue
            ready = await asyncio.to_thread(verify_role_target, target, text_probe=self._text_probe)
            items.append(
                LocalReaderModelOutcome(
                    model=ready.model,
                    roles=target.roles,
                    succeeded=ready.ready,
                    step=step,
                    resident=ready.resident,
                    answered=ready.answered,
                    elapsed_ms=ready.elapsed_ms,
                    facts=dict(ready.facts),
                    precondition_verdict=ready.precondition_verdict,
                )
            )
        return items

    async def _remove(self, targets: tuple[RoleModelTarget, ...]) -> list[LocalReaderModelOutcome]:
        items: list[LocalReaderModelOutcome] = []
        for target in targets:
            if target.model is None:
                items.append(_refused_target(target, None))
                continue
            removed = await asyncio.to_thread(remove_runtime_model, target.model)
            items.append(
                LocalReaderModelOutcome(
                    model=removed.model,
                    roles=target.roles,
                    succeeded=removed.removed,
                    freed_bytes=removed.freed_bytes,
                    was_installed=removed.was_installed,
                    facts=dict(removed.facts),
                    precondition_verdict=removed.precondition_verdict,
                )
            )
        return items

    async def _setup(self, *, consent: bool) -> LocalReaderProvisionOutcome:
        progress = _LocalReaderSetupProgress()
        await self._setup_install(progress, consent=consent)
        if progress.stopped is None:
            await self._setup_start(progress)
        targets = _targets(None) if progress.stopped is None else ()
        if progress.stopped is None:
            await self._setup_pull(progress, targets)
        if progress.stopped is None:
            await self._setup_load(progress, targets)
        if progress.stopped is None:
            await self._setup_verify(progress, targets)
        return progress.outcome()

    async def _setup_install(self, progress: _LocalReaderSetupProgress, *, consent: bool) -> None:
        await self._events.step(LocalReaderSetupStep.INSTALL)
        if await asyncio.to_thread(read_runtime_version) is not None:
            # A runtime that already answers needs no install, wherever it lives.
            progress.record(LocalReaderSetupStep.INSTALL, LocalReaderSetupStepState.UNCHANGED)
            return
        installed = await self._install(consent=consent)
        progress.install = installed.install
        if not installed.succeeded:
            progress.refusal = installed
            progress.record(
                LocalReaderSetupStep.INSTALL, LocalReaderSetupStepState.FAILED, installed.failed_condition_id
            )
        elif installed.install is not None and installed.install.already_installed:
            progress.record(LocalReaderSetupStep.INSTALL, LocalReaderSetupStepState.UNCHANGED)
        else:
            progress.record(LocalReaderSetupStep.INSTALL, LocalReaderSetupStepState.CHANGED)

    async def _setup_start(self, progress: _LocalReaderSetupProgress) -> None:
        await self._events.step(LocalReaderSetupStep.START)
        started = await self._start()
        progress.runtime_started = started.runtime_started
        if not started.succeeded:
            progress.refusal = started
            progress.record(LocalReaderSetupStep.START, LocalReaderSetupStepState.FAILED, started.failed_condition_id)
            return
        state = LocalReaderSetupStepState.CHANGED if started.runtime_started else LocalReaderSetupStepState.UNCHANGED
        progress.record(LocalReaderSetupStep.START, state)

    async def _setup_pull(self, progress: _LocalReaderSetupProgress, targets: tuple[RoleModelTarget, ...]) -> None:
        await self._events.step(LocalReaderSetupStep.PULL)
        items = await self._pull(targets, step=LocalReaderSetupStep.PULL, skip_installed=True)
        progress.record_models(LocalReaderSetupStep.PULL, items)

    async def _setup_load(self, progress: _LocalReaderSetupProgress, targets: tuple[RoleModelTarget, ...]) -> None:
        await self._events.step(LocalReaderSetupStep.LOAD)
        items = await self._load(targets, step=LocalReaderSetupStep.LOAD)
        progress.record_models(LocalReaderSetupStep.LOAD, items)

    async def _setup_verify(self, progress: _LocalReaderSetupProgress, targets: tuple[RoleModelTarget, ...]) -> None:
        await self._events.step(LocalReaderSetupStep.VERIFY)
        items = await self._verify_targets(targets, step=LocalReaderSetupStep.VERIFY)
        progress.record_verification(items)


async def provision_local_reader(
    payload: LocalReaderProvisionRequest,
    *,
    spawn: RuntimeSpawner,
    run_installer: InstallerRunner,
    text_probe: TextExtractionFitnessProbe,
    events: LocalReaderProvisionEvents | None = None,
) -> LocalReaderProvisionOutcome:
    """Run one provisioning action and return its settled outcome.

    The single implementation of install, start, pull, load, verify, remove
    and setup. The supervised operation wraps it with journaled progress for
    frontends that hold a profile session; a host-level caller such as the
    command line runs it directly, because provisioning the machine's runtime
    needs no profile. Never raises for a refusal: every refusal is a typed
    verdict on the outcome.
    """
    provisioner = _LocalReaderProvisioner(
        spawn=spawn,
        run_installer=run_installer,
        text_probe=text_probe,
        events=_UnobservedEvents() if events is None else events,
    )
    return await provisioner.run(payload)


class _JournaledEvents:
    """Carries provisioning progress onto the supervised operation's event stream."""

    def __init__(self, events: OperationEventEmitter) -> None:
        self._events = events

    async def step(self, step: LocalReaderSetupStep) -> None:
        await self._events.phase(local_reader_setup_phase(step))

    async def progress(self, *, completed: int, total: int) -> None:
        await self._events.progress(completed=completed, total=total, unit_code=LOCAL_READER_PULL_PROGRESS_UNIT)


class LocalReaderProvisionExecutor:
    """Supervise :func:`provision_local_reader`: journal its progress and persist its outcome."""

    def __init__(
        self,
        *,
        spawn: RuntimeSpawner,
        run_installer: InstallerRunner,
        text_probe: TextExtractionFitnessProbe,
    ) -> None:
        """Bind the injected runtime spawner, installer runner and text-reader fitness probe."""
        self._spawn = spawn
        self._run_installer = run_installer
        self._text_probe = text_probe

    async def execute(
        self,
        request: OperationRequest[LocalReaderProvisionRequest],
        context: OperationExecutorContext,
    ) -> str:
        """Execute the requested action and persist its settled outcome."""
        if request.subject_ref != LOCAL_READER_OPERATION_SUBJECT:
            raise ValueError("local-reader operation subject must name the local runtime")
        await context.events.phase(_PREFLIGHT)
        await context.events.phase(_EXECUTE)
        await context.events.effect(OperationEffect.UNKNOWN)
        outcome = await provision_local_reader(
            request.payload,
            spawn=self._spawn,
            run_installer=self._run_installer,
            text_probe=self._text_probe,
            events=_JournaledEvents(context.events),
        )
        await context.events.effect(local_reader_provision_effect(outcome))
        await context.events.phase(_SETTLEMENT)
        return await context.operands.put(outcome, written_at=now())


def _settled(action: LocalReaderProvisionAction, items: list[LocalReaderModelOutcome]) -> LocalReaderProvisionOutcome:
    return LocalReaderProvisionOutcome(
        action=action,
        succeeded=bool(items) and all(item.succeeded for item in items),
        models=tuple(items),
    )
