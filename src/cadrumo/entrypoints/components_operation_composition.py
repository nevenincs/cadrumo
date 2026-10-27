"""The sole operation gateway to the native components client and wire protocol."""

from __future__ import annotations

import asyncio
import time
from collections import deque
from dataclasses import dataclass
from threading import Lock
from typing import Final, override

from cadrumo_client.contracts.contracts import RefusalError

from ..adapters.outbound.components.client import ComponentsCancellation, ComponentsRequest, run_components_role
from ..adapters.outbound.components.protocol import (
    ComponentsCommand,
    ComponentsEvent,
    ComponentsNoticeCode,
    ComponentsNoticeLine,
    ComponentsPhaseLine,
    ComponentsProgressLine,
    ComponentsResultLine,
)
from ..application.components_operations import (
    ComponentsOperationPort,
    ProvisionCommand,
    ProvisionOutcome,
    ProvisionPlan,
    ProvisionResult,
    build_components_definitions,
    build_components_registration,
)
from ..application.dependency_contracts import DependencyItemKind
from ..application.operations.capabilities import OperationOwnedResource
from ..application.operations.operation_definition import OperationDefinition
from ..application.operations.owner import OperationExecutorContext, retain_failed_operation_resources
from ..application.operations.registry import OperationPublicDefinitionRegistrationV1
from ..core.async_cleanup import AsyncResourceCleanupError, await_cancellation_complete, has_async_cleanup_failure
from ..core.time.clock import now

_QUICK_TIMEOUT: Final = 30.0
_PROGRESS_INTERVAL: Final = 0.25
_CANCELLATION_POLL: Final = 0.2
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


class _RoleOwner:
    def __init__(self, task: asyncio.Task[ComponentsResultLine], cancellation: ComponentsCancellation) -> None:
        """Bind the declared collaborators without starting any work."""
        self.task, self.cancellation = task, cancellation

    async def close(self) -> None:
        if not self.task.done():
            self.cancellation.cancel()
        # The contained client's finally block ends the complete role process
        # tree. Settlement must wait for that ownership, not abandon a thread.
        try:
            await asyncio.shield(self.task)
        except AsyncResourceCleanupError as error:
            resources = error.resources
            await error.retry_cleanup()
            error.discard_released_resources(*resources)
        except RefusalError as error:
            if has_async_cleanup_failure(error):
                raise
            # This is the client's execution result, already reported to the
            # executor. Its contract ends the contained role before refusing;
            # replaying that refusal here would invent a cleanup failure.
            return


class NativeComponentsOperationPort(ComponentsOperationPort):
    """Run the contained role off-loop while journaling bounded progress."""

    @override
    async def run(
        self,
        command: ProvisionCommand,
        items: tuple[DependencyItemKind, ...],
        context: OperationExecutorContext,
        *,
        approve: str | None = None,
    ) -> ProvisionResult:
        """Hold role ownership, relay events and cancellation, and await terminal cleanup."""
        loop = asyncio.get_running_loop()
        changed = asyncio.Event()
        pending: deque[ComponentsEvent] = deque()
        guard = Lock()
        last_progress: dict[str, tuple[float, int, int]] = {}
        latest_progress: dict[str, ComponentsProgressLine] = {}
        cancellation = ComponentsCancellation()
        followed_other_plan = False

        def emit(event: ComponentsEvent) -> None:
            nonlocal followed_other_plan
            if (
                isinstance(event, ComponentsNoticeLine)
                and event.notice_code is ComponentsNoticeCode.FOLLOWING
                and approve is not None
                and event.plan_digest != approve
            ):
                followed_other_plan = True
                cancellation.cancel()
            with guard:
                if isinstance(event, ComponentsPhaseLine):
                    pending.extend(latest_progress.values())
                    latest_progress.clear()
                if isinstance(event, ComponentsProgressLine):
                    previous = last_progress.get(event.subject_code)
                    instant = time.monotonic()
                    if previous is not None and previous[1:] == (event.completed, event.total):
                        return
                    latest_progress[event.subject_code] = event
                    if (
                        previous is not None
                        and instant - previous[0] < _PROGRESS_INTERVAL
                        and event.completed != event.total
                    ):
                        return
                    last_progress[event.subject_code] = (instant, event.completed, event.total)
                    latest_progress.pop(event.subject_code, None)
                pending.append(event)
            loop.call_soon_threadsafe(changed.set)

        async def drain() -> None:
            with guard:
                events = tuple(pending)
                pending.clear()
            for event in events:
                if isinstance(event, ComponentsPhaseLine):
                    await context.events.phase(event.phase_code)
                elif isinstance(event, ComponentsProgressLine):
                    await context.events.progress(
                        completed=event.completed,
                        total=event.total,
                        unit_code=event.unit_code,
                        subject_code=event.subject_code,
                    )
                else:
                    await context.events.notice(_NOTICE_LOCALE_KEYS[event.notice_code])

        full = command is ProvisionCommand.VERIFY
        request = ComponentsRequest(
            ComponentsCommand.STATUS if full else ComponentsCommand(command.value),
            items=items,
            full=full,
            approve=approve,
        )
        task = asyncio.create_task(
            asyncio.to_thread(
                run_components_role,
                request,
                on_event=emit,
                cancellation=cancellation,
                timeout=_QUICK_TIMEOUT if command is ProvisionCommand.STATUS and not full else None,
            )
        )
        owner = _RoleOwner(task, cancellation)
        context.cleanup.own(owner, family=OperationOwnedResource.PROCESS)
        try:
            while not task.done():
                changed.clear()
                await drain()
                if context.cancellation.cancellation_requested or (
                    context.deadlines.execution_deadline is not None and now() >= context.deadlines.execution_deadline
                ):
                    cancellation.cancel()
                waiter = asyncio.create_task(changed.wait())
                try:
                    await asyncio.wait((task, waiter), timeout=_CANCELLATION_POLL, return_when=asyncio.FIRST_COMPLETED)
                finally:
                    waiter.cancel()
                    await asyncio.gather(waiter, return_exceptions=True)
            with guard:
                pending.extend(latest_progress.values())
                latest_progress.clear()
            await drain()
            try:
                result = await task
            except RefusalError as error:
                if has_async_cleanup_failure(error):
                    raise
                if followed_other_plan:
                    # The client has already ended the contained role. A
                    # follower that ignored cancellation still needs a fresh
                    # reviewed plan; its timeout must not erase that reason.
                    return ProvisionResult(outcome=ProvisionOutcome.FOLLOWED_PLAN_MISMATCH)
                raise
            if followed_other_plan:
                # The role may already have emitted another owner's successful
                # result. It cannot establish this approved invocation's effect.
                return ProvisionResult(outcome=ProvisionOutcome.FOLLOWED_PLAN_MISMATCH)
            return _result(result)
        except BaseException:
            with retain_failed_operation_resources(context.cleanup, family=OperationOwnedResource.PROCESS):
                cancellation.cancel()
                await await_cancellation_complete(owner.close(), task_name="components-role-cleanup")
                raise


@dataclass(frozen=True, slots=True)
class ComponentsOperations:
    """The component definitions and their public contract bindings."""

    definitions: tuple[OperationDefinition, ...]
    registrations: tuple[OperationPublicDefinitionRegistrationV1, ...]


def build_components_operations(port: ComponentsOperationPort | None = None) -> ComponentsOperations:
    """Compose the component group without launching a role."""
    definitions = build_components_definitions(NativeComponentsOperationPort() if port is None else port)
    return ComponentsOperations(definitions, tuple(build_components_registration(item) for item in definitions))
