"""Real asyncio proofs for cancellation-complete cleanup awaiting."""

from __future__ import annotations

import asyncio

import pytest

from ..async_cleanup import AsyncResourceCleanupError, await_cancellation_complete, close_async_resources
from ..errors.error_codes import get_registered_error_code
from ..errors.hierarchy import CoreError

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_cleanup_error_retains_failures_and_registry_contract() -> None:
    """Cleanup failures remain retryable, typed, and registry-bound."""
    failure = RuntimeError("owned resource close failed")
    error = AsyncResourceCleanupError(
        (),
        (failure,),
        retry_task_name="test-retained-cleanup",
        close_attempts=2,
    )

    assert isinstance(error, CoreError)
    assert isinstance(error, RuntimeError)
    assert error._failures == (failure,)
    code = get_registered_error_code(error)
    assert code.code == "ERROR_CADRUMO_ASYNC_RESOURCE_CLEANUP"
    assert code.retryable is True


@pytest.mark.asyncio
async def test_repeated_cancellation_waits_for_real_cleanup_completion() -> None:
    """Repeated caller cancellation cannot interrupt the retained coroutine."""
    started = asyncio.Event()
    release = asyncio.Event()
    finished = asyncio.Event()

    async def cleanup() -> None:
        started.set()
        await release.wait()
        finished.set()

    owner = asyncio.create_task(
        await_cancellation_complete(cleanup(), task_name="test-success-cleanup"),
    )
    await started.wait()
    owner.cancel()
    await asyncio.sleep(0)
    owner.cancel()
    await asyncio.sleep(0)
    release.set()

    with pytest.raises(asyncio.CancelledError):
        await owner
    assert finished.is_set()


@pytest.mark.asyncio
async def test_repeated_cancellation_preserves_real_cleanup_exception() -> None:
    """A genuine cleanup failure remains attached to primary cancellation."""
    started = asyncio.Event()
    release = asyncio.Event()

    async def cleanup() -> None:
        started.set()
        await release.wait()
        raise RuntimeError("cleanup failed after cancellation")

    owner = asyncio.create_task(
        await_cancellation_complete(cleanup(), task_name="test-failing-cleanup"),
    )
    await started.wait()
    owner.cancel()
    await asyncio.sleep(0)
    owner.cancel()
    await asyncio.sleep(0)
    release.set()

    with pytest.raises(asyncio.CancelledError) as exc_info:
        await owner
    assert isinstance(exc_info.value.__dict__.get("cleanup_error"), RuntimeError)


@pytest.mark.asyncio
async def test_async_finally_preserves_body_exception_across_cleanup_boundary() -> None:
    """The production cleanup boundary observes the active async body error."""
    with pytest.raises(RuntimeError, match="primary body failure"):
        try:
            raise RuntimeError("primary body failure")
        finally:
            await close_async_resources(
                task_name="test-active-body-cleanup",
            )
