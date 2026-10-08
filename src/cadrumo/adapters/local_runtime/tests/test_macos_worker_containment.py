"""Native launchd coalition containment of the private worker and every descendant on owner loss.

Preconditions are explicit on Darwin: the user's GUI launchd domain must exist
(a logged-in Aqua session) and browser cases need Playwright's managed Chromium.
A missing precondition fails with its remedy rather than skipping acceptance.
"""

from __future__ import annotations

import asyncio
import json
import os
import signal
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast

import pytest

from cadrumo.application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from cadrumo.core.async_cleanup import close_async_resources
from cadrumo.core.config import Settings
from cadrumo.core.storage_environment import storage_directory
from cadrumo.tests.audited_process import run_audited_process

from ..containment_commands import ContainmentCommand, run_containment_command_sync
from ..macos_coalition import (
    NativeMacosCoalitionPort,
    macos_coalition_members,
    read_macos_resource_coalition,
    terminate_macos_coalition,
)
from ..macos_process import (
    MacosProcessIncarnation,
    MacosSignalDelivery,
    read_macos_incarnation,
    read_macos_process,
    signal_macos_incarnation,
)
from ..macos_worker_process import (
    MacosJobPrint,
    _NativeMacosWorkerHost,
    decode_macos_worker_marker,
    parse_macos_job_print,
)
from .macos_test_process import MacosTestProcess

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_outbound_adapter,
    pytest.mark.skipif(sys.platform != "darwin", reason="requires native macOS launchd coalition containment"),
    pytest.mark.usefixtures("authority_operation"),
]

_CLEAN_ENVIRONMENT = {"PATH": "/usr/bin:/bin", "LANG": "C", "LC_ALL": "C", "PYDANTIC_DISABLE_PLUGINS": "__all__"}
_SENTINEL = "CADRUMO_TEST_RUNTIME_ONLY"
_SERVICE_ABSENT = 113
_SIGKILL = 9


def _send(pid: int, *, stop: bool = False) -> None:
    """Stop or kill one controller-owned test process by PID."""
    if sys.platform == "darwin":
        os.kill(pid, signal.SIGSTOP if stop else signal.SIGKILL)
        return
    raise AssertionError("requires Darwin")


def _uid() -> int:
    if sys.platform == "darwin":
        return os.getuid()
    raise AssertionError("requires Darwin")


def _require_gui_domain() -> None:
    """Fail with the remedy when the user's Aqua launchd domain is unavailable."""
    probe = run_containment_command_sync(ContainmentCommand.LAUNCHCTL, ("print-disabled", f"gui/{_uid()}"))
    if probe.returncode != 0:
        pytest.fail(
            f"macOS containment acceptance needs the launchd GUI domain gui/{_uid()}: log this user in at the "
            "console (an Aqua session) before running it, including over SSH",
            pytrace=False,
        )


def _native_tool(*arguments: str) -> str:
    """Run one fixed read-only macOS inspection tool and return its bounded output."""
    executable = Path(arguments[0])
    if not executable.is_file():
        pytest.fail(f"macOS containment acceptance needs {executable}", pytrace=False)
    if arguments[0] not in {"/bin/ps", "/usr/sbin/lsof"}:
        raise AssertionError("unsupported native inspection tool")
    completed = run_audited_process(
        arguments, capture_output=True, check=False, timeout=None, env={"PATH": "/usr/bin:/bin", "LANG": "C"}
    )
    assert isinstance(completed.stdout, bytes)
    return completed.stdout.decode("utf-8", errors="replace")


def _commands(pids: set[int]) -> dict[int, str]:
    if not pids:
        return {}
    output = _native_tool("/bin/ps", "-o", "pid=,command=", "-p", ",".join(str(pid) for pid in sorted(pids)))
    commands: dict[int, str] = {}
    for row in output.splitlines():
        text = row.strip()
        if not text:
            continue
        pid, _separator, command = text.partition(" ")
        commands[int(pid)] = command.strip()
    return commands


def _open_paths(pids: set[int]) -> set[str]:
    output = _native_tool("/usr/sbin/lsof", "-n", "-P", "-w", "-F", "n", "-p", ",".join(str(pid) for pid in pids))
    return {row[1:] for row in output.splitlines() if row.startswith("n")}


def _process_state(pid: int) -> str:
    return _native_tool("/bin/ps", "-o", "stat=", "-p", str(pid)).strip()


def _members(coalition: int) -> tuple[MacosProcessIncarnation, ...]:
    return macos_coalition_members(coalition, port=NativeMacosCoalitionPort())


def _alive(incarnation: MacosProcessIncarnation) -> bool:
    return read_macos_incarnation(incarnation.pid) == incarnation


def _target(label: str) -> str:
    return f"gui/{_uid()}/{label}"


def _job(label: str) -> MacosJobPrint | None:
    printed = run_containment_command_sync(ContainmentCommand.LAUNCHCTL, ("print", _target(label)))
    if printed.returncode == _SERVICE_ABSENT:
        return None
    assert printed.returncode == 0, "launchctl print failed for the owned job"
    return parse_macos_job_print(printed.output, target=_target(label), label=label)


def _marker_path(label: str) -> Path:
    return Path("/").joinpath("tmp", f"cdr-{_uid()}-launchd-workers", label + ".json")


def _definition_path(label: str) -> Path:
    return _marker_path(label).with_suffix(".plist")


def _read_json(path: Path) -> Any:
    encoded = path.read_bytes()
    assert len(encoded) <= 64 * 1024
    return json.loads(encoded)


@dataclass
class _ContainmentCleanup:
    """Retain this fixture's exact native resources until each release succeeds."""

    parents: list[MacosTestProcess]
    directory: Path
    label: str | None = None
    coalition: int | None = None
    retired: bool = False
    labels: list[str] = field(default_factory=list)

    def record(self, facts: dict[str, Any]) -> None:
        label, coalition = facts.get("label"), facts.get("coalition")
        if not isinstance(label, str) or not label.startswith("com.cadrumo.worker."):
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        if coalition is not None and (type(coalition) is not int or coalition <= 0):
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        if self.label is not None and self.label != label:
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        self.label = label
        self.coalition = coalition if coalition is not None else self.coalition

    def _discover(self) -> None:
        acquired = self.directory / "macos-worker-acquired.json"
        if self.label is None and acquired.exists():
            facts = _read_json(acquired)
            if isinstance(facts, dict):
                self.record(cast(dict[str, Any], facts))

    def _retire(self, label: str, coalition: int | None) -> None:
        job = _job(label)
        if coalition is None and job is not None and job.coalition is not None:
            coalition = job.coalition.coalition_id
        if coalition is not None:
            own = read_macos_resource_coalition(os.getpid())
            assert coalition != own, "fixture cleanup must never target the test's own coalition"
            terminate_macos_coalition(coalition, deadline=time.monotonic() + 10)
        if job is not None:
            run_containment_command_sync(ContainmentCommand.LAUNCHCTL, ("bootout", _target(label)))
            deadline = time.monotonic() + 10
            while _job(label) is not None:
                if time.monotonic() >= deadline:
                    raise RuntimeRefusalError(RuntimeRefusalCode.DEADLINE_EXCEEDED)
                time.sleep(0.05)
        _NativeMacosWorkerHost().remove_marker(label)

    def _release(self) -> None:
        failures: list[BaseException] = []
        for parent in self.parents:
            try:
                if parent.poll() is None:
                    parent.kill()
                parent.wait(timeout=10)
            except ProcessLookupError:
                pass
            except BaseException as error:
                failures.append(error)
        try:
            self._discover()
        except BaseException as error:
            failures.append(error)
        if not self.retired:
            try:
                for label in dict.fromkeys([*([self.label] if self.label else []), *self.labels]):
                    self._retire(label, self.coalition if label == self.label else None)
                self.retired = True
            except BaseException as error:
                failures.append(error)
        if failures:
            raise BaseExceptionGroup("macOS containment fixture cleanup failed", failures)

    async def close(self) -> None:
        """Settle all release attempts under canonical cancellation ownership."""
        await asyncio.to_thread(self._release)


def _launch_parent(tmp_path: Path, *, mode: str | None = None) -> MacosTestProcess:
    # The expendable parent is a development test module excluded from the
    # installed wheel. Only this fixture interpreter gets the source path; the
    # production guardian and worker still launch with isolated Python.
    source_root = Path(__file__).resolve().parents[4]
    return MacosTestProcess(
        (
            sys.executable,
            "-m",
            "cadrumo.entrypoints.runtime.tests.macos_worker_parent_fixture",
            str(tmp_path),
            *((mode,) if mode is not None else ()),
        ),
        cwd=tmp_path,
        env={
            **{name: value for name, value in os.environ.items() if name in Settings.storage_env_var_names()},
            "PATH": "/usr/bin:/bin",
            "LANG": "C",
            "LC_ALL": "C",
            "PYDANTIC_DISABLE_PLUGINS": "__all__",
            "PYTHONPATH": str(source_root),
            "CADRUMO_AUTHORITY_ROOT": os.environ["CADRUMO_AUTHORITY_ROOT"],
            "CADRUMO_LOCAL_STORAGE_ROOT": str(tmp_path / "cadrumo-storage"),
            _SENTINEL: "runtime-environment-must-not-reach-the-worker",
        },
    )


def _failure(directory: Path) -> str:
    failure = directory / "macos-worker-failure.json"
    return failure.read_text(encoding="ascii") if failure.exists() else "no safe diagnostic"


def _assert_browser_not_failed(directory: Path) -> None:
    failure = directory / "macos-worker-browser-failure.json"
    if failure.exists():
        document = _read_json(failure)
        assert isinstance(document, dict) and set(document) == {"code"}
        code = document["code"]
        assert isinstance(code, str) and 0 < len(code) <= 128 and code.isidentifier()
        if code == "PlaywrightChromiumMissing":
            pytest.fail(
                "Playwright-managed Chromium is not installed for this environment; run "
                "`uv run --no-sync playwright install chromium` before macOS browser containment acceptance",
                pytrace=False,
            )
        raise AssertionError("contained post-admission browser failed: " + code)


def _wait_for(path: Path, parent: MacosTestProcess, *, timeout: float, browser: bool = False) -> Any:
    deadline = time.monotonic() + timeout
    while not path.exists():
        if browser:
            _assert_browser_not_failed(path.parent)
        assert parent.poll() is None, f"the macOS runtime owner exited before {path.name}: {_failure(path.parent)}"
        assert time.monotonic() < deadline, f"{path.name} was not published within its bound"
        time.sleep(0.05)
    return _read_json(path)


def _incarnation(pid: int) -> MacosProcessIncarnation:
    incarnation = read_macos_incarnation(pid)
    assert incarnation is not None, f"process {pid} is not alive"
    return incarnation


def _assert_owned_job(facts: dict[str, Any], parent: MacosTestProcess) -> tuple[int, int, int]:
    worker_pid, guardian_pid, coalition = int(facts["worker_pid"]), int(facts["guardian_pid"]), int(facts["coalition"])
    owner = str(_uid())
    assert int(facts["runtime_pid"]) == parent.pid
    own = read_macos_resource_coalition(os.getpid())
    runtime = read_macos_resource_coalition(parent.pid)
    assert coalition not in {own, runtime}, "launchd did not give the job its own resource coalition"
    assert read_macos_resource_coalition(guardian_pid) == coalition
    assert read_macos_resource_coalition(worker_pid) == coalition
    guardian = read_macos_process(guardian_pid, expected_owner=owner)
    worker = read_macos_process(worker_pid, expected_owner=owner)
    assert guardian.parent_pid == 1 and worker.parent_pid == guardian_pid
    # The worker shares the guardian's process group, so launchd's group kill reaches it.
    assert worker.process_group_id == guardian.process_group_id == int(facts["guardian_group"])
    assert int(facts["worker_group"]) == worker.process_group_id
    job = _job(str(facts["label"]))
    assert job is not None and job.state == "running" and job.pid == guardian_pid
    assert job.coalition is not None and job.coalition.coalition_id == coalition
    marker = decode_macos_worker_marker(
        _marker_path(str(facts["label"])).read_bytes(), name=str(facts["label"]) + ".json"
    )
    assert marker.runtime.pid == parent.pid and marker.coalition == coalition
    return worker_pid, guardian_pid, coalition


def _assert_worker_inherited_nothing(directory: Path, worker_pid: int) -> None:
    record = _read_json(directory / "macos-worker-inheritance.json")
    assert record["pid"] == worker_pid
    environment = cast(dict[str, str], record["environment"])
    assert _SENTINEL not in environment
    # Explicit storage routing is part of the launch contract. Darwin may add its locale variable.
    root = directory / "cadrumo-storage"
    expected = _CLEAN_ENVIRONMENT | {
        name: value for name, value in os.environ.items() if name in Settings.storage_env_var_names()
    }
    expected["CADRUMO_LOCAL_STORAGE_ROOT"] = str(root)
    temporary_root = storage_directory("CADRUMO_TEMP_DIR", "tmp", root=root)
    expected.update({name: str(temporary_root) for name in ("TEMP", "TMP", "TMPDIR")})
    expected["CADRUMO_AUTHORITY_ROOT"] = os.environ["CADRUMO_AUTHORITY_ROOT"]
    assert {name: value for name, value in environment.items() if name != "__CF_USER_TEXT_ENCODING"} == expected
    marker = _read_json(directory / "macos-parent-marker.json")
    identities = {(int(device), int(inode)) for _fd, device, inode in record["descriptors"]}
    assert (int(marker["device"]), int(marker["inode"])) not in identities


def _wait_retired(coalition: int, incarnations: list[MacosProcessIncarnation], *, timeout: float = 10) -> None:
    deadline = time.monotonic() + timeout
    while _members(coalition) or any(_alive(incarnation) for incarnation in incarnations):
        assert time.monotonic() < deadline, "the private worker coalition survived owner loss"
        time.sleep(0.05)


def _resistant_descendants(directory: Path, coalition: int, guardian_group: int) -> list[MacosProcessIncarnation]:
    records = _read_json(directory / "macos-worker-descendants.json")
    assert isinstance(records, list) and {record["role"] for record in records} == {"setsid", "regrouped", "orphan"}
    incarnations: list[MacosProcessIncarnation] = []
    for record in records:
        incarnation = MacosProcessIncarnation(
            pid=int(record["pid"]), version=int(record["version"]), unique_id=int(record["unique_id"])
        )
        assert _alive(incarnation)
        assert record["coalition"] == coalition == read_macos_resource_coalition(incarnation.pid)
        assert record["group"] != guardian_group
        if record["role"] == "setsid":
            assert record["session"] == record["pid"] == record["group"]
        elif record["role"] == "regrouped":
            assert record["group"] == record["pid"] != record["session"]
        else:
            # Orphaned to launchd inside its exited intermediate's new session.
            assert record["parent_pid"] == 1 and record["group"] == record["session"] != record["pid"]
        incarnations.append(incarnation)
    return incarnations


def _browser_descendants(
    directory: Path, parent: MacosTestProcess, coalition: int, worker_pid: int, guardian_pid: int
) -> list[MacosProcessIncarnation]:
    browser = _wait_for(directory / "macos-worker-browser.json", parent, timeout=60, browser=True)
    assert browser["title"] == "synthetic containment" and browser["worker_pid"] == worker_pid
    assert browser["worker_version"] == _incarnation(worker_pid).version
    executable = Path(browser["executable"])
    bundle = next((path for path in (executable, *executable.parents) if path.suffix == ".app"), executable.parent)
    members = {member.pid: member for member in _members(coalition)}
    commands = _commands(set(members) - {worker_pid, guardian_pid})
    roles: set[str] = set()
    for pid, command in commands.items():
        if command.startswith(str(executable)) and "--remote-debugging-pipe" in command and "--type=" not in command:
            roles.add("browser")
        elif command.startswith(str(bundle)) and "--type=renderer" in command:
            roles.add("renderer")
        assert read_macos_resource_coalition(pid) == coalition
    assert roles == {"browser", "renderer"}, "the admitted worker's Chromium did not run inside the coalition"
    parent_marker = str(_read_json(directory / "macos-parent-marker.json")["path"])
    worker_marker = str(_read_json(directory / "macos-worker-marker.json")["path"])
    inherited = _open_paths(set(members) - {worker_pid})
    assert parent_marker not in inherited and worker_marker not in inherited
    return list(members.values())


@pytest.mark.parametrize(
    ("failed_owner", "descendants"),
    [
        pytest.param("runtime_parent", None, id="runtime_parent"),
        pytest.param("guardian", None, id="guardian"),
        pytest.param("runtime_parent", "resistant", id="runtime_parent-resistant"),
        pytest.param("guardian", "resistant", id="guardian-resistant"),
        pytest.param("runtime_parent", "browser", id="runtime_parent-browser"),
        pytest.param("guardian", "browser", id="guardian-browser"),
        pytest.param("worker", "browser", id="worker-browser"),
    ],
)
def test_macos_worker_coalition_retires_independent_groups_on_owner_loss(
    tmp_path: Path, failed_owner: str, descendants: str | None
) -> None:
    _require_gui_domain()
    mode = {"resistant": "resistant-descendants", "browser": "browser-descendants"}.get(descendants or "")
    parent = _launch_parent(tmp_path, mode=mode)
    cleanup = _ContainmentCleanup([parent], tmp_path)
    primary: BaseException | None = None
    try:
        facts = cast(
            dict[str, Any],
            _wait_for(tmp_path / "macos-worker-ready.json", parent, timeout=90, browser=descendants == "browser"),
        )
        cleanup.record(facts)
        worker_pid, guardian_pid, coalition = _assert_owned_job(facts, parent)
        watched = [_incarnation(worker_pid), _incarnation(guardian_pid)]
        if descendants is not None:
            _assert_worker_inherited_nothing(tmp_path, worker_pid)
            assert str(_read_json(tmp_path / "macos-parent-marker.json")["path"]) not in _open_paths({guardian_pid})
        if descendants == "resistant":
            watched += _resistant_descendants(tmp_path, coalition, int(facts["guardian_group"]))
        elif descendants == "browser":
            watched += _browser_descendants(tmp_path, parent, coalition, worker_pid, guardian_pid)
        assert all(_alive(incarnation) for incarnation in watched)
        if failed_owner == "runtime_parent":
            _send(parent.pid)
        elif failed_owner == "guardian":
            assert signal_macos_incarnation(watched[1], _SIGKILL) is MacosSignalDelivery.DELIVERED
        else:
            assert signal_macos_incarnation(watched[0], _SIGKILL) is MacosSignalDelivery.DELIVERED
        _wait_retired(coalition, watched)
        if failed_owner != "runtime_parent":
            assert parent.poll() is None, "guardian or worker loss must not take the runtime down"
    except BaseException as error:
        primary = error
        raise
    finally:
        asyncio.run(close_async_resources(cleanup, task_name="macos-containment-fixture-close", primary_error=primary))


def test_macos_worker_owner_loss_during_registration(tmp_path: Path) -> None:
    """Lose the owner after launchd registered the job, before launch received its acknowledgement."""
    _require_gui_domain()
    parent = _launch_parent(tmp_path, mode="registration-loss")
    cleanup = _ContainmentCleanup([parent], tmp_path)
    primary: BaseException | None = None
    try:
        record = cast(dict[str, Any], _wait_for(tmp_path / "macos-worker-registered.json", parent, timeout=90))
        cleanup.record(record)
        label = str(record["label"])
        barrier_deadline = record["barrier_deadline"]
        assert record["runtime_pid"] == parent.pid and not (tmp_path / "macos-worker-ready.json").exists()
        marker = decode_macos_worker_marker(_marker_path(label).read_bytes(), name=label + ".json")
        assert marker.runtime.pid == parent.pid and marker.coalition is None
        deadline = time.monotonic() + 10
        while True:
            job = _job(label)
            if job is not None and job.state == "running" and job.pid is not None and job.coalition is not None:
                break
            assert parent.poll() is None and time.monotonic() < deadline, "registered guardian did not start"
            time.sleep(0.05)
        coalition = job.coalition.coalition_id
        guardian_pid = job.pid
        cleanup.record({"label": label, "coalition": coalition})
        deadline = time.monotonic() + 30
        while True:
            members = {member.pid: member for member in _members(coalition)}
            workers = [
                pid
                for pid, command in _commands(set(members) - {guardian_pid}).items()
                if "-I -B -m cadrumo.entrypoints.runtime.worker" in command
            ]
            if workers:
                (worker_pid,) = workers
                break
            assert parent.poll() is None and read_macos_incarnation(guardian_pid) is not None
            assert time.monotonic() < deadline, "registered guardian did not launch the real installed worker"
            time.sleep(0.05)
        # The guardian already executed Python to launch the worker, so its
        # incarnation is final; the job's env stage had a different one.
        guardian = _incarnation(guardian_pid)
        guardian_command = _commands({guardian_pid})[guardian_pid]
        assert "-I -m cadrumo.entrypoints.runtime.macos_worker_guardian" in guardian_command
        assert f"--parent-pid {parent.pid} " in guardian_command
        worker = members[worker_pid]
        assert read_macos_process(worker_pid, expected_owner=str(_uid())).parent_pid == guardian_pid
        assert barrier_deadline - time.monotonic() >= 5, "registration barrier expired before owner loss"
        _send(parent.pid)
        assert time.monotonic() < barrier_deadline, "owner-loss signal was issued after barrier expiry"
        _wait_retired(coalition, [guardian, worker])
        # Lost inside launchctl bootstrap, the owner never deleted its job
        # definition; a later runtime of the same storage root retires it.
        assert _marker_path(label).exists() and _definition_path(label).exists()
        successor = _launch_parent(tmp_path, mode="reap")
        cleanup.parents.append(successor)
        reaped = _wait_for(tmp_path / "macos-reap-done.json", successor, timeout=60)
        cleanup.labels.append(str(reaped["label"]))
        assert reaped["label"] != label
        assert _job(label) is None and not _marker_path(label).exists() and not _definition_path(label).exists()
        assert successor.wait(timeout=30) == 0, _failure(tmp_path)
    except BaseException as error:
        primary = error
        raise
    finally:
        asyncio.run(close_async_resources(cleanup, task_name="macos-registration-fixture-close", primary_error=primary))


def test_macos_worker_terminate_converges_under_fork_churn(tmp_path: Path) -> None:
    """Runtime-driven retirement empties a coalition whose regrouped member forks continuously."""
    _require_gui_domain()
    parent = _launch_parent(tmp_path, mode="churn-descendants")
    cleanup = _ContainmentCleanup([parent], tmp_path)
    primary: BaseException | None = None
    try:
        facts = cast(dict[str, Any], _wait_for(tmp_path / "macos-worker-ready.json", parent, timeout=90))
        cleanup.record(facts)
        worker_pid, guardian_pid, coalition = _assert_owned_job(facts, parent)
        (churn,) = _read_json(tmp_path / "macos-worker-descendants.json")
        root = _incarnation(int(churn["pid"]))
        assert read_macos_resource_coalition(root.pid) == coalition
        watched = [_incarnation(worker_pid), _incarnation(guardian_pid), root]
        assert len(_members(coalition)) >= 3
        (tmp_path / "macos-close-release").touch()
        closed = _wait_for(tmp_path / "macos-worker-closed.json", parent, timeout=30)
        assert closed == {"closed": True}
        assert parent.wait(timeout=30) == 0, _failure(tmp_path)
        assert not _members(coalition) and not any(_alive(incarnation) for incarnation in watched)
        label = str(facts["label"])
        assert _job(label) is None and not _marker_path(label).exists()
        cleanup.retired = True
    except BaseException as error:
        primary = error
        raise
    finally:
        asyncio.run(close_async_resources(cleanup, task_name="macos-churn-fixture-close", primary_error=primary))


def test_macos_stale_job_is_reaped_after_simultaneous_runtime_and_guardian_loss(tmp_path: Path) -> None:
    """A later runtime of the same storage root retires a job whose runtime and guardian died together."""
    _require_gui_domain()
    parent = _launch_parent(tmp_path, mode="resistant-descendants")
    cleanup = _ContainmentCleanup([parent], tmp_path)
    primary: BaseException | None = None
    try:
        facts = cast(dict[str, Any], _wait_for(tmp_path / "macos-worker-ready.json", parent, timeout=90))
        cleanup.record(facts)
        worker_pid, guardian_pid, coalition = _assert_owned_job(facts, parent)
        independent = _resistant_descendants(tmp_path, coalition, int(facts["guardian_group"]))
        guardian = _incarnation(guardian_pid)
        # Stop both owners first so neither can react to the other's loss.
        _send(parent.pid, stop=True)
        _send(guardian.pid, stop=True)
        deadline = time.monotonic() + 5
        while not all("T" in _process_state(pid) for pid in (parent.pid, guardian.pid)):
            assert time.monotonic() < deadline, "owners did not stop"
            time.sleep(0.02)
        assert signal_macos_incarnation(guardian, _SIGKILL) is MacosSignalDelivery.DELIVERED
        _send(parent.pid)
        parent.wait(timeout=10)
        deadline = time.monotonic() + 10
        while _alive(guardian) or read_macos_incarnation(worker_pid) is not None:
            assert time.monotonic() < deadline, "launchd did not retire the guardian's own process group"
            time.sleep(0.05)
        # Independent groups survive both owners until a later runtime reaps them.
        assert all(_alive(incarnation) for incarnation in independent)
        assert {incarnation.pid for incarnation in independent} <= {member.pid for member in _members(coalition)}
        label = str(facts["label"])
        stale = _job(label)
        assert stale is not None and stale.coalition is not None and stale.coalition.coalition_id == coalition
        assert _marker_path(label).exists()
        successor = _launch_parent(tmp_path, mode="reap")
        cleanup.parents.append(successor)
        reaped = _wait_for(tmp_path / "macos-reap-done.json", successor, timeout=60)
        cleanup.labels.append(str(reaped["label"]))
        assert reaped["label"] != label
        assert not _members(coalition) and not any(_alive(incarnation) for incarnation in independent)
        assert _job(label) is None and not _marker_path(label).exists()
        assert successor.wait(timeout=30) == 0, _failure(tmp_path)
        assert _read_json(tmp_path / "macos-reap-closed.json") == {"closed": True}
        assert _job(str(reaped["label"])) is None and not _marker_path(str(reaped["label"])).exists()
    except BaseException as error:
        primary = error
        raise
    finally:
        asyncio.run(close_async_resources(cleanup, task_name="macos-reap-fixture-close", primary_error=primary))
