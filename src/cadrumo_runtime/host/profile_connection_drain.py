"""Runtime drain behavior for profile connections."""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from threading import RLock, Thread
from typing import TYPE_CHECKING
from uuid import UUID

from cadrumo.core.diagnostic_log import diagnostic_error_fields, diagnostic_event
from cadrumo.core.logging import get_logger
from cadrumo_client.contracts.contracts import ExitReason, ShutdownIncompleteError
from cadrumo_client.contracts.deadline_budget import DEFAULT_TIMEOUT_POLICY
from cadrumo_runtime.contracts.profile_host import ProfileDrainResult
from cadrumo_runtime.contracts.profile_worker import ProfileWorkerDrained

from ..adapters.profile_worker import ProfileWorkerProcess
from .profile_host import RuntimeProfileHost
from .shutdown import RuntimeStop
from .terminated_operations import settle_drained_worker_operations, settle_terminated_worker_operations

if TYPE_CHECKING:
    from .profile_connections import RuntimeProfileConnections

_LOGGER = get_logger(__name__)


@dataclass
class ProfileDrainRecord:
    """Retain the original worker and its actual shutdown attempts until settlement."""

    host: RuntimeProfileHost
    worker: ProfileWorkerProcess | None = None
    begun: bool = False
    request: Thread | None = None
    containment: Thread | None = None
    receipt: ProfileWorkerDrained | None = None
    contained: bool = False
    settlement: Thread | None = None
    parent_settled: bool = False
    drained_settlement: Thread | None = None
    guard: RLock = field(default_factory=RLock, repr=False)


def containment_retry_needed(record: ProfileDrainRecord) -> bool:
    """Retry only a completed containment attempt that did not contain its worker."""
    thread = record.containment
    if thread is None or thread.ident is None or thread.is_alive():
        return False
    with record.guard:
        return not record.contained


def drain_record_can_settle(record: ProfileDrainRecord, contained: bool, running: bool) -> bool:
    """Settle only after every drain thread and worker containment is complete."""
    return not running and (record.worker is None or contained)


class ProfileConnectionDrainMixin:
    """Own the drain behavior of the profile connection service."""

    def close(self: RuntimeProfileConnections) -> None:
        """Fence all admissions before releasing profile workers and nonsecret state."""
        if not self._drain_guard.acquire(blocking=False):
            raise ShutdownIncompleteError()
        try:
            if self._drain_records is not None and self._drain_result is None:
                # A plain close cannot forget the original daemon threads or
                # compete with their native containment. Resume through drain.
                raise ShutdownIncompleteError()
            self._close_profiles()
        finally:
            self._drain_guard.release()

    def _close_profiles(self: RuntimeProfileConnections) -> None:
        with self._guard:
            self._closed = True
            hosts = tuple(self._profiles.items())
        self._cancel_service_admissions()
        self._views.close()
        self._enrollments.close()
        failures: list[Exception] = []
        for profile_id, host in hosts:
            try:
                host.close()
            except Exception as error:
                failures.append(error)
            else:
                with self._guard:
                    if self._profiles.get(profile_id) is host:
                        self._profiles.pop(profile_id)
        if self._settle_pending_logins(deadline=DEFAULT_TIMEOUT_POLICY.deadline().instant):
            failures.append(ShutdownIncompleteError())
        with self._guard:
            self._connections.clear()
            self._logins.clear()
        if failures:
            raise ExceptionGroup("runtime profile cleanup failed", failures)

    def drain(self: RuntimeProfileConnections, *, deadline: float) -> ProfileDrainResult:
        """Resume the original fenced shutdown under this attempt's absolute deadline."""
        self.stop.set()
        if isinstance(self.stop, RuntimeStop) and self.stop.reason is ExitReason.SESSION_END_SETTLE:
            deadline = min(deadline, time.monotonic() + 3.0)
        if not self._drain_guard.acquire(timeout=max(0.0, deadline - time.monotonic())):
            raise ShutdownIncompleteError()
        try:
            return self._drain_profiles(deadline=deadline)
        finally:
            self._drain_guard.release()

    def _drain_profiles(self: RuntimeProfileConnections, *, deadline: float) -> ProfileDrainResult:
        if self._drain_result is not None:
            return self._drain_result
        records = self._snapshot_drain_records(deadline=deadline)
        self._enrollments.close()
        session_end = isinstance(self.stop, RuntimeStop) and self.stop.reason is ExitReason.SESSION_END_SETTLE
        approval_failures = self._prepare_drain_requests(records, deadline=deadline, session_end=session_end)
        self._join_drain_requests(records, deadline=deadline)
        self._start_needed_containment(records, deadline=deadline)
        self._join_drain_containment(records, deadline=deadline)
        if session_end:
            self._settle_terminated_operations(records, deadline=deadline)
        else:
            self._settle_drained_operations(records, deadline=deadline)
        result = self._collect_drain_result(records, approval_failures, deadline=deadline)
        if not result.uncontained and not result.unsettled:
            self._commit_drain_result(result, deadline=deadline)
        return result

    def _snapshot_drain_records(
        self: RuntimeProfileConnections, *, deadline: float
    ) -> tuple[tuple[UUID, ProfileDrainRecord], ...]:
        if not self._guard.acquire(timeout=max(0.0, deadline - time.monotonic())):
            raise ShutdownIncompleteError()
        try:
            self._closed = True
            self._views.close()
            if self._drain_records is None:
                self._drain_records = {
                    profile_id: ProfileDrainRecord(host) for profile_id, host in self._profiles.items()
                }
            records = tuple(self._drain_records.items())
        finally:
            self._guard.release()
        return records

    def _prepare_drain_requests(
        self: RuntimeProfileConnections,
        records: tuple[tuple[UUID, ProfileDrainRecord], ...],
        *,
        deadline: float,
        session_end: bool = False,
    ) -> set[UUID]:
        approval_failures: set[UUID] = set()
        for profile_id, record in records:
            try:
                # Retire idle password/DEK proof before containing the worker;
                # active callback phases retain their own cleanup until settled.
                record.host.approvals.close()
            except Exception:
                approval_failures.add(profile_id)
            if not record.begun:
                record.worker = record.host.owner.begin_drain()
                record.begun = True
            if not session_end and record.worker is not None and record.request is None:
                self._start_drain_request(record, deadline=deadline)
            # A prior terminal failed containment may have left its request
            # blocked. Retry containment before joining that original request.
            if containment_retry_needed(record):
                self._start_drain_containment(record, deadline=deadline)
        return approval_failures

    def _settle_terminated_operations(
        self: RuntimeProfileConnections,
        records: tuple[tuple[UUID, ProfileDrainRecord], ...],
        *,
        deadline: float,
    ) -> None:
        for _, record in records:
            if not record.contained or record.worker is None or record.parent_settled:
                continue
            if record.settlement is None or not record.settlement.is_alive():
                self._start_parent_settlement(record, deadline=deadline)
        for _, record in records:
            if record.settlement is not None and record.settlement.ident is not None:
                record.settlement.join(timeout=max(0.0, deadline - time.monotonic()))

    def _settle_drained_operations(
        self: RuntimeProfileConnections,
        records: tuple[tuple[UUID, ProfileDrainRecord], ...],
        *,
        deadline: float,
    ) -> None:
        """Record what each contained worker left unfinished as interrupted, keeping its effect.

        Without this, work cut by a stop stayed running in the journal under
        the dead worker's lease until the lease lapsed. A settlement that cannot
        finish leaves that record to the same lapse reconciliation as before.
        """
        for _, record in records:
            with record.guard:
                contained, receipt = record.contained, record.receipt
            if (
                not contained
                or record.worker is None
                or receipt is None
                or not receipt.recovery_required
                or record.drained_settlement is not None
            ):
                continue
            self._start_drained_settlement(record, receipt, deadline=deadline)
        for _, record in records:
            thread = record.drained_settlement
            if thread is not None and thread.ident is not None:
                thread.join(timeout=max(0.0, deadline - time.monotonic()))

    def _start_drained_settlement(
        self: RuntimeProfileConnections,
        record: ProfileDrainRecord,
        receipt: ProfileWorkerDrained,
        *,
        deadline: float,
    ) -> None:
        worker, registry = record.worker, self._registry
        if worker is None:
            return

        def settle() -> None:
            try:
                if registry is None:
                    raise ShutdownIncompleteError()
                asyncio.run(
                    settle_drained_worker_operations(
                        root=self.root,
                        identity=worker.identity,
                        registry=registry,
                        operation_ids=receipt.recovery_required,
                        deadline=deadline,
                    )
                )
            except BaseException as error:
                # The record stays running for lease-lapse reconciliation; only its type is logged.
                diagnostic_event(
                    _LOGGER,
                    "drained worker operations left for lapse reconciliation",
                    level=logging.WARNING,
                    fields={"operation_count": len(receipt.recovery_required), **diagnostic_error_fields(error)},
                )

        record.drained_settlement = Thread(target=settle, name="profile-worker-drained-settlement", daemon=True)
        record.drained_settlement.start()

    def _start_parent_settlement(
        self: RuntimeProfileConnections, record: ProfileDrainRecord, *, deadline: float
    ) -> None:
        worker, registry = record.worker, self._registry
        if worker is None:
            return

        def settle() -> None:
            try:
                if registry is None:
                    raise ShutdownIncompleteError()
                asyncio.run(
                    settle_terminated_worker_operations(
                        root=self.root,
                        identity=worker.identity,
                        registry=registry,
                        deadline=deadline,
                    )
                )
            except BaseException:
                # Keep the original attempt and worker until settlement succeeds.
                return
            with record.guard:
                record.parent_settled = True

        record.settlement = Thread(target=settle, name="profile-worker-parent-settlement", daemon=True)
        record.settlement.start()

    @staticmethod
    def _join_drain_requests(
        records: tuple[tuple[UUID, ProfileDrainRecord], ...],
        *,
        deadline: float,
    ) -> None:
        for _, record in records:
            if record.request is not None and record.request.ident is not None:
                record.request.join(timeout=max(0.0, deadline - time.monotonic()))

    def _start_needed_containment(
        self: RuntimeProfileConnections,
        records: tuple[tuple[UUID, ProfileDrainRecord], ...],
        *,
        deadline: float,
    ) -> None:
        for _, record in records:
            with record.guard:
                contained = record.contained
            if record.worker is not None and not contained and record.containment is None:
                self._start_drain_containment(record, deadline=deadline)

    @staticmethod
    def _join_drain_containment(
        records: tuple[tuple[UUID, ProfileDrainRecord], ...],
        *,
        deadline: float,
    ) -> None:
        for _, record in records:
            if record.containment is not None and record.containment.ident is not None:
                record.containment.join(timeout=max(0.0, deadline - time.monotonic()))

    def _collect_drain_result(
        self: RuntimeProfileConnections,
        records: tuple[tuple[UUID, ProfileDrainRecord], ...],
        approval_failures: set[UUID],
        *,
        deadline: float,
    ) -> ProfileDrainResult:
        uncontained: list[UUID] = []
        unsettled: list[UUID] = list(approval_failures)
        received: dict[UUID, ProfileWorkerDrained] = {}
        for profile_id, record in records:
            with record.guard:
                contained, receipt = record.contained, record.receipt
            if receipt is not None:
                received[profile_id] = receipt
            if record.worker is not None and not contained:
                uncontained.append(profile_id)
            running = self._drain_threads_running(record)
            if record.settlement is not None and not record.parent_settled:
                unsettled.append(profile_id)
            if running:
                unsettled.append(profile_id)
            # A pre-fence launch may own a native scope without a published
            # worker. Its incomplete containment retains runtime ownership.
            if not record.host.owner.wait_construction(deadline=deadline):
                uncontained.append(profile_id)
                continue
            if not drain_record_can_settle(record, contained, running):
                continue
            self._settle_drained_record(profile_id, record, unsettled, deadline=deadline)
        unsettled.extend(self._settle_pending_logins(deadline=deadline))
        return self._build_drain_result(records, received, uncontained, unsettled)

    @staticmethod
    def _drain_threads_running(record: ProfileDrainRecord) -> bool:
        return any(
            thread is not None and (thread.ident is None or thread.is_alive())
            for thread in (record.request, record.containment, record.settlement, record.drained_settlement)
        )

    @staticmethod
    def _settle_drained_record(
        profile_id: UUID,
        record: ProfileDrainRecord,
        unsettled: list[UUID],
        *,
        deadline: float,
    ) -> None:
        try:
            record.host.owner.settle(deadline=deadline)
        except Exception:
            unsettled.append(profile_id)
        try:
            # Callback settlement may complete a retired proof phase. Reap
            # again and retain this host if any proof still owns cleanup.
            if record.host.approvals.close():
                unsettled.append(profile_id)
        except Exception:
            unsettled.append(profile_id)

    @staticmethod
    def _build_drain_result(
        records: tuple[tuple[UUID, ProfileDrainRecord], ...],
        received: dict[UUID, ProfileWorkerDrained],
        uncontained: list[UUID],
        unsettled: list[UUID],
    ) -> ProfileDrainResult:
        return ProfileDrainResult(
            receipts=tuple(received[profile_id] for profile_id in sorted(received)),
            missing_receipts=tuple(
                sorted(
                    profile_id
                    for profile_id, record in records
                    if record.worker is not None and profile_id not in received
                )
            ),
            uncontained=tuple(sorted(set(uncontained))),
            unsettled=tuple(sorted(set(unsettled))),
            parent_settled_profiles=tuple(
                sorted(profile_id for profile_id, record in records if record.parent_settled)
            ),
        )

    def _commit_drain_result(self: RuntimeProfileConnections, result: ProfileDrainResult, *, deadline: float) -> None:
        if not self._guard.acquire(timeout=max(0.0, deadline - time.monotonic())):
            raise ShutdownIncompleteError()
        try:
            self._profiles.clear()
            self._connections.clear()
            self._logins.clear()
            self._drain_result = result
            if self._drain_records is not None:
                self._drain_records.clear()
        finally:
            self._guard.release()

    @staticmethod
    def _start_drain_request(record: ProfileDrainRecord, *, deadline: float) -> None:
        worker = record.worker
        if worker is None:
            return

        def request() -> None:
            try:
                receipt = worker.drain(deadline=deadline)
            except BaseException:
                # The original worker remains owned, regardless of why its
                # protocol request failed. Only a real receipt may be recorded.
                return
            with record.guard:
                record.receipt = receipt
                record.contained = True

        thread = Thread(target=request, name="profile-worker-drain", daemon=True)
        record.request = thread
        thread.start()

    @staticmethod
    def _start_drain_containment(record: ProfileDrainRecord, *, deadline: float) -> None:
        worker = record.worker
        if worker is None:
            return

        def contain() -> None:
            try:
                worker.close(deadline=deadline)
            except BaseException:
                return
            with record.guard:
                record.contained = True

        thread = Thread(target=contain, name="profile-worker-contain", daemon=True)
        record.containment = thread
        thread.start()
