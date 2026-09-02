"""Cancellation-complete awaiting for owned asynchronous cleanup.

Resource owners use :func:`await_cancellation_complete` when losing the local
task handle would make a second cancellation leak an external process or
session. The cleanup runs in one retained task; every caller cancellation is
deferred until that task reaches a terminal state.
"""

from __future__ import annotations

import asyncio
import sys
from collections.abc import Awaitable
from typing import Protocol

from .errors.hierarchy import CoreError


class AsyncCloseable(Protocol):
    """Structural asynchronous resource owner."""

    async def close(self) -> None:
        """Release the owned resource."""
        ...


class _AutoPrimaryException:
    """Sentinel selecting the exception active at the call boundary."""


_AUTO_PRIMARY_EXCEPTION = _AutoPrimaryException()


class AsyncResourceCleanupError(CoreError, RuntimeError):
    """Retain asynchronous resource owners whose close attempts failed."""

    def __init__(
        self,
        resources: tuple[AsyncCloseable, ...],
        failures: tuple[BaseException, ...],
        *,
        retry_task_name: str,
        close_attempts: int,
    ) -> None:
        """Retain failed owners, their failures, and the retry task label."""
        super().__init__("Asynchronous resource cleanup failed; call retry_cleanup() on this error")
        self._resources = resources
        self._failures = failures
        self._retry_task_name = retry_task_name
        self._close_attempts = close_attempts

    async def retry_cleanup(self) -> None:
        """Retry only the resource owners whose prior close failed."""
        await close_async_resources(
            *self._resources,
            task_name=self._retry_task_name,
            close_attempts=self._close_attempts,
            primary_error=None,
        )

    def merged_with(self, later: AsyncResourceCleanupError) -> AsyncResourceCleanupError:
        """Combine nested cleanup failures without losing either owner."""
        return AsyncResourceCleanupError(
            self._resources + later._resources,
            self._failures + later._failures,
            retry_task_name=self._retry_task_name,
            close_attempts=max(self._close_attempts, later._close_attempts),
        )


async def await_cancellation_complete[T](
    awaitable: Awaitable[T],
    *,
    task_name: str,
    cancellation: asyncio.CancelledError | None = None,
) -> T:
    """Finish ``awaitable`` before preserving and re-raising cancellation.

    Repeated calls to :meth:`asyncio.Task.cancel` are absorbed while the
    retained cleanup task is pending. If cleanup itself fails while a caller
    cancellation is pending, that failure is retained on the cancellation as
    ``cleanup_error`` and the cancellation remains the primary exception.
    """
    cleanup_task = asyncio.ensure_future(awaitable)
    if isinstance(cleanup_task, asyncio.Task):
        cleanup_task.set_name(task_name)

    pending_cancellation = cancellation
    while not cleanup_task.done():
        try:
            await asyncio.shield(cleanup_task)
        except asyncio.CancelledError as caught:
            if pending_cancellation is None:
                pending_cancellation = caught
        except BaseException:
            # The retained task is terminal. Read its exact outcome below so a
            # pending caller cancellation remains the primary exception.
            break

    try:
        result = cleanup_task.result()
    except BaseException as cleanup_error:
        if pending_cancellation is None:
            raise
        _merge_cleanup_failure_into_cancellation(pending_cancellation, cleanup_error)
        raise pending_cancellation from cleanup_error

    if pending_cancellation is not None:
        raise pending_cancellation
    return result


def _merge_cleanup_failure_into_cancellation(
    cancellation: asyncio.CancelledError,
    cleanup_error: BaseException,
) -> None:
    """Attach a retained cleanup failure to a pending cancellation.

    A distinct failure is stored on the cancellation's ``cleanup_error``,
    merging with any prior :class:`AsyncResourceCleanupError` so no owner is
    lost. When the failure *is* the cancellation itself, nothing is attached.
    """
    if cleanup_error is not cancellation:
        previous_cleanup_error = cancellation.__dict__.get("cleanup_error")
        if isinstance(previous_cleanup_error, AsyncResourceCleanupError) and isinstance(
            cleanup_error,
            AsyncResourceCleanupError,
        ):
            cleanup_error = previous_cleanup_error.merged_with(cleanup_error)
        cancellation.__dict__["cleanup_error"] = cleanup_error
        cancellation.add_note(f"Retained asynchronous cleanup also failed ({type(cleanup_error).__name__})")


async def _close_with_retries(resource: AsyncCloseable, close_attempts: int) -> BaseException | None:
    """Close one resource, retrying, and return the final failure or ``None``.

    Every attempt's failure is absorbed so a later attempt can still succeed.
    When all attempts fail, the last failure carries a note counting them.
    """
    prior_failures: list[BaseException] = []
    for _ in range(close_attempts):
        try:
            await resource.close()
        except BaseException as error:
            prior_failures.append(error)
        else:
            return None
    final_error = prior_failures[-1]
    if len(prior_failures) > 1:
        final_error.add_note(f"resource close failed {len(prior_failures)} times")
    return final_error


async def _close_all_resources(
    resources: tuple[AsyncCloseable | None, ...],
    *,
    task_name: str,
    close_attempts: int,
) -> None:
    """Close every resource, retaining the owners whose close attempts all failed."""
    failed_resources: list[AsyncCloseable] = []
    failures: list[BaseException] = []
    for resource in resources:
        if resource is None:
            continue
        failure = await _close_with_retries(resource, close_attempts)
        if failure is not None:
            failed_resources.append(resource)
            failures.append(failure)
    if failures:
        raise AsyncResourceCleanupError(
            tuple(failed_resources),
            tuple(failures),
            retry_task_name=task_name,
            close_attempts=close_attempts,
        ) from failures[0]


async def close_async_resources(
    *resources: AsyncCloseable | None,
    task_name: str,
    cancellation: asyncio.CancelledError | None = None,
    primary_error: BaseException | _AutoPrimaryException | None = _AUTO_PRIMARY_EXCEPTION,
    close_attempts: int = 1,
) -> None:
    """Close every resource without replacing an exception already unwinding.

    When called from an ``async finally`` block, :func:`sys.exception`
    exposes the body exception across this coroutine boundary. Cleanup still
    reaches a terminal state, and any owner-retaining cleanup error is attached
    to that primary exception instead of replacing it.
    """
    if close_attempts < 1:
        raise ValueError("close_attempts must be at least 1")
    active_error = sys.exception() if isinstance(primary_error, _AutoPrimaryException) else primary_error
    primary_cancellation = active_error if isinstance(active_error, asyncio.CancelledError) else None

    try:
        await await_cancellation_complete(
            _close_all_resources(resources, task_name=task_name, close_attempts=close_attempts),
            task_name=task_name,
            cancellation=cancellation or primary_cancellation,
        )
    except asyncio.CancelledError as cleanup_cancellation:
        _attach_body_error_to_cancellation(cleanup_cancellation, active_error)
        raise
    except AsyncResourceCleanupError as cleanup_error:
        if not _attach_cleanup_error_to_body(active_error, cleanup_error):
            raise


def _attach_body_error_to_cancellation(
    cancellation: asyncio.CancelledError,
    active_error: BaseException | None,
) -> None:
    """Attach a still-unwinding non-cancellation body exception to a cancellation."""
    if active_error is not None and not isinstance(active_error, asyncio.CancelledError):
        cancellation.__dict__["body_error"] = active_error
        cancellation.add_note(
            "Cancellation arrived while an earlier body exception was unwinding; "
            "the body exception is attached as body_error"
        )


def _attach_cleanup_error_to_body(
    active_error: BaseException | None,
    cleanup_error: AsyncResourceCleanupError,
) -> bool:
    """Attach a cleanup failure to a still-unwinding body exception.

    Returns ``True`` when the failure was attached (merging with any prior
    :class:`AsyncResourceCleanupError`) and should be suppressed, ``False``
    when there is no eligible body exception and the caller must re-raise.
    """
    if active_error is None or isinstance(active_error, asyncio.CancelledError):
        return False
    previous_cleanup_error = active_error.__dict__.get("async_cleanup_error")
    if isinstance(previous_cleanup_error, AsyncResourceCleanupError):
        cleanup_error = previous_cleanup_error.merged_with(cleanup_error)
    active_error.__dict__["async_cleanup_error"] = cleanup_error
    active_error.add_note("Asynchronous resource cleanup also failed; retry through the attached async_cleanup_error")
    return True


__all__ = [
    "AsyncCloseable",
    "AsyncResourceCleanupError",
    "await_cancellation_complete",
    "close_async_resources",
]
