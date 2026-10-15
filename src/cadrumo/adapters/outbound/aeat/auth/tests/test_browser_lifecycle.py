"""Real Playwright proofs for bounded authentication-owned cleanup."""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from ......application.auth.session_types import (
    AeatSession,
    ClaveMovilSessionDetail,
    ClavePermanenteSessionDetail,
)
from ......core.config import Settings
from ......core.errors.hierarchy import AeatLoginAssertionError
from ...browser.factory import create_browser_session
from ...browser.profile import Profile
from ...tests.process_support import wait_for_process_exit
from ..browser_lifecycle import (
    CloseIntentBarrier,
    close_owned_browser_context,
    close_owned_browser_session,
)
from ..clave_movil import ClaveMovilAuthProvider
from ..clave_permanente import ClavePermanenteAuthProvider

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]


async def _exercise_close_intent_serialization() -> None:
    """Two close intents keep ordinary work barred until both have exited."""
    barrier = CloseIntentBarrier()
    first_entered = asyncio.Event()
    release_first = asyncio.Event()
    second_entered = asyncio.Event()
    release_second = asyncio.Event()
    work_entered = asyncio.Event()

    async def close(entered: asyncio.Event, release: asyncio.Event) -> None:
        async with barrier.close():
            entered.set()
            await release.wait()

    async def work() -> None:
        async with barrier.work():
            work_entered.set()

    first = asyncio.create_task(close(first_entered, release_first))
    await first_entered.wait()
    second = asyncio.create_task(close(second_entered, release_second))
    for _ in range(100):
        if barrier._close_intents == 2:
            break
        await asyncio.sleep(0)
    assert barrier._close_intents == 2
    assert barrier.closing
    assert not second_entered.is_set()

    ordinary_work = asyncio.create_task(work())
    await asyncio.sleep(0)
    assert not work_entered.is_set()

    release_first.set()
    await second_entered.wait()
    assert barrier._close_intents == 1
    assert barrier.closing
    assert not work_entered.is_set()

    release_second.set()
    await asyncio.gather(first, second)
    await ordinary_work
    assert work_entered.is_set()
    assert barrier._close_intents == 0
    assert not barrier.closing


@pytest.mark.asyncio
async def test_close_intent_barrier_serializes_closers_and_bars_work() -> None:
    """Two close intents keep ordinary work barred until both have exited."""
    await asyncio.wait_for(_exercise_close_intent_serialization(), timeout=1.0)


async def _exercise_cancelled_close_intent() -> None:
    barrier = CloseIntentBarrier()
    first_entered = asyncio.Event()
    release_first = asyncio.Event()

    async def hold_first_close() -> None:
        async with barrier.close():
            first_entered.set()
            await release_first.wait()

    async def queue_second_close() -> None:
        async with barrier.close():
            pytest.fail("cancelled closer unexpectedly entered the serialized close body")

    first = asyncio.create_task(hold_first_close())
    await first_entered.wait()
    second = asyncio.create_task(queue_second_close())
    try:
        for _ in range(100):
            if barrier._close_intents == 2:
                break
            await asyncio.sleep(0)
        assert barrier._close_intents == 2

        second.cancel()
        with pytest.raises(asyncio.CancelledError):
            await second
        assert barrier._close_intents == 1
        assert barrier.closing
    finally:
        release_first.set()
        await asyncio.gather(first, return_exceptions=True)

    assert barrier._close_intents == 0
    assert not barrier.closing


@pytest.mark.asyncio
async def test_cancelled_queued_closer_releases_its_intent() -> None:
    """Cancellation cannot leave the close-intent barrier permanently closed."""
    await asyncio.wait_for(_exercise_cancelled_close_intent(), timeout=1.0)


@pytest.mark.asyncio
async def test_bounded_cleanup_retains_real_resources_for_retry() -> None:
    """A timed-out cleanup leaves each real owner available for a successful retry."""
    settings = Settings()
    session = await create_browser_session(
        settings,
        Profile(name="bounded-cleanup"),
    )
    driver_pid = session._playwright._impl_obj._connection._transport._proc.pid
    context = await session.create_context()
    page = await context.new_page()
    await page.goto("data:text/html,<title>bounded-cleanup</title>")
    assert await page.title() == "bounded-cleanup"

    assert not await close_owned_browser_context(
        context,
        timeout_ms=0,
        logger=logging.getLogger(__name__),
        owner="test-real-playwright-owner",
    )
    assert await close_owned_browser_context(
        context,
        timeout_ms=settings.cadrumo_browser_close_timeout_ms,
        logger=logging.getLogger(__name__),
        owner="test-real-playwright-owner",
    )
    assert not await close_owned_browser_session(
        session,
        timeout_ms=0,
        logger=logging.getLogger(__name__),
        owner="test-real-playwright-owner",
    )
    assert await close_owned_browser_session(
        session,
        timeout_ms=settings.cadrumo_browser_close_timeout_ms,
        logger=logging.getLogger(__name__),
        owner="test-real-playwright-owner",
    )
    await wait_for_process_exit(driver_pid, after="session close")


@pytest.mark.asyncio
async def test_timed_session_close_reports_success_after_runtime_settles_owner() -> None:
    """A timed graceful close is complete when Playwright stop reaps and finalizes it."""
    settings = Settings()
    session = await create_browser_session(
        settings,
        Profile(name="timed-runtime-settlement"),
    )
    driver_pid = int(session._playwright._impl_obj._connection._transport._proc.pid)
    context = await session.create_context()
    page = await context.new_page()
    await page.goto("data:text/html,<title>timed-runtime-settlement</title>")
    assert await page.title() == "timed-runtime-settlement"
    await context.close()

    profile_directory = session.session._working_directory
    assert profile_directory is not None
    profile_path = profile_directory.name
    await session.session._lifecycle_lock.acquire()
    try:
        closed = await close_owned_browser_session(
            session,
            timeout_ms=100,
            logger=logging.getLogger(__name__),
            owner="test-real-playwright-owner",
        )
        assert closed
        assert session.cleanup_complete
        assert session.session._browser is None
        assert session.session._working_directory is None
        assert not Path(profile_path).exists()
    finally:
        session.session._lifecycle_lock.release()
        if not session.cleanup_complete:
            await session.close()
        if session.session._working_directory is not None:
            session.session._cleanup_working_directory()

    await wait_for_process_exit(driver_pid, after="timed session close")


@pytest.mark.asyncio
async def test_profile_cleanup_failure_after_runtime_stop_remains_retryable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A failed profile deletion remains owned until a later close removes it."""
    session = await create_browser_session(
        Settings(),
        Profile(name="retry-runtime-profile-cleanup"),
    )
    driver_pid = int(session._playwright._impl_obj._connection._transport._proc.pid)
    context = await session.create_context()
    page = await context.new_page()
    await page.goto("data:text/html,<title>retry-runtime-profile-cleanup</title>")
    assert await page.title() == "retry-runtime-profile-cleanup"
    await context.close()

    working_directory = session.session._working_directory
    assert working_directory is not None
    profile_path = Path(working_directory.name)
    original_cleanup = session.session._cleanup_working_directory
    cleanup_attempts = 0

    def fail_once() -> None:
        nonlocal cleanup_attempts
        cleanup_attempts += 1
        if cleanup_attempts == 1:
            raise OSError("temporary profile is still in use")
        original_cleanup()

    monkeypatch.setattr(session.session, "_cleanup_working_directory", fail_once)
    await session.session._lifecycle_lock.acquire()
    try:
        closed = await close_owned_browser_session(
            session,
            timeout_ms=100,
            logger=logging.getLogger(__name__),
            owner="test-real-playwright-owner",
        )
    finally:
        session.session._lifecycle_lock.release()

    try:
        assert not closed
        assert not session.cleanup_complete
        assert session._playwright_stopped
        assert session.session._working_directory is working_directory
        assert profile_path.is_dir()

        await session.close()
        assert session.cleanup_complete
        assert cleanup_attempts == 2
        assert session.session._working_directory is None
        assert not profile_path.exists()
    finally:
        if not session.cleanup_complete:
            await session.close()
        if session.session._working_directory is not None:
            original_cleanup()

    await wait_for_process_exit(driver_pid, after="profile cleanup retry")


@pytest.mark.asyncio
async def test_parent_cancellation_propagates_after_runtime_fallback_settles() -> None:
    """Caller cancellation remains primary even when stop completes cleanup."""
    session = await create_browser_session(
        Settings(),
        Profile(name="cancelled-runtime-settlement"),
    )
    driver_pid = int(session._playwright._impl_obj._connection._transport._proc.pid)
    context = await session.create_context()
    page = await context.new_page()
    await page.goto("data:text/html,<title>cancelled-runtime-settlement</title>")
    assert await page.title() == "cancelled-runtime-settlement"
    await context.close()

    working_directory = session.session._working_directory
    assert working_directory is not None
    profile_path = Path(working_directory.name)
    await session.session._lifecycle_lock.acquire()
    close_task = asyncio.create_task(
        close_owned_browser_session(
            session,
            timeout_ms=15_000,
            logger=logging.getLogger(__name__),
            owner="test-real-playwright-owner",
        )
    )
    try:
        for _ in range(500):
            if session._close_lock.locked():
                break
            await asyncio.sleep(0.01)
        assert session._close_lock.locked()

        close_task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await close_task
        assert session.cleanup_complete
        assert session.session._browser is None
        assert session.session._working_directory is None
        assert not profile_path.exists()
    finally:
        session.session._lifecycle_lock.release()
        if not close_task.done():
            close_task.cancel()
            await asyncio.gather(close_task, return_exceptions=True)
        if not session.cleanup_complete:
            await session.close()
        if session.session._working_directory is not None:
            session.session._cleanup_working_directory()

    await wait_for_process_exit(driver_pid, after="cancelled session close")


@pytest.mark.parametrize("provider_type", [ClaveMovilAuthProvider, ClavePermanenteAuthProvider])
@pytest.mark.asyncio
async def test_clave_provider_close_waits_for_its_active_work_lease(provider_type: type) -> None:
    """Each real Cl@ve provider wires public close through the shared barrier."""
    provider = provider_type(Settings())
    async with provider._lifecycle.work():
        close_task = asyncio.create_task(provider.close())
        for _ in range(100):
            if provider._lifecycle._close_intents == 1:
                break
            await asyncio.sleep(0)
        assert provider._lifecycle._close_intents == 1
        assert not close_task.done()

    await asyncio.wait_for(close_task, timeout=1.0)
    assert provider._lifecycle._close_intents == 0


@pytest.mark.parametrize(
    ("provider_type", "provider_detail"),
    [
        (ClaveMovilAuthProvider, ClaveMovilSessionDetail(dni_nie="12345678Z")),
        (ClavePermanenteAuthProvider, ClavePermanenteSessionDetail(dni_nie="12345678Z")),
    ],
)
@pytest.mark.asyncio
async def test_clave_provider_close_intent_bars_public_verify_until_no_context_validation(
    provider_type: type,
    provider_detail: ClaveMovilSessionDetail | ClavePermanenteSessionDetail,
) -> None:
    """Public verify cannot enter while close owns the provider lifecycle."""
    provider = provider_type(Settings())
    authenticated_at = datetime.now(UTC)
    session = AeatSession(
        authenticated_at=authenticated_at,
        idle_deadline=authenticated_at + timedelta(minutes=1),
        storage_state_path=None,
        identity_nif="12345678Z",
        provider_detail=provider_detail,
    )

    async with provider._lifecycle.close():
        verify_task = asyncio.create_task(provider.verify(session))
        await asyncio.sleep(0)
        assert not verify_task.done()

    with pytest.raises(AeatLoginAssertionError, match="requires an active browser context"):
        await asyncio.wait_for(verify_task, timeout=1.0)
