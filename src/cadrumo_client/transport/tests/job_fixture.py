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

from cadrumo.tests.process_support import fixture_arguments, fixture_environment, native_python


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
    original = windows_process.launch_in_windows_job
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
            interception.setattr(windows_process, "launch_in_windows_job", paused_launch)
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
    if mode == "pid-churn":
        _pid_churn(record)
    elif mode == "launch-owner-loss":
        _launch_owner_loss(record)
    elif mode in {"owner", "browser-owner"}:
        from ..windows_process import WindowsProcessScope

        scope = WindowsProcessScope()
        try:
            scope.launch(
                executable=native_python(),
                arguments=fixture_arguments(
                    "cadrumo_client.transport.tests.job_fixture",
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


def _pid_churn(record: Path) -> None:
    """Exercise process enumeration and retained-handle cleanup against real exits."""
    from concurrent.futures import ThreadPoolExecutor

    from ..windows_process import WindowsProcessScope, _release_job_members, _retain_job_members

    scope = WindowsProcessScope()
    try:

        def churn() -> int:
            for _ in range(16):
                process = scope.launch(
                    executable=native_python(),
                    arguments=("-c", "pass"),
                    directory=record.parent,
                    environment=fixture_environment(),
                )
                assert process.wait(timeout=5) == 0
            return 16

        queries = 0
        with ThreadPoolExecutor(max_workers=3) as workers:
            running = [workers.submit(churn) for _ in range(3)]
            while not all(future.done() for future in running):
                assert scope._job is not None
                retained = _retain_job_members(scope._job)
                _release_job_members(retained)
                assert all(pid > 0 for pid in scope.active_process_ids())
                queries += 1
            launched = sum(future.result() for future in running)
        record.write_text(json.dumps({"launched": launched, "queries": queries}))
    finally:
        scope.terminate()
    assert scope.active_process_ids() == ()


if __name__ == "__main__":
    main()
