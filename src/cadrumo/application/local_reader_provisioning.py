"""Execution of supervised local-reader requests: start, load, verify and remove.

None of these actions downloads or installs anything. Fetching a model and
installing the local model program run under the registered setup operation,
through the setup items in :mod:`.local_reader_setup_items`.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Coroutine, Mapping
from dataclasses import dataclass
from pathlib import Path

from ..core.config import override_settings
from ..core.model_catalogue import ModelRole
from ..core.operations import OperationEffect
from ..core.time.clock import now
from .local_reader import RoleModelTarget, TextExtractionFitnessProbe, role_model_targets, verify_role_target
from .local_reader_contracts import (
    LOCAL_READER_EXECUTE_PHASE,
    LOCAL_READER_OPERATION_SUBJECT,
    LOCAL_READER_PREFLIGHT_PHASE,
    LOCAL_READER_SETTLEMENT_PHASE,
    LocalReaderModelOutcome,
    LocalReaderProvisionAction,
    LocalReaderProvisionOutcome,
    LocalReaderProvisionRequest,
)
from .operations.models import OperationIdentity, OperationRequest
from .operations.owner import OperationExecutorContext
from .provisioning_host import RuntimeSpawner, start_runtime
from .provisioning_runtime import load_runtime_model, remove_runtime_model

__all__ = [
    "LocalReaderProvisionExecutor",
    "RuntimeServerOwnerStart",
    "local_reader_provision_effect",
    "owner_started_spawner",
    "provision_local_reader",
]

_PREFLIGHT = LOCAL_READER_PREFLIGHT_PHASE
_EXECUTE = LOCAL_READER_EXECUTE_PHASE
_SETTLEMENT = LOCAL_READER_SETTLEMENT_PHASE


@dataclass(frozen=True, slots=True)
class RuntimeServerOwnerStart:
    """Starts the runtime's server through the process that owns the one executing the operation.

    A process that is itself contained cannot keep a server alive: whatever it
    starts ends with it. Its owner starts the server instead. ``start`` asks
    for that on behalf of one invocation and returns the server's process id,
    or ``None`` when the owner did not start it. The owner locates the runtime
    and derives its environment itself, so nothing here names a program.
    """

    start: Callable[[OperationIdentity], Coroutine[None, None, int | None]]


def owner_started_spawner(
    port: RuntimeServerOwnerStart,
    identity: OperationIdentity,
    loop: asyncio.AbstractEventLoop,
) -> RuntimeSpawner:
    """Return a spawner that asks the owning process to start the runtime's server for one invocation.

    The returned spawner runs on a worker thread and asks the owner over
    ``loop``. What this process located is deliberately not sent: the owner
    locates the runtime and derives its environment itself.
    """

    def spawn(executable: Path, environment: Mapping[str, str]) -> int:
        del executable, environment
        process_id = asyncio.run_coroutine_threadsafe(port.start(identity), loop).result()
        if process_id is None:
            raise OSError("the owning process did not start the runtime server")
        return process_id

    return spawn


def _refused_target(target: RoleModelTarget) -> LocalReaderModelOutcome:
    return LocalReaderModelOutcome(
        roles=target.roles,
        licence_advisories=target.licence_advisories,
        succeeded=False,
        facts=dict(target.selection_facts),
        precondition_verdict=target.selection_verdict,
    )


def _targets(role: ModelRole | None, model: str | None = None) -> tuple[RoleModelTarget, ...]:
    return role_model_targets(None if role is None else (role,), explicit_model=model)


def _settled_effect(changed: int, failed: int) -> OperationEffect:
    if changed == 0:
        return OperationEffect.NONE
    return OperationEffect.PARTIAL if failed else OperationEffect.UPDATED


def local_reader_provision_effect(outcome: LocalReaderProvisionOutcome) -> OperationEffect:
    """Return the committed extent a settled local-reader outcome represents."""
    if outcome.action is LocalReaderProvisionAction.START:
        return OperationEffect.UPDATED if outcome.runtime_started else OperationEffect.NONE
    if outcome.action is LocalReaderProvisionAction.VERIFY:
        return OperationEffect.NONE
    changed = sum(item.succeeded and not item.already_satisfied for item in outcome.models)
    failed = sum(not item.succeeded for item in outcome.models)
    return _settled_effect(changed, failed)


class _LocalReaderProvisioner:
    """Every local-reader action, over the injected process and fitness ports."""

    def __init__(self, *, spawn: RuntimeSpawner, text_probe: TextExtractionFitnessProbe) -> None:
        self._spawn = spawn
        self._text_probe = text_probe

    async def run(self, payload: LocalReaderProvisionRequest) -> LocalReaderProvisionOutcome:
        match payload.action:
            case LocalReaderProvisionAction.START:
                return await self._start()
            case LocalReaderProvisionAction.LOAD:
                return _settled(
                    LocalReaderProvisionAction.LOAD, await self._load(_targets(payload.role, payload.model))
                )
            case LocalReaderProvisionAction.VERIFY:
                return _settled(
                    LocalReaderProvisionAction.VERIFY, await self._verify(_targets(payload.role, payload.model))
                )
            case LocalReaderProvisionAction.REMOVE:
                return _settled(
                    LocalReaderProvisionAction.REMOVE, await self._remove(_targets(payload.role, payload.model))
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

    async def _load(self, targets: tuple[RoleModelTarget, ...]) -> list[LocalReaderModelOutcome]:
        items: list[LocalReaderModelOutcome] = []
        for target in targets:
            if target.model is None or target.requirement_bytes is None:
                items.append(_refused_target(target))
                continue
            loaded = await asyncio.to_thread(load_runtime_model, target.model, target.requirement_bytes)
            items.append(
                LocalReaderModelOutcome(
                    model=loaded.model,
                    roles=target.roles,
                    licence_advisories=target.licence_advisories,
                    succeeded=loaded.loaded,
                    already_satisfied=loaded.already_loaded,
                    contention=loaded.contention,
                    resident=loaded.loaded,
                    elapsed_ms=loaded.elapsed_ms,
                    facts=dict(loaded.facts),
                    precondition_verdict=loaded.precondition_verdict,
                )
            )
        return items

    async def _verify(self, targets: tuple[RoleModelTarget, ...]) -> list[LocalReaderModelOutcome]:
        items: list[LocalReaderModelOutcome] = []
        for target in targets:
            if target.model is None:
                items.append(_refused_target(target))
                continue
            ready = await asyncio.to_thread(verify_role_target, target, text_probe=self._text_probe)
            items.append(
                LocalReaderModelOutcome(
                    model=ready.model,
                    roles=target.roles,
                    licence_advisories=target.licence_advisories,
                    succeeded=ready.ready,
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
                items.append(_refused_target(target))
                continue
            removed = await asyncio.to_thread(remove_runtime_model, target.model)
            items.append(
                LocalReaderModelOutcome(
                    model=removed.model,
                    roles=target.roles,
                    licence_advisories=target.licence_advisories,
                    succeeded=removed.removed,
                    freed_bytes=removed.freed_bytes,
                    was_installed=removed.was_installed,
                    facts=dict(removed.facts),
                    precondition_verdict=removed.precondition_verdict,
                )
            )
        return items


async def provision_local_reader(
    payload: LocalReaderProvisionRequest,
    *,
    spawn: RuntimeSpawner,
    text_probe: TextExtractionFitnessProbe,
) -> LocalReaderProvisionOutcome:
    """Run one local-reader action and return its settled outcome.

    The single implementation of start, load, verify and remove, which the
    supervised operation wraps. Never raises for a refusal: every refusal is a
    typed verdict on the outcome.
    """
    provisioner = _LocalReaderProvisioner(spawn=spawn, text_probe=text_probe)
    language = payload.output_language
    # A licence advisory is prose, written where the model is selected; the
    # frontend that asked must read it in its own language, not this host's.
    if language is None:
        return await provisioner.run(payload)
    with override_settings(cadrumo_output_language=language.value):
        return await provisioner.run(payload)


class LocalReaderProvisionExecutor:
    """Supervise :func:`provision_local_reader` and persist its outcome."""

    def __init__(
        self,
        *,
        spawn: RuntimeSpawner | RuntimeServerOwnerStart,
        text_probe: TextExtractionFitnessProbe,
    ) -> None:
        """Bind the injected runtime server start and text-reader fitness probe."""
        self._spawn = spawn
        self._text_probe = text_probe

    def _spawner(self, identity: OperationIdentity) -> RuntimeSpawner:
        """Return the spawner one invocation starts the runtime's server with."""
        port = self._spawn
        if not isinstance(port, RuntimeServerOwnerStart):
            return port
        return owner_started_spawner(port, identity, asyncio.get_running_loop())

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
            request.payload, spawn=self._spawner(context.identity), text_probe=self._text_probe
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
