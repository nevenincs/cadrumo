"""Runtime drain behavior for profile connections."""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from threading import RLock, Thread
from typing import TYPE_CHECKING
from uuid import UUID

from ...adapters.local_runtime.profile_worker import ProfileWorkerProcess
from ...application.runtime.contracts import (
    RuntimeExitReason,
    RuntimeShutdownIncompleteError,
)
from ...application.runtime.profile_access import (
    RuntimeProfileDrainResult,
)
from ...application.runtime.profile_worker import ProfileWorkerDrained
from .profile_host import RuntimeProfileHost
from .shutdown import RuntimeStop
from .terminated_operations import settle_terminated_worker_operations

if TYPE_CHECKING:
    from .profile_connections import RuntimeProfileConnections


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
    guard: RLock = field(default_factory=RLock, repr=False)


class ProfileConnectionDrainMixin:
    """Own the drain behavior of the profile connection service."""

    def close(self: RuntimeProfileConnections) -> None:
        """Fence all admissions before releasing profile workers and nonsecret state."""
        if not self._drain_guard.acquire(blocking=False):
            raise RuntimeShutdownIncompleteError()
        try:
            if self._drain_records is not None and self._drain_result is None:
                # A plain close cannot forget the original daemon threads or
                # compete with their native containment. Resume through drain.
                raise RuntimeShutdownIncompleteError()
            self._close_profiles()
        finally:
            self._drain_guard.release()

    def _close_profiles(self: RuntimeProfileConnections) -> None:
        with self._guard:
            self._closed = True
            hosts = tuple(self._profiles.items())
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
        with self._guard:
            self._connections.clear()
            self._logins.clear()
        if failures:
            raise ExceptionGroup("runtime profile cleanup failed", failures)

    def drain(self: RuntimeProfileConnections, *, deadline: float) -> RuntimeProfileDrainResult:
        """Resume the original fenced shutdown under this attempt's absolute deadline."""
        self.stop.set()
        if not self._drain_guard.acquire(timeout=max(0.0, deadline - time.monotonic())):
            raise RuntimeShutdownIncompleteError()
        try:
            return self._drain_profiles(deadline=deadline)
        finally:
            self._drain_guard.release()

    def _drain_profiles(self: RuntimeProfileConnections, *, deadline: float) -> RuntimeProfileDrainResult:
        if self._drain_result is not None:
            return self._drain_result
        records = self._snapshot_drain_records(deadline=deadline)
        self._enrollments.close()
        session_end = isinstance(self.stop, RuntimeStop) and self.stop.reason is RuntimeExitReason.SESSION_END_SETTLE
        approval_failures = self._prepare_drain_requests(records, deadline=deadline, session_end=session_end)
        self._join_drain_requests(records, deadline=deadline)
        self._start_needed_containment(records, deadline=deadline)
        self._join_drain_containment(records, deadline=deadline)
        if session_end:
            self._settle_terminated_operations(records, deadline=deadline)
        result = self._collect_drain_result(records, approval_failures, deadline=deadline)
        if not result.uncontained and not result.unsettled:
            self._commit_drain_result(result, deadline=deadline)
        return result

    def _snapshot_drain_records(
        self: RuntimeProfileConnections, *, deadline: float
    ) -> tuple[tuple[UUID, ProfileDrainRecord], ...]:
        if not self._guard.acquire(timeout=max(0.0, deadline - time.monotonic())):
            raise RuntimeShutdownIncompleteError()
        try:
            self._closed = True
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
            if (
                record.containment is not None
                and record.containment.ident is not None
                and not record.containment.is_alive()
            ):
                with record.guard:
                    contained = record.contained
                if not contained:
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

    def _start_parent_settlement(
        self: RuntimeProfileConnections, record: ProfileDrainRecord, *, deadline: float
    ) -> None:
        worker, registry = record.worker, self._registry
        if worker is None:
            return

        def settle() -> None:
            try:
                if registry is None:
                    raise RuntimeShutdownIncompleteError()
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
    ) -> RuntimeProfileDrainResult:
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
            if running or (record.worker is not None and not contained):
                continue
            self._settle_drained_record(profile_id, record, unsettled, deadline=deadline)
        return self._build_drain_result(records, received, uncontained, unsettled)

    @staticmethod
    def _drain_threads_running(record: ProfileDrainRecord) -> bool:
        return any(
            thread is not None and (thread.ident is None or thread.is_alive())
            for thread in (record.request, record.containment, record.settlement)
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
    ) -> RuntimeProfileDrainResult:
        return RuntimeProfileDrainResult(
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

    def _commit_drain_result(
        self: RuntimeProfileConnections, result: RuntimeProfileDrainResult, *, deadline: float
    ) -> None:
        if not self._guard.acquire(timeout=max(0.0, deadline - time.monotonic())):
            raise RuntimeShutdownIncompleteError()
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
