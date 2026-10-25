"""Execution of supervised local-reader requests: load and verify.

Neither action downloads, installs, starts or removes anything: both act on
models the native component engine installed, on the server the runtime
manager runs.
"""

from __future__ import annotations

import asyncio

from ..core.config import override_settings
from ..core.model_catalogue import ModelRole
from ..core.operations import OperationEffect
from ..core.time.clock import now
from .local_reader import RoleModelTarget, role_model_targets, verify_role_target
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
from .operations.models import OperationRequest
from .operations.owner import OperationExecutorContext
from .provisioning_runtime import load_runtime_model

__all__ = ["LocalReaderProvisionExecutor", "local_reader_provision_effect", "provision_local_reader"]

_PREFLIGHT = LOCAL_READER_PREFLIGHT_PHASE
_EXECUTE = LOCAL_READER_EXECUTE_PHASE
_SETTLEMENT = LOCAL_READER_SETTLEMENT_PHASE


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
    if outcome.action is LocalReaderProvisionAction.VERIFY:
        return OperationEffect.NONE
    changed = sum(item.succeeded and not item.already_satisfied for item in outcome.models)
    failed = sum(not item.succeeded for item in outcome.models)
    return _settled_effect(changed, failed)


class _LocalReaderProvisioner:
    """Every local-reader action."""

    async def run(self, payload: LocalReaderProvisionRequest) -> LocalReaderProvisionOutcome:
        match payload.action:
            case LocalReaderProvisionAction.LOAD:
                return _settled(
                    LocalReaderProvisionAction.LOAD, await self._load(_targets(payload.role, payload.model))
                )
            case LocalReaderProvisionAction.VERIFY:
                return _settled(
                    LocalReaderProvisionAction.VERIFY, await self._verify(_targets(payload.role, payload.model))
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
            ready = await asyncio.to_thread(verify_role_target, target)
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


async def provision_local_reader(payload: LocalReaderProvisionRequest) -> LocalReaderProvisionOutcome:
    """Run one local-reader action and return its settled outcome.

    The single implementation of load and verify, which the supervised
    operation wraps. Never raises for a refusal: every refusal is a typed
    verdict on the outcome.
    """
    provisioner = _LocalReaderProvisioner()
    language = payload.output_language
    # A licence advisory is prose, written where the model is selected; the
    # frontend that asked must read it in its own language, not this host's.
    if language is None:
        return await provisioner.run(payload)
    with override_settings(cadrumo_output_language=language.value):
        return await provisioner.run(payload)


class LocalReaderProvisionExecutor:
    """Supervise :func:`provision_local_reader` and persist its outcome."""

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
        outcome = await provision_local_reader(request.payload)
        await context.events.effect(local_reader_provision_effect(outcome))
        await context.events.phase(_SETTLEMENT)
        return await context.operands.put(outcome, written_at=now())


def _settled(action: LocalReaderProvisionAction, items: list[LocalReaderModelOutcome]) -> LocalReaderProvisionOutcome:
    return LocalReaderProvisionOutcome(
        action=action,
        succeeded=bool(items) and all(item.succeeded for item in items),
        models=tuple(items),
    )
