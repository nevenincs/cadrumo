"""Portable launchd job, print, marker and scope-lifecycle contracts through a synthetic native host."""

from __future__ import annotations

import json
import os
import plistlib
import stat
import sys
import time
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from threading import Event
from types import SimpleNamespace
from typing import cast
from uuid import UUID, uuid4

import pytest

from cadrumo.application.runtime.contracts import RuntimePeer, RuntimeRefusalCode, RuntimeRefusalError
from cadrumo.core import descriptor_write

from .. import macos_worker_process
from ..containment_commands import ContainmentCommandResult
from ..macos_login import MacosPeerAuditToken
from ..macos_process import MacosProcessIncarnation, MacosProcessObservation
from ..macos_worker_process import (
    MacosJobCoalition,
    MacosProcessScope,
    MacosWorkerMarker,
    decode_macos_worker_marker,
    encode_macos_worker_marker,
    macos_worker_job_definition,
    macos_worker_label,
    macos_worker_scope_key,
    parse_macos_job_print,
    stale_macos_worker_markers,
)
from ..posix_channel import PosixRuntimeChannel

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

_UID = 501
_DEFAULT = ("-I", "-m", "cadrumo.entrypoints.runtime.worker")
_ENVIRONMENT = {"PATH": "/usr/bin:/bin", "LANG": "C", "LC_ALL": "C", "PYDANTIC_DISABLE_PLUGINS": "__all__"}
_RUNTIME = MacosProcessIncarnation(pid=os.getpid(), version=11, unique_id=1011)
_RUNTIME_COALITION = 5000
_JOB_COALITION = 7000
_GUARDIAN = MacosProcessIncarnation(pid=900, version=21, unique_id=2021)
_WORKER = MacosProcessIncarnation(pid=901, version=31, unique_id=3031)
_SCOPE = "0123456789abcdef"
_OTHER_SCOPE = "fedcba9876543210"


def _label(scope: str = _SCOPE, worker_id: UUID | None = None) -> str:
    return macos_worker_label(scope_key=scope, worker_id=worker_id or uuid4())


def _printed(target: str, label: str, *, pid: int | None, coalition: int | None, state: str | None = None) -> str:
    running = pid is not None
    lines = [
        f"{target} = {{",
        "\tactive count = " + ("1" if running else "0"),
        "\tpath = (submitted by launchctl)",
        "\ttype = LaunchAgent",
        "\tstate = " + (state or ("running" if running else "not running")),
        "",
        "\tprogram = /usr/bin/env",
        "\targuments = {",
        "\t\t/usr/bin/env",
        "\t\t-i",
        "\t\tPATH=/usr/bin:/bin",
        "\t}",
        "",
        "\tdefault environment = {",
        "\t\tPATH => /usr/bin:/bin:/usr/sbin:/sbin",
        "\t}",
        "",
        "\tdomain = gui/501 [100009]",
        "\tasid = 100009",
        "\tminimum runtime = 10",
        "\texit timeout = 1",
        "\truns = 1",
    ]
    if running:
        lines.append(f"\tpid = {pid}")
    lines += ["\timmediate reason = speculative", "\tforks = 2", "\texecs = 1"]
    if coalition is not None:
        lines += [
            "",
            "\tresource coalition = {",
            f"\t\tID = {coalition}",
            "\t\ttype = resource",
            "\t\tstate = active",
            "\t\tactive count = " + ("1" if running else "0"),
            f"\t\tname = {label}",
            "\t}",
            "",
            "\tjetsam coalition = {",
            f"\t\tID = {coalition + 1}",
            "\t\ttype = jetsam",
            "\t\tstate = active",
            "\t\tactive count = 1",
            f"\t\tname = {label}",
            "\t}",
        ]
    lines += ["", "\tspawn type = interactive (4)", "\tproperties = runatload | inferred program", "}"]
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------- pure contracts


def test_job_definition_runs_the_guardian_through_a_clean_environment_in_aqua(tmp_path: Path) -> None:
    label = _label()
    script = tmp_path / "worker.py"
    interpreter = tmp_path / "bin" / "python3"
    payload = macos_worker_job_definition(
        label=label,
        executable=interpreter,
        directory=tmp_path,
        parent=_RUNTIME,
        worker_arguments=("-I", "/private/var/worker.py", "--worker-id", "w"),
        worker_script=script,
    )
    definition = plistlib.loads(payload)
    assert definition == {
        "Label": label,
        "ProgramArguments": [
            "/usr/bin/env",
            "-i",
            "PATH=/usr/bin:/bin",
            "LANG=C",
            "LC_ALL=C",
            "PYDANTIC_DISABLE_PLUGINS=__all__",
            str(interpreter),
            "-I",
            "-m",
            "cadrumo.entrypoints.runtime.macos_worker_guardian",
            "--parent-pid",
            str(_RUNTIME.pid),
            "--parent-version",
            "11",
            "--worker-script",
            str(script),
            "--",
            "-I",
            "/private/var/worker.py",
            "--worker-id",
            "w",
        ],
        "EnvironmentVariables": _ENVIRONMENT,
        "WorkingDirectory": str(tmp_path),
        "StandardOutPath": "/dev/null",
        "StandardErrorPath": "/dev/null",
        "RunAtLoad": True,
        "KeepAlive": False,
        "AbandonProcessGroup": False,
        "LimitLoadToSessionType": "Aqua",
        "ExitTimeOut": 1,
        "Umask": 0o077,
    }


@pytest.mark.parametrize("invalid", ["label", "relative", "null"])
def test_job_definition_refuses_unscoped_label_relative_paths_and_nul(invalid: str, tmp_path: Path) -> None:
    with pytest.raises(RuntimeRefusalError) as caught:
        macos_worker_job_definition(
            label="com.cadrumo.worker.other" if invalid == "label" else _label(),
            executable=Path("python3") if invalid == "relative" else tmp_path / "python3",
            directory=tmp_path,
            parent=_RUNTIME,
            worker_arguments=("-I", "/w.py", "bad\0argument" if invalid == "null" else "ok"),
            worker_script=None,
        )
    assert caught.value.reason is RuntimeRefusalCode.CONTAINMENT_UNAVAILABLE


def test_labels_are_unguessable_and_bound_to_one_canonical_storage_root(tmp_path: Path) -> None:
    root = tmp_path / "storage"
    root.mkdir()
    alias = tmp_path / "storage" / ".." / "storage"
    key = macos_worker_scope_key(root)
    assert key == macos_worker_scope_key(alias)
    other = tmp_path / "other"
    other.mkdir()
    assert macos_worker_scope_key(other) != key
    worker_id = uuid4()
    assert macos_worker_label(scope_key=key, worker_id=worker_id) == f"com.cadrumo.worker.{key}.{worker_id.hex}"
    with pytest.raises(RuntimeRefusalError):
        macos_worker_scope_key(tmp_path / "missing")
    with pytest.raises(RuntimeRefusalError):
        macos_worker_label(scope_key="../escape", worker_id=worker_id)


def test_print_parser_reads_running_job_and_its_resource_coalition() -> None:
    label = _label()
    target = f"gui/{_UID}/{label}"
    job = parse_macos_job_print(_printed(target, label, pid=94587, coalition=1056028), target=target, label=label)
    assert job.state == "running" and job.pid == 94587
    assert job.coalition == MacosJobCoalition(coalition_id=1056028, state="active", active_count=1)
    stopped = parse_macos_job_print(_printed(target, label, pid=None, coalition=1056028), target=target, label=label)
    assert stopped.state == "not running" and stopped.pid is None and stopped.coalition is not None
    unspawned = parse_macos_job_print(_printed(target, label, pid=None, coalition=None), target=target, label=label)
    assert unspawned.coalition is None


def test_print_parser_keeps_unrelated_nested_blocks_opaque() -> None:
    label = _label()
    target = f"gui/{_UID}/{label}"
    text = _printed(target, label, pid=7, coalition=9).replace(
        "\tspawn type", '\tendpoints = {\n\t\t"com.example" = {\n\t\t\tport = 0x1\n\t\t}\n\t}\n\tspawn type'
    )
    assert parse_macos_job_print(text, target=target, label=label).coalition is not None


def _mutated(kind: str, target: str, label: str) -> str:
    text = _printed(target, label, pid=94587, coalition=1056028)
    replacements = {
        "target": (target + " = {", f"gui/{_UID}/com.cadrumo.worker.other = {{"),
        "duplicate": ("\ttype = LaunchAgent\n", "\ttype = LaunchAgent\n\tstate = running\n"),
        "unknown-coalition-field": ("\t\ttype = resource\n", "\t\ttype = resource\n\t\tflags = 1\n"),
        "missing-coalition-field": ("\t\tactive count = 1\n\t\tname", "\t\tname"),
        "foreign-name": (f"\t\tname = {label}\n\t}}\n\n\tjetsam", "\t\tname = com.example\n\t}\n\n\tjetsam"),
        "jetsam-type": ("\t\ttype = resource\n", "\t\ttype = jetsam\n"),
        "unterminated": ("\t}\n\n\tspawn type", "\n\tspawn type"),
        "non-ascii-pid": ("\tpid = 94587\n", "\tpid = Ã™Â©Ã™Â¤\n"),
        "control": ("\tforks = 2\n", "\tforks = \x1b2\n"),
        "orphan-member": ("\tforks = 2\n", "\t\tforks = 2\n"),
        "missing-state": ("\tstate = running\n", ""),
        "zero-coalition": ("\t\tID = 1056028\n", "\t\tID = 0\n"),
    }
    old, new = replacements[kind]
    assert text.count(old) >= 1
    return text.replace(old, new, 1)


@pytest.mark.parametrize(
    "kind",
    [
        "target",
        "duplicate",
        "unknown-coalition-field",
        "missing-coalition-field",
        "foreign-name",
        "jetsam-type",
        "unterminated",
        "non-ascii-pid",
        "control",
        "orphan-member",
        "missing-state",
        "zero-coalition",
    ],
)
def test_print_parser_refuses_unknown_duplicate_or_missing_shape(kind: str) -> None:
    label = _label()
    target = f"gui/{_UID}/{label}"
    with pytest.raises(RuntimeRefusalError) as caught:
        parse_macos_job_print(_mutated(kind, target, label), target=target, label=label)
    assert caught.value.reason is RuntimeRefusalCode.CONTAINMENT_UNAVAILABLE


def test_marker_round_trips_only_in_its_canonical_form() -> None:
    marker = MacosWorkerMarker(label=_label(), runtime=_RUNTIME, coalition=None)
    payload = encode_macos_worker_marker(marker)
    assert decode_macos_worker_marker(payload, name=marker.label + ".json") == marker
    known = MacosWorkerMarker(label=marker.label, runtime=_RUNTIME, coalition=_JOB_COALITION)
    assert decode_macos_worker_marker(encode_macos_worker_marker(known), name=marker.label + ".json") == known
    document = json.loads(payload)
    for variant in (
        json.dumps(document, sort_keys=True).encode("ascii"),
        json.dumps(document | {"extra": 1}, sort_keys=True, separators=(",", ":")).encode("ascii"),
        json.dumps(document | {"runtime_pid": True}, sort_keys=True, separators=(",", ":")).encode("ascii"),
        json.dumps(document | {"coalition": -4}, sort_keys=True, separators=(",", ":")).encode("ascii"),
        json.dumps(document | {"runtime_version": 0}, sort_keys=True, separators=(",", ":")).encode("ascii"),
        b"[]",
        b"\xff",
    ):
        with pytest.raises(RuntimeRefusalError):
            decode_macos_worker_marker(variant, name=marker.label + ".json")
    with pytest.raises(RuntimeRefusalError):
        decode_macos_worker_marker(payload, name=_label() + ".json")


def test_stale_selection_reaps_only_dead_runtimes_of_this_storage_scope() -> None:
    dead = MacosProcessIncarnation(pid=4242, version=3, unique_id=4243)
    reused = MacosProcessIncarnation(pid=4343, version=9, unique_id=4344)
    stale = MacosWorkerMarker(label=_label(), runtime=dead, coalition=8100)
    replaced = MacosWorkerMarker(label=_label(), runtime=reused, coalition=None)
    live = MacosWorkerMarker(label=_label(), runtime=_RUNTIME, coalition=_JOB_COALITION)
    foreign_name = _label(_OTHER_SCOPE) + ".json"
    entries = {
        stale.label + ".json": encode_macos_worker_marker(stale),
        replaced.label + ".json": encode_macos_worker_marker(replaced),
        live.label + ".json": encode_macos_worker_marker(live),
        # Another storage scope's entry is never decoded, even when corrupt.
        foreign_name: b"not a marker",
        stale.label + ".pending": b"partial",
    }
    current = {_RUNTIME.pid: _RUNTIME, reused.pid: MacosProcessIncarnation(pid=4343, version=10, unique_id=4345)}
    selected = stale_macos_worker_markers(
        entries, scope_key=_SCOPE, live=lambda runtime: current.get(runtime.pid) == runtime
    )
    assert set(selected) == {stale, replaced}
    entries[_label() + ".json"] = b"{}"
    with pytest.raises(RuntimeRefusalError):
        stale_macos_worker_markers(entries, scope_key=_SCOPE, live=lambda _runtime: False)


# ---------------------------------------------------------------- scope lifecycle


@dataclass
class _Process:
    incarnation: MacosProcessIncarnation
    coalition: int
    parent_pid: int
    exited: Event = field(default_factory=Event)


class _Watch:
    def __init__(self, process: _Process) -> None:
        self.process = process
        self.closed = False

    @property
    def exited(self) -> bool:
        return self.process.exited.is_set()

    def wait(self, *, timeout: float) -> bool:
        assert 0 <= timeout <= 60
        return self.process.exited.wait(timeout)

    def close(self) -> None:
        self.closed = True


@dataclass
class _Job:
    pid: int | None
    coalition: int | None


class _Host:
    """Synthetic launchd, kernel and marker directory recording every native step."""

    def __init__(self) -> None:
        self.events: list[tuple[object, ...]] = []
        self.store: dict[str, bytes] = {}
        self.processes: dict[int, _Process] = {_RUNTIME.pid: _Process(_RUNTIME, _RUNTIME_COALITION, 1)}
        self.jobs: dict[str, _Job] = {}
        self.job_coalition = _JOB_COALITION
        self.guardian_parent = 1
        self.bootstrap_code = 0
        self.bootout_codes: list[int] = []
        self.termination_failures: list[RuntimeRefusalError] = []
        self.watches: list[_Watch] = []
        self.definition: dict[str, object] = {}

    def owner_uid(self) -> int:
        return _UID

    def launchctl(self, arguments: tuple[str, ...]) -> ContainmentCommandResult:
        self.events.append(("launchctl", *arguments))
        action, target = arguments
        label = target.rsplit("/", 1)[1]
        job = self.jobs.get(label)
        if action == "print":
            if job is None:
                return ContainmentCommandResult(113, "")
            pid = job.pid if job.pid is not None and not self.processes[job.pid].exited.is_set() else None
            return ContainmentCommandResult(0, _printed(target, label, pid=pid, coalition=job.coalition))
        assert action == "bootout"
        code = self.bootout_codes.pop(0) if self.bootout_codes else (0 if job is not None else 3)
        if code == 0:
            self.jobs.pop(label, None)
        return ContainmentCommandResult(code, "")

    def bootstrap(self, label: str, definition: bytes) -> ContainmentCommandResult:
        self.events.append(("bootstrap", label))
        self.definition = plistlib.loads(definition)
        if self.bootstrap_code == 0:
            self.processes[_GUARDIAN.pid] = _Process(_GUARDIAN, self.job_coalition, self.guardian_parent)
            self.jobs[label] = _Job(pid=_GUARDIAN.pid, coalition=self.job_coalition)
        return ContainmentCommandResult(self.bootstrap_code, "")

    def _live(self, pid: int) -> _Process | None:
        process = self.processes.get(pid)
        return None if process is None or process.exited.is_set() else process

    def incarnation(self, pid: int) -> MacosProcessIncarnation | None:
        process = self._live(pid)
        return process.incarnation if process is not None else None

    def coalition(self, pid: int) -> int | None:
        process = self._live(pid)
        return process.coalition if process is not None else None

    def observe(self, pid: int) -> MacosProcessObservation:
        process = self._live(pid)
        if process is None:
            raise RuntimeRefusalError(RuntimeRefusalCode.PEER_UNTRUSTED)
        return MacosProcessObservation(
            pid=pid,
            os_owner_id=str(_UID),
            parent_pid=process.parent_pid,
            process_group_id=_GUARDIAN.pid,
            started_seconds=1,
            started_microseconds=0,
        )

    def watch(self, observation: MacosProcessObservation) -> _Watch:
        watch = _Watch(self.processes[observation.pid])
        self.watches.append(watch)
        return watch

    def terminate_coalition(self, coalition: int, *, deadline: float) -> None:
        assert deadline > 0
        self.events.append(("terminate", coalition))
        if self.termination_failures:
            raise self.termination_failures.pop(0)
        for process in self.processes.values():
            if process.coalition == coalition:
                process.exited.set()

    def markers(self, prefix: str) -> dict[str, bytes]:
        return {name: payload for name, payload in self.store.items() if name.startswith(prefix)}

    def publish_marker(self, label: str, payload: bytes) -> None:
        self.events.append(("publish", label))
        self.store[label + ".json"] = payload

    def remove_marker(self, label: str) -> None:
        self.events.append(("remove", label))
        self.store.pop(label + ".json", None)

    def add_worker(self, *, coalition: int = _JOB_COALITION, parent_pid: int = _GUARDIAN.pid) -> None:
        self.processes[_WORKER.pid] = _Process(_WORKER, coalition, parent_pid)


@dataclass
class _Channel:
    """Kernel-verified peer facts of an accepted worker connection."""

    peer: RuntimePeer
    token: MacosPeerAuditToken

    def capture_peer_audit_token(self) -> MacosPeerAuditToken:
        return self.token


def _channel(*, version: int = _WORKER.version, owner: str = str(_UID)) -> PosixRuntimeChannel:
    token = MacosPeerAuditToken(_UID, _UID, _UID, _WORKER.pid, 100009, version)
    return cast(PosixRuntimeChannel, _Channel(RuntimePeer(os_owner_id=owner, process_id=_WORKER.pid), token))


@pytest.fixture
def host(monkeypatch: pytest.MonkeyPatch) -> _Host:
    monkeypatch.setattr(macos_worker_process, "sys", SimpleNamespace(platform="darwin"))
    return _Host()


@pytest.fixture
def scope(host: _Host, tmp_path: Path) -> Iterator[MacosProcessScope]:
    owned = MacosProcessScope(worker_id=uuid4(), storage_root=tmp_path, host=host)
    try:
        yield owned
    finally:
        if owned._started:
            owned.terminate(timeout=5)


def _launch(scope: MacosProcessScope, tmp_path: Path) -> macos_worker_process.MacosOwnedProcess:
    return scope.launch(
        executable=Path(sys.executable), arguments=_DEFAULT, directory=tmp_path, environment=_ENVIRONMENT
    )


def test_marker_and_stop_obligation_precede_an_unacknowledged_registration(
    host: _Host, scope: MacosProcessScope, tmp_path: Path
) -> None:
    host.bootstrap_code = 5
    with pytest.raises(RuntimeRefusalError) as caught:
        _launch(scope, tmp_path)
    assert caught.value.reason is RuntimeRefusalCode.CONTAINMENT_UNAVAILABLE
    label = scope._label
    assert host.events.index(("publish", label)) < host.events.index(("bootstrap", label))
    assert scope._started
    assert decode_macos_worker_marker(host.store[label + ".json"], name=label + ".json") == MacosWorkerMarker(
        label=label, runtime=_RUNTIME, coalition=None
    )
    scope.terminate(timeout=2)
    assert not scope._started and host.store == {}


def test_admitted_guardian_runs_in_a_fresh_launchd_coalition(
    host: _Host, scope: MacosProcessScope, tmp_path: Path
) -> None:
    guardian = _launch(scope, tmp_path)
    assert guardian.pid == _GUARDIAN.pid and guardian.alive
    arguments = host.definition["ProgramArguments"]
    assert isinstance(arguments, list)
    assert arguments[:2] == ["/usr/bin/env", "-i"] and arguments[-3:] == list(_DEFAULT)
    marker = decode_macos_worker_marker(host.store[scope._label + ".json"], name=scope._label + ".json")
    assert marker.coalition == _JOB_COALITION
    scope.terminate(timeout=2)
    assert not guardian.alive and all(watch.closed for watch in host.watches)
    assert ("launchctl", "bootout", f"gui/{_UID}/{scope._label}") in host.events
    assert host.store == {} and not host.jobs


@pytest.mark.parametrize("defect", ["runtime-coalition", "not-launchd-child"])
def test_guardian_outside_a_fresh_launchd_coalition_refuses(
    host: _Host, scope: MacosProcessScope, tmp_path: Path, defect: str
) -> None:
    if defect == "runtime-coalition":
        host.job_coalition = _RUNTIME_COALITION
    else:
        host.guardian_parent = 4242
    with pytest.raises(RuntimeRefusalError) as caught:
        _launch(scope, tmp_path)
    assert caught.value.reason is RuntimeRefusalCode.CONTAINMENT_UNAVAILABLE
    if defect == "runtime-coalition":
        # Retirement never kills the coalition the runtime itself belongs to.
        with pytest.raises(RuntimeRefusalError):
            scope.terminate(timeout=1)
        assert ("terminate", _RUNTIME_COALITION) not in host.events
        host.jobs.clear()
        scope._started = False
    else:
        scope.terminate(timeout=2)
        assert ("terminate", _JOB_COALITION) in host.events and host.store == {}


def test_worker_admission_binds_the_exact_peer_incarnation(
    host: _Host, scope: MacosProcessScope, tmp_path: Path
) -> None:
    _launch(scope, tmp_path)
    host.add_worker()
    assert scope.verify_worker(_channel(), owner_id=str(_UID)) == _WORKER.pid
    assert scope.verify_worker(_channel(), owner_id=str(_UID)) == _WORKER.pid
    assert scope.owns_process(_WORKER.pid) and scope.active_process_ids() == (_WORKER.pid,)
    assert scope.worker_pid == _WORKER.pid
    assert len(host.watches) == 3
    with pytest.raises(RuntimeRefusalError):
        scope.verify_worker(_channel(version=_WORKER.version + 1), owner_id=str(_UID))
    host.processes[_WORKER.pid].exited.set()
    assert not scope.owns_process(_WORKER.pid) and scope.active_process_ids() == ()


@pytest.mark.parametrize("defect", ["version", "coalition", "parent", "owner", "guardian-pid"])
def test_worker_outside_the_guardian_coalition_or_incarnation_refuses(
    host: _Host, scope: MacosProcessScope, tmp_path: Path, defect: str
) -> None:
    _launch(scope, tmp_path)
    host.add_worker(
        coalition=_RUNTIME_COALITION if defect == "coalition" else _JOB_COALITION,
        parent_pid=4242 if defect == "parent" else _GUARDIAN.pid,
    )
    channel = _channel(
        version=99 if defect == "version" else _WORKER.version, owner="502" if defect == "owner" else "501"
    )
    if defect == "guardian-pid":
        token = MacosPeerAuditToken(_UID, _UID, _UID, _GUARDIAN.pid, 100009, _GUARDIAN.version)
        channel = cast(PosixRuntimeChannel, _Channel(RuntimePeer(os_owner_id="501", process_id=_GUARDIAN.pid), token))
    with pytest.raises(RuntimeRefusalError) as caught:
        scope.verify_worker(channel, owner_id=str(_UID))
    assert caught.value.reason is RuntimeRefusalCode.PEER_UNTRUSTED
    assert scope.worker_pid == 0


def test_guardian_loss_immediately_kills_the_coalition_and_fences_the_scope(
    host: _Host, scope: MacosProcessScope, tmp_path: Path
) -> None:
    _launch(scope, tmp_path)
    host.add_worker()
    scope.verify_worker(_channel(), owner_id=str(_UID))
    host.processes[_GUARDIAN.pid].exited.set()
    deadline = time.monotonic() + 5
    while ("terminate", _JOB_COALITION) not in host.events:
        assert time.monotonic() < deadline, "guardian loss did not kill the coalition"
        time.sleep(0.01)
    assert host.processes[_WORKER.pid].exited.is_set()
    assert not scope.owns_process(_WORKER.pid)
    with pytest.raises(RuntimeRefusalError):
        scope.verify_worker(_channel(), owner_id=str(_UID))
    scope.terminate(timeout=2)
    assert host.store == {} and not host.jobs


def test_failed_termination_is_retained_until_a_retry_proves_the_coalition_empty(
    host: _Host, scope: MacosProcessScope, tmp_path: Path
) -> None:
    guardian = _launch(scope, tmp_path)
    host.add_worker()
    scope.verify_worker(_channel(), owner_id=str(_UID))
    host.termination_failures.append(RuntimeRefusalError(RuntimeRefusalCode.DEADLINE_EXCEEDED))
    with pytest.raises(RuntimeRefusalError) as caught:
        scope.terminate(timeout=1)
    assert caught.value.reason is RuntimeRefusalCode.DEADLINE_EXCEEDED
    assert scope._started and scope._label + ".json" in host.store and not any(w.closed for w in host.watches[:1])
    assert not any(event[:2] == ("launchctl", "bootout") for event in host.events)
    scope.terminate(timeout=2)
    assert not scope._started and host.store == {} and not guardian.alive
    assert host.events.index(("terminate", _JOB_COALITION)) < host.events.index(
        ("launchctl", "bootout", f"gui/{_UID}/{scope._label}")
    )


def test_bootout_refused_while_loaded_is_retained(host: _Host, scope: MacosProcessScope, tmp_path: Path) -> None:
    _launch(scope, tmp_path)
    host.bootout_codes.append(5)
    with pytest.raises(RuntimeRefusalError) as caught:
        scope.terminate(timeout=1)
    assert caught.value.reason is RuntimeRefusalCode.CONTAINMENT_UNAVAILABLE
    assert scope._started and scope._label + ".json" in host.store
    scope.terminate(timeout=2)
    assert not scope._started and not host.jobs


def test_absent_job_is_accepted_only_after_its_coalition_was_emptied(
    host: _Host, scope: MacosProcessScope, tmp_path: Path
) -> None:
    _launch(scope, tmp_path)
    host.jobs.clear()
    scope.terminate(timeout=2)
    target = f"gui/{_UID}/{scope._label}"
    assert host.events.index(("terminate", _JOB_COALITION)) < host.events.index(("launchctl", "bootout", target))
    assert not scope._started and host.store == {}


def test_stale_jobs_of_dead_runtimes_in_this_scope_are_reaped_before_registration(host: _Host, tmp_path: Path) -> None:
    key = macos_worker_scope_key(tmp_path)
    dead = MacosProcessIncarnation(pid=4242, version=3, unique_id=4243)
    stale = MacosWorkerMarker(label=_label(key), runtime=dead, coalition=8100)
    unloaded = MacosWorkerMarker(label=_label(key), runtime=dead, coalition=None)
    live = MacosWorkerMarker(label=_label(key), runtime=_RUNTIME, coalition=8200)
    foreign = MacosWorkerMarker(label=_label(_OTHER_SCOPE), runtime=dead, coalition=8300)
    for marker in (stale, unloaded, live, foreign):
        host.store[marker.label + ".json"] = encode_macos_worker_marker(marker)
    host.jobs[stale.label] = _Job(pid=None, coalition=8100)
    host.jobs[foreign.label] = _Job(pid=None, coalition=8300)
    orphan = _Process(MacosProcessIncarnation(pid=950, version=1, unique_id=951), 8100, 1)
    host.processes[950] = orphan
    scope = MacosProcessScope(worker_id=uuid4(), storage_root=tmp_path, host=host)
    try:
        _launch(scope, tmp_path)
        assert orphan.exited.is_set()
        assert stale.label not in host.jobs and foreign.label in host.jobs
        assert set(host.store) == {live.label + ".json", foreign.label + ".json", scope._label + ".json"}
        assert ("terminate", 8300) not in host.events and ("terminate", 8200) not in host.events
        assert host.events.index(("remove", stale.label)) < host.events.index(("bootstrap", scope._label))
    finally:
        scope.terminate(timeout=2)


@pytest.mark.parametrize("termination_fails", [False, True])
def test_absent_stale_job_keeps_its_recorded_coalition_retirement_obligation(
    host: _Host, tmp_path: Path, termination_fails: bool
) -> None:
    stale = MacosWorkerMarker(
        label=_label(macos_worker_scope_key(tmp_path)),
        runtime=MacosProcessIncarnation(pid=4242, version=3, unique_id=4243),
        coalition=8100,
    )
    host.store[stale.label + ".json"] = encode_macos_worker_marker(stale)
    orphan = _Process(MacosProcessIncarnation(pid=950, version=1, unique_id=951), 8100, 1)
    host.processes[950] = orphan
    scope = MacosProcessScope(worker_id=uuid4(), storage_root=tmp_path, host=host)
    if termination_fails:
        host.termination_failures.append(RuntimeRefusalError(RuntimeRefusalCode.DEADLINE_EXCEEDED))
        with pytest.raises(RuntimeRefusalError) as caught:
            _launch(scope, tmp_path)
        assert caught.value.reason is RuntimeRefusalCode.DEADLINE_EXCEEDED
        assert not orphan.exited.is_set() and stale.label + ".json" in host.store
        assert not any(event[0] == "bootstrap" for event in host.events)
        return
    try:
        _launch(scope, tmp_path)
        assert orphan.exited.is_set() and stale.label + ".json" not in host.store
        assert host.events.index(("terminate", 8100)) < host.events.index(("remove", stale.label))
        assert host.events.index(("remove", stale.label)) < host.events.index(("bootstrap", scope._label))
    finally:
        scope.terminate(timeout=2)


def test_stale_marker_naming_a_different_coalition_refuses_registration(host: _Host, tmp_path: Path) -> None:
    key = macos_worker_scope_key(tmp_path)
    stale = MacosWorkerMarker(
        label=_label(key), runtime=MacosProcessIncarnation(pid=4242, version=3, unique_id=4243), coalition=8100
    )
    host.store[stale.label + ".json"] = encode_macos_worker_marker(stale)
    host.jobs[stale.label] = _Job(pid=None, coalition=8999)
    scope = MacosProcessScope(worker_id=uuid4(), storage_root=tmp_path, host=host)
    with pytest.raises(RuntimeRefusalError) as caught:
        _launch(scope, tmp_path)
    assert caught.value.reason is RuntimeRefusalCode.CONTAINMENT_UNAVAILABLE
    assert not scope._started and not any(event[0] in {"bootstrap", "terminate"} for event in host.events)


@pytest.mark.parametrize("invalid", ["environment", "module", "relative"])
def test_scope_refuses_substitution_before_any_native_step(
    host: _Host, scope: MacosProcessScope, tmp_path: Path, invalid: str
) -> None:
    with pytest.raises(RuntimeRefusalError) as caught:
        scope.launch(
            executable=Path("python3") if invalid == "relative" else Path(sys.executable),
            arguments=("-I", "-m", "other.worker") if invalid == "module" else _DEFAULT,
            directory=tmp_path,
            environment=_ENVIRONMENT | {"PYTHONPATH": "/opt/override"} if invalid == "environment" else _ENVIRONMENT,
        )
    assert caught.value.reason is RuntimeRefusalCode.CONTAINMENT_UNAVAILABLE
    assert host.events == [] and not scope._started


def test_scope_refuses_off_darwin(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(macos_worker_process, "sys", SimpleNamespace(platform="linux"))
    with pytest.raises(RuntimeRefusalError) as caught:
        MacosProcessScope(worker_id=uuid4(), storage_root=tmp_path, host=_Host())
    assert caught.value.reason is RuntimeRefusalCode.CONTAINMENT_UNAVAILABLE


def test_job_definition_keeps_explicit_storage_controls_and_refuses_ambient_inputs(tmp_path: Path) -> None:
    """Storage routing survives env -i without allowing loader or ambient credential inputs."""
    environment = _ENVIRONMENT | {
        "CADRUMO_LOCAL_STORAGE_ROOT": str(tmp_path),
        "CADRUMO_AUTHORITY_ROOT": str(tmp_path / "published-authority"),
        "TMPDIR": str(tmp_path / "scratch"),
    }

    def definition_for(selected: dict[str, str]) -> bytes:
        return macos_worker_job_definition(
            label=_label(),
            executable=tmp_path / "python",
            directory=tmp_path,
            parent=_RUNTIME,
            worker_arguments=_DEFAULT,
            worker_script=None,
            environment=selected,
        )

    definition = plistlib.loads(definition_for(environment))
    assert definition["EnvironmentVariables"] == environment
    assert "CADRUMO_LOCAL_STORAGE_ROOT=" + str(tmp_path) in definition["ProgramArguments"]
    assert "CADRUMO_AUTHORITY_ROOT=" + str(tmp_path / "published-authority") in definition["ProgramArguments"]
    assert "TMPDIR=" + str(tmp_path / "scratch") in definition["ProgramArguments"]
    for extra in ({"PYTHONPATH": "/untrusted"}, {"PRIVATE_CREDENTIAL": "secret"}, {"TMPDIR": "bad\0path"}):
        with pytest.raises(RuntimeRefusalError) as caught:
            definition_for(environment | extra)
        assert caught.value.reason is RuntimeRefusalCode.CONTAINMENT_UNAVAILABLE


@pytest.mark.parametrize("method_name", ("bootstrap", "publish_marker"))
@pytest.mark.parametrize("write_result", (0, -1))
def test_native_host_translates_nonpositive_writes_before_publication(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    method_name: str,
    write_result: int,
) -> None:
    """A stalled native file write refuses before launchd or marker publication."""
    native = macos_worker_process._NativeMacosWorkerHost()
    directory_fd = 41
    file_fd = 42
    label = "com.cadrumo.worker.0123456789abcdef.0123456789abcdef0123456789abcdef"
    payload = b"definition" if method_name == "bootstrap" else b"marker"
    events: list[tuple[object, ...]] = []
    created_files: set[str] = set()
    write_calls = 0

    def fake_open(name: str, flags: int, mode: int, *, dir_fd: int) -> int:
        events.append(("open", name, flags, mode, dir_fd))
        created_files.add(name)
        return file_fd

    def fake_write(descriptor: int, data: bytes | memoryview) -> int:
        nonlocal write_calls
        write_calls += 1
        if write_calls > 1:
            pytest.fail("a nonpositive write must refuse without retrying")
        events.append(("write", descriptor, bytes(data)))
        return write_result

    def fake_close(descriptor: int) -> None:
        events.append(("close", descriptor))

    def fake_unlink(name: str, *, dir_fd: int) -> None:
        events.append(("unlink", name, dir_fd))
        created_files.discard(name)

    def fake_fstat(descriptor: int) -> SimpleNamespace:
        events.append(("fstat", descriptor))
        return SimpleNamespace(st_mode=stat.S_IFREG | 0o600, st_uid=_UID, st_nlink=1)

    def fake_fsync(descriptor: int) -> None:
        events.append(("fsync", descriptor))

    def fake_replace(source: str, destination: str, *, src_dir_fd: int, dst_dir_fd: int) -> None:
        events.append(("replace", source, destination, src_dir_fd, dst_dir_fd))

    native_os = SimpleNamespace(
        O_WRONLY=os.O_WRONLY,
        O_CREAT=os.O_CREAT,
        O_EXCL=os.O_EXCL,
        O_TRUNC=os.O_TRUNC,
        open=fake_open,
        write=fake_write,
        close=fake_close,
        unlink=fake_unlink,
        fstat=fake_fstat,
        fsync=fake_fsync,
        replace=fake_replace,
    )
    monkeypatch.setattr(native, "_directory", lambda *, create: (tmp_path, directory_fd))
    monkeypatch.setattr(macos_worker_process, "os", native_os)
    monkeypatch.setattr(descriptor_write, "os", native_os)
    monkeypatch.setattr(macos_worker_process, "_private_open_flags", lambda *, nonblocking=False: 0)
    monkeypatch.setattr(macos_worker_process, "posix_owner_uid", lambda: _UID)
    monkeypatch.setattr(
        macos_worker_process,
        "run_containment_command_sync",
        lambda *args, **kwargs: pytest.fail("launchctl must not run after a failed definition write"),
    )

    with pytest.raises(RuntimeRefusalError) as caught:
        if method_name == "bootstrap":
            native.bootstrap(label, payload)
        else:
            native.publish_marker(label, payload)

    assert caught.value.reason is RuntimeRefusalCode.CONTAINMENT_UNAVAILABLE
    assert str(caught.value) == RuntimeRefusalCode.CONTAINMENT_UNAVAILABLE.value
    assert [event for event in events if event[0] == "write"] == [("write", file_fd, payload)]
    assert [event[1] for event in events if event[0] == "close"] == [file_fd, directory_fd]
    assert not any(event[0] in {"fsync", "replace"} for event in events)
    if method_name == "bootstrap":
        assert [event[1] for event in events if event[0] == "unlink"] == [label + ".plist"]
        assert created_files == set()
    else:
        assert not any(event[0] == "unlink" for event in events)
        assert created_files == {label + ".pending"}
