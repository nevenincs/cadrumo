"""Retained native worker resource release with original failure and cancellation ownership."""

from __future__ import annotations

import asyncio
from collections.abc import Callable

from ...core.async_cleanup import AsyncResourceCleanupError, attach_async_cleanup_error


class WorkerResourceCleanup:
    """Retain native release until it succeeds, including asynchronous retries."""

    def __init__(self, release: Callable[[], None], *, retry_release: Callable[[], None] | None = None) -> None:
        """Retain the first release and its original recovery callback."""
        self._release = release
        self._retry_release = retry_release or release
        self._released = False

    def close_now(self) -> None:
        """Mark release complete only after the actual native callback succeeds."""
        if not self._released:
            release, self._release = self._release, self._retry_release
            release()
            self._released = True

    async def close(self) -> None:
        """Finish native release through the owning asynchronous cleanup machinery."""
        await asyncio.to_thread(self.close_now)


def release_worker_resources(*owners: WorkerResourceCleanup, primary_error: BaseException | None = None) -> None:
    """Try every owner and preserve failed callbacks beside the exact primary error."""
    failed: list[WorkerResourceCleanup] = []
    failures: list[BaseException] = []
    for owner in owners:
        try:
            owner.close_now()
        except BaseException as error:
            failed.append(owner)
            failures.append(error)
    if not failures:
        return
    cleanup = AsyncResourceCleanupError(
        tuple(failed), tuple(failures), retry_task_name="profile-worker-cleanup", close_attempts=1
    )
    if primary_error is None:
        raise cleanup from failures[0]
    attach_async_cleanup_error(
        primary_error,
        cleanup,
        note="Worker cleanup also failed; retry through the attached async_cleanup_error",
    )
