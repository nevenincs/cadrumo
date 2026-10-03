"""Bounded Windows job trees; records contain only synthetic process facts."""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from threading import Timer

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


class _UnpublishedHandles:
    """Retain the actual creation handles until the real launch receives them."""

    def __init__(self, process: int, thread: int) -> None:
        self.process: int | None = process
        self.thread: int | None = thread

    async def close(self) -> None:
        import win32api

        failures: list[BaseException] = []
        for name in ("thread", "process"):
            handle = getattr(self, name)
            if handle is not None:
                try:
                    win32api.CloseHandle(handle)
                except BaseException as error:
                    failures.append(error)
                else:
                    setattr(self, name, None)
        if failures:
            raise BaseExceptionGroup("unpublished creation handles remain owned", failures)


def _launch_owner_loss(record: Path) -> None:
    """Hold only the return from the real native creation, before its Python owner exists."""
    from collections.abc import Mapping, Sequence
    from threading import Event

    import pytest
    import win32api
    import win32job
    import win32process

    from cadrumo.core.async_cleanup import close_async_resources

    from .. import windows_process
    from ..windows_process import WindowsProcessScope

    scope = WindowsProcessScope()
    original = windows_process._launch_in_job
    primary: BaseException | None = None

    def paused_launch(
        job: int, *, executable: Path, arguments: Sequence[str], directory: Path, environment: Mapping[str, str]
    ) -> tuple[int, int, int]:
        created = original(
            job, executable=executable, arguments=arguments, directory=directory, environment=environment
        )
        unpublished = _UnpublishedHandles(created[0], created[1])
        transferred = False
        body: BaseException | None = None
        try:
            assert scope._children == []
            assert scope._job == job and win32job.IsProcessInJob(created[0], job)
            deadline = time.monotonic() + 15
            facts = {
                "owner_pid": os.getpid(),
                "owner_created": win32process.GetProcessTimes(win32api.GetCurrentProcess())["CreationTime"].isoformat(),
                "child_pid": created[2],
                "child_created": win32process.GetProcessTimes(created[0])["CreationTime"].isoformat(),
                "job_handle": job,
                "published_children": len(scope._children),
                "barrier_deadline": deadline,
            }
            pending = record.with_suffix(".pending")
            pending.write_text(json.dumps(facts), encoding="utf-8")
            pending.replace(record)
            print("native-created-unpublished", flush=True)
            Event().wait(max(0, deadline - time.monotonic()))
            transferred = True
            return created
        except BaseException as error:
            body = error
            raise
        finally:
            if not transferred:
                asyncio.run(
                    close_async_resources(unpublished, task_name="unpublished-native-handles-close", primary_error=body)
                )

    try:
        with pytest.MonkeyPatch.context() as interception:
            interception.setattr(windows_process, "_launch_in_job", paused_launch)
            scope.launch(
                executable=native_python(),
                arguments=("-c", "import time; time.sleep(60)"),
                directory=record.parent,
                environment=fixture_environment(),
            )
    except BaseException as error:
        primary = error
        raise
    finally:
        asyncio.run(close_async_resources(scope, task_name="native-launch-owner-scope-close", primary_error=primary))


def main() -> None:
    """Keep every synthetic process finite even if the outer test fails."""
    lifetime = Timer(20, os._exit, args=(124,))
    lifetime.daemon = True
    lifetime.start()
    mode, filename = sys.argv[1:]
    record = Path(filename)
    if mode == "launch-owner-loss":
        _launch_owner_loss(record)
    elif mode in {"owner", "browser-owner"}:
        from ..windows_process import WindowsProcessScope

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
