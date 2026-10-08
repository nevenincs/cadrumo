"""Retryable worker release ownership and failure provenance retention."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import cast

from ...core.async_cleanup import AsyncResourceCleanupError


class WorkerRelease[Result]:
    """Keep one worker release retryable until its callback succeeds."""

    def __init__(self, release: Callable[[], Awaitable[Result]]) -> None:
        """Retain the single release callback and its eventual result."""
        self._release = release
        self._results: list[Result] = []

    async def release(self) -> Result:
        """Run the release at most once, retaining its exact result."""
        if not self._results:
            self._results.append(await self._release())
        return self._results[0]

    async def close(self) -> None:
        """Expose release as an asynchronous cleanup callback."""
        await self.release()


def retain_task_failures(primary: BaseException, failures: tuple[BaseException, ...]) -> None:
    """Keep known worker body diagnostics and their actual failed release owners."""
    pending = [primary, *failures]
    retained: list[BaseException] = []
    seen: set[int] = set()
    seen_cleanup: set[int] = set()
    cleanup = primary.__dict__.get("async_cleanup_error")
    combined = cleanup if isinstance(cleanup, AsyncResourceCleanupError) else None
    if combined is not None:
        seen_cleanup.add(id(combined))
    combined_owner = [combined]
    for failure in pending:
        _retain_one_failure(failure, primary, pending, retained, seen, seen_cleanup, combined_owner)
    if combined_owner[0] is not None:
        primary.__dict__["async_cleanup_error"] = combined_owner[0]
        if isinstance(primary, asyncio.CancelledError):
            primary.__dict__["cleanup_error"] = combined_owner[0]
    if retained:
        primary.__dict__["worker_task_errors"] = tuple(retained)
        primary.add_note("Worker task/body failures are retained as worker_task_errors")


def _retain_one_failure(
    failure: BaseException,
    primary: BaseException,
    pending: list[BaseException],
    retained: list[BaseException],
    seen: set[int],
    seen_cleanup: set[int],
    combined: list[AsyncResourceCleanupError | None],
) -> None:
    if id(failure) in seen:
        return
    seen.add(id(failure))
    if failure is not primary:
        retained.append(failure)
    nested = failure.__dict__.get("worker_task_errors")
    if isinstance(nested, tuple):
        pending.extend(error for error in cast(tuple[object, ...], nested) if isinstance(error, BaseException))
    _collect_attached_failures(failure, pending, seen_cleanup, combined)


def _collect_attached_failures(
    failure: BaseException,
    pending: list[BaseException],
    seen_cleanup: set[int],
    combined: list[AsyncResourceCleanupError | None],
) -> None:
    for name in ("async_cleanup_error", "cleanup_error", "body_error"):
        cleanup = failure.__dict__.get(name)
        if isinstance(cleanup, AsyncResourceCleanupError):
            if id(cleanup) not in seen_cleanup:
                seen_cleanup.add(id(cleanup))
                combined[0] = combined[0].merged_with(cleanup) if combined[0] is not None else cleanup
        elif isinstance(cleanup, BaseException):
            pending.append(cleanup)
