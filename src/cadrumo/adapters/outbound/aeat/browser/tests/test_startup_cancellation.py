"""Cancellation at real subprocess acquisition must finish resource release."""

from __future__ import annotations

import asyncio

import pytest
from playwright.async_api import BrowserType
from playwright.async_api._context_manager import PlaywrightContextManager

from cadrumo.core.config import Settings

from ...tests.process_support import wait_for_process_exit
from ..factory import create_browser_session
from ..profile import Profile

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]


@pytest.mark.asyncio
async def test_cancelled_runtime_start_reaps_real_driver(monkeypatch: pytest.MonkeyPatch) -> None:
    ready, release = asyncio.Event(), asyncio.Event()
    original = PlaywrightContextManager.start
    runtimes = []

    async def delayed_start(manager):
        runtime = await original(manager)
        runtimes.append(runtime)
        ready.set()
        await release.wait()
        return runtime

    monkeypatch.setattr(PlaywrightContextManager, "start", delayed_start)
    task = asyncio.create_task(create_browser_session(Settings(), Profile(name="cancel-start")))
    try:
        await asyncio.wait_for(ready.wait(), 15)
        pid = runtimes[0]._impl_obj._connection._transport._proc.pid
        task.cancel()
        await asyncio.sleep(0)
        task.cancel()
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await task
        await wait_for_process_exit(pid, after="cancelled runtime startup")
    finally:
        release.set()
        await asyncio.gather(task, return_exceptions=True)
        for runtime in runtimes:
            await runtime.stop()


@pytest.mark.asyncio
async def test_cancelled_chromium_launch_reaps_real_browser(monkeypatch: pytest.MonkeyPatch) -> None:
    ready, release = asyncio.Event(), asyncio.Event()
    original = BrowserType.launch_persistent_context
    browsers = []
    session = await create_browser_session(Settings(), Profile(name="cancel-launch"))

    async def delayed_launch(browser_type, **kwargs):
        context = await original(browser_type, **kwargs)
        browser = context.browser
        assert browser is not None
        browsers.append(browser)
        ready.set()
        await release.wait()
        return context

    monkeypatch.setattr(BrowserType, "launch_persistent_context", delayed_launch)
    task = asyncio.create_task(session.create_context())
    try:
        await asyncio.wait_for(ready.wait(), 15)
        cdp = await browsers[0].new_browser_cdp_session()
        processes = await cdp.send("SystemInfo.getProcessInfo")
        pids = [row["id"] for row in processes["processInfo"]]
        await cdp.detach()
        task.cancel()
        await asyncio.sleep(0)
        task.cancel()
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert not browsers[0].is_connected()
        assert session.session._browser is None
        for pid in pids:
            await wait_for_process_exit(pid, after="cancelled Chromium launch")
    finally:
        release.set()
        await asyncio.gather(task, return_exceptions=True)
        await session.close()
