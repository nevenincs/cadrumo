"""Real admitted Windows worker and browser containment acceptance fixture.

Only the development owner imports test profile helpers. The absolute isolated
worker script uses installed production composition and ordinary native ports.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from collections.abc import Callable, Generator
from contextlib import contextmanager
from functools import partial
from pathlib import Path
from threading import Event, Thread, Timer

from cadrumo.adapters.local_runtime.windows_process import WindowsProcessScope
from cadrumo.core.async_cleanup import close_async_resources
from cadrumo.core.config import load_settings
from cadrumo.entrypoints.runtime.worker import installed_profile_worker_composition, run


class _BlockingRelease:
    """Retain an actual fixture resource until its blocking close succeeds."""

    def __init__(self, release: Callable[[], None]) -> None:
        self.release = release
        self.released = False

    async def close(self) -> None:
        if not self.released:
            await asyncio.to_thread(self.release)
            self.released = True


class _BrowserWork:
    """Settle the owned browser loop and non-daemon thread before scope exit."""

    def __init__(self, directory: Path) -> None:
        self.directory = directory
        self.stop = Event()
        self.failure: BaseException | None = None
        self.failure_reported = False
        self.thread = Thread(target=self._run, name="windows-admitted-browser", daemon=False)

    def _run(self) -> None:
        try:
            asyncio.run(self._browser())
        except BaseException as error:
            self.failure = error
            (self.directory / "windows-worker-browser-failure.json").write_text(
                json.dumps({"type": type(error).__name__}), encoding="utf-8"
            )

    async def _browser(self) -> None:
        from playwright.async_api import async_playwright

        barrier = self.directory / "windows-start-browser"
        while not barrier.exists():
            if self.stop.is_set():
                return
            await asyncio.sleep(0.02)
        if self.stop.is_set():
            return
        # The controller creates the barrier only after a real install/status ACK.
        admitted = json.loads((self.directory / "windows-worker-admitted.json").read_text(encoding="utf-8"))
        assert admitted["worker_pid"] == os.getpid() and admitted["buffer_wiped"] is True
        async with async_playwright() as playwright:
            executable = str(Path(playwright.chromium.executable_path).resolve(strict=True))
            browser = await playwright.chromium.launch(
                executable_path=executable, headless=True, args=["--disable-background-networking"]
            )
            try:
                page = await browser.new_page()
                await page.goto("data:text/html,<title>synthetic containment</title>")
                title = await page.title()
                assert title == "synthetic containment"
                pending = self.directory / "windows-worker-browser.pending.json"
                pending.write_text(
                    json.dumps({"worker_pid": os.getpid(), "executable": executable, "title": title}),
                    encoding="utf-8",
                )
                pending.replace(self.directory / "windows-worker-browser.json")
                while not self.stop.is_set():
                    await asyncio.sleep(0.02)
            finally:
                await asyncio.wait_for(browser.close(), timeout=10)

    def close(self) -> None:
        self.stop.set()
        self.thread.join(timeout=15)
        if self.thread.is_alive():
            raise TimeoutError("owned browser thread has not settled")
        if self.failure is not None and not self.failure_reported:
            self.failure_reported = True
            raise self.failure


@contextmanager
def _admitted_worker_composition() -> Generator[None]:
    """Keep canonical private worker composition and own the admitted browser thread."""
    root = Path(load_settings().cadrumo_local_storage_root)
    config = json.loads((root / "windows-browser-config.json").read_text(encoding="utf-8"))
    directory = Path(config["directory"])
    work = _BrowserWork(directory)
    work_owner = _BlockingRelease(work.close)
    primary: BaseException | None = None
    resources: list[_BlockingRelease] = []
    try:
        with installed_profile_worker_composition():
            work.thread.start()
            resources.insert(0, work_owner)
            yield
    except BaseException as error:
        primary = error
        raise
    finally:
        asyncio.run(close_async_resources(*resources, task_name="windows-browser-fixture-close", primary_error=primary))


def _admitted_browser_owner(directory: Path) -> None:
    """Admit an encrypted profile before releasing the actual browser barrier."""
    from cadrumo.adapters.local_runtime.profile_worker import ProfileWorkerProcess
    from cadrumo.adapters.local_runtime.tests.profile_worker_support import lease, worker_profiles
    from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority
    from cadrumo.entrypoints.adapter_composition import profile_adapter_composition

    if sys.platform != "win32":
        raise RuntimeError("requires Windows")
    import win32api
    import win32event
    import win32job
    import win32process

    print(
        json.dumps(
            {
                "runtime_pid": os.getpid(),
                "created": win32process.GetProcessTimes(win32api.GetCurrentProcess())["CreationTime"].isoformat(),
            }
        ),
        flush=True,
    )
    directory.mkdir(parents=True, exist_ok=True)
    worker: ProfileWorkerProcess | None = None
    with (
        bundled_indexed_authority().operation(),
        profile_adapter_composition(),
        worker_profiles(directory) as subjects,
    ):
        root, ((identity, key), _other) = subjects
        (root / "windows-browser-config.json").write_text(
            json.dumps({"directory": str(directory.resolve())}),
            encoding="utf-8",
        )
        inner_primary: BaseException | None = None
        try:
            worker = ProfileWorkerProcess(identity, storage_root=root, worker_script=Path(__file__).resolve())
            admitted = lease(identity)
            buffer = bytearray(key)
            worker.install(admitted, buffer)
            assert not any(buffer)
            assert worker.status().sessions == (admitted.session_id,)
            channel = worker._channel
            assert channel is not None
            worker_pid = channel.peer.process_id
            assert worker_pid is not None
            assert worker_pid in worker._scope.active_process_ids()
            (directory / "windows-worker-admitted.json").write_text(
                json.dumps(
                    {
                        "runtime_pid": os.getpid(),
                        "worker_pid": worker_pid,
                        "session_id": str(admitted.session_id),
                        "buffer_wiped": True,
                    }
                ),
                encoding="utf-8",
            )
            print("ready", flush=True)
            for command in sys.stdin:
                if (directory / "windows-worker-browser-failure.json").exists():
                    raise RuntimeError("owned browser failed; see type-only diagnostic")
                if command == "members\n":
                    assert isinstance(worker._scope, WindowsProcessScope)
                    job = worker._scope._job
                    assert job is not None
                    rows: list[dict[str, int | str]] = []
                    for pid in worker._scope.active_process_ids():
                        handle = win32api.OpenProcess(0x1000 | 0x100000, False, pid)
                        query_primary: BaseException | None = None
                        try:
                            assert win32event.WaitForSingleObject(handle, 0) == win32event.WAIT_TIMEOUT
                            assert win32job.IsProcessInJob(handle, job)
                            created = win32process.GetProcessTimes(handle)["CreationTime"].isoformat()
                            rows.append({"pid": pid, "created": created})
                        except BaseException as error:
                            query_primary = error
                            raise
                        finally:
                            asyncio.run(
                                close_async_resources(
                                    _BlockingRelease(partial(win32api.CloseHandle, handle)),
                                    task_name="windows-member-query-close",
                                    primary_error=query_primary,
                                )
                            )
                    print(json.dumps(rows), flush=True)
                elif command == "stop\n":
                    break
                else:
                    raise ValueError("unknown fixture command")
        except BaseException as error:
            inner_primary = error
            raise
        finally:
            if worker is not None:
                asyncio.run(
                    close_async_resources(
                        _BlockingRelease(worker.close),
                        task_name="windows-admitted-worker-close",
                        primary_error=inner_primary,
                    )
                )


def main() -> None:
    """Keep owner and isolated worker finite without replacing canonical runtime."""
    lifetime = Timer(180, os._exit, args=(124,))
    lifetime.daemon = True
    lifetime.start()
    if sys.argv[1:2] == ["--storage-root"]:
        exit_code = run(composition_factory=_admitted_worker_composition)
        lifetime.cancel()
        raise SystemExit(exit_code)
    if len(sys.argv) != 3 or sys.argv[1] != "admitted-browser-owner":
        raise ValueError("expected admitted-browser-owner <directory> or canonical worker arguments")
    try:
        _admitted_browser_owner(Path(sys.argv[2]))
    finally:
        lifetime.cancel()


if __name__ == "__main__":
    main()
