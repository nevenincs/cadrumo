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

pytestmark = [pytest.mark.integration, pytest.mark.hex_outbound_adapter]


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
    session = await create_browser_session(Settings(), _profile(tmp_path, "protocol"))
    assert isinstance(session, BrowserSessionLike)

    driver_pid = session._playwright._impl_obj._connection._transport._proc.pid
    context = await session.create_context()
    page = await context.new_page()
    await page.goto("data:text/html,<title>browser-lifecycle</title>")
    assert await page.title() == "browser-lifecycle"

    live_descendants = await _wait_for_descendants(driver_pid, expect_non_empty=True)
    assert live_descendants
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
