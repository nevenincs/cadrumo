"""Trusted Linux launch contracts through explicit ports, without native admission."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

from cadrumo.adapters.local_runtime import linux_worker_process
from cadrumo.adapters.local_runtime.manager_commands import NativeManagerCommand
from cadrumo.application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from cadrumo.core.config import Settings
from cadrumo.entrypoints.runtime import linux_worker_guardian

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_DEFAULT = ("-I", "-m", "cadrumo.entrypoints.runtime.worker")
_ENVIRONMENT = {"PATH": "/usr/bin:/bin", "LANG": "C", "LC_ALL": "C", "PYDANTIC_DISABLE_PLUGINS": "__all__"}


@pytest.mark.parametrize("invalid", ["relative", "missing", "directory"])
def test_scope_rejects_invalid_selected_script_before_native_launch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, invalid: str
) -> None:
    monkeypatch.setattr(linux_worker_process, "sys", SimpleNamespace(platform="linux"))
    script = {"relative": Path("worker.py"), "missing": tmp_path / "missing.py", "directory": tmp_path}[invalid]
    with pytest.raises(RuntimeRefusalError) as refused:
        linux_worker_process.LinuxProcessScope(worker_id=uuid4(), worker_script=script)
    assert refused.value.reason is RuntimeRefusalCode.CONTAINMENT_UNAVAILABLE


@pytest.mark.parametrize("invalid", ["unselected", "other_module", "mismatch", "relative", "removed", "null"])
def test_scope_rejects_worker_substitution_before_manager_access(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, invalid: str
) -> None:
    monkeypatch.setattr(linux_worker_process, "sys", SimpleNamespace(platform="linux"))
    script = tmp_path / "worker.py"
    script.write_text("# synthetic trusted host entrypoint\n", encoding="ascii")
    selected = None if invalid in {"unselected", "other_module"} else script
    scope = linux_worker_process.LinuxProcessScope(worker_id=uuid4(), worker_script=selected)
    command = {
        "unselected": ("-I", str(script)),
        "other_module": ("-I", "-m", "other.worker"),
        "mismatch": _DEFAULT,
        "relative": ("-I", script.name),
        "removed": ("-I", str(script)),
        "null": ("-I", str(script), "--worker-id", "bad\0argument"),
    }[invalid]
    if invalid == "removed":
        script.unlink()

    def forbidden(*_args: object) -> None:
        pytest.fail("an untrusted worker command reached the native manager")

    monkeypatch.setattr(linux_worker_process, "run_manager_command_sync", forbidden)
    with pytest.raises(RuntimeRefusalError) as refused:
        scope.launch(executable=Path(sys.executable), arguments=command, directory=tmp_path, environment=_ENVIRONMENT)
    assert refused.value.reason is RuntimeRefusalCode.CONTAINMENT_UNAVAILABLE


@pytest.mark.parametrize("script_mode", [False, True])
def test_scope_forwards_trusted_selection_inside_existing_guardian_containment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, script_mode: bool
) -> None:
    script = tmp_path / "worker.py"
    script.write_text("# synthetic trusted host entrypoint\n", encoding="ascii")
    executable = tmp_path / "python"
    executable.write_text("synthetic interpreter port", encoding="ascii")
    monkeypatch.setattr(linux_worker_process, "sys", SimpleNamespace(platform="linux"))
    monkeypatch.setattr(
        linux_worker_process, "os", SimpleNamespace(access=lambda *_args: True, X_OK=1, getpid=lambda: 41)
    )
    monkeypatch.setattr(linux_worker_process, "linux_process_start_identity", lambda _pid: "start-41")
    selected = script if script_mode else None
    scope = linux_worker_process.LinuxProcessScope(worker_id=uuid4(), worker_script=selected)
    command = ("-I", str(script)) if script_mode else _DEFAULT
    recorded: list[tuple[str, ...]] = []
    unavailable = RuntimeRefusalError(RuntimeRefusalCode.CONTAINMENT_UNAVAILABLE)

    def manager(tool: NativeManagerCommand, arguments: tuple[str, ...]) -> None:
        assert tool is NativeManagerCommand.SYSTEMD_RUN
        recorded.append(arguments)
        raise unavailable

    monkeypatch.setattr(linux_worker_process, "run_manager_command_sync", manager)
    with pytest.raises(RuntimeRefusalError) as refused:
        scope.launch(executable=executable, arguments=command, directory=tmp_path, environment=_ENVIRONMENT)
    assert refused.value is unavailable
    (arguments,) = recorded
    guardian = arguments.index("cadrumo.entrypoints.runtime.linux_worker_guardian")
    assert arguments[guardian - 2 : guardian] == ("-I", "-m")
    assert arguments[guardian + 1 : guardian + 5] == ("--parent-pid", "41", "--parent-start", "start-41")
    separator = arguments.index("--", guardian)
    selection = arguments[guardian + 5 : separator]
    assert selection == (("--worker-script", str(script)) if script_mode else ())
    assert arguments[separator + 1 :] == command
    assert "--property=KillMode=control-group" in arguments
    assert "--property=ExitType=main" in arguments
    assert "--property=SendSIGKILL=yes" in arguments
    assert "--property=Restart=no" in arguments
    assert "/usr/bin/env" in arguments and "-i" in arguments
    assert scope._started  # a lost manager acknowledgement retains stop ownership


@pytest.mark.parametrize("invalid", ["unselected", "mismatch", "relative", "missing", "null"])
def test_guardian_refuses_worker_substitution_before_parent_or_process_access(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, invalid: str
) -> None:
    script = tmp_path / "worker.py"
    script.write_text("# synthetic trusted host entrypoint\n", encoding="ascii")
    selected = script
    command = ("-I", str(script))
    if invalid == "unselected":
        selected = None
    elif invalid == "mismatch":
        command = _DEFAULT
    elif invalid == "relative":
        selected = Path("worker.py")
    elif invalid == "missing":
        selected = tmp_path / "missing.py"
    else:
        command += ("bad\0argument",)
    monkeypatch.setattr(
        linux_worker_guardian, "sys", SimpleNamespace(platform="linux", flags=SimpleNamespace(isolated=True))
    )

    def forbidden(*_args: object) -> None:
        pytest.fail("an untrusted worker command reached native parent verification")

    monkeypatch.setattr(linux_worker_guardian, "linux_process_start_identity", forbidden)
    monkeypatch.setattr(linux_worker_guardian, "open_linux_pidfd", forbidden)
    selection = ("--worker-script", str(selected)) if selected is not None else ()
    assert (
        linux_worker_guardian.run(["--parent-pid", "41", "--parent-start", "start-41", *selection, "--", *command]) == 2
    )


@pytest.mark.parametrize("script_mode", [False, True])
def test_guardian_checks_parent_twice_then_launches_only_selected_isolated_worker(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, script_mode: bool
) -> None:
    script = tmp_path / "worker.py"
    script.write_text("# synthetic trusted host entrypoint\n", encoding="ascii")
    selected = script if script_mode else None
    command = ("-I", str(script)) if script_mode else _DEFAULT
    starts: list[int] = []
    opened: list[int] = []
    closed: list[int] = []
    launched: list[tuple[str, ...]] = []
    forwarded_names = Settings.storage_env_var_names() | {"CADRUMO_AUTHORITY_ROOT", "TEMP", "TMP", "TMPDIR"}
    expected_environment = _ENVIRONMENT | {name: value for name, value in os.environ.items() if name in forwarded_names}
    native_stat = Path.stat

    def stat(path: Path, *, follow_symlinks: bool = True) -> os.stat_result:
        if path.name == "41" and path.parent.name == "proc":
            return os.stat_result((0, 0, 0, 1, 1001, 1001, 0, 0, 0, 0))
        return native_stat(path, follow_symlinks=follow_symlinks)

    def start(pid: int) -> str:
        starts.append(pid)
        return "start-41"

    def pidfd(pid: int) -> int:
        opened.append(pid)
        return 51

    class Poller:
        def register(self, descriptor: int, flags: int) -> None:
            assert descriptor == 51 and flags == 7

        def poll(self, timeout: int) -> list[tuple[int, int]]:
            assert timeout in {0, 200}
            return []

    class Child:
        def poll(self) -> int:
            return 7

    def launch(
        arguments: tuple[str, ...],
        *,
        stdin: int,
        stdout: int,
        stderr: int,
        env: dict[str, str],
        close_fds: bool,
        start_new_session: bool,
    ) -> Child:
        assert starts == [41, 41] and opened == [41]
        assert stdin == stdout == stderr == -3
        assert env == expected_environment and close_fds and start_new_session
        launched.append(arguments)
        return Child()

    monkeypatch.setattr(Path, "stat", stat)
    monkeypatch.setattr(
        linux_worker_guardian,
        "sys",
        SimpleNamespace(platform="linux", flags=SimpleNamespace(isolated=True), executable=sys.executable),
    )
    monkeypatch.setattr(
        linux_worker_guardian,
        "os",
        SimpleNamespace(getuid=lambda: 1001, close=closed.append, environ=os.environ),
    )
    monkeypatch.setattr(linux_worker_guardian, "select", SimpleNamespace(poll=Poller, POLLIN=1, POLLERR=2, POLLHUP=4))
    monkeypatch.setattr(linux_worker_guardian, "subprocess", SimpleNamespace(Popen=launch, DEVNULL=-3))
    monkeypatch.setattr(linux_worker_guardian, "linux_process_start_identity", start)
    monkeypatch.setattr(linux_worker_guardian, "open_linux_pidfd", pidfd)
    selection = ("--worker-script", str(selected)) if selected is not None else ()
    assert (
        linux_worker_guardian.run(["--parent-pid", "41", "--parent-start", "start-41", *selection, "--", *command]) == 7
    )
    assert launched == [(sys.executable, *command)]
    assert closed == [51]


def test_guardian_forwards_only_storage_controls_to_the_contained_worker(monkeypatch: pytest.MonkeyPatch) -> None:
    inherited = {
        "CADRUMO_STORAGE_ROOT": "/managed/storage",
        "CADRUMO_AUTHORITY_ROOT": "/managed/published-authority",
        "CADRUMO_TEMP_DIR": "tmp",
        "CADRUMO_RUNTIME_SOCKET_DIR": "runtime",
        "CADRUMO_LLM_OPENAI_API_KEY": "must-not-cross-worker-boundary",
        "TEMP": "/managed/storage/tmp",
        "TMP": "/managed/storage/tmp",
        "TMPDIR": "/managed/storage/tmp",
    }
    captured: dict[str, object] = {}
    sentinel = object()

    def launch(_arguments: tuple[str, ...], **kwargs: object) -> object:
        captured.update(kwargs)
        return sentinel

    monkeypatch.setattr(linux_worker_guardian, "os", SimpleNamespace(environ=inherited))
    monkeypatch.setattr(linux_worker_guardian, "sys", SimpleNamespace(executable="/python"))
    monkeypatch.setattr(linux_worker_guardian, "subprocess", SimpleNamespace(Popen=launch, DEVNULL=-3))

    assert linux_worker_guardian._launch_worker(_DEFAULT) is sentinel
    expected = _ENVIRONMENT | {
        name: value
        for name, value in inherited.items()
        if name in Settings.storage_env_var_names() | {"CADRUMO_AUTHORITY_ROOT", "TEMP", "TMP", "TMPDIR"}
    }
    assert captured["env"] == expected
    assert "CADRUMO_LLM_OPENAI_API_KEY" not in expected
