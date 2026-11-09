"""A console sign-in runs the bundled agent's own login against the profile's hosted root, with the terminal inherited."""

from __future__ import annotations

import os
import shutil
import stat
import sys
import tempfile
from collections.abc import Iterator
from pathlib import Path
from uuid import UUID

import pytest

from cadrumo.domain.user_profile.errors import ProfileNotFoundError
from cadrumo_client.commands import profile_selection
from cadrumo_client.commands.profile_selection import LoginTarget
from cadrumo_client.contracts.contracts import RefusalCode, RefusalError

from .. import provider_login
from ..agent_programs import PACKAGE_AGENT_VARIABLE, profile_agent_root
from ..provider_login import ProviderLoginRefusalError, main, prepare_provider_login, selected_profile_id

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

_PROFILE = UUID("12345678-1234-5678-1234-567812345678")
_AMBIENT_VARIABLE = "OPENAI_API_KEY"


def _system_temporary_directory() -> Path:
    """The operating system's own temporary directory; the test session redirects ``TMP`` into the checkout."""
    if sys.platform == "win32":
        return Path(os.environ["LOCALAPPDATA"]) / "Temp"
    return Path(os.sep, "tmp")


@pytest.fixture
def outside_git() -> Iterator[Path]:
    """A folder with no Git project above it, removed afterwards: the sign-in refuses a root inside one."""
    folder = Path(tempfile.mkdtemp(prefix="cadrumo-login-", dir=_system_temporary_directory())).resolve()
    try:
        assert not any((parent / ".git").exists() for parent in (folder, *folder.parents))
        yield folder
    finally:
        shutil.rmtree(folder, ignore_errors=True)


def _shim(directory: Path, *, status: int) -> Path:
    """A stand-in agent program: records its arguments and the names it was given, prints a line, exits with ``status``."""
    directory.mkdir(parents=True, exist_ok=True)
    if sys.platform == "win32":
        program = directory / "cadrumo-agent.cmd"
        program.write_text(
            "@echo off\r\n"
            "echo %*> arguments.txt\r\n"
            "set CADRUMO_ > names.txt\r\n"
            f"if defined {_AMBIENT_VARIABLE} echo leaked> leaked.txt\r\n"
            "echo shim-output-line\r\n"
            f"exit /b {status}\r\n",
            encoding="ascii",
        )
    else:
        program = directory / "cadrumo-agent"
        program.write_text(
            "#!/bin/sh\n"
            'echo "$@" > arguments.txt\n'
            "env | grep '^CADRUMO_' > names.txt\n"
            f'[ -n "${{{_AMBIENT_VARIABLE}+x}}" ] && echo leaked > leaked.txt\n'
            "echo shim-output-line\n"
            f"exit {status}\n",
            encoding="ascii",
        )
        program.chmod(program.stat().st_mode | stat.S_IEXEC)
    return program


def _agent_root(storage: Path) -> Path:
    storage.mkdir(parents=True, exist_ok=True)
    return profile_agent_root(storage, _PROFILE)


def _door(monkeypatch: pytest.MonkeyPatch, storage: Path, shim: Path, *arguments: str) -> int:
    monkeypatch.setenv("CADRUMO_STORAGE_ROOT", str(storage))
    monkeypatch.setenv(PACKAGE_AGENT_VARIABLE, str(shim))
    monkeypatch.setenv(_AMBIENT_VARIABLE, "not-a-real-credential")
    return main(list(arguments))


def _launch(outside_git: Path, shim: Path, *, provider: str = "codex", device: bool = False):
    return prepare_provider_login(
        storage_root=outside_git / "storage",
        profile_id=_PROFILE,
        provider=provider,
        device=device,
        received={PACKAGE_AGENT_VARIABLE: str(shim)},
    )


def test_the_launch_names_the_agents_login_the_profiles_hosted_root_and_no_browser_override(outside_git: Path) -> None:
    root = _agent_root(outside_git / "storage")
    shim = _shim(outside_git / "package", status=0)
    launch = _launch(outside_git, shim, device=True)
    assert launch.executable == shim
    assert launch.arguments == ("-m", "cadrumo_agent.cli.main", "auth", "login", "--provider", "codex", "--device")
    assert launch.directory == root
    assert launch.environment["CADRUMO_AGENT_HOSTED_ROOT"] == str(root)
    assert "CADRUMO_AGENT_AUTH_BROWSER_EXECUTABLE" not in launch.environment
    assert _AMBIENT_VARIABLE not in launch.environment


@pytest.mark.parametrize("provider", ["claude", "codex", "antigravity"])
def test_every_supported_provider_is_passed_through_without_the_device_flag(outside_git: Path, provider: str) -> None:
    _agent_root(outside_git / "storage")
    launch = _launch(outside_git, _shim(outside_git / "package", status=0), provider=provider)
    assert launch.arguments[-2:] == ("--provider", provider)
    assert "--device" not in launch.arguments


@pytest.mark.parametrize(
    ("provider", "device", "reason"),
    [("gemini", False, "gemini"), ("claude", True, "--device"), ("", False, "Provider")],
)
def test_an_unsupported_provider_or_device_flow_is_refused_with_its_reason(
    outside_git: Path, provider: str, device: bool, reason: str
) -> None:
    _agent_root(outside_git / "storage")
    with pytest.raises(ProviderLoginRefusalError, match=reason):
        _launch(outside_git, _shim(outside_git / "package", status=0), provider=provider, device=device)


def test_a_profile_whose_agent_never_started_is_refused_and_nothing_is_created(outside_git: Path) -> None:
    (outside_git / "storage").mkdir()
    with pytest.raises(ProviderLoginRefusalError, match="has not started"):
        _launch(outside_git, _shim(outside_git / "package", status=0))
    assert list((outside_git / "storage").iterdir()) == []


def test_another_profile_has_no_root_even_when_one_profile_has(outside_git: Path) -> None:
    _agent_root(outside_git / "storage")
    with pytest.raises(ProviderLoginRefusalError, match="has not started"):
        prepare_provider_login(
            storage_root=outside_git / "storage",
            profile_id=UUID(int=7),
            provider="codex",
            device=False,
            received={PACKAGE_AGENT_VARIABLE: str(_shim(outside_git / "package", status=0))},
        )


def test_a_root_inside_a_git_project_is_refused(outside_git: Path) -> None:
    (outside_git / ".git").mkdir()
    _agent_root(outside_git / "storage")
    with pytest.raises(ProviderLoginRefusalError, match="Git project"):
        _launch(outside_git, _shim(outside_git / "package", status=0))


def test_without_a_bundled_agent_the_refusal_says_what_is_missing(outside_git: Path) -> None:
    _agent_root(outside_git / "storage")
    with pytest.raises(ProviderLoginRefusalError, match="bundled agent"):
        prepare_provider_login(
            storage_root=outside_git / "storage",
            profile_id=_PROFILE,
            provider="codex",
            device=False,
            received={},
            interpreter=outside_git / "python.exe",
        )


def test_the_bundled_agent_beside_the_package_interpreter_is_found_without_the_package_variable(
    outside_git: Path,
) -> None:
    _agent_root(outside_git / "storage")
    image = outside_git / "package" / "bin" / ("cadrumo-agent.exe" if sys.platform == "win32" else "cadrumo-agent")
    image.parent.mkdir(parents=True)
    image.write_bytes(b"")
    interpreter = outside_git / "package" / "python.exe"
    interpreter.write_bytes(b"")
    launch = prepare_provider_login(
        storage_root=outside_git / "storage",
        profile_id=_PROFILE,
        provider="claude",
        device=False,
        received={},
        interpreter=interpreter,
    )
    assert launch.executable == image


def test_the_console_door_inherits_the_terminal_and_records_the_hosted_root_and_no_credential(
    outside_git: Path, monkeypatch: pytest.MonkeyPatch, capfd: pytest.CaptureFixture[str]
) -> None:
    storage = outside_git / "storage"
    root = _agent_root(storage)
    shim = _shim(outside_git / "package", status=0)
    status = _door(monkeypatch, storage, shim, "--profile", str(_PROFILE), "--provider", "codex", "--device")
    assert status == 0
    assert "shim-output-line" in capfd.readouterr().out
    assert "--provider codex --device" in (root / "arguments.txt").read_text()
    names = (root / "names.txt").read_text()
    assert f"CADRUMO_AGENT_HOSTED_ROOT={root}" in names
    assert "AUTH_BROWSER_EXECUTABLE" not in names
    assert not (root / "leaked.txt").exists()


@pytest.mark.parametrize("status", [1, 3])
def test_the_agents_exit_status_is_the_commands_exit_status(
    outside_git: Path, monkeypatch: pytest.MonkeyPatch, status: int
) -> None:
    storage = outside_git / "storage"
    _agent_root(storage)
    shim = _shim(outside_git / "package", status=status)
    done = _door(monkeypatch, storage, shim, "--profile", str(_PROFILE), "--provider", "claude")
    assert done == status


def test_a_refusal_ends_the_door_with_its_reason_on_standard_error_and_status_two(
    outside_git: Path, monkeypatch: pytest.MonkeyPatch, capfd: pytest.CaptureFixture[str]
) -> None:
    storage = outside_git / "storage"
    storage.mkdir()
    shim = _shim(outside_git / "package", status=0)
    status = _door(monkeypatch, storage, shim, "--profile", str(_PROFILE), "--provider", "codex")
    captured = capfd.readouterr()
    assert status == 2
    assert "has not started" in captured.err
    assert "shim-output-line" not in captured.out


def test_a_profile_uuid_is_used_as_given_without_asking_the_runtime(monkeypatch: pytest.MonkeyPatch) -> None:
    def unreachable(*_: object) -> None:
        raise AssertionError("the runtime was asked")

    monkeypatch.setattr(profile_selection, "require_runtime_login_target", unreachable)
    monkeypatch.setattr(profile_selection, "command_profile_id", unreachable)
    assert selected_profile_id(f" {_PROFILE} ") == _PROFILE


def test_a_label_is_resolved_by_the_runtime(monkeypatch: pytest.MonkeyPatch) -> None:
    asked: list[str] = []

    def resolve(name: str) -> LoginTarget:
        asked.append(name)
        return LoginTarget(str(_PROFILE), name)

    monkeypatch.setattr(profile_selection, "require_runtime_login_target", resolve)
    assert selected_profile_id("Mi perfil") == _PROFILE
    assert asked == ["Mi perfil"]


def test_without_a_profile_the_runtimes_selection_is_used(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(profile_selection, "command_profile_id", lambda: str(_PROFILE))
    assert selected_profile_id(None) == _PROFILE


def test_no_selected_profile_unknown_label_or_silent_runtime_is_refused_with_its_reason(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(profile_selection, "command_profile_id", lambda: None)
    with pytest.raises(ProviderLoginRefusalError, match="No profile is selected"):
        selected_profile_id("  ")

    def unknown(name: str) -> LoginTarget:
        raise ProfileNotFoundError(translated_message="cli.config.profile.unknown_profile", context={"name": name})

    monkeypatch.setattr(profile_selection, "require_runtime_login_target", unknown)
    with pytest.raises(ProviderLoginRefusalError, match="No profile is named"):
        selected_profile_id("Otro")

    def unavailable() -> str | None:
        raise RefusalError(RefusalCode.UNAVAILABLE)

    monkeypatch.setattr(profile_selection, "command_profile_id", unavailable)
    with pytest.raises(ProviderLoginRefusalError, match="could not say which profile"):
        selected_profile_id(None)


def test_the_service_executable_dispatches_provider_login_before_the_service_imports(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from ... import bootstrap

    received: list[list[str]] = []
    monkeypatch.setattr(provider_login, "main", lambda argv: received.append(list(argv)) or 5)
    monkeypatch.setattr(sys, "argv", ["cadrumo-agent-service", "provider-login", "--provider", "codex"])
    with pytest.raises(SystemExit) as ended:
        bootstrap.main()
    assert ended.value.code == 5
    assert received == [["--provider", "codex"]]
