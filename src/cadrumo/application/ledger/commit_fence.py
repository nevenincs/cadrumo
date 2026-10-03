"""Fence concrete ledger persistence calls inside an operation commit section."""

from __future__ import annotations

import asyncio
import queue
import threading
from collections.abc import Callable, Iterable
from datetime import date

from ...core.async_cleanup import await_cancellation_complete
from ...core.operations import OperationEffect
from ...core.secure_object_write import SecureObjectWrite
from ...domain.transactions.models import LedgerDatePartition, Transaction, TransactionCatalogue
from ..operations.owner import OperationExecutorContext
from .persistence_ports import LedgerPersistenceConflictError
from .protocols import (
    RevisionGuardedTransactionCatalogueCoCommitWriterProtocol,
    TransactionCatalogueCoCommitWriterProtocol,
)


class _WriterAttempt:
    """One synchronous persistence call held until its operation fence is active."""

    def __init__(self) -> None:
        self._authorized = threading.Event()
        self._released = threading.Event()
        self.finished = threading.Event()
        self.allowed = False
        self.succeeded = False
        self.retryable_conflict = False

    def authorize(self) -> None:
        self.allowed = True
        self._authorized.set()

    def refuse(self) -> None:
        self.allowed = False
        self._authorized.set()
        self._released.set()

    def release(self) -> None:
        """Let canonical retry/read logic continue after the async fence exits."""
        self._released.set()

    def wait_for_authority(self) -> bool:
        self._authorized.wait()
        return self.allowed

    def wait_for_release(self) -> None:
        self._released.wait()


class LedgerCommitAttemptTracker:
    """Coordinate each canonical co-commit attempt with the async operation fence."""

    def __init__(self) -> None:
        """Initialize the pending calls and synchronized write outcome state."""
        self._pending: queue.SimpleQueue[_WriterAttempt] = queue.SimpleQueue()
        self._lock = threading.Lock()
        self._attempt_count = 0
        self._confirmed_write = False
        self._uncertain_write = False
        self._closed = False

    @property
    def attempt_count(self) -> int:
        """Return how many persistence calls requested commit authority."""
        with self._lock:
            return self._attempt_count

    @property
    def confirmed_write(self) -> bool:
        """Report whether an authorized persistence call returned successfully."""
        with self._lock:
            return self._confirmed_write

    @property
    def has_uncertain_write(self) -> bool:
        """Report whether a writer raised an unclassified persistence failure."""
        with self._lock:
            return self._uncertain_write

    @property
    def has_possible_write(self) -> bool:
        """Report any confirmed write or uncertain persistence outcome."""
        with self._lock:
            return self._uncertain_write or self._confirmed_write

    def next_attempt(self) -> _WriterAttempt | None:
        """Take the next call awaiting commit authority, if one is queued."""
        try:
            return self._pending.get_nowait()
        except queue.Empty:
            return None

    def abort(self) -> None:
        """Release queued/future calls without letting them reach persistence."""
        with self._lock:
            self._closed = True
        while (attempt := self.next_attempt()) is not None:
            attempt.refuse()

    def call_writer(self, write: Callable[[], None]) -> None:
        """Announce writer entry, await the async fence, then classify its outcome."""
        attempt = _WriterAttempt()
        with self._lock:
            self._attempt_count += 1
            closed = self._closed
            if not closed:
                self._pending.put(attempt)
        if closed:
            attempt.refuse()
        if not attempt.wait_for_authority():
            attempt.finished.set()
            raise RuntimeError("ledger writer was not authorized by its operation fence")
        failure: BaseException | None = None
        try:
            write()
        except LedgerPersistenceConflictError as error:
            # The canonical repository contract uses this only for a rejected
            # revision-guarded co-commit, which is safe for the service retry.
            attempt.retryable_conflict = True
            failure = error
        except BaseException as error:
            with self._lock:
                self._uncertain_write = True
            failure = error
        else:
            attempt.succeeded = True
            with self._lock:
                self._confirmed_write = True
        finally:
            attempt.finished.set()
        attempt.wait_for_release()
        if failure is not None:
            raise failure


class TrackedLedgerTransactionRepository:
    """Track each canonical transaction/event co-commit and delegate all reads."""

    def __init__(
        self,
        repository: TransactionCatalogueCoCommitWriterProtocol,
        tracker: LedgerCommitAttemptTracker,
    ) -> None:
        """Bind the catalogue port and its operation commit tracker."""
        self._repository = repository
        self._tracker = tracker

    @property
    def bucket_id(self) -> str:
        """Return the profile identity of the bound catalogue."""
        return self._repository.bucket_id

    def exists(self) -> bool:
        """Check catalogue existence without entering a write fence."""
        return self._repository.exists()

    def load(self) -> TransactionCatalogue:
        """Read the catalogue without entering a write fence."""
        return self._repository.load()

    def load_for_date_range(self, start: date, end: date) -> TransactionCatalogue:
        """Read the requested date window without entering a write fence."""
        return self._repository.load_for_date_range(start, end)

    def load_by_ids(self, transaction_ids: Iterable[str]) -> TransactionCatalogue:
        """Read selected transaction identities without entering a write fence."""
        return self._repository.load_by_ids(transaction_ids)

    def partition_by_date_range(self, start: date, end: date) -> LedgerDatePartition:
        """Partition the catalogue without entering a write fence."""
        return self._repository.partition_by_date_range(start, end)

    def save(self, catalogue: TransactionCatalogue) -> None:
        """Fence the actual catalogue save behind commit authority."""
        self._tracker.call_writer(lambda: self._repository.save(catalogue))

    def save_with_secure_object_writes(
        self,
        catalogue: TransactionCatalogue,
        extra_writes: tuple[SecureObjectWrite, ...],
    ) -> None:
        """Fence the atomic catalogue and related-object write."""
        self._tracker.call_writer(lambda: self._repository.save_with_secure_object_writes(catalogue, extra_writes))

    def replace_if_current_with_secure_object_writes(
        self,
        current: Transaction,
        replacement: Transaction,
        extra_writes: tuple[SecureObjectWrite, ...],
    ) -> None:
        """Fence a baseline-guarded replacement and its related-object writes."""
        self._tracker.call_writer(
            lambda: self._repository.replace_if_current_with_secure_object_writes(current, replacement, extra_writes)
        )


class RevisionGuardedTrackedLedgerTransactionRepository(TrackedLedgerTransactionRepository):
    """Expose whole-catalogue CAS only when the underlying port proves it."""

    def __init__(
        self,
        repository: RevisionGuardedTransactionCatalogueCoCommitWriterProtocol,
        tracker: LedgerCommitAttemptTracker,
    ) -> None:
        """Bind the proven revision-guarded port to the commit tracker."""
        super().__init__(repository, tracker)
        self._revisioned_repository = repository

    def load_revisioned(self) -> tuple[TransactionCatalogue, str]:
        """Delegate the proven full-catalogue snapshot without a write fence."""
        return self._revisioned_repository.load_revisioned()

    def save_if_revision_with_secure_object_writes(
        self,
        catalogue: TransactionCatalogue,
        *,
        expected_revision_id: str,
        extra_writes: tuple[SecureObjectWrite, ...],
    ) -> None:
        """Fence whole-catalogue CAS at its actual persistence call."""
        self._tracker.call_writer(
            lambda: self._revisioned_repository.save_if_revision_with_secure_object_writes(
                catalogue,
                expected_revision_id=expected_revision_id,
                extra_writes=extra_writes,
            )
        )


def _final_attempt_effect(
    attempt: _WriterAttempt,
    tracker: LedgerCommitAttemptTracker,
    *,
    prior_commit: bool,
) -> OperationEffect | None:
    """Map a completed canonical writer outcome onto its honest effect axis."""
    if attempt.succeeded:
        return OperationEffect.UPDATED
    if not attempt.retryable_conflict:
        return None
    return OperationEffect.PARTIAL if prior_commit or tracker.confirmed_write else OperationEffect.NONE


async def _settle_writer_attempt(
    attempt: _WriterAttempt,
    *,
    tracker: LedgerCommitAttemptTracker,
    context: OperationExecutorContext,
    task_name: str,
    prior_commit: bool,
) -> None:
    """Authorize one actual persistence call, then publish its measured outcome."""
    async with context.cancellation.irreversible_section():
        await context.events.effect(OperationEffect.UNKNOWN)
        attempt.authorize()
        await await_cancellation_complete(
            asyncio.to_thread(attempt.finished.wait),
            task_name=f"{task_name}-writer",
        )
        effect = _final_attempt_effect(attempt, tracker, prior_commit=prior_commit)
        if effect is not None:
            await context.events.effect(effect)
    attempt.release()


async def _settle_failed_worker[ResultT](
    worker: asyncio.Task[ResultT],
    *,
    task_name: str,
    error: BaseException,
) -> None:
    """Wait for worker cleanup after refusing queued writes, preserving cancellation handling."""
    try:
        await await_cancellation_complete(
            worker,
            task_name=f"{task_name}-settle",
            cancellation=error if isinstance(error, asyncio.CancelledError) else None,
        )
    except BaseException:
        if isinstance(error, asyncio.CancelledError):
            raise


async def run_with_ledger_commit_fence[ResultT](
    work: Callable[[], ResultT],
    *,
    tracker: LedgerCommitAttemptTracker,
    context: OperationExecutorContext,
    task_name: str,
    prior_commit: bool = False,
) -> ResultT:
    """Run canonical work, fencing only the concrete persistence calls it reaches."""
    worker = asyncio.create_task(asyncio.to_thread(work), name=task_name)
    active_attempt: _WriterAttempt | None = None
    try:
        while True:
            attempt = tracker.next_attempt()
            if attempt is not None:
                active_attempt = attempt
                await _settle_writer_attempt(
                    attempt,
                    tracker=tracker,
                    context=context,
                    task_name=task_name,
                    prior_commit=prior_commit,
                )
                active_attempt = None
                continue
            if worker.done():
                break
            await asyncio.sleep(0.005)
        return await await_cancellation_complete(worker, task_name=task_name)
    except BaseException as error:
        if active_attempt is not None:
            active_attempt.refuse()
        tracker.abort()
        await _settle_failed_worker(worker, task_name=task_name, error=error)
        raise


def is_guaranteed_prewrite_failure(tracker: LedgerCommitAttemptTracker) -> bool:
    """Return true only when no canonical persistence method was entered."""
    return tracker.attempt_count == 0 and not tracker.has_possible_write
