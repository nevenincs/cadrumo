"""Supervised operation for provisioning the local document reader from any frontend.

One definition, ``local-reader.provision``, carries every action a status area
or the command line offers -- install, start, pull, load, verify, remove, and
the one-shot setup that runs the first five in order -- so a TUI button and
``aeat config provision <verb>`` run the same implementation. Installing runs
a package manager and therefore requires ``consent`` on the request; every
frontend gathers that consent explicitly before submitting.

Process control is injected. The application layer never spawns a process
itself; the entrypoint composition binds the outbound adapters.
"""

from __future__ import annotations

import asyncio
import threading
from collections.abc import Mapping
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, NonNegativeInt, model_validator

from ..core.model_catalogue import ModelRole
from ..core.models import STRICT_FROZEN_CONFIG
from ..core.operations import (
    OperationCancellation,
    OperationClosePolicy,
    OperationDeadline,
    OperationDurability,
    OperationEffect,
    OperationInteractionKind,
)
from ..core.time.clock import now
from .local_reader import (
    RoleModelTarget,
    TextExtractionFitnessProbe,
    role_model_targets,
    runtime_model_names_match,
    verify_role_target,
)
from .operations.capabilities import (
    OperationBaselinePolicy,
    OperationCapabilities,
    OperationConflictScope,
    OperationReplayPolicy,
    OperationRequestStoragePolicy,
    OperationSensitiveInputPolicy,
)
from .operations.models import CredentialFreeOperationRequest, OperationRequest, OperationTerminalReceipt
from .operations.owner import OperationEventEmitter, OperationExecutorContext
from .operations.registry import (
    OperationDefinition,
    OperationExecutorFactory,
    OperationFrontendProjection,
    OperationPublicDefinitionRegistrationV1,
    OperationReconciliationPolicy,
    OperationSchemaBindingV1,
)
from .operator_actions.models import PreconditionVerdict
from .provisioning_contracts import ProvisioningFactValue
from .provisioning_host import (
    InstallerRunner,
    RuntimeInstaller,
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
)

__all__ = [
    "LOCAL_READER_OPERATION_DEFINITION_ID",
    "LOCAL_READER_OPERATION_SUBJECT",
    "LOCAL_READER_PULL_PROGRESS_UNIT",
    "LocalReaderInstallOutcome",
    "LocalReaderInstallOutcomeV1",
    "LocalReaderModelOutcome",
    "LocalReaderModelOutcomeV1",
    "LocalReaderProvisionAction",
    "LocalReaderProvisionExecutor",
    "LocalReaderProvisionOutcome",
    "LocalReaderProvisionPublicResultV1",
    "LocalReaderProvisionRequest",
    "LocalReaderSetupStep",
    "LocalReaderSetupStepOutcome",
    "LocalReaderSetupStepOutcomeV1",
    "LocalReaderSetupStepState",
    "build_local_reader_install_request",
    "build_local_reader_load_request",
    "build_local_reader_operation_definition",
    "build_local_reader_operation_registration",
    "build_local_reader_pull_request",
    "build_local_reader_remove_request",
    "build_local_reader_setup_request",
    "build_local_reader_start_request",
    "build_local_reader_verify_request",
    "local_reader_setup_phase",
]

LOCAL_READER_OPERATION_DEFINITION_ID = "local-reader.provision"
#: The runtime is one per host, so every provisioning request shares one
#: subject and the definition-subject lease serialises them.
LOCAL_READER_OPERATION_SUBJECT = "local-reader:runtime"
LOCAL_READER_PULL_PROGRESS_UNIT = "local-reader.bytes"
_PREFLIGHT = "local-reader.provision.preflight"
_EXECUTE = "local-reader.provision.execute"
_SETTLEMENT = "local-reader.provision.settlement"
_PROGRESS_POLL_S = 0.5


class LocalReaderProvisionAction(StrEnum):
    """What one provisioning operation does."""

    INSTALL = "install"
    START = "start"
    PULL = "pull"
    LOAD = "load"
    VERIFY = "verify"
    REMOVE = "remove"
    SETUP = "setup"


class LocalReaderSetupStep(StrEnum):
    """The ordered steps of a one-shot setup."""

    INSTALL = "install"
    START = "start"
    PULL = "pull"
    LOAD = "load"
    VERIFY = "verify"


class LocalReaderSetupStepState(StrEnum):
    """What one setup step did: nothing needed, a change, a refusal, or not run."""

    UNCHANGED = "unchanged"
    CHANGED = "changed"
    FAILED = "failed"
    NOT_REACHED = "not_reached"


def local_reader_setup_phase(step: LocalReaderSetupStep) -> str:
    """Return the declared phase code a setup publishes when ``step`` begins."""
    return f"local-reader.provision.step.{step.value}"


_PHASES = (
    _PREFLIGHT,
    _EXECUTE,
    *(local_reader_setup_phase(step) for step in LocalReaderSetupStep),
    _SETTLEMENT,
)
_CONSENTING_ACTIONS = frozenset({LocalReaderProvisionAction.INSTALL, LocalReaderProvisionAction.SETUP})
_MODEL_NAMING_ACTIONS = frozenset({LocalReaderProvisionAction.LOAD, LocalReaderProvisionAction.REMOVE})


class LocalReaderProvisionRequest(CredentialFreeOperationRequest):
    """One provisioning action, over one role's model, a named model, or every role's.

    ``consent`` is the operator's explicit agreement to run the package-manager
    install and is accepted only by the actions that may install. ``model``
    names a model outright and is accepted only by load and remove; remove
    requires a role or a model so it never deletes every model by default.
    """

    action: LocalReaderProvisionAction
    role: ModelRole | None = None
    model: str | None = Field(default=None, min_length=1, max_length=256)
    consent: bool = False

    @model_validator(mode="after")
    def _require_coherent_request(self) -> LocalReaderProvisionRequest:
        if self.consent and self.action not in _CONSENTING_ACTIONS:
            raise ValueError("only install and setup accept install consent")
        if self.model is not None and self.action not in _MODEL_NAMING_ACTIONS:
            raise ValueError("only load and remove accept an explicit model")
        if self.action in {LocalReaderProvisionAction.INSTALL, LocalReaderProvisionAction.START} and (
            self.role is not None
        ):
            raise ValueError("install and start act on the runtime, not on a role")
        if self.action is LocalReaderProvisionAction.REMOVE and self.role is None and self.model is None:
            raise ValueError("remove requires a role or a model")
        return self


def _request(
    action: LocalReaderProvisionAction,
    *,
    role: ModelRole | None = None,
    model: str | None = None,
    consent: bool = False,
) -> OperationRequest[LocalReaderProvisionRequest]:
    return OperationRequest(
        definition_id=LOCAL_READER_OPERATION_DEFINITION_ID,
        subject_ref=LOCAL_READER_OPERATION_SUBJECT,
        payload=LocalReaderProvisionRequest(action=action, role=role, model=model, consent=consent),
    )


def build_local_reader_install_request(*, consent: bool) -> OperationRequest[LocalReaderProvisionRequest]:
    """Build the request that installs the runtime; nothing is installed without ``consent``."""
    return _request(LocalReaderProvisionAction.INSTALL, consent=consent)


def build_local_reader_start_request() -> OperationRequest[LocalReaderProvisionRequest]:
    """Build the request that starts the local runtime when it is not answering."""
    return _request(LocalReaderProvisionAction.START)


def build_local_reader_pull_request(role: ModelRole | None = None) -> OperationRequest[LocalReaderProvisionRequest]:
    """Build the request that pulls ``role``'s model, or every reader role's model."""
    return _request(LocalReaderProvisionAction.PULL, role=role)


def build_local_reader_load_request(
    role: ModelRole | None = None, model: str | None = None
) -> OperationRequest[LocalReaderProvisionRequest]:
    """Build the request that loads ``role``'s model, a named model, or every role's model."""
    return _request(LocalReaderProvisionAction.LOAD, role=role, model=model)


def build_local_reader_verify_request(role: ModelRole | None = None) -> OperationRequest[LocalReaderProvisionRequest]:
    """Build the request that verifies ``role``'s model, or every reader role's model."""
    return _request(LocalReaderProvisionAction.VERIFY, role=role)


def build_local_reader_remove_request(
    role: ModelRole | None = None, model: str | None = None
) -> OperationRequest[LocalReaderProvisionRequest]:
    """Build the request that removes ``role``'s model or a named model from the runtime's store."""
    return _request(LocalReaderProvisionAction.REMOVE, role=role, model=model)


def build_local_reader_setup_request(*, consent: bool) -> OperationRequest[LocalReaderProvisionRequest]:
    """Build the one-shot setup request: install (with ``consent``), start, pull, load, verify."""
    return _request(LocalReaderProvisionAction.SETUP, consent=consent)


class LocalReaderModelOutcome(BaseModel):
    """What happened to one model, or to one role whose selection refused.

    ``already_satisfied`` marks a model that needed nothing: already pulled for
    a pull, already resident for a load. ``step`` names the setup step that
    produced the item, and is absent outside setup.
    """

    model_config = STRICT_FROZEN_CONFIG

    model: str | None = None
    roles: tuple[ModelRole, ...]
    succeeded: bool
    already_satisfied: bool = False
    step: LocalReaderSetupStep | None = None
    bytes_fetched: int | None = Field(default=None, ge=0)
    freed_bytes: int | None = Field(default=None, ge=0)
    was_installed: bool = False
    resident: bool = False
    answered: bool = False
    elapsed_ms: int | None = Field(default=None, ge=0)
    facts: Mapping[str, ProvisioningFactValue] = Field(default_factory=dict)
    precondition_verdict: PreconditionVerdict | None = None

    @property
    def failed_condition_id(self) -> str | None:
        """Return the refused condition, when there is one."""
        return None if self.precondition_verdict is None else self.precondition_verdict.failed_condition_id


class LocalReaderInstallOutcome(BaseModel):
    """What the install request found and did."""

    model_config = STRICT_FROZEN_CONFIG

    installed: bool
    already_installed: bool = False
    installer: RuntimeInstaller
    consented: bool
    installer_exit_code: int | None = None


class LocalReaderSetupStepOutcome(BaseModel):
    """One setup step's state and, when it failed, the refused condition."""

    model_config = STRICT_FROZEN_CONFIG

    step: LocalReaderSetupStep
    state: LocalReaderSetupStepState
    failed_condition_id: str | None = None


class LocalReaderProvisionOutcome(BaseModel):
    """The settled result of one provisioning operation.

    ``facts`` and ``precondition_verdict`` describe the runtime-level action
    (install or start); per-model detail is in ``models``. For setup,
    ``steps`` lists every step in order and ``stopped_step`` names the step
    that failed, after which every later step is ``not_reached``.
    """

    model_config = STRICT_FROZEN_CONFIG

    action: LocalReaderProvisionAction
    succeeded: bool
    runtime_started: bool = False
    already_running: bool = False
    started_pid: int | None = Field(default=None, ge=0)
    install: LocalReaderInstallOutcome | None = None
    models: tuple[LocalReaderModelOutcome, ...] = ()
    steps: tuple[LocalReaderSetupStepOutcome, ...] = ()
    stopped_step: LocalReaderSetupStep | None = None
    facts: Mapping[str, ProvisioningFactValue] = Field(default_factory=dict)
    precondition_verdict: PreconditionVerdict | None = None

    @property
    def failed_condition_id(self) -> str | None:
        """Return the first refused condition across the runtime action, steps and models."""
        if self.precondition_verdict is not None:
            return self.precondition_verdict.failed_condition_id
        failed_step = next((step.failed_condition_id for step in self.steps if step.failed_condition_id), None)
        if failed_step is not None:
            return failed_step
        return next((item.failed_condition_id for item in self.models if not item.succeeded), None)


_PUBLIC_CONFIG = ConfigDict(strict=True, frozen=True, extra="forbid", validate_default=True)


class LocalReaderModelOutcomeV1(BaseModel):
    """Public projection of one model outcome."""

    model_config = _PUBLIC_CONFIG

    model: str | None = Field(default=None, min_length=1, max_length=256)
    roles: tuple[ModelRole, ...]
    succeeded: bool
    already_satisfied: bool
    step: LocalReaderSetupStep | None = None
    bytes_fetched: NonNegativeInt | None = None
    freed_bytes: NonNegativeInt | None = None
    was_installed: bool
    resident: bool
    answered: bool
    elapsed_ms: NonNegativeInt | None = None
    failed_condition_id: str | None = Field(default=None, min_length=1, max_length=128)
    facts: Mapping[str, str | int | bool]
    precondition_verdict: PreconditionVerdict | None = None


class LocalReaderInstallOutcomeV1(BaseModel):
    """Public projection of the install request."""

    model_config = _PUBLIC_CONFIG

    installed: bool
    already_installed: bool
    installer: RuntimeInstaller
    consented: bool
    installer_exit_code: int | None = None


class LocalReaderSetupStepOutcomeV1(BaseModel):
    """Public projection of one setup step."""

    model_config = _PUBLIC_CONFIG

    step: LocalReaderSetupStep
    state: LocalReaderSetupStepState
    failed_condition_id: str | None = Field(default=None, min_length=1, max_length=128)


class LocalReaderProvisionPublicResultV1(BaseModel):
    """Public projection of a settled provisioning operation."""

    model_config = _PUBLIC_CONFIG

    action: LocalReaderProvisionAction
    succeeded: bool
    runtime_started: bool
    already_running: bool
    started_pid: NonNegativeInt | None = None
    install: LocalReaderInstallOutcomeV1 | None = None
    failed_condition_id: str | None = Field(default=None, min_length=1, max_length=128)
    models: tuple[LocalReaderModelOutcomeV1, ...]
    steps: tuple[LocalReaderSetupStepOutcomeV1, ...]
    stopped_step: LocalReaderSetupStep | None = None
    facts: Mapping[str, str | int | bool]
    precondition_verdict: PreconditionVerdict | None = None


def _project_model(item: LocalReaderModelOutcome) -> LocalReaderModelOutcomeV1:
    return LocalReaderModelOutcomeV1(
        model=item.model,
        roles=item.roles,
        succeeded=item.succeeded,
        already_satisfied=item.already_satisfied,
        step=item.step,
        bytes_fetched=item.bytes_fetched,
        freed_bytes=item.freed_bytes,
        was_installed=item.was_installed,
        resident=item.resident,
        answered=item.answered,
        elapsed_ms=item.elapsed_ms,
        failed_condition_id=item.failed_condition_id,
        facts=dict(item.facts),
        precondition_verdict=item.precondition_verdict,
    )


def _project_result(result: BaseModel, terminal_receipt: OperationTerminalReceipt) -> BaseModel:
    del terminal_receipt
    outcome = LocalReaderProvisionOutcome.model_validate(result, strict=True)
    install = outcome.install
    return LocalReaderProvisionPublicResultV1(
        action=outcome.action,
        succeeded=outcome.succeeded,
        runtime_started=outcome.runtime_started,
        already_running=outcome.already_running,
        started_pid=outcome.started_pid,
        install=(
            None
            if install is None
            else LocalReaderInstallOutcomeV1(
                installed=install.installed,
                already_installed=install.already_installed,
                installer=install.installer,
                consented=install.consented,
                installer_exit_code=install.installer_exit_code,
            )
        ),
        failed_condition_id=outcome.failed_condition_id,
        models=tuple(_project_model(item) for item in outcome.models),
        steps=tuple(
            LocalReaderSetupStepOutcomeV1(
                step=step.step, state=step.state, failed_condition_id=step.failed_condition_id
            )
            for step in outcome.steps
        ),
        stopped_step=outcome.stopped_step,
        facts=dict(outcome.facts),
        precondition_verdict=outcome.precondition_verdict,
    )


def _refused_target(target: RoleModelTarget, step: LocalReaderSetupStep | None) -> LocalReaderModelOutcome:
    return LocalReaderModelOutcome(
        roles=target.roles,
        succeeded=False,
        step=step,
        facts=dict(target.selection_facts),
        precondition_verdict=target.selection_verdict,
    )


class _ProgressRelay:
    """Carries the latest fetch progress from the worker thread to the event loop."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._latest: PullProgress | None = None
        self._published: tuple[int, int] | None = None

    def record(self, progress: PullProgress) -> None:
        with self._lock:
            self._latest = progress

    async def publish(self, events: OperationEventEmitter) -> None:
        with self._lock:
            latest = self._latest
        if latest is None or latest.total_bytes is None or latest.completed_bytes is None:
            return
        reading = (min(latest.completed_bytes, latest.total_bytes), latest.total_bytes)
        if reading == self._published or reading[1] == 0:
            return
        self._published = reading
        await events.progress(completed=reading[0], total=reading[1], unit_code=LOCAL_READER_PULL_PROGRESS_UNIT)


def _targets(role: ModelRole | None, model: str | None = None) -> tuple[RoleModelTarget, ...]:
    return role_model_targets(None if role is None else (role,), explicit_model=model)


def _settled_effect(changed: int, failed: int) -> OperationEffect:
    if changed == 0:
        return OperationEffect.NONE
    return OperationEffect.PARTIAL if failed else OperationEffect.UPDATED


class LocalReaderProvisionExecutor:
    """Run one provisioning action through the application's provisioning doors."""

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
        payload = request.payload
        await context.events.phase(_PREFLIGHT)
        await context.events.phase(_EXECUTE)
        await context.events.effect(OperationEffect.UNKNOWN)
        outcome = await self._dispatch(payload, context)
        await context.events.effect(self._effect_of(outcome))
        await context.events.phase(_SETTLEMENT)
        return await context.operands.put(outcome, written_at=now())

    async def _dispatch(
        self, payload: LocalReaderProvisionRequest, context: OperationExecutorContext
    ) -> LocalReaderProvisionOutcome:
        match payload.action:
            case LocalReaderProvisionAction.INSTALL:
                return await self._install(consent=payload.consent)
            case LocalReaderProvisionAction.START:
                return await self._start()
            case LocalReaderProvisionAction.PULL:
                return _settled(LocalReaderProvisionAction.PULL, await self._pull(_targets(payload.role), context))
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
                return await self._setup(consent=payload.consent, context=context)

    @staticmethod
    def _effect_of(outcome: LocalReaderProvisionOutcome) -> OperationEffect:
        if outcome.action is LocalReaderProvisionAction.SETUP:
            changed = sum(step.state is LocalReaderSetupStepState.CHANGED for step in outcome.steps)
            return _settled_effect(changed, 0 if outcome.succeeded else 1)
        if outcome.action is LocalReaderProvisionAction.INSTALL:
            install = outcome.install
            changed = install is not None and install.installed and not install.already_installed
            return OperationEffect.UPDATED if changed else OperationEffect.NONE
        if outcome.action is LocalReaderProvisionAction.START:
            return OperationEffect.UPDATED if outcome.runtime_started else OperationEffect.NONE
        if outcome.action is LocalReaderProvisionAction.VERIFY:
            return OperationEffect.NONE
        changed = sum(item.succeeded and not item.already_satisfied for item in outcome.models)
        failed = sum(not item.succeeded for item in outcome.models)
        return _settled_effect(changed, failed)

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
        context: OperationExecutorContext,
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
                await relay.publish(context.events)
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

    async def _setup(self, *, consent: bool, context: OperationExecutorContext) -> LocalReaderProvisionOutcome:
        steps: list[LocalReaderSetupStepOutcome] = []
        models: list[LocalReaderModelOutcome] = []
        install: LocalReaderInstallOutcome | None = None
        runtime_started = False
        stopped: LocalReaderSetupStep | None = None

        def record(step: LocalReaderSetupStep, state: LocalReaderSetupStepState, failed: str | None = None) -> None:
            nonlocal stopped
            steps.append(LocalReaderSetupStepOutcome(step=step, state=state, failed_condition_id=failed))
            if state is LocalReaderSetupStepState.FAILED:
                stopped = step

        def record_models(step: LocalReaderSetupStep, items: list[LocalReaderModelOutcome]) -> None:
            models.extend(items)
            failed = next((item for item in items if not item.succeeded), None)
            if failed is not None:
                record(step, LocalReaderSetupStepState.FAILED, failed.failed_condition_id)
            elif all(item.already_satisfied for item in items):
                record(step, LocalReaderSetupStepState.UNCHANGED)
            else:
                record(step, LocalReaderSetupStepState.CHANGED)

        await context.events.phase(local_reader_setup_phase(LocalReaderSetupStep.INSTALL))
        if await asyncio.to_thread(read_runtime_version) is not None:
            # A runtime that already answers needs no install, wherever it lives.
            record(LocalReaderSetupStep.INSTALL, LocalReaderSetupStepState.UNCHANGED)
        else:
            installed = await self._install(consent=consent)
            install = installed.install
            if not installed.succeeded:
                record(LocalReaderSetupStep.INSTALL, LocalReaderSetupStepState.FAILED, installed.failed_condition_id)
            elif install is not None and install.already_installed:
                record(LocalReaderSetupStep.INSTALL, LocalReaderSetupStepState.UNCHANGED)
            else:
                record(LocalReaderSetupStep.INSTALL, LocalReaderSetupStepState.CHANGED)

        if stopped is None:
            await context.events.phase(local_reader_setup_phase(LocalReaderSetupStep.START))
            started = await self._start()
            runtime_started = started.runtime_started
            if not started.succeeded:
                record(LocalReaderSetupStep.START, LocalReaderSetupStepState.FAILED, started.failed_condition_id)
            else:
                record(
                    LocalReaderSetupStep.START,
                    LocalReaderSetupStepState.CHANGED if runtime_started else LocalReaderSetupStepState.UNCHANGED,
                )

        targets = _targets(None) if stopped is None else ()
        if stopped is None:
            await context.events.phase(local_reader_setup_phase(LocalReaderSetupStep.PULL))
            pulled = await self._pull(targets, context, step=LocalReaderSetupStep.PULL, skip_installed=True)
            record_models(LocalReaderSetupStep.PULL, pulled)
        if stopped is None:
            await context.events.phase(local_reader_setup_phase(LocalReaderSetupStep.LOAD))
            record_models(LocalReaderSetupStep.LOAD, await self._load(targets, step=LocalReaderSetupStep.LOAD))
        if stopped is None:
            await context.events.phase(local_reader_setup_phase(LocalReaderSetupStep.VERIFY))
            verified = await self._verify_targets(targets, step=LocalReaderSetupStep.VERIFY)
            models.extend(verified)
            failed = next((item for item in verified if not item.succeeded), None)
            if failed is not None:
                record(LocalReaderSetupStep.VERIFY, LocalReaderSetupStepState.FAILED, failed.failed_condition_id)
            else:
                # Verification observes; a pass changes nothing.
                record(LocalReaderSetupStep.VERIFY, LocalReaderSetupStepState.UNCHANGED)

        reached = {step.step for step in steps}
        steps.extend(
            LocalReaderSetupStepOutcome(step=step, state=LocalReaderSetupStepState.NOT_REACHED)
            for step in LocalReaderSetupStep
            if step not in reached
        )
        return LocalReaderProvisionOutcome(
            action=LocalReaderProvisionAction.SETUP,
            succeeded=stopped is None,
            runtime_started=runtime_started,
            install=install,
            models=tuple(models),
            steps=tuple(steps),
            stopped_step=stopped,
        )


def _settled(action: LocalReaderProvisionAction, items: list[LocalReaderModelOutcome]) -> LocalReaderProvisionOutcome:
    return LocalReaderProvisionOutcome(
        action=action,
        succeeded=bool(items) and all(item.succeeded for item in items),
        models=tuple(items),
    )


def build_local_reader_operation_definition(
    *,
    spawn: RuntimeSpawner,
    run_installer: InstallerRunner,
    text_probe: TextExtractionFitnessProbe,
) -> OperationDefinition:
    """Bind the injected process and fitness ports to the canonical provisioning operation."""

    def build() -> LocalReaderProvisionExecutor:
        return LocalReaderProvisionExecutor(spawn=spawn, run_installer=run_installer, text_probe=text_probe)

    return OperationDefinition(
        definition_id=LOCAL_READER_OPERATION_DEFINITION_ID,
        request_type=LocalReaderProvisionRequest,
        result_type=LocalReaderProvisionOutcome,
        executor_factory=OperationExecutorFactory(
            request_type=LocalReaderProvisionRequest,
            executor_type=LocalReaderProvisionExecutor,
            build=build,
        ),
        phase_codes=_PHASES,
        interaction_kinds=frozenset[OperationInteractionKind](),
        capabilities=OperationCapabilities(
            durability=OperationDurability.RECORDED,
            cancellation=OperationCancellation.UNSUPPORTED,
            deadline=OperationDeadline.ABSENT,
            replay=OperationReplayPolicy.IDEMPOTENT_SUBMIT,
            baseline=OperationBaselinePolicy.NONE,
            request_storage=OperationRequestStoragePolicy.CREDENTIAL_FREE_JOURNAL,
            sensitive_input=OperationSensitiveInputPolicy.NONE,
            conflict_scope=OperationConflictScope.DEFINITION_SUBJECT,
            owned_resources=frozenset(),
            # Pulling several models, or a setup that installs and then stops
            # at a later step, commits only part of what was asked.
            permitted_effects=frozenset(OperationEffect),
            close_policy=OperationClosePolicy.DETACH_ALLOWED,
        ),
        reconciliation_policy=OperationReconciliationPolicy.INTERRUPT,
        permitted_frontends=frozenset(
            {OperationFrontendProjection.CLI, OperationFrontendProjection.MCP, OperationFrontendProjection.TUI}
        ),
    )


def build_local_reader_operation_registration(
    definition: OperationDefinition,
) -> OperationPublicDefinitionRegistrationV1:
    """Bind the provisioning definition to its stable public schemas."""
    return OperationPublicDefinitionRegistrationV1.compose(
        definition=definition,
        request_schema=OperationSchemaBindingV1.bind(
            schema_id=f"{LOCAL_READER_OPERATION_DEFINITION_ID}.request",
            schema_version=1,
            model_type=LocalReaderProvisionRequest,
        ),
        result_schema=OperationSchemaBindingV1.bind(
            schema_id=f"{LOCAL_READER_OPERATION_DEFINITION_ID}.result",
            schema_version=1,
            model_type=LocalReaderProvisionPublicResultV1,
        ),
        result_projector=_project_result,
    )
