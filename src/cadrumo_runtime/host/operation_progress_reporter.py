"""Tell the runtime parent which operations committed, without ever delaying a commit."""

from __future__ import annotations

import logging
from collections.abc import Callable
from threading import Condition, Thread

from cadrumo.application.operations.models import OperationId
from cadrumo.core.diagnostic_log import diagnostic_error_fields, diagnostic_event
from cadrumo.core.logging import get_logger

from ..contracts.worker_authorization import WORKER_OPERATIONS_ADVANCED_MAX

_LOGGER = get_logger(__name__)

_CLOSE_JOIN_SECONDS = 5.0


class OperationProgressReporter:
    """Coalesce committed operations and report them from one thread.

    A commit only records its operation and returns. While one report is in
    flight, every later commit joins the next one, so a burst produces at most
    one report in flight and one queued. A report that cannot be delivered is
    dropped: a waiting client is still bounded by its own deadline.
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
                # However this thread ended, pending and later commits get a fresh one. Each
                # run takes a batch before it can fail, so replacements end with the backlog.
                self._thread = None
                if self._pending and not self._closed:
                    self._start()

    def _report_until_closed(self) -> None:
        while True:
            with self._condition:
                while not self._pending and not self._closed:
                    self._condition.wait()
                if not self._pending:
                    return
                batch = tuple(self._pending)[:WORKER_OPERATIONS_ADVANCED_MAX]
                for operation_id in batch:
                    del self._pending[operation_id]
            try:
                self._send(batch)
            except Exception as error:
                diagnostic_event(
                    _LOGGER,
                    "profile_operation_progress_unreported",
                    fields={"operations": len(batch), **diagnostic_error_fields(error)},
                    level=logging.DEBUG,
                )
