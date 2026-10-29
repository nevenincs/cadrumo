"""Tell the runtime parent which operations committed, without ever delaying a commit."""

from __future__ import annotations

import logging
from collections.abc import Callable
from threading import Condition, Thread
from time import monotonic

from cadrumo.application.operations.models import OperationId
from cadrumo.core.diagnostic_log import diagnostic_error_fields, diagnostic_event
from cadrumo.core.logging import get_logger

from ..contracts.worker_authorization import WORKER_OPERATIONS_ADVANCED_MAX

_LOGGER = get_logger(__name__)

_CLOSE_JOIN_SECONDS = 5.0
_RETRY_FIRST_SECONDS = 0.05
_RETRY_LONGEST_SECONDS = 1.0


class OperationProgressReporter:
    """Coalesce committed operations and report them from one thread.

    A commit only records its operation and returns. While one report is in
    flight, every later commit joins the next one, so a burst produces at most
    one report in flight and one queued. A report the runtime does not take is
    queued again ahead of later commits and retried after a backoff, because a
    waiter without a deadline would otherwise never see that change. Closing
    tries what is pending once.
    """

    def __init__(self, send: Callable[[tuple[OperationId, ...]], None]) -> None:
        """Report through ``send``, which blocks until the runtime acknowledges."""
        self._send = send
        self._condition = Condition()
        # Insertion-ordered set: the oldest commits are reported first.
        self._pending: dict[OperationId, None] = {}
        self._closed = False
        self._thread: Thread | None = None

    def committed(self, operation_id: OperationId) -> None:
        """Record one committed operation for the next report; never blocks on the runtime."""
        with self._condition:
            if self._closed:
                return
            self._pending[operation_id] = None
            if self._thread is None:
                self._start()
            self._condition.notify()

    def close(self) -> None:
        """Deliver what is pending, then stop; later commits are not reported."""
        with self._condition:
            self._closed = True
            thread = self._thread
            self._condition.notify()
        if thread is not None:
            thread.join(_CLOSE_JOIN_SECONDS)

    def _start(self) -> None:
        self._thread = Thread(target=self._run, name="profile-operation-progress", daemon=True)
        self._thread.start()

    def _run(self) -> None:
        try:
            self._report_until_closed()
        finally:
            with self._condition:
                # However this thread ended, pending and later commits get a fresh one. An
                # escape loses the batch it took, so replacements end with the backlog.
                self._thread = None
                if self._pending and not self._closed:
                    self._start()

    def _report_until_closed(self) -> None:
        backoff = 0.0
        while True:
            batch = self._take_pending(backoff)
            if batch is None:
                return
            try:
                self._send(batch)
            except Exception as error:
                diagnostic_event(
                    _LOGGER,
                    "profile_operation_progress_unreported",
                    fields={"operations": len(batch), **diagnostic_error_fields(error)},
                    level=logging.DEBUG,
                )
                with self._condition:
                    # Ahead of what committed meanwhile, so the oldest changes still go first.
                    # Once closed, each batch has had its one try and the rest still get theirs.
                    if not self._closed:
                        self._pending = dict.fromkeys(batch) | self._pending
                backoff = min(max(backoff * 2, _RETRY_FIRST_SECONDS), _RETRY_LONGEST_SECONDS)
            else:
                backoff = 0.0

    def _take_pending(self, backoff: float) -> tuple[OperationId, ...] | None:
        """Wait for work and preserve the retry bound unless closed."""
        with self._condition:
            while not self._pending and not self._closed:
                self._condition.wait()
            if not self._pending:
                return
            # A commit's notify does not cut a backoff short; a close does.
            retry_at = monotonic() + backoff
            while not self._closed and (remaining := retry_at - monotonic()) > 0:
                self._condition.wait(remaining)
            batch = tuple(self._pending)[:WORKER_OPERATIONS_ADVANCED_MAX]
            for operation_id in batch:
                del self._pending[operation_id]
            return batch
