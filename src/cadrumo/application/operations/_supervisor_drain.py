"""Bounded admission close and local-task settlement for the operation owner."""

from __future__ import annotations

import asyncio
from datetime import timedelta
from typing import override

from ...core.logging import get_logger
from ...core.operations import OperationCancellation, OperationClosePolicy, OperationLifecycle
from ._supervisor_host import SupervisorHost
from .drain import OperationDrainResult
from .models import OperationId
from .persistence.journal import OperationPersistedSnapshot

_log = get_logger("cadrumo.application.operations.supervisor")


def require_positive_duration(name: str, duration: timedelta | None) -> None:
    if duration is not None and duration <= timedelta():
        raise ValueError(f"{name} must be positive when configured")


class SupervisorDrainMixin(SupervisorHost):
    """Own one finite shutdown window and its recovery accounting."""

    @override
    async def drain(self, timeout: timedelta) -> OperationDrainResult:
        """Stop admissions and wait one total monotonic window for declared close.

        Any live task at the deadline is reported, not assumed cancelled. The
        caller owns process and descendant containment before releasing custody.
        Repeating drain observes the same local work under a new finite window.
        """
        require_positive_duration("operation host drain timeout", timeout)
        loop = asyncio.get_running_loop()
        deadline = loop.time() + timeout.total_seconds()
        self._accepting_admissions = False
        self._ephemeral_secrets.close()
        if self._typed_financial_operands is not None:
            for operation_id, task in self._typed_financial_operands.begin_close().items():
                self._drain_tasks.setdefault(operation_id, set()).add(task)
                task.add_done_callback(self._drain_close_completed)
        self._capture_drain_tasks()
        self._schedule_drain_settlement_closes(deadline)
        await self._await_pending_drain_tasks(deadline)
        await self._cancel_pending_drain_tasks(deadline)
        self._capture_drain_tasks()
        unresolved, recovery_required = self._drain_operation_ids()
        return OperationDrainResult(unresolved=unresolved, recovery_required=recovery_required)

    @override
    def _schedule_drain_settlement_closes(self, deadline: float) -> None:
        for operation_id, settlement in tuple(self._settlement_tasks.items()):
            if settlement.done() or operation_id in self._drain_close_tasks:
                continue
            close_task = asyncio.create_task(
                self._close_unsettled(operation_id, settlement, deadline),
                name=f"operation-drain-{operation_id}",
            )
            self._drain_close_tasks[operation_id] = close_task
            self._drain_tasks.setdefault(operation_id, set()).add(close_task)
            close_task.add_done_callback(self._drain_close_completed)

    @override
    async def _await_pending_drain_tasks(self, deadline: float) -> None:
        pending = self._pending_drain_tasks()
        if pending:
            await asyncio.wait(pending, timeout=max(0.0, deadline - asyncio.get_running_loop().time()))

    @override
    async def _cancel_pending_drain_tasks(self, deadline: float) -> None:
        self._capture_drain_tasks()
        pending = self._pending_drain_tasks()
        if pending:
            for task in pending:
                if task not in self._admissions:
                    task.cancel()
            await asyncio.wait(pending, timeout=max(0.0, deadline - asyncio.get_running_loop().time()))

    @override
    def _drain_operation_ids(self) -> tuple[tuple[OperationId, ...], tuple[OperationId, ...]]:
        unresolved = tuple(
            sorted(
                operation_id
                for operation_id, tasks in self._drain_tasks.items()
                if any(not task.done() for task in tasks)
            )
        )
        recovery_required = tuple(
            sorted(
                operation_id
                for operation_id, tasks in self._drain_tasks.items()
                if self._requires_recovery(operation_id, tasks)
            )
        )
        return unresolved, recovery_required

    @override
    async def shutdown(self) -> OperationDrainResult:
        """Close within a default bound and expose any remaining ownership."""
        return await self.drain(timedelta(seconds=5))

    @override
    def _capture_drain_tasks(self) -> None:
        for operation_id in tuple(self._leases_by_operation):
            self._drain_tasks.setdefault(operation_id, set())
        for mapping in (self._executor_tasks, self._cleanup_tasks, self._continuation_tasks, self._settlement_tasks):
            for operation_id, task in tuple(mapping.items()):
                self._drain_tasks.setdefault(operation_id, set()).add(task)
        for operation_id, task in tuple(self._settlement_tasks.items()):
            self._drain_settlements.setdefault(operation_id, task)
        for task, operation_id in tuple(self._admissions.items()):
            self._drain_tasks.setdefault(operation_id, set()).add(task)

    @override
    def _pending_drain_tasks(self) -> set[asyncio.Task[object]]:
        return {task for tasks in self._drain_tasks.values() for task in tasks if not task.done()}

    @override
    def _requires_recovery(self, operation_id: OperationId, tasks: set[asyncio.Task[object]]) -> bool:
        settlement = self._drain_settlements.get(operation_id)
        if settlement is None:
            return operation_id in self._leases_by_operation or bool(tasks)
        if not settlement.done() or settlement.cancelled():
            return True
        try:
            return settlement.result().lifecycle is not OperationLifecycle.TERMINAL
        except Exception:
            return True

    @override
    @staticmethod
    def _drain_close_completed(task: asyncio.Task[None]) -> None:
        if task.cancelled():
            return
        error = task.exception()
        if error is not None:
            _log.error("operation close failed: %s", task.get_name(), exc_info=error)

    @override
    async def _close_unsettled(
        self,
        operation_id: OperationId,
        settlement: asyncio.Task[OperationPersistedSnapshot],
        deadline: float,
    ) -> None:
        definition = self._require_pinned_definition(await self.inspect(operation_id))
        capabilities = definition.capabilities
        if (
            capabilities.close_policy is not OperationClosePolicy.DETACH_ALLOWED
            and capabilities.cancellation is not OperationCancellation.UNSUPPORTED
        ):
            try:
                await self.request_cancel(operation_id)
            except ValueError:
                _log.debug("operation %s could not accept a cancellation at host close", operation_id)
            else:
                loop = asyncio.get_running_loop()
                window = self._cleanup_timeout.total_seconds() if self._cleanup_timeout is not None else 0.0
                await asyncio.wait((settlement,), timeout=min(window, max(0.0, deadline - loop.time())))
        if not settlement.done():
            settlement.cancel()


__all__ = ["SupervisorDrainMixin"]
