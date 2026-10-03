"""Bounded Windows job trees; records contain only synthetic process facts."""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
from pathlib import Path
from threading import Timer

from ..windows_process import WindowsProcessScope
from .process_support import fixture_arguments, fixture_environment, native_python


async def _tree(record: Path, *, exit_parent: bool) -> None:
    if sys.platform != "win32":
        raise RuntimeError("requires Windows")
    child = await asyncio.create_subprocess_exec(
        str(native_python()),
        "-c",
        "import time; time.sleep(15)",
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
    )
    breakaway_refused = False
    try:
        escaped = await asyncio.create_subprocess_exec(
            str(native_python()),
            "-c",
            "import time; time.sleep(1)",
            creationflags=subprocess.CREATE_BREAKAWAY_FROM_JOB,
        )
    except OSError as error:
        breakaway_refused = error.winerror == 5
    else:
        await asyncio.wait_for(escaped.wait(), timeout=3)
    record.write_text(json.dumps({"parent": os.getpid(), "child": child.pid, "breakaway_refused": breakaway_refused}))
    if exit_parent:
        os._exit(0)
    await child.wait()


async def _browser(record: Path) -> None:
    from playwright.async_api import async_playwright

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True, args=["--disable-background-networking"])
        try:
            page = await browser.new_page()
            await page.goto("data:text/html,<title>synthetic containment</title>")
            assert await page.title() == "synthetic containment"
            record.write_text("browser-ready")
            await asyncio.sleep(12)
        finally:
            await browser.close()


def main() -> None:
    """Keep every synthetic process finite even if the outer test fails."""
    lifetime = Timer(20, os._exit, args=(124,))
    lifetime.daemon = True
    lifetime.start()
    mode, filename = sys.argv[1:]
    record = Path(filename)
    if mode in {"owner", "browser-owner"}:
        scope = WindowsProcessScope()
        try:
            scope.launch(
                executable=native_python(),
                arguments=fixture_arguments(
                    "cadrumo.adapters.local_runtime.tests.job_fixture",
                    "browser" if mode == "browser-owner" else "tree",
                    filename,
                ),
                directory=record.parent,
                environment=fixture_environment(),
            )
            print("ready", flush=True)
            if sys.stdin.readline() == "members\n":
                print(json.dumps(scope.active_process_ids()), flush=True)
                sys.stdin.readline()
        finally:
            scope.terminate()
    elif mode == "browser":
        asyncio.run(_browser(record))
    else:
        asyncio.run(_tree(record, exit_parent=mode == "exited"))
    lifetime.cancel()


if __name__ == "__main__":
    main()
