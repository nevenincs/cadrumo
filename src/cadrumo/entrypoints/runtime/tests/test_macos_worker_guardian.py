"""macOS guardian decisions through explicit native ports, without a real launchd job."""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace

import pytest

from cadrumo.adapters.local_runtime.macos_process import MacosProcessIncarnation, MacosProcessObservation
from cadrumo.application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from cadrumo.entrypoints.runtime import macos_worker_guardian

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_DEFAULT = ("-I", "-B", "-m", "cadrumo.entrypoints.runtime.worker")
_ENVIRONMENT = {"PATH": "/usr/bin:/bin", "LANG": "C", "LC_ALL": "C", "PYDANTIC_DISABLE_PLUGINS": "__all__"}
_OWN = MacosProcessIncarnation(pid=77, version=5, unique_id=505)
_PARENT = MacosProcessIncarnation(pid=41, version=9, unique_id=909)
_OWN_COALITION = 7000
_PARENT_COALITION = 5000


@dataclass
class _Kernel:
    """Synthetic native facts and the guardian's recorded effects."""

    incarnations: dict[int, list[MacosProcessIncarnation | None]] = field(default_factory=dict)
    coalitions: dict[int, int | None] = field(default_factory=dict)
    parent_exit: list[bool] = field(default_factory=list)
    worker_codes: list[int | None] = field(default_factory=list)
    termination_failure: RuntimeRefusalError | None = None
    native_reads: int = 0
    launched: list[tuple[tuple[str, ...], dict[str, object]]] = field(default_factory=list)
    terminations: list[tuple[int, MacosProcessIncarnation | None]] = field(default_factory=list)
    closed: int = 0

    def incarnation(self, pid: int) -> MacosProcessIncarnation | None:
        self.native_reads += 1
        values = self.incarnations[pid]
        return values.pop(0) if len(values) > 1 else values[0]

    def coalition(self, pid: int) -> int | None:
        self.native_reads += 1
        return self.coalitions[pid]

    def observe(self, pid: int, *, expected_owner: str) -> MacosProcessObservation:
        assert expected_owner == "501"
        return MacosProcessObservation(pid, expected_owner, 1, pid, 1, 0)

    def terminate(self, coalition: int, *, deadline: float, exclude: MacosProcessIncarnation | None = None) -> None:
        assert deadline > 0
        self.terminations.append((coalition, exclude))
        if self.termination_failure is not None:
            raise self.termination_failure


class _Watch:
    def __init__(self, kernel: _Kernel, observation: MacosProcessObservation) -> None:
        assert observation.pid == _PARENT.pid
        self.kernel = kernel

    @property
    def exited(self) -> bool:
        return False

    def wait(self, *, timeout: float) -> bool:
        assert timeout == 0.2
        return self.kernel.parent_exit.pop(0) if self.kernel.parent_exit else False

    def close(self) -> None:
        self.kernel.closed += 1


class _Child:
    def __init__(self, kernel: _Kernel) -> None:
        self.kernel = kernel

    @property
    def returncode(self) -> int | None:
        return self.kernel.worker_codes.pop(0) if self.kernel.worker_codes else 0

    async def wait(self) -> int:
        return self.returncode or 0


def _install(monkeypatch: pytest.MonkeyPatch, kernel: _Kernel) -> None:
    async def launch(*arguments: str, **options: object) -> _Child:
        kernel.launched.append((arguments, options))
        return _Child(kernel)

    monkeypatch.setattr(
        macos_worker_guardian,
        "sys",
        SimpleNamespace(platform="darwin", flags=SimpleNamespace(isolated=True), executable=sys.executable),
    )
    monkeypatch.setattr(
        macos_worker_guardian, "os", SimpleNamespace(getpid=lambda: _OWN.pid, getuid=lambda: 501, environ={})
    )
    monkeypatch.setattr(macos_worker_guardian, "read_macos_incarnation", kernel.incarnation)
    monkeypatch.setattr(macos_worker_guardian, "read_macos_resource_coalition", kernel.coalition)
    monkeypatch.setattr(macos_worker_guardian, "read_macos_process", kernel.observe)
    monkeypatch.setattr(macos_worker_guardian, "MacosProcessWatch", lambda observation: _Watch(kernel, observation))
    monkeypatch.setattr(macos_worker_guardian, "terminate_macos_coalition", kernel.terminate)
    monkeypatch.setattr(macos_worker_guardian.asyncio, "create_subprocess_exec", launch)


def _kernel() -> _Kernel:
    return _Kernel(
        incarnations={_OWN.pid: [_OWN], _PARENT.pid: [_PARENT]},
        coalitions={_OWN.pid: _OWN_COALITION, _PARENT.pid: _PARENT_COALITION},
    )


def _run(
    *, version: int = _PARENT.version, selection: tuple[str, ...] = (), command: tuple[str, ...] = _DEFAULT
) -> int:
    return macos_worker_guardian.run(
        ["--parent-pid", str(_PARENT.pid), "--parent-version", str(version), *selection, "--", *command]
    )


@pytest.mark.parametrize(
    "invalid", ["unselected", "mismatch", "relative", "missing", "null", "missing-bytecode", "extra-flag"]
)
def test_guardian_refuses_worker_substitution_before_native_access(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, invalid: str
) -> None:
    script = tmp_path / "worker.py"
    script.write_text("# synthetic trusted host entrypoint\n", encoding="ascii")
    selected: Path | None = script
    command: tuple[str, ...] = ("-I", "-B", str(script))
    if invalid == "unselected":
        selected = None
    elif invalid == "mismatch":
        command = _DEFAULT
    elif invalid == "relative":
        selected = Path("worker.py")
    elif invalid == "missing":
        selected = tmp_path / "missing.py"
    elif invalid == "null":
        command += ("bad\0argument",)
    elif invalid == "missing-bytecode":
        command = ("-I", str(script))
    else:
        command = ("-I", "-B", "-O", str(script))
    kernel = _kernel()
    _install(monkeypatch, kernel)
    selection = ("--worker-script", str(selected)) if selected is not None else ()
    assert _run(selection=selection, command=command) == 2
    assert kernel.native_reads == 0 and kernel.launched == []


@pytest.mark.parametrize("defect", ["shared-coalition", "version", "parent-gone", "own-unreadable"])
def test_guardian_refuses_a_parent_it_cannot_bind_exactly(monkeypatch: pytest.MonkeyPatch, defect: str) -> None:
    kernel = _kernel()
    if defect == "shared-coalition":
        kernel.coalitions[_PARENT.pid] = _OWN_COALITION
    elif defect == "parent-gone":
        kernel.incarnations[_PARENT.pid] = [None]
    elif defect == "own-unreadable":
        kernel.coalitions[_OWN.pid] = None
    _install(monkeypatch, kernel)
    assert _run(version=_PARENT.version + 1 if defect == "version" else _PARENT.version) == 2
    assert kernel.launched == [] and kernel.terminations == []


def test_parent_pid_reused_before_the_watch_registered_refuses(monkeypatch: pytest.MonkeyPatch) -> None:
    kernel = _kernel()
    kernel.incarnations[_PARENT.pid] = [_PARENT, MacosProcessIncarnation(pid=_PARENT.pid, version=10, unique_id=910)]
    _install(monkeypatch, kernel)
    assert _run() == 2
    assert kernel.launched == [] and kernel.closed == 1


@pytest.mark.parametrize("script_mode", [False, True])
def test_worker_exit_retires_the_rest_of_the_coalition_and_returns_its_code(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, script_mode: bool
) -> None:
    script = tmp_path / "worker.py"
    script.write_text("# synthetic trusted host entrypoint\n", encoding="ascii")
    command = ("-I", "-B", str(script)) if script_mode else _DEFAULT
    kernel = _kernel()
    kernel.worker_codes = [None, None, 7]
    _install(monkeypatch, kernel)
    selection = ("--worker-script", str(script)) if script_mode else ()
    assert _run(selection=selection, command=command) == 7
    ((arguments, options),) = kernel.launched
    assert arguments == (sys.executable, *command)
    # Same session and process group: no new session is requested.
    assert options == {"stdin": -3, "stdout": -3, "stderr": -3, "env": _ENVIRONMENT, "close_fds": True}
    assert kernel.terminations == [(_OWN_COALITION, _OWN)]
    assert kernel.closed == 1


def test_parent_loss_retires_the_coalition_except_the_guardian(monkeypatch: pytest.MonkeyPatch) -> None:
    kernel = _kernel()
    kernel.parent_exit = [False, True]
    kernel.worker_codes = [None]
    _install(monkeypatch, kernel)
    assert _run() == 2
    assert len(kernel.launched) == 1
    assert kernel.terminations == [(_OWN_COALITION, _OWN)]
    assert kernel.closed == 1


def test_unproven_retirement_after_worker_exit_reports_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    kernel = _kernel()
    kernel.worker_codes = [0]
    kernel.termination_failure = RuntimeRefusalError(RuntimeRefusalCode.DEADLINE_EXCEEDED)
    _install(monkeypatch, kernel)
    assert _run() == 2
    assert kernel.terminations == [(_OWN_COALITION, _OWN)]


def test_guardian_refuses_off_darwin_or_without_isolation(monkeypatch: pytest.MonkeyPatch) -> None:
    kernel = _kernel()
    _install(monkeypatch, kernel)
    monkeypatch.setattr(
        macos_worker_guardian, "sys", SimpleNamespace(platform="linux", flags=SimpleNamespace(isolated=True))
    )
    assert _run() == 2
    monkeypatch.setattr(
        macos_worker_guardian, "sys", SimpleNamespace(platform="darwin", flags=SimpleNamespace(isolated=False))
    )
    assert _run() == 2
    assert kernel.native_reads == 0 and kernel.launched == []


def test_guardian_carries_only_explicit_storage_controls_to_its_worker(monkeypatch: pytest.MonkeyPatch) -> None:
    kernel = _kernel()
    kernel.worker_codes = [0]
    _install(monkeypatch, kernel)
    monkeypatch.setattr(
        macos_worker_guardian.os,
        "environ",
        {
            "CADRUMO_LOCAL_STORAGE_ROOT": "/synthetic/root",
            "CADRUMO_AUTHORITY_ROOT": "/synthetic/published-authority",
            "TMPDIR": "/synthetic/scratch",
            "PRIVATE_CREDENTIAL": "never-forwarded",
            "PYTHONPATH": "/untrusted",
        },
    )
    assert _run() == 0
    assert kernel.launched[0][1]["env"] == _ENVIRONMENT | {
        "CADRUMO_LOCAL_STORAGE_ROOT": "/synthetic/root",
        "CADRUMO_AUTHORITY_ROOT": "/synthetic/published-authority",
        "TMPDIR": "/synthetic/scratch",
    }
