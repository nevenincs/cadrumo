"""The sole operation gateway to the native components client and wire protocol."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Final, override

from ..adapters.outbound.components.client import ComponentsCancellation, ComponentsRequest, run_components_role
from ..adapters.outbound.components.protocol import (
    ComponentsCommand,
    ComponentsEvent,
    ComponentsNoticeCode,
    ComponentsPhaseLine,
    ComponentsProgressLine,
    ComponentsResultLine,
)
from ..application.components_operations import (
    ComponentsOperationPort,
    ComponentsRoleEvent,
    ComponentsRoleEventSink,
    ComponentsRoleLauncher,
    ComponentsRoleNotice,
    ComponentsRolePhase,
    ComponentsRoleProgress,
    ComponentsRoleRun,
    LaunchedComponentsOperationPort,
    ProvisionCommand,
    ProvisionOutcome,
    ProvisionPlan,
    ProvisionResult,
    build_components_definitions,
    build_components_registration,
)
from ..application.dependency_contracts import DependencyItemKind
from ..application.operations.operation_definition import OperationDefinition
from ..application.operations.registry import OperationPublicDefinitionRegistrationV1

_QUICK_TIMEOUT: Final = 30.0
_NOTICE_LOCALE_KEYS: Final[dict[ComponentsNoticeCode, str]] = {
    ComponentsNoticeCode.RETRYING: "dependencies.setup.retrying",
    ComponentsNoticeCode.WAITING_FOR_SERVER: "dependencies.setup.waiting_for_server",
    ComponentsNoticeCode.FOLLOWING: "dependencies.setup.following",
    ComponentsNoticeCode.CANCEL_REQUESTED: "dependencies.setup.cancel_requested",
    ComponentsNoticeCode.INPUT_REFUSED: "dependencies.setup.input_refused",
}


def _result(result: ComponentsResultLine) -> ProvisionResult:
    return ProvisionResult(
        outcome=ProvisionOutcome(result.outcome.value),
        rows=result.status_rows(),
        setup_complete=result.setup_complete,
        plan=None if result.plan is None else ProvisionPlan.model_validate_json(result.plan.model_dump_json()),
        plan_digest=result.plan_digest,
        failure_category=result.failure_category,
        item_id=result.item_id,
        items=result.items,
    )


def read_component_status(items: tuple[DependencyItemKind, ...] = ()) -> ProvisionResult:
    """Quick local engine read for composed application readers during migration."""
    return _result(
        run_components_role(ComponentsRequest(ComponentsCommand.STATUS, items=items), timeout=_QUICK_TIMEOUT)
    )


class _NativeRoleRun(ComponentsRoleRun):
    def __init__(self, task: asyncio.Task[ProvisionResult], cancellation: ComponentsCancellation) -> None:
        """Bind the declared collaborators without starting any work."""
        self._task, self._cancellation = task, cancellation

    @property
    @override
    def task(self) -> asyncio.Task[ProvisionResult]:
        return self._task

    @override
    def cancel(self) -> None:
        self._cancellation.cancel()


def _application_event(
    event: ComponentsEvent, *, approve: str | None, cancellation: ComponentsCancellation
) -> ComponentsRoleEvent:
    """Translate one wire event; a follower of an unapproved plan is stopped where it is observed."""
    if isinstance(event, ComponentsPhaseLine):
        return ComponentsRolePhase(event.phase_code)
    if isinstance(event, ComponentsProgressLine):
        return ComponentsRoleProgress(
            completed=event.completed,
            total=event.total,
            unit_code=event.unit_code,
            subject_code=event.subject_code,
        )
    followed_other_plan = (
        event.notice_code is ComponentsNoticeCode.FOLLOWING and approve is not None and event.plan_digest != approve
    )
    if followed_other_plan:
        cancellation.cancel()
    return ComponentsRoleNotice(_NOTICE_LOCALE_KEYS[event.notice_code], followed_other_plan=followed_other_plan)


class NativeComponentsRoleLauncher(ComponentsRoleLauncher):
    """Start the contained role through the native components client."""

    @override
    def start(
        self,
        command: ProvisionCommand,
        items: tuple[DependencyItemKind, ...],
        *,
        approve: str | None,
        on_event: ComponentsRoleEventSink,
    ) -> ComponentsRoleRun:
        """Run the command on a worker thread and relay its wire events as application events."""
        cancellation = ComponentsCancellation()
        full = command is ProvisionCommand.VERIFY
        request = ComponentsRequest(
            ComponentsCommand.STATUS if full else ComponentsCommand(command.value),
            items=items,
            full=full,
            approve=approve,
        )
        timeout = _QUICK_TIMEOUT if command is ProvisionCommand.STATUS and not full else None

        def relay(event: ComponentsEvent) -> None:
            on_event(_application_event(event, approve=approve, cancellation=cancellation))

        async def drive() -> ProvisionResult:
            line = await asyncio.to_thread(
                run_components_role, request, on_event=relay, cancellation=cancellation, timeout=timeout
            )
            return _result(line)

        return _NativeRoleRun(asyncio.create_task(drive()), cancellation)


@dataclass(frozen=True, slots=True)
class ComponentsOperations:
    """The component definitions and their public contract bindings."""

    definitions: tuple[OperationDefinition, ...]
    registrations: tuple[OperationPublicDefinitionRegistrationV1, ...]


def build_components_operations(port: ComponentsOperationPort | None = None) -> ComponentsOperations:
    """Compose the component group without launching a role."""
    definitions = build_components_definitions(
        LaunchedComponentsOperationPort(NativeComponentsRoleLauncher()) if port is None else port
    )
    return ComponentsOperations(definitions, tuple(build_components_registration(item) for item in definitions))
