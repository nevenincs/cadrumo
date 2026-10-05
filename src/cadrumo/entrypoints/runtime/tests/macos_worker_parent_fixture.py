"""Expendable real macOS runtime owner for abrupt-death coalition containment proofs."""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from collections.abc import Generator
from contextlib import contextmanager, nullcontext
from pathlib import Path
from uuid import uuid4

import pytest

from cadrumo.adapters.local_runtime import macos_worker_process
from cadrumo.adapters.local_runtime.containment_commands import ContainmentCommand, ContainmentCommandResult
from cadrumo.adapters.local_runtime.macos_worker_process import MacosProcessScope
from cadrumo.adapters.local_runtime.profile_worker import ProfileWorkerProcess, unreturned_profile_worker
from cadrumo.adapters.local_runtime.runtime_transport_cleanup import RuntimeTransportCleanup
from cadrumo.adapters.local_runtime.tests.profile_worker_support import lease, worker_profiles
from cadrumo.application.runtime.contracts import RuntimeRefusalError
from cadrumo.core.async_cleanup import close_async_resources
from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority
from cadrumo.entrypoints.adapter_composition import profile_adapter_composition

MODES = frozenset(("resistant-descendants", "browser-descendants", "registration-loss", "churn-descendants", "reap"))
_CLEAN_ENVIRONMENT = {"PATH": "/usr/bin:/bin", "LANG": "C", "LC_ALL": "C", "PYDANTIC_DISABLE_PLUGINS": "__all__"}

# Shared by every worker wrapper: the worker reports its own environment and
# descriptor identities, so the controller can prove nothing of the runtime's
# environment or inheritable descriptors crossed the launchd job boundary.
_INHERITANCE_PRELUDE = """import json
import os
from pathlib import Path

directory = Path({directory!r})


def publish(name, document):
    pending = directory / (name + ".pending")
    pending.write_text(json.dumps(document), encoding="ascii")
    pending.replace(directory / (name + ".json"))


def descriptor_identities():
    identities = []
    for name in os.listdir("/dev/fd"):
        try:
            metadata = os.fstat(int(name))
        except OSError:
            continue
        identities.append([int(name), metadata.st_dev, metadata.st_ino])
    return identities


publish(
    "macos-worker-inheritance",
    {{"pid": os.getpid(), "environment": dict(os.environ), "descriptors": descriptor_identities()}},
)
"""


def _resistant_worker_script(directory: Path) -> Path:
    """Wrap the actual isolated worker with setsid, regrouped and orphaned descendants."""
    script = directory / "macos-resistant-worker.py"
    script.write_text(
        _INHERITANCE_PRELUDE.format(directory=str(directory))
        + """
import select
import signal
import time

from cadrumo.adapters.local_runtime.macos_coalition import read_macos_resource_coalition
from cadrumo.adapters.local_runtime.macos_process import read_macos_incarnation
from cadrumo.entrypoints.runtime.worker import run

read_fd, write_fd = os.pipe()


def report_and_park(role):
    os.close(read_fd)
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
    incarnation = read_macos_incarnation(os.getpid())
    record = {
        "role": role,
        "pid": os.getpid(),
        "version": incarnation.version,
        "unique_id": incarnation.unique_id,
        "parent_pid": os.getppid(),
        "group": os.getpgid(0),
        "session": os.getsid(0),
        "coalition": read_macos_resource_coalition(os.getpid()),
    }
    encoded = json.dumps(record).encode("ascii") + b"\\n"
    if os.write(write_fd, encoded) != len(encoded):
        os._exit(2)
    os.close(write_fd)
    while True:
        signal.pause()


if os.fork() == 0:
    os.setsid()
    report_and_park("setsid")
if os.fork() == 0:
    os.setpgid(0, 0)
    report_and_park("regrouped")
intermediate = os.fork()
if intermediate == 0:
    os.setsid()
    if os.fork() == 0:
        deadline = time.monotonic() + 5
        while os.getppid() != 1 and time.monotonic() < deadline:
            time.sleep(0.01)
        report_and_park("orphan")
    os._exit(0)
os.waitpid(intermediate, 0)
os.close(write_fd)
records = bytearray()
deadline = time.monotonic() + 10
try:
    while records.count(b"\\n") < 3:
        remaining = deadline - time.monotonic()
        if remaining <= 0 or not select.select((read_fd,), (), (), remaining)[0]:
            raise TimeoutError("resistant descendant startup")
        block = os.read(read_fd, 1024)
        if not block or len(records) + len(block) > 4096:
            raise RuntimeError("resistant descendant startup")
        records.extend(block)
finally:
    os.close(read_fd)
publish("macos-worker-descendants", [json.loads(row) for row in records.splitlines()])
raise SystemExit(run())
""",
        encoding="utf-8",
    )
    return script


def _churn_worker_script(directory: Path) -> Path:
    """Wrap the actual worker with a regrouped process that forks continuously."""
    script = directory / "macos-churn-worker.py"
    script.write_text(
        _INHERITANCE_PRELUDE.format(directory=str(directory))
        + """
import signal
import time

from cadrumo.entrypoints.runtime.worker import run

root = os.fork()
if root == 0:
    os.setsid()
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
    while True:
        link = os.fork()
        if link == 0:
            # Each link orphans one short-lived grandchild and exits at once.
            if os.fork() == 0:
                time.sleep(0.05)
                os._exit(0)
            os._exit(0)
        os.waitpid(link, 0)
        time.sleep(0.002)
publish("macos-worker-descendants", [{"role": "churn", "pid": root}])
raise SystemExit(run())
""",
        encoding="utf-8",
    )
    return script


def _browser_worker_script(directory: Path) -> Path:
    """Launch Playwright's managed Chromium only after the real worker admitted its lease."""
    script = directory / "macos-browser-worker.py"
    script.write_text(
        _INHERITANCE_PRELUDE.format(directory=str(directory))
        + """
import asyncio
import sys
import time

from playwright.async_api import async_playwright

from cadrumo.adapters.local_runtime.runtime_transport_cleanup import RuntimeTransportCleanup
from cadrumo.adapters.local_runtime.macos_coalition import read_macos_resource_coalition
from cadrumo.adapters.local_runtime.macos_process import read_macos_incarnation
from cadrumo.core.async_cleanup import await_cancellation_complete, close_async_resources
from cadrumo.entrypoints.runtime.worker import run


class PlaywrightChromiumMissing(RuntimeError):
    pass


def publish_failure(error):
    publish("macos-worker-browser-failure", {"code": type(error).__name__})


async def actual_worker():
    try:
        code = await asyncio.to_thread(run)
        return code if code == 0 else RuntimeError("actual worker refused startup")
    except BaseException as error:
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
        ready = directory / "macos-worker-ready.json"
        deadline = time.monotonic() + 45
        while not ready.exists():
            worker_owner.require_running()
            if time.monotonic() >= deadline:
                raise TimeoutError("real worker admission witness")
            await asyncio.sleep(0.05)
        worker_owner.require_running()
        admitted = json.loads(ready.read_text(encoding="ascii"))
        pid = os.getpid()
        incarnation = read_macos_incarnation(pid)
        assert admitted["worker_pid"] == pid
        assert read_macos_resource_coalition(pid) == admitted["coalition"]
        marker = (directory / "macos-worker-inheritance.marker").open("xb")
        marker_owner = RuntimeTransportCleanup(marker)
        os.set_inheritable(marker.fileno(), True)
        publish("macos-worker-marker", {"pid": pid, "fd": marker.fileno(), "path": marker.name})
        playwright_owner = PlaywrightOwner()
        await await_cancellation_complete(playwright_owner.start(), task_name="contained-playwright-start")
        playwright = playwright_owner.playwright
        # Only Playwright's own managed Chromium build is acceptable here.
        executable = Path(playwright.chromium.executable_path)
        if not executable.is_file():
            raise PlaywrightChromiumMissing(str(executable))

        async def launch_browser():
            browsers.append(await playwright.chromium.launch(
                executable_path=str(executable),
                headless=True,
                args=["--disable-background-networking"],
            ))

        await await_cancellation_complete(launch_browser(), task_name="contained-browser-launch")
        worker_owner.require_running()
        page = await browsers[0].new_page()
        await page.goto("data:text/html,<title>synthetic containment</title>")
        assert await page.title() == "synthetic containment"
        worker_owner.require_running()
        assert read_macos_incarnation(pid) == incarnation
        publish("macos-worker-browser", {
            "title": await page.title(),
            "executable": str(executable.resolve(strict=True)),
            "worker_pid": pid,
            "worker_version": incarnation.version,
        })
        outcome = await asyncio.shield(worker_owner.task)
        if isinstance(outcome, BaseException):
            worker_owner.observed_error = outcome
            raise outcome
        return outcome
    except BaseException as error:
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


def _publish(directory: Path, name: str, document: object) -> None:
    pending = directory / (name + ".pending")
    pending.write_text(json.dumps(document), encoding="ascii")
    pending.replace(directory / (name + ".json"))


def _publish_scope(directory: Path, worker: ProfileWorkerProcess) -> dict[str, int | str | None]:
    """Publish acquired native identity before private installation can fail."""
    scope = worker._scope
    assert isinstance(scope, MacosProcessScope)
    guardian = scope._guardian
    record: dict[str, int | str | None] = {
        "runtime_pid": os.getpid(),
        "label": scope._label,
        "coalition": scope._coalition,
        "guardian_pid": guardian.pid if guardian is not None else None,
        "worker_pid": scope.worker_pid,
    }
    _publish(directory, "macos-worker-acquired", record)
    return record


@contextmanager
def _registration_barrier(directory: Path) -> Generator[None]:
    """Hold the real launchd acknowledgement before guardian ownership transfers."""
    original = macos_worker_process.run_containment_command_sync

    def register(tool: ContainmentCommand, arguments: tuple[str, ...]) -> ContainmentCommandResult:
        if tool is not ContainmentCommand.LAUNCHCTL or arguments[:1] != ("bootstrap",):
            return original(tool, arguments)
        label = Path(arguments[-1]).name.removesuffix(".plist")
        # Publish the reservation before asking launchd: a lost acknowledgement
        # or later publication failure still has one exact cleanup target.
        record = {"runtime_pid": os.getpid(), "label": label, "coalition": None}
        _publish(directory, "macos-worker-acquired", record)
        result = original(tool, arguments)
        if result.returncode == 0:
            deadline = time.monotonic() + 30
            _publish(directory, "macos-worker-registered", record | {"barrier_deadline": deadline})
            while not (directory / "macos-registration-release").exists():
                if time.monotonic() >= deadline:
                    raise TimeoutError("registration acknowledgement barrier")
                time.sleep(0.05)
        return result

    with pytest.MonkeyPatch.context() as scheduling:
        scheduling.setattr(macos_worker_process, "run_containment_command_sync", register)
        yield


def _reap(directory: Path) -> int:
    """Start one fresh scope on the same storage root; its first launch reaps stale jobs."""
    root = directory / "cadrumo-storage"
    sleeper = directory / "macos-sleeper.py"
    sleeper.write_text("import time\nwhile True:\n    time.sleep(60)\n", encoding="ascii")
    scope = MacosProcessScope(worker_id=uuid4(), storage_root=root, worker_script=sleeper)
    try:
        scope.launch(
            executable=Path(sys.executable),
            arguments=("-I", str(sleeper.resolve(strict=True))),
            directory=root,
            environment=_CLEAN_ENVIRONMENT,
        )
        _publish(directory, "macos-reap-done", {"label": scope._label, "coalition": scope._coalition})
    finally:
        scope.terminate(timeout=10)
    _publish(directory, "macos-reap-closed", {"closed": True})
    return 0


def run(directory: Path, *, mode: str | None = None) -> int:
    """Own one real contained worker until killed, or run one bounded lifecycle mode."""
    if sys.platform != "darwin":
        raise RuntimeError("macOS worker parent fixture requires Darwin")
    if mode == "reap":
        return _reap(directory)
    builders = {
        "browser-descendants": _browser_worker_script,
        "resistant-descendants": _resistant_worker_script,
        "churn-descendants": _churn_worker_script,
    }
    builder = builders.get(mode or "")
    worker_script = builder(directory) if builder is not None else None
    with (
        profile_adapter_composition(),
        bundled_indexed_authority().operation(),
        worker_profiles(directory) as (root, subjects),
    ):
        identity, key = subjects[0]
        worker: ProfileWorkerProcess | None = None
        marker_owner: RuntimeTransportCleanup | None = None
        try:
            if mode in {"browser-descendants", "resistant-descendants"}:
                marker = (directory / "macos-parent-inheritance.marker").open("xb")
                marker_owner = RuntimeTransportCleanup(marker)
                os.set_inheritable(marker.fileno(), True)
                metadata = os.fstat(marker.fileno())
                assert os.get_inheritable(marker.fileno())
                _publish(
                    directory,
                    "macos-parent-marker",
                    {"fd": marker.fileno(), "device": metadata.st_dev, "inode": metadata.st_ino, "path": marker.name},
                )
            try:
                with _registration_barrier(directory) if mode == "registration-loss" else nullcontext():
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
            assert isinstance(scope, MacosProcessScope)
            guardian = scope._guardian
            assert guardian is not None
            record |= {
                "worker_pid": scope.worker_pid,
                "worker_group": os.getpgid(scope.worker_pid),
                "guardian_group": os.getpgid(guardian.pid),
            }
            _publish(directory, "macos-worker-ready", record)
            if mode == "churn-descendants":
                deadline = time.monotonic() + 60
                while not (directory / "macos-close-release").exists():
                    if time.monotonic() >= deadline:
                        raise TimeoutError("churn close release")
                    time.sleep(0.05)
                worker.close(deadline=time.monotonic() + 10)
                _publish(directory, "macos-worker-closed", {"closed": True})
                return 0
            while True:
                time.sleep(1)
        finally:
            asyncio.run(
                close_async_resources(
                    RuntimeTransportCleanup(worker) if worker is not None else None,
                    marker_owner,
                    task_name="macos-contained-parent-worker-close",
                    primary_error=sys.exception(),
                )
            )


if __name__ == "__main__":
    if sys.platform != "darwin" or len(sys.argv) not in {2, 3}:
        raise SystemExit(2)
    if len(sys.argv) == 3 and sys.argv[2] not in MODES:
        raise SystemExit(2)
    try:
        exit_code = run(Path(sys.argv[1]), mode=sys.argv[2] if len(sys.argv) == 3 else None)
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
        (Path(sys.argv[1]) / "macos-worker-failure.json").write_text(
            json.dumps({"code": code, "source_locations": locations}), encoding="ascii"
        )
        raise SystemExit(1) from None
    raise SystemExit(exit_code)
