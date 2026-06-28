"""Live tests for bot evasion strategies and browser lifecycle cleanup."""

from __future__ import annotations

import asyncio
import json
import platform
import shutil
import subprocess
import textwrap
import time
from dataclasses import dataclass

import pytest
from playwright.async_api import async_playwright

from ......core.config import load_settings
from ......tests.live_gate import requires_live_enabled
from ..profile import Profile
from ..session import BrowserSession

pytestmark = [pytest.mark.aeat_live, pytest.mark.hex_outbound_adapter]


@dataclass(frozen=True)
class _ProcessInfo:
    pid: int
    parent_pid: int
    name: str
    command_line: str


def _require_executable(name: str) -> str:
    """Resolve a required system executable for local process inspection."""
    resolved = shutil.which(name)
    if resolved is None:
        pytest.skip(f"required system executable is unavailable: {name}")
    return resolved


def _driver_descendants(driver_pid: int) -> tuple[_ProcessInfo, ...]:
    """Return the recursive process tree owned by the Playwright driver."""
    system = platform.system()
    if system == "Windows":
        script = textwrap.dedent(
            f"""
            $ErrorActionPreference = 'Stop'
            function Get-Descendants([int]$ParentPid) {{
              $result = @()
              $queue = [System.Collections.Generic.Queue[int]]::new()
              $queue.Enqueue($ParentPid)
              while ($queue.Count -gt 0) {{
                $current = $queue.Dequeue()
                $children = Get-CimInstance Win32_Process -Filter "ParentProcessId = $current"
                foreach ($child in $children) {{
                  $result += [pscustomobject]@{{
                    pid = [int]$child.ProcessId
                    parent_pid = [int]$child.ParentProcessId
                    name = [string]$child.Name
                    command_line = [string]$child.CommandLine
                  }}
                  $queue.Enqueue([int]$child.ProcessId)
                }}
              }}
              $result | ConvertTo-Json -Depth 3 -Compress
            }}
            Get-Descendants {driver_pid}
            """,
        ).strip()
        completed = subprocess.run(
            [_require_executable("powershell"), "-NoProfile", "-Command", script],
            check=True,
            capture_output=True,
            text=True,
        )
        payload = completed.stdout.strip()
        if not payload:
            return ()
        decoded = json.loads(payload)
        if isinstance(decoded, dict):
            decoded = [decoded]
        return tuple(
            _ProcessInfo(
                pid=int(item["pid"]),
                parent_pid=int(item["parent_pid"]),
                name=str(item["name"]),
                command_line=str(item.get("command_line") or ""),
            )
            for item in decoded
        )

    completed = subprocess.run(
        [_require_executable("ps"), "-axo", "pid=,ppid=,comm=,args="],
        check=True,
        capture_output=True,
        text=True,
    )
    children_by_parent: dict[int, list[_ProcessInfo]] = {}
    for raw_line in completed.stdout.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        parts = line.split(None, 3)
        if len(parts) < 3:
            continue
        pid = int(parts[0])
        parent_pid = int(parts[1])
        name = parts[2]
        command_line = parts[3] if len(parts) > 3 else name
        info = _ProcessInfo(pid=pid, parent_pid=parent_pid, name=name, command_line=command_line)
        children_by_parent.setdefault(parent_pid, []).append(info)

    descendants: list[_ProcessInfo] = []
    queue = [driver_pid]
    while queue:
        current = queue.pop(0)
        for child in children_by_parent.get(current, []):
            descendants.append(child)
            queue.append(child.pid)
    return tuple(descendants)


async def _wait_for_descendants(
    driver_pid: int,
    *,
    expect_non_empty: bool,
    timeout_seconds: float = 10.0,
) -> tuple[_ProcessInfo, ...]:
    """Poll the driver process tree until it matches the expected emptiness."""
    deadline = time.monotonic() + timeout_seconds
    snapshot: tuple[_ProcessInfo, ...] = ()
    while time.monotonic() < deadline:
        snapshot = _driver_descendants(driver_pid)
        if expect_non_empty and snapshot:
            return snapshot
        if not expect_non_empty and not snapshot:
            return snapshot
        await asyncio.sleep(0.2)
    return snapshot


@pytest.mark.asyncio
async def test_live_bot_detection_probe(tmp_path) -> None:
    """Test the browser session against a live bot detection probe.

    Gated by the ``aeat_live`` module-level marker (excluded from the default
    ``just test`` selection) and by ``AEAT_LIVE_TESTS_ENABLED`` when invoked
    via ``just test-live``.
    """
    requires_live_enabled()

    settings = load_settings()
    profile = Profile(name="live_test", storage_state_path=tmp_path / "live_state.json")

    async with async_playwright() as p:
        session = BrowserSession(playwright=p, settings=settings, profile=profile)
        context = await session.create_context()
        page = await context.new_page()

        response = await page.goto("https://bot.sannysoft.com/", wait_until="networkidle")
        assert response is not None
        assert response.ok

        webdriver_result = await page.evaluate("navigator.webdriver")
        assert webdriver_result is False, "navigator.webdriver is True, bot detected!"

        await context.close()
        await session.close()


@pytest.mark.asyncio
async def test_live_browser_session_reaps_driver_descendants_across_cycles(tmp_path) -> None:
    """A real BrowserSession must fully reap browser OS processes on close."""
    requires_live_enabled()

    settings = load_settings()
    profile = Profile(name="live_test_reap", storage_state_path=tmp_path / "live_reap_state.json")

    async with async_playwright() as p:
        driver_pid = p._impl_obj._connection._transport._proc.pid
        assert await _wait_for_descendants(driver_pid, expect_non_empty=False, timeout_seconds=2.0) == ()

        for idx in range(3):
            session = BrowserSession(playwright=p, settings=settings, profile=profile)
            context = await session.create_context()
            page = await context.new_page()
            response = await page.goto("https://bot.sannysoft.com/", wait_until="domcontentloaded")
            assert response is not None, f"cycle {idx}: navigation returned no response"

            descendants_while_live = await _wait_for_descendants(driver_pid, expect_non_empty=True)
            assert descendants_while_live, f"cycle {idx}: expected live browser descendants"

            await context.close()
            descendants_after_context_close = await _wait_for_descendants(driver_pid, expect_non_empty=True)
            assert descendants_after_context_close, (
                f"cycle {idx}: context.close() unexpectedly reaped the retained browser "
                "before BrowserSession.close() ran"
            )

            await session.close()
            descendants_after_session_close = await _wait_for_descendants(
                driver_pid,
                expect_non_empty=False,
            )
            assert descendants_after_session_close == (), (
                f"cycle {idx}: leaked browser descendants after BrowserSession.close(): "
                f"{descendants_after_session_close!r}"
            )
