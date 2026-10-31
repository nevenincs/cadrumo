"""Real Playwright proofs for the central asynchronous cleanup authority."""

from __future__ import annotations

import asyncio
import time

import pytest

from ......core.async_cleanup import AsyncResourceCleanupError, close_async_resources
from ......core.config import Settings
from ...tests.process_support import playwright_driver_pid, wait_for_process_exit
from ..factory import DefaultBrowserSession, create_browser_session
from ..profile import Profile

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]


async def _opened_real_session(name: str) -> tuple[DefaultBrowserSession, int]:
    """Open a concrete Playwright owner with a live page and return its driver PID."""
    session = await create_browser_session(
        Settings(),
        Profile(name=name, locale="es-ES", timezone_id="Europe/Madrid"),
    )
    driver_pid = playwright_driver_pid(session._playwright)
    context = await session.create_context()
    page = await context.new_page()
    await page.goto(f"data:text/html,<title>{name}</title>")
    assert await page.title() == name
    return session, driver_pid


async def _cancel_blocked_cleanup_attempts(
    *,
    task_name: str,
    close_lock: asyncio.Lock,
    attempts: int = 1,
) -> None:
    """Cancel real Playwright close attempts blocked on their production lock."""
    deadline = time.monotonic() + 10.0
    cleanup_task: asyncio.Task[object] | None = None
    while cleanup_task is None and time.monotonic() < deadline:
        cleanup_task = next(
            (task for task in asyncio.all_tasks() if task.get_name() == task_name),
            None,
        )
        if cleanup_task is None:
            await asyncio.sleep(0.01)
    if cleanup_task is None:
        close_lock.release()
        pytest.fail(f"cleanup task {task_name!r} did not start")

    try:
        # Each cancellation lands only after the concrete owner is queued on
        # its production lock, leaving the Playwright process retryable.
        for _ in range(attempts):
            waiter: object | None = None
            while time.monotonic() < deadline:
                waiters = getattr(close_lock, "_waiters", None)
                if waiters:
                    waiter = waiters[0]
                    break
                await asyncio.sleep(0.01)
            if waiter is None:
                pytest.fail(f"cleanup task {task_name!r} did not reach the owner close lock")
            cleanup_task.cancel()
            while time.monotonic() < deadline:
                waiters = getattr(close_lock, "_waiters", None)
                if not waiters or waiter not in waiters:
                    break
                await asyncio.sleep(0)
    finally:
        close_lock.release()


@pytest.mark.asyncio
async def test_body_error_retains_real_playwright_close_failure_for_retry() -> None:
    """A body error stays primary while its failed concrete owner remains retryable."""
    task_name = "test-body-error-real-playwright-close"
    session, driver_pid = await _opened_real_session("body-error-cleanup")

    await session._close_lock.acquire()
    cancel_close = asyncio.create_task(
        _cancel_blocked_cleanup_attempts(task_name=task_name, close_lock=session._close_lock),
    )
    with pytest.raises(RuntimeError, match="primary body failure") as exc_info:
        try:
            raise RuntimeError("primary body failure")
        finally:
            await close_async_resources(session, task_name=task_name)
    await cancel_close

    cleanup_error = exc_info.value.__dict__.get("async_cleanup_error")
    assert isinstance(cleanup_error, AsyncResourceCleanupError)
    assert cleanup_error._resources == (session,)
    assert cleanup_error._failures
    await cleanup_error.retry_cleanup()
    await wait_for_process_exit(driver_pid, after="cleanup retry")


@pytest.mark.asyncio
async def test_cancellation_stays_primary_when_real_playwright_close_fails() -> None:
    """Task cancellation retains a concrete cleanup failure without replacing itself."""
    task_name = "test-cancelled-body-real-playwright-close"
    session, driver_pid = await _opened_real_session("cancelled-body-cleanup")
    entered = asyncio.Event()
    hold_body = asyncio.Event()

    async def cancelled_owner() -> None:
        try:
            entered.set()
            await hold_body.wait()
        finally:
            await close_async_resources(session, task_name=task_name)

    owner_task = asyncio.create_task(cancelled_owner())
    await entered.wait()
    await session._close_lock.acquire()
    cancel_close = asyncio.create_task(
        _cancel_blocked_cleanup_attempts(task_name=task_name, close_lock=session._close_lock),
    )
    owner_task.cancel()
    with pytest.raises(asyncio.CancelledError) as exc_info:
        await owner_task
    await cancel_close

    cleanup_error = exc_info.value.__dict__.get("cleanup_error")
    assert isinstance(cleanup_error, AsyncResourceCleanupError)
    assert cleanup_error._resources == (session,)
    await cleanup_error.retry_cleanup()
    await wait_for_process_exit(driver_pid, after="cleanup retry")


@pytest.mark.asyncio
async def test_only_failed_real_owner_is_retained_and_retried(monkeypatch: pytest.MonkeyPatch) -> None:
    """Successful concrete owners are dropped while only the failed owner retries."""
    task_name = "test-multiple-real-playwright-owner-close"
    healthy_session, healthy_driver_pid = await _opened_real_session("healthy-cleanup-owner")
    failed_session, failed_driver_pid = await _opened_real_session("failed-cleanup-owner")
    healthy_entered, release_healthy, failed_entered = asyncio.Event(), asyncio.Event(), asyncio.Event()
    healthy_close, failed_close = healthy_session.close, failed_session.close

    async def delayed_healthy_close() -> None:
        healthy_entered.set()
        await release_healthy.wait()
        await healthy_close()

    async def observed_failed_close() -> None:
        failed_entered.set()
        await failed_close()

    monkeypatch.setattr(healthy_session, "close", delayed_healthy_close)
    monkeypatch.setattr(failed_session, "close", observed_failed_close)
    await failed_session._close_lock.acquire()
    cleanup_task = asyncio.create_task(
        close_async_resources(healthy_session, failed_session, task_name=task_name),
    )
    failed_ready = asyncio.create_task(failed_entered.wait())
    cancellers: list[asyncio.Task[None]] = []
    try:
        await healthy_entered.wait()
        assert not failed_entered.is_set(), "the second owner must wait for the first"
        release_healthy.set()
        done, _ = await asyncio.wait({failed_ready, cleanup_task}, return_when=asyncio.FIRST_COMPLETED)
        assert failed_ready in done, "cleanup finished without attempting the second owner"
        assert healthy_session.cleanup_complete
        cancel_close = asyncio.create_task(
            _cancel_blocked_cleanup_attempts(
                task_name=task_name,
                close_lock=failed_session._close_lock,
            ),
        )
        cancellers.append(cancel_close)
        try:
            with pytest.raises(AsyncResourceCleanupError) as exc_info:
                await cleanup_task
        finally:
            await cancel_close

        cleanup_error = exc_info.value
        await wait_for_process_exit(healthy_driver_pid, after="cleanup retry")
        assert cleanup_error._resources == (failed_session,)
        assert len(cleanup_error._failures) == 1
        await cleanup_error.retry_cleanup()
        await wait_for_process_exit(failed_driver_pid, after="cleanup retry")
    finally:
        release_healthy.set()
        try:
            if not cancellers:
                if failed_session._close_lock.locked():
                    failed_session._close_lock.release()
            else:
                await cancellers[0]
        finally:
            if not failed_ready.done():
                failed_ready.cancel()
            await asyncio.gather(failed_ready, cleanup_task, return_exceptions=True)
            await healthy_session.close()
            await failed_session.close()


@pytest.mark.asyncio
async def test_real_owner_exhausts_every_configured_close_attempt_before_retry() -> None:
    """A concrete owner is retained only after every configured attempt fails."""
    task_name = "test-exhausted-real-playwright-close"
    session, driver_pid = await _opened_real_session("exhausted-cleanup")

    await session._close_lock.acquire()
    cancel_close = asyncio.create_task(
        _cancel_blocked_cleanup_attempts(
            task_name=task_name,
            close_lock=session._close_lock,
            attempts=2,
        ),
    )
    with pytest.raises(AsyncResourceCleanupError) as exc_info:
        await close_async_resources(
            session,
            task_name=task_name,
            close_attempts=2,
        )
    await cancel_close

    cleanup_error = exc_info.value
    assert cleanup_error._resources == (session,)
    assert len(cleanup_error._failures) == 1
    assert cleanup_error._failures[0].__notes__ == ["resource close failed 2 times"]
    await cleanup_error.retry_cleanup()
    await wait_for_process_exit(driver_pid, after="cleanup retry")
