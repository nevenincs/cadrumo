"""Expendable real Linux runtime owner for abrupt-death containment proofs."""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from collections.abc import Generator
from contextlib import contextmanager, nullcontext
from pathlib import Path

import pytest

from cadrumo.adapters.local_runtime import linux_worker_process
from cadrumo.adapters.local_runtime.linux_worker_process import LinuxProcessScope
from cadrumo.adapters.local_runtime.manager_commands import ManagerCommandResult, NativeManagerCommand
from cadrumo.adapters.local_runtime.profile_worker import ProfileWorkerProcess, unreturned_profile_worker
from cadrumo.adapters.local_runtime.runtime_transport_cleanup import RuntimeTransportCleanup
from cadrumo.adapters.local_runtime.tests.profile_worker_support import lease, worker_profiles
from cadrumo.application.runtime.contracts import RuntimeRefusalError
from cadrumo.core.async_cleanup import close_async_resources
from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority
from cadrumo.entrypoints.adapter_composition import profile_adapter_composition


def _resistant_worker_script(directory: Path) -> Path:
    """Wrap the actual isolated worker with two key-free resistant descendants."""
    script = directory / "linux-resistant-worker.py"
    output = directory / "linux-worker-descendants.json"
    script.write_text(
        """import json
import os
import select
import signal
import time
from pathlib import Path

from cadrumo.adapters.local_runtime.linux_worker_process import linux_process_start_identity
from cadrumo.entrypoints.runtime.worker import run

read_fd, write_fd = os.pipe()
child = os.fork()
if child == 0:
    os.close(read_fd)
    os.setsid()
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
    grandchild = os.fork()
    if grandchild == 0:
        os.setsid()
        role = "grandchild"
    else:
        role = "child"
    record = {
        "role": role,
        "pid": os.getpid(),
        "parent_pid": os.getppid(),
        "start_identity": linux_process_start_identity(os.getpid()),
    }
    encoded = json.dumps(record).encode("ascii") + b"\\n"
    if os.write(write_fd, encoded) != len(encoded):
        os._exit(2)
    os.close(write_fd)
    while True:
        signal.pause()

os.close(write_fd)
records = bytearray()
deadline = time.monotonic() + 5
try:
    while records.count(b"\\n") < 2:
        remaining = deadline - time.monotonic()
        if remaining <= 0 or not select.select((read_fd,), (), (), remaining)[0]:
            raise TimeoutError("resistant descendant startup")
        block = os.read(read_fd, 1024)
        if not block or len(records) + len(block) > 2048:
            raise RuntimeError("resistant descendant startup")
        records.extend(block)
finally:
    os.close(read_fd)

output = Path("""
        + repr(str(output))
        + """)
pending = output.with_suffix(".pending")
pending.write_text(json.dumps([json.loads(row) for row in records.splitlines()]), encoding="ascii")
pending.replace(output)
raise SystemExit(run())
""",
        encoding="utf-8",
    )
    return script


def _publish_scope(directory: Path, worker: ProfileWorkerProcess) -> dict[str, int | str | None]:
    """Publish acquired native identity before private installation can fail."""
    scope = worker._scope
    assert isinstance(scope, LinuxProcessScope)
    guardian = scope._guardian
    record = {
        "runtime_pid": os.getpid(),
        "worker_pid": scope._worker_pid,
        "guardian_pid": guardian.pid if guardian is not None else None,
        "unit": scope._unit,
        "cgroup": scope._cgroup,
    }
    pending = directory / "linux-worker-acquired.pending"
    pending.write_text(json.dumps(record), encoding="ascii")
    pending.replace(directory / "linux-worker-acquired.json")
    return record


def _browser_worker_script(directory: Path) -> Path:
    """Launch Chromium only after the real worker has admitted its exact lease."""
    script = directory / "linux-browser-worker.py"
    output = directory / "linux-worker-browser.json"
    script.write_text(
        """import asyncio
import json
import os
import sys
import time
from pathlib import Path

from playwright.async_api import async_playwright
from cadrumo.adapters.local_runtime.runtime_transport_cleanup import RuntimeTransportCleanup
from cadrumo.adapters.local_runtime.linux_worker_process import linux_process_start_identity
from cadrumo.core.async_cleanup import await_cancellation_complete, close_async_resources
from cadrumo.entrypoints.runtime.worker import run

directory = Path("""
        + repr(str(directory))
        + """)

def publish_failure(error):
    pending = directory / "linux-worker-browser-failure.pending"
    pending.write_text(json.dumps({"code": type(error).__name__}), encoding="ascii")
    pending.replace(directory / "linux-worker-browser-failure.json")

async def actual_worker():
    try:
        code = await asyncio.to_thread(run)
        return code if code == 0 else RuntimeError("actual worker refused startup")
    except BaseException as error:
        # Transport terminal cancellation as a value; do not let a shield
        # manufacture a different cancellation while retaining the real task.
        return error

class WorkerTaskOwner:
    def __init__(self, task):
        self.task = task
        self.observed_error = None

    def require_running(self):
        if self.task.done():
            outcome = self.task.result()
            if isinstance(outcome, BaseException):
                self.observed_error = outcome
                raise outcome
            raise RuntimeError("actual worker exited before browser readiness")

    async def close(self):
        outcome = await await_cancellation_complete(self.task, task_name="contained-real-worker-settle")
        if isinstance(outcome, BaseException) and outcome is not self.observed_error:
            self.observed_error = outcome
            raise outcome

class PlaywrightOwner:
    def __init__(self):
        self.context = async_playwright()
        self.playwright = None
        self.released = False

    async def start(self):
        self.playwright = await self.context.__aenter__()

    async def close(self):
        if not self.released:
            await self.context.__aexit__(None, None, None)
            self.released = True

async def serve():
    worker_owner = WorkerTaskOwner(asyncio.create_task(actual_worker(), name="contained-real-worker"))
    playwright_owner = None
    marker_owner = None
    browsers = []
    try:
        ready = directory / "linux-worker-ready.json"
        deadline = time.monotonic() + 45
        while not ready.exists():
            worker_owner.require_running()
            if time.monotonic() >= deadline:
                raise TimeoutError("real worker admission witness")
            await asyncio.sleep(0.05)
        worker_owner.require_running()
        admitted = json.loads(ready.read_text(encoding="ascii"))
        pid = os.getpid()
        started = linux_process_start_identity(pid)
        assert admitted["worker_pid"] == pid
        assert admitted["worker_group"] == os.getpgid(pid) == pid
        assert (Path("/proc") / str(pid) / "cgroup").read_text(encoding="ascii").strip() == "0::" + admitted["cgroup"]
        marker = (directory / "linux-worker-inheritance.marker").open("xb")
        marker_owner = RuntimeTransportCleanup(marker)
        os.set_inheritable(marker.fileno(), True)
        metadata = os.fstat(marker.fileno())
        assert os.get_inheritable(marker.fileno())
        pending = directory / "linux-worker-marker.pending"
        pending.write_text(json.dumps({
            "pid": pid, "fd": marker.fileno(), "device": metadata.st_dev, "inode": metadata.st_ino,
        }), encoding="ascii")
        pending.replace(directory / "linux-worker-marker.json")
        playwright_owner = PlaywrightOwner()
        await await_cancellation_complete(playwright_owner.start(), task_name="contained-playwright-start")
        playwright = playwright_owner.playwright
        executable = Path(playwright.chromium.executable_path)
        if not executable.is_file():
            raise RuntimeError("installed Chromium unavailable")

        async def launch_browser():
            browsers.append(await playwright.chromium.launch(
                executable_path=str(executable),
                headless=True,
                args=["--disable-background-networking"],
            ))

        await await_cancellation_complete(launch_browser(), task_name="contained-browser-launch")
        worker_owner.require_running()
        browser = browsers[0]
        page = await browser.new_page()
        await page.goto("data:text/html,<title>synthetic containment</title>")
        assert await page.title() == "synthetic containment"
        worker_owner.require_running()
        assert linux_process_start_identity(pid) == started
        output = Path("""
        + repr(str(output))
        + """)
        pending = output.with_suffix(".pending")
        pending.write_text(json.dumps({
            "title": await page.title(),
            "executable": str(executable.resolve(strict=True)),
            "worker_pid": pid,
            "worker_start_identity": started,
        }), encoding="ascii")
        pending.replace(output)
        outcome = await asyncio.shield(worker_owner.task)
        if isinstance(outcome, BaseException):
            worker_owner.observed_error = outcome
            raise outcome
        return outcome
    except BaseException as error:
        # The controller owns bounded exact-unit retirement. Report BEFORE
        # awaiting this serving thread; cancellation alone cannot stop run().
        try:
            publish_failure(error)
        except BaseException as publication:
            error.__dict__["browser_failure_publication_error"] = publication
        raise
    finally:
        await close_async_resources(
            *browsers, playwright_owner, marker_owner, worker_owner,
            task_name="contained-browser-worker-close", primary_error=sys.exception(),
        )

raise SystemExit(asyncio.run(serve()))
""",
        encoding="utf-8",
    )
    return script


@contextmanager
def _registration_barrier(directory: Path) -> Generator[None]:
    """Hold real registration acknowledgment before guardian ownership transfers."""
    original = linux_worker_process.run_manager_command_sync

    def register(tool: NativeManagerCommand, arguments: tuple[str, ...]) -> ManagerCommandResult:
        if tool is not NativeManagerCommand.SYSTEMD_RUN:
            return original(tool, arguments)
        units = [argument.removeprefix("--unit=") for argument in arguments if argument.startswith("--unit=")]
        assert len(units) == 1
        # Publish reservation before asking the manager: lost acknowledgment or
        # subsequent publication failure still has one exact cleanup target.
        record = {"runtime_pid": os.getpid(), "unit": units[0], "cgroup": ""}
        pending = directory / "linux-worker-acquired.pending"
        pending.write_text(json.dumps(record), encoding="ascii")
        pending.replace(directory / "linux-worker-acquired.json")
        result = original(tool, arguments)
        if result.returncode == 0:
            deadline = time.monotonic() + 30
            pending = directory / "linux-worker-registered.pending"
            pending.write_text(json.dumps(record | {"barrier_deadline": deadline}), encoding="ascii")
            pending.replace(directory / "linux-worker-registered.json")
            while not (directory / "linux-registration-release").exists():
                if time.monotonic() >= deadline:
                    raise TimeoutError("registration acknowledgment barrier")
                time.sleep(0.05)
        return result

    with pytest.MonkeyPatch.context() as scheduling:
        scheduling.setattr(linux_worker_process, "run_manager_command_sync", register)
        yield


def run(
    directory: Path,
    *,
    resistant_descendants: bool = False,
    browser_descendants: bool = False,
    registration_loss: bool = False,
) -> int:
    if sys.platform != "linux":
        raise RuntimeError("Linux worker parent fixture requires Linux")
    assert not (resistant_descendants and browser_descendants)
    assert not (registration_loss and (resistant_descendants or browser_descendants))
    worker_script = (
        _browser_worker_script(directory)
        if browser_descendants
        else _resistant_worker_script(directory)
        if resistant_descendants
        else None
    )
    with (
        profile_adapter_composition(),
        bundled_indexed_authority().operation(),
        worker_profiles(directory) as (root, subjects),
    ):
        identity, key = subjects[0]
        worker: ProfileWorkerProcess | None = None
        marker_owner: RuntimeTransportCleanup | None = None
        try:
            if browser_descendants:
                marker = (directory / "linux-parent-inheritance.marker").open("xb")
                marker_owner = RuntimeTransportCleanup(marker)
                os.set_inheritable(marker.fileno(), True)
                marker_stat = os.fstat(marker.fileno())
                assert os.get_inheritable(marker.fileno())
                pending_marker = directory / "linux-parent-marker.pending"
                pending_marker.write_text(
                    json.dumps({"fd": marker.fileno(), "device": marker_stat.st_dev, "inode": marker_stat.st_ino}),
                    encoding="ascii",
                )
                pending_marker.replace(directory / "linux-parent-marker.json")
            try:
                with _registration_barrier(directory) if registration_loss else nullcontext():
                    worker = ProfileWorkerProcess(identity, storage_root=root, worker_script=worker_script)
            except BaseException as error:
                worker = unreturned_profile_worker(error)
                if worker is not None:
                    try:
                        _publish_scope(directory, worker)
                    except BaseException as publication_error:
                        error.__dict__["scope_publication_error"] = publication_error
                raise
            record = _publish_scope(directory, worker)
            admitted = lease(identity)
            worker.install(admitted, bytearray(key))
            assert worker.status().sessions == (admitted.session_id,)
            scope = worker._scope
            assert isinstance(scope, LinuxProcessScope)
            guardian = scope._guardian
            assert guardian is not None
            record |= {
                "worker_group": os.getpgid(scope._worker_pid),
                "guardian_group": os.getpgid(guardian.pid),
            }
            pending = directory / "linux-worker-ready.pending"
            pending.write_text(json.dumps(record), encoding="ascii")
            pending.replace(directory / "linux-worker-ready.json")
            while True:
                time.sleep(1)
        finally:
            asyncio.run(
                close_async_resources(
                    RuntimeTransportCleanup(worker) if worker is not None else None,
                    marker_owner,
                    task_name="linux-contained-parent-worker-close",
                    primary_error=sys.exception(),
                )
            )


if __name__ == "__main__":
    if sys.platform != "linux" or len(sys.argv) not in {2, 3}:
        raise SystemExit(2)
    if len(sys.argv) == 3 and sys.argv[2] not in {"resistant-descendants", "browser-descendants", "registration-loss"}:
        raise SystemExit(2)
    try:
        mode = sys.argv[2] if len(sys.argv) == 3 else None
        exit_code = run(
            Path(sys.argv[1]),
            resistant_descendants=mode == "resistant-descendants",
            browser_descendants=mode == "browser-descendants",
            registration_loss=mode == "registration-loss",
        )
    except BaseException as error:
        # The disposable parent never reports exception text, native paths,
        # profile material, or worker frames to the test controller.
        code = error.reason.value if isinstance(error, RuntimeRefusalError) else type(error).__name__
        locations: list[str] = []
        trace = error.__traceback__
        while trace is not None and len(locations) < 16:
            source = trace.tb_frame.f_code
            locations.append(f"{Path(source.co_filename).name}:{source.co_name}:{trace.tb_lineno}")
            trace = trace.tb_next
        (Path(sys.argv[1]) / "linux-worker-failure.json").write_text(
            json.dumps({"code": code, "source_locations": locations}), encoding="ascii"
        )
        raise SystemExit(1) from None
    raise SystemExit(exit_code)
