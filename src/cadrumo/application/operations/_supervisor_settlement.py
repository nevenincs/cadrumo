"""Cancellation and terminal-settlement stages for operation supervision."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any, Protocol

from ...core.async_cleanup import close_async_resources
from ...core.operations import (
    LIFECYCLES_BEFORE_EXECUTOR_ENTRY,
    OperationCancellation,
    OperationLifecycle,
    OperationTerminalCondition,
)
from .errors import OperationDeclarationError
from .models import OperationId, OperationTerminalReceipt
from .persistence.events import (
    OperationDiagnosticEvent,
    OperationEvent,
    OperationTerminalEvent,
)
from .persistence.journal import OperationPersistedSnapshot
from .persistence.leases import OperationOwnerLease


class SupervisorHost(Protocol):
    if TYPE_CHECKING:

        def __getattr__(self, name: str) -> Any: ...


class SupervisorSettlementMixin(SupervisorHost):
    """Own cancellation requests, cleanup, terminal receipts, and commits."""

    def _validate_cancellation_request(self, snapshot: OperationPersistedSnapshot) -> timedelta:
        """Validate cancellation policy and return the configured cleanup window."""
        cancellation = self._require_pinned_definition(snapshot).capabilities.cancellation
        if cancellation is OperationCancellation.UNSUPPORTED:
            raise ValueError("operation does not support cancellation")
        self._require_cleanup_timeout(cancellation)
        if snapshot.lifecycle is OperationLifecycle.TERMINAL:
            raise ValueError("terminal operation cannot receive a cancellation request")
        if snapshot.lifecycle in LIFECYCLES_BEFORE_EXECUTOR_ENTRY:
            raise ValueError("operation must be running before cancellation can be requested")
        cleanup_timeout = self._cleanup_timeout
        if cleanup_timeout is None:
            raise ValueError("cancellable operation requires a configured cleanup timeout")
        return cleanup_timeout

    async def _persist_cancellation_request(
        self,
        operation_id: OperationId,
        snapshot: OperationPersistedSnapshot,
        cleanup_timeout: timedelta,
    ) -> OperationPersistedSnapshot:
        """Persist the cancellation state and update its in-memory context."""
        requested_at = self._clock()
        successor = await self._advance(
            snapshot,
            lifecycle=OperationLifecycle.CANCELLATION_REQUESTED,
            cleanup_deadline=requested_at + cleanup_timeout,
            cancellation_requested_at=requested_at,
        )
        context = self._contexts.get(operation_id)
        if context is not None:
            context.cancellation.record_request(successor)
        return successor

    async def request_cancel(
        self,
        operation_id: OperationId,
        *,
        expected_revision: int | None = None,
    ) -> OperationPersistedSnapshot:
        """Request cooperative cancellation at an optional exact revision."""
        snapshot = await self.inspect(operation_id)
        if expected_revision is not None and snapshot.revision != expected_revision:
            raise ValueError("operation cancellation expected revision is stale")
        pre_entry = await self._cancel_pre_entry_secret(snapshot)
        if pre_entry is not None:
            return pre_entry
        cleanup_timeout = self._validate_cancellation_request(snapshot)
        if snapshot.cancellation_requested_at is not None:
            return snapshot
        return await self._persist_cancellation_request(operation_id, snapshot, cleanup_timeout)

    async def _acknowledge_cancellation(
        self,
        context_snapshot: OperationPersistedSnapshot,
    ) -> OperationPersistedSnapshot:
        """Persist an executor's safe-stop acknowledgement after its request."""
        snapshot = await self.inspect(context_snapshot.identity.operation_id)
        if snapshot.identity != context_snapshot.identity:
            raise ValueError("cancellation acknowledgement identity does not match current operation")
        if snapshot.cancellation_requested_at is None:
            raise ValueError("cancellation acknowledgement requires a durable request")
        if snapshot.cancellation_acknowledged_at is not None:
            return snapshot
        if snapshot.lifecycle not in {OperationLifecycle.CANCELLATION_REQUESTED, OperationLifecycle.SETTLING}:
            raise ValueError("cancellation acknowledgement requires requested or settling lifecycle")
        return await self._advance(
            snapshot,
            lifecycle=OperationLifecycle.SETTLING,
            cancellation_acknowledged_at=self._clock(),
        )

    async def _set_cancellation_deferred(
        self,
        context_snapshot: OperationPersistedSnapshot,
        deferred: bool,
    ) -> OperationPersistedSnapshot:
        """Persist current cancellation availability across an irreversible section."""
        while True:
            current = await self.inspect(context_snapshot.identity.operation_id)
            if current.identity != context_snapshot.identity:
                raise ValueError("cancellation availability identity does not match current operation")
            if deferred and current.cancellation_requested_at is not None:
                raise ValueError("cancellation was requested before the irreversible section began")
            if current.cancellation_deferred is deferred:
                return current
            try:
                return await self._advance(
                    current,
                    lifecycle=current.lifecycle,
                    cancellation_deferred=deferred,
                )
            except Exception:
                latest = await self.inspect(current.identity.operation_id)
                if latest.revision == current.revision:
                    raise

    async def _escalate_cleanup_deadline(self, operation_id: OperationId) -> OperationPersistedSnapshot:
        """Retain uncertainty after the cleanup window without publishing a false terminal state."""
        snapshot = await self.inspect(operation_id)
        if snapshot.lifecycle is OperationLifecycle.TERMINAL:
            return snapshot
        if snapshot.cancellation_requested_at is None or snapshot.cleanup_deadline is None:
            raise ValueError("cleanup escalation requires a durable cancellation deadline")
        if snapshot.lifecycle is OperationLifecycle.SETTLING:
            return snapshot
        return await self._advance(snapshot, lifecycle=OperationLifecycle.SETTLING)

    def _validate_settlement_request(
        self,
        snapshot: OperationPersistedSnapshot,
        receipt: OperationTerminalReceipt,
    ) -> None:
        """Validate receipt identity, declared effects, and local stop proof."""
        if receipt.identity != snapshot.identity or receipt.revision != snapshot.revision + 1:
            raise ValueError("terminal receipt does not match successor revision")
        definition = self._require_pinned_definition(snapshot)
        if receipt.effect not in definition.capabilities.permitted_effects:
            raise OperationDeclarationError("terminal receipt effect is not declared by its definition")
        if (
            receipt.condition is not OperationTerminalCondition.INTERRUPTED
            or snapshot.identity.operation_id in self._executor_tasks
        ):
            self._validate_executor_stopped_for_settlement(snapshot, receipt.condition)
        if receipt.condition is OperationTerminalCondition.CANCELLED:
            self._validate_cancelled_settlement(snapshot)

    @staticmethod
    def _settlement_events(
        snapshot: OperationPersistedSnapshot,
        receipt: OperationTerminalReceipt,
        now: datetime,
    ) -> tuple[OperationEvent, ...]:
        """Build diagnostic and terminal events in their durable sequence order."""
        diagnostic_event = (
            OperationDiagnosticEvent(
                identity=snapshot.identity,
                revision=receipt.revision,
                sequence=snapshot.event_cursor + 1,
                timestamp=now,
                code="operation.diagnostic",
                diagnostic_ref=receipt.diagnostic_ref,
            )
            if receipt.diagnostic_ref is not None
            else None
        )
        terminal_event = OperationTerminalEvent(
            identity=snapshot.identity,
            revision=receipt.revision,
            sequence=snapshot.event_cursor + (2 if diagnostic_event is not None else 1),
            timestamp=now,
            code="operation.terminal",
            receipt=receipt,
        )
        return (diagnostic_event, terminal_event) if diagnostic_event is not None else (terminal_event,)

    @staticmethod
    def _settlement_successor(
        snapshot: OperationPersistedSnapshot,
        receipt: OperationTerminalReceipt,
        events: tuple[OperationEvent, ...],
    ) -> OperationPersistedSnapshot:
        """Materialize the terminal snapshot from the committed receipt events."""
        return snapshot.model_copy(
            update={
                "revision": receipt.revision,
                "lifecycle": OperationLifecycle.TERMINAL,
                "terminal_condition": receipt.condition,
                "effect": receipt.effect,
                "updated_at": receipt.settled_at,
                "event_cursor": events[-1].sequence,
                "events": events,
                "terminal_receipt": receipt,
                "pending_interaction": None,
            }
        )

    async def _commit_settlement(
        self,
        operation_id: OperationId,
        snapshot: OperationPersistedSnapshot,
        receipt: OperationTerminalReceipt,
        lease: OperationOwnerLease,
    ) -> tuple[OperationPersistedSnapshot | None, bool]:
        """Complete cleanup and atomically commit terminal events and state."""
        try:
            await self._complete_cleanup_before_settlement(snapshot)
        except TimeoutError:
            return None, True
        events = self._settlement_events(snapshot, receipt, receipt.settled_at)
        successor = self._settlement_successor(snapshot, receipt, events)
        await self._journal.commit(successor, expected_revision=snapshot.revision, lease=lease)
        await self._release_exact_lease(lease, observed_at=receipt.settled_at)
        self._ephemeral_secrets.discard(operation_id)
        return successor, False

    async def settle(self, operation_id: OperationId, receipt: OperationTerminalReceipt) -> OperationPersistedSnapshot:
        """Persist one validated terminal receipt after owned cleanup completes."""
        snapshot = await self.inspect(operation_id)
        self._validate_settlement_request(snapshot, receipt)
        now = receipt.settled_at
        successor: OperationPersistedSnapshot | None = None
        cleanup_deadline_elapsed = False
        async with self._lease_lock(snapshot.identity.operation_id):
            lease = await self._require_owned_lease_unlocked(snapshot.identity, now)
            successor, cleanup_deadline_elapsed = await self._commit_settlement(
                operation_id,
                snapshot,
                receipt,
                lease,
            )
        if cleanup_deadline_elapsed:
            await self._escalate_cleanup_deadline(operation_id)
            raise TimeoutError("operation cleanup deadline elapsed before terminal settlement")
        if successor is None:
            raise RuntimeError("operation terminal settlement did not produce a successor snapshot")
        self._contexts.pop(operation_id, None)
        self._executor_tasks.pop(operation_id, None)
        self._cleanup_tasks.pop(operation_id, None)
        self._continuation_tasks.pop(operation_id, None)
        self._notify_durable_change(successor)
        return successor

    def _validate_executor_stopped_for_settlement(
        self,
        snapshot: OperationPersistedSnapshot,
        condition: OperationTerminalCondition,
    ) -> None:
        """Require local stop proof before a terminal condition claims work is over."""
        if snapshot.executor_entered_at is None or snapshot.lifecycle in LIFECYCLES_BEFORE_EXECUTOR_ENTRY:
            return
        executor_task = self._executor_tasks.get(snapshot.identity.operation_id)
        if executor_task is None or not executor_task.done():
            raise ValueError(f"{condition.value} settlement requires completed executor work")

    def _validate_cancelled_settlement(self, snapshot: OperationPersistedSnapshot) -> None:
        """Reject a cancellation terminal claim until the executor's safe stop is proven."""
        if snapshot.cancellation_acknowledged_at is None:
            raise ValueError("cancelled settlement requires durable executor acknowledgement")
        cleanup_deadline = snapshot.cleanup_deadline
        if cleanup_deadline is None:
            raise ValueError("cancelled settlement requires a durable cleanup deadline")
        if self._clock() >= cleanup_deadline:
            raise ValueError("cleanup deadline elapsed; cancellation remains unsettled")

    async def _complete_cleanup_before_settlement(self, snapshot: OperationPersistedSnapshot) -> None:
        """Close owned resources within the durable cleanup window before any terminal commit."""
        operation_id = snapshot.identity.operation_id
        cleanup_task = self._cleanup_tasks.get(operation_id)
        if cleanup_task is None:
            cleanup_task = asyncio.create_task(
                close_async_resources(*self._resources.get(operation_id, ()), task_name="operation-settlement"),
                name=f"operation-cleanup-{operation_id}",
            )
            self._cleanup_tasks[operation_id] = cleanup_task
        cleanup_deadline = snapshot.cleanup_deadline
        if cleanup_deadline is not None:
            now = self._clock()
            if now >= cleanup_deadline:
                raise TimeoutError("operation cleanup deadline elapsed before terminal settlement")
            done, _ = await asyncio.wait(
                (cleanup_task,),
                timeout=(cleanup_deadline - now).total_seconds(),
            )
            if cleanup_task not in done:
                raise TimeoutError("operation cleanup deadline elapsed before terminal settlement")
        await cleanup_task
        self._resources.pop(operation_id, None)
