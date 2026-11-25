"""Observe contained child exits after a Windows Job termination deadline."""

from __future__ import annotations

import time
from collections.abc import Sequence
from contextlib import suppress
from logging import DEBUG, WARNING
from threading import Thread
from typing import TYPE_CHECKING

from cadrumo.core.diagnostic_log import diagnostic_event
from cadrumo.core.logging import get_logger

from ..contracts.contracts import RefusalCode, RefusalError

if TYPE_CHECKING:
    from cadrumo_client.transport.windows_owned_process import WindowsOwnedProcess

_LOGGER = get_logger("cadrumo_client.transport.windows_process")


def watch_windows_late_exit(
    children: Sequence[WindowsOwnedProcess], *, started: float, seconds: float
) -> Thread | None:
    """Report from a daemon thread when each child that outlived its termination bound exits.

    The thread waits on duplicated handles, so it neither depends on the scope
    releasing its own nor keeps the process alive. It starts nothing when no
    child can be duplicated, and a failure here is never the caller's.
    """
    waiters: list[WindowsOwnedProcess] = []
    for child in children:
        with suppress(Exception):
            waiters.append(child.retain_waiter())
    if not waiters:
        return None
    watcher = Thread(
        target=_report_late_exit, args=(tuple(waiters), started, seconds), name="windows-job-late-exit", daemon=True
    )
    try:
        watcher.start()
    except BaseException:
        for waiter in waiters:
            with suppress(Exception):
                waiter.close()
        return None
    return watcher


def _report_late_exit(waiters: tuple[WindowsOwnedProcess, ...], started: float, seconds: float) -> None:
    """Wait up to ``seconds`` after ``started`` for each child's exit and log its status and the total time."""
    deadline = started + seconds
    try:
        for waiter in waiters:
            code: int | None = None
            outcome = "exited"
            try:
                code = waiter.wait(timeout=max(0.0, deadline - time.monotonic()))
            except RefusalError as error:
                outcome = "observation_expired" if error.reason is RefusalCode.TIMEOUT else "unavailable"
            except Exception:
                outcome = "unavailable"
            diagnostic_event(
                _LOGGER,
                "windows_job_child_exit_observed_late",
                fields={
                    "child_process_id": waiter.pid,
                    "exit_code": code,
                    "elapsed_seconds": round(max(0.0, time.monotonic() - started), 3),
                    "timeout_seconds": seconds,
                    "outcome": outcome,
                },
                level=DEBUG if code is not None else WARNING,
            )
    finally:
        for waiter in waiters:
            with suppress(Exception):
                waiter.close()
