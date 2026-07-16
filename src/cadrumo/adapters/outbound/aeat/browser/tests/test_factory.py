"""Real Playwright lifecycle tests for the default browser-session factory."""

from __future__ import annotations

import asyncio
import time
from pathlib import Path

import psutil
import pytest

from ......core.config import Settings
from ...auth import BrowserSessionLike
from .. import BrowserError, Profile, create_browser_session

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]


def _descendant_pids(pid: int) -> tuple[int, ...]:
    try:
        process = psutil.Process(pid)
        return tuple(child.pid for child in process.children(recursive=True) if child.is_running())
    except psutil.NoSuchProcess:
        return ()


async def _wait_for_descendants(
    pid: int,
    *,
    expect_non_empty: bool,
    timeout_seconds: float = 10.0,
) -> tuple[int, ...]:
    deadline = time.monotonic() + timeout_seconds
    observed = _descendant_pids(pid)
    while time.monotonic() < deadline:
        if bool(observed) is expect_non_empty:
            return observed
        await asyncio.sleep(0.1)
        observed = _descendant_pids(pid)
    return observed


async def _wait_for_process_exit(pid: int, *, timeout_seconds: float = 10.0) -> None:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if not psutil.pid_exists(pid):
            return
        await asyncio.sleep(0.1)
    pytest.fail(f"Playwright driver process {pid} remained alive after session close")


def _profile(tmp_path: Path, name: str) -> Profile:
    return Profile(
        name=name,
        storage_state_path=tmp_path / f"{name}-storage.json",
        locale="es-ES",
        timezone_id="Europe/Madrid",
    )


@pytest.mark.asyncio
async def test_default_browser_session_is_protocol_complete_and_reaps_runtime(tmp_path: Path) -> None:
    """The production session owns Chromium and its Playwright driver."""
    settings = Settings()
    session = await create_browser_session(settings, _profile(tmp_path, "protocol"))
    assert isinstance(session, BrowserSessionLike)

    driver_pid = session._playwright._impl_obj._connection._transport._proc.pid
    context = await session.create_context()
    page = await context.new_page()
    await page.goto("data:text/html,<title>browser-lifecycle</title>")
    assert await page.title() == "browser-lifecycle"
    assert await page.evaluate("navigator.webdriver") is False

    live_descendants = await _wait_for_descendants(driver_pid, expect_non_empty=True)
    assert live_descendants
    with pytest.raises(BrowserError, match=r"call close\(\) before create_context\(\) again") as excinfo:
        await session.create_context()
    assert excinfo.value.failure_mode == "session_busy"

    await context.close()
    assert await _wait_for_descendants(driver_pid, expect_non_empty=True)

    await session.close()
    await session.close()
    await _wait_for_process_exit(driver_pid)


@pytest.mark.asyncio
async def test_default_browser_session_reaps_browser_after_real_context_failure(tmp_path: Path) -> None:
    """A real Playwright context-construction failure must not leave Chromium alive."""
    session = await create_browser_session(Settings(), _profile(tmp_path, "context-failure"))
    driver_pid = session._playwright._impl_obj._connection._transport._proc.pid

    with pytest.raises(BrowserError):
        await session.create_context(
            storage_state={
                "cookies": "not-a-cookie-array",
                "origins": [],
            },
        )

    assert await _wait_for_descendants(driver_pid, expect_non_empty=False) == ()
    await session.close()
    await _wait_for_process_exit(driver_pid)


@pytest.mark.asyncio
async def test_profile_storage_state_is_ignored_until_explicitly_requested(tmp_path: Path) -> None:
    """Only an explicit storage-state argument may preload a browser context."""
    settings = Settings()
    profile = _profile(tmp_path, "explicit-storage")
    cookie_name = "explicit-storage-authority"

    seed_session = await create_browser_session(settings, profile)
    seed_context = await seed_session.create_context(storage_state={})
    try:
        await seed_context.add_cookies(
            [
                {
                    "name": cookie_name,
                    "value": "test-only",
                    "url": "https://example.test",
                },
            ],
        )
        await seed_context.storage_state(path=profile.storage_state_path)
    finally:
        await seed_context.close()
        await seed_session.close()

    implicit_session = await create_browser_session(settings, profile)
    implicit_context = await implicit_session.create_context()
    try:
        implicit_state = await implicit_context.storage_state()
        implicit_cookies = implicit_state.get("cookies", [])
        assert all(cookie.get("name") != cookie_name for cookie in implicit_cookies)
    finally:
        await implicit_context.close()
        await implicit_session.close()

    explicit_session = await create_browser_session(settings, profile)
    explicit_context = await explicit_session.create_context(
        storage_state_path=profile.storage_state_path,
    )
    try:
        explicit_state = await explicit_context.storage_state()
        explicit_cookies = explicit_state.get("cookies", [])
        assert any(cookie.get("name") == cookie_name for cookie in explicit_cookies)
    finally:
        await explicit_context.close()
        await explicit_session.close()


@pytest.mark.asyncio
async def test_real_browser_process_count_returns_to_zero_across_repeated_cycles(tmp_path: Path) -> None:
    """Repeated real Chromium sessions must reap every Playwright driver."""
    settings = Settings()

    for index in range(3):
        session = await create_browser_session(settings, _profile(tmp_path, f"cycle-{index}"))
        driver_pid = session._playwright._impl_obj._connection._transport._proc.pid
        context = await session.create_context()
        page = await context.new_page()
        await page.goto(f"data:text/html,<title>cycle-{index}</title>")
        assert await page.title() == f"cycle-{index}"

        await context.close()
        await session.close()
        await _wait_for_process_exit(driver_pid)
