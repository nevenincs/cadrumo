"""Real-behaviour tests for detecting, starting and installing the local model runtime.

The runtime endpoint is a real loopback server or a real closed port. Process
control is the injected port the application layer declares; the doubles here
stand in for the operating system, never for the logic under test, and each
one records what it was asked to do so a refusal can be shown to have run
nothing.
"""

from __future__ import annotations

from collections.abc import Callable, Generator, Mapping
from contextlib import contextmanager
from http import HTTPStatus
from pathlib import Path
from typing import ClassVar, override

import pytest

from ...core.config import override_settings
from ...tests.loopback_llm import SilentLoopbackHandler, serving_loopback, write_json_response
from ..provisioning_contracts import ProvisioningPreconditionCondition
from ..provisioning_host import (
    RuntimeHostPlatform,
    RuntimeInstaller,
    available_runtime_installer,
    current_runtime_platform,
    install_runtime,
    locate_runtime_executable,
    probe_runtime_host,
    read_runtime_version,
    runtime_endpoint_is_local,
    start_runtime,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_CLOSED_ENDPOINT = "http://127.0.0.1:1/api/chat"


class _VersionEndpoint(SilentLoopbackHandler):
    """A runtime endpoint that answers ``/api/version`` only while ``up`` is set."""

    up: ClassVar[bool] = True

    @override
    def do_GET(self) -> None:
        if self.path != "/api/version" or not self.up:
            self.send_error(HTTPStatus.SERVICE_UNAVAILABLE)
            return
        write_json_response(self, {"version": "0.9.0"}, status=HTTPStatus.OK)


@contextmanager
def _runtime(*, up: bool) -> Generator[str]:
    _VersionEndpoint.up = up
    with serving_loopback(_VersionEndpoint, path="/api/chat") as chat_url:
        yield chat_url


def _lookup(found: Mapping[str, str]) -> Callable[[str], str | None]:
    def which(name: str) -> str | None:
        return found.get(name)

    return which


class _Spawner:
    """Records spawn requests and optionally brings the runtime endpoint up."""

    def __init__(self, *, bring_up: bool = False, fail: bool = False) -> None:
        self.calls: list[tuple[Path, str]] = []
        self._bring_up = bring_up
        self._fail = fail

    def __call__(self, executable: Path, env: Mapping[str, str]) -> int:
        self.calls.append((executable, env["OLLAMA_HOST"]))
        if self._fail:
            raise FileNotFoundError(str(executable))
        if self._bring_up:
            _VersionEndpoint.up = True
        return 4242


class _Installer:
    """Records install requests; ``creates`` makes the runtime executable appear."""

    def __init__(self, *, exit_code: int = 0, creates: Path | None = None) -> None:
        self.calls: list[tuple[RuntimeInstaller, Path]] = []
        self._exit_code = exit_code
        self._creates = creates

    def __call__(self, installer: RuntimeInstaller, executable: Path, timeout_s: float) -> int:
        assert timeout_s > 0
        self.calls.append((installer, executable))
        if self._creates is not None:
            self._creates.parent.mkdir(parents=True, exist_ok=True)
            self._creates.write_bytes(b"")
        return self._exit_code


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("win32", RuntimeHostPlatform.WINDOWS),
        ("darwin", RuntimeHostPlatform.MACOS),
        ("linux", RuntimeHostPlatform.LINUX),
        ("freebsd14", RuntimeHostPlatform.OTHER),
    ],
)
def test_platform_classification(value: str, expected: RuntimeHostPlatform) -> None:
    assert current_runtime_platform(value) is expected


def test_path_lookup_wins_over_standard_locations(tmp_path: Path) -> None:
    located = locate_runtime_executable(
        platform=RuntimeHostPlatform.WINDOWS,
        env={"LOCALAPPDATA": str(tmp_path)},
        which=_lookup({"ollama": "C:/tools/ollama.exe"}),
    )
    assert located == Path("C:/tools/ollama.exe")


def test_windows_standard_location_is_found_when_path_does_not_have_it(tmp_path: Path) -> None:
    """A just-installed runtime is not on this process's PATH yet; the install directory still finds it."""
    binary = tmp_path / "Programs" / "Ollama" / "ollama.exe"
    binary.parent.mkdir(parents=True)
    binary.write_bytes(b"")
    located = locate_runtime_executable(
        platform=RuntimeHostPlatform.WINDOWS,
        env={"LOCALAPPDATA": str(tmp_path)},
        which=_lookup({}),
    )
    assert located == binary


def test_absent_runtime_is_not_located(tmp_path: Path) -> None:
    assert (
        locate_runtime_executable(
            platform=RuntimeHostPlatform.WINDOWS,
            env={"LOCALAPPDATA": str(tmp_path)},
            which=_lookup({}),
        )
        is None
    )


@pytest.mark.parametrize(
    ("platform", "found", "expected"),
    [
        (RuntimeHostPlatform.WINDOWS, {"winget": "winget.exe"}, RuntimeInstaller.WINGET),
        (RuntimeHostPlatform.WINDOWS, {}, RuntimeInstaller.NONE),
        (RuntimeHostPlatform.MACOS, {"brew": "/opt/homebrew/bin/brew"}, RuntimeInstaller.HOMEBREW),
        # Linux has no unprivileged installer even when a package manager exists.
        (RuntimeHostPlatform.LINUX, {"brew": "/home/linuxbrew/bin/brew"}, RuntimeInstaller.NONE),
    ],
)
def test_installer_availability_per_platform(
    platform: RuntimeHostPlatform,
    found: Mapping[str, str],
    expected: RuntimeInstaller,
) -> None:
    assert available_runtime_installer(platform=platform, which=_lookup(found)) is expected


@pytest.mark.parametrize(
    ("url", "local"),
    [
        ("http://127.0.0.1:11434/api/chat", True),
        ("http://localhost:11434/api/chat", True),
        ("http://[::1]:11434/api/chat", True),
        ("http://gpu-box.lan:11434/api/chat", False),
    ],
)
def test_endpoint_locality(url: str, local: bool) -> None:
    assert runtime_endpoint_is_local(url) is local


def test_version_is_read_from_a_real_endpoint_and_absent_from_a_closed_one() -> None:
    with _runtime(up=True) as chat_url, override_settings(cadrumo_llm_ollama_chat_url=chat_url):
        assert read_runtime_version() == "0.9.0"
    with override_settings(cadrumo_llm_ollama_chat_url=_CLOSED_ENDPOINT):
        assert read_runtime_version() is None


def test_host_probe_names_install_when_nothing_is_located(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    with override_settings(cadrumo_llm_ollama_chat_url=_CLOSED_ENDPOINT):
        status = probe_runtime_host(platform=RuntimeHostPlatform.WINDOWS, which=_lookup({"winget": "winget.exe"}))
    assert status.available is False
    assert status.executable_located is False
    assert status.installer is RuntimeInstaller.WINGET
    assert status.precondition_verdict is not None
    assert status.precondition_verdict.failed_condition_id == ProvisioningPreconditionCondition.RUNTIME_INSTALLED


def test_host_probe_names_reachability_when_installed_but_silent() -> None:
    with override_settings(cadrumo_llm_ollama_chat_url=_CLOSED_ENDPOINT):
        status = probe_runtime_host(which=_lookup({"ollama": "/usr/bin/ollama"}))
    assert status.available is False
    assert status.executable_located is True
    assert status.precondition_verdict is not None
    assert status.precondition_verdict.failed_condition_id == ProvisioningPreconditionCondition.RUNTIME_REACHABLE


def test_host_probe_is_available_when_the_endpoint_answers() -> None:
    with _runtime(up=True) as chat_url, override_settings(cadrumo_llm_ollama_chat_url=chat_url):
        status = probe_runtime_host(which=_lookup({"ollama": "/usr/bin/ollama"}))
    assert status.available is True
    assert status.version == "0.9.0"
    assert status.precondition_verdict is None


def test_start_is_a_no_op_when_the_runtime_already_answers() -> None:
    spawner = _Spawner()
    with _runtime(up=True) as chat_url, override_settings(cadrumo_llm_ollama_chat_url=chat_url):
        outcome = start_runtime(spawn=spawner, which=_lookup({"ollama": "/usr/bin/ollama"}))
    assert outcome.running is True
    assert outcome.already_running is True
    assert spawner.calls == []


def test_start_spawns_the_located_runtime_and_waits_for_it_to_answer() -> None:
    spawner = _Spawner(bring_up=True)
    with _runtime(up=False) as chat_url, override_settings(cadrumo_llm_ollama_chat_url=chat_url):
        outcome = start_runtime(spawn=spawner, which=_lookup({"ollama": "/usr/bin/ollama"}), timeout_s=5)
    assert outcome.running is True
    assert outcome.already_running is False
    assert outcome.started_pid == 4242
    port = chat_url.split(":")[2].split("/")[0]
    assert spawner.calls == [(Path("/usr/bin/ollama"), f"127.0.0.1:{port}")]


def test_start_refuses_a_remote_endpoint_without_spawning() -> None:
    spawner = _Spawner()
    with override_settings(cadrumo_llm_ollama_chat_url="http://192.0.2.1:9/api/chat"):
        outcome = start_runtime(spawn=spawner, which=_lookup({"ollama": "/usr/bin/ollama"}))
    assert outcome.running is False
    assert outcome.precondition_verdict is not None
    assert outcome.precondition_verdict.failed_condition_id == ProvisioningPreconditionCondition.RUNTIME_ENDPOINT_LOCAL
    assert spawner.calls == []


def test_start_refuses_when_no_runtime_is_installed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    spawner = _Spawner()
    with override_settings(cadrumo_llm_ollama_chat_url=_CLOSED_ENDPOINT):
        outcome = start_runtime(spawn=spawner, which=_lookup({}))
    assert outcome.running is False
    assert outcome.precondition_verdict is not None
    assert outcome.precondition_verdict.failed_condition_id == ProvisioningPreconditionCondition.RUNTIME_INSTALLED
    assert spawner.calls == []


def test_start_reports_a_runtime_that_never_answers() -> None:
    spawner = _Spawner(bring_up=False)
    with _runtime(up=False) as chat_url, override_settings(cadrumo_llm_ollama_chat_url=chat_url):
        outcome = start_runtime(spawn=spawner, which=_lookup({"ollama": "/usr/bin/ollama"}), timeout_s=1)
    assert outcome.running is False
    assert outcome.facts["spawned"] is True
    assert outcome.precondition_verdict is not None
    assert outcome.precondition_verdict.failed_condition_id == ProvisioningPreconditionCondition.RUNTIME_START_SUCCEEDED


def test_start_reports_a_spawn_the_system_refused() -> None:
    spawner = _Spawner(fail=True)
    with _runtime(up=False) as chat_url, override_settings(cadrumo_llm_ollama_chat_url=chat_url):
        outcome = start_runtime(spawn=spawner, which=_lookup({"ollama": "/usr/bin/ollama"}), timeout_s=1)
    assert outcome.running is False
    assert outcome.facts["spawned"] is False
    assert outcome.facts["start_error_type"] == "FileNotFoundError"


def test_install_is_a_no_op_when_the_runtime_is_already_located() -> None:
    installer = _Installer()
    outcome = install_runtime(
        consent=False,
        run=installer,
        platform=RuntimeHostPlatform.WINDOWS,
        which=_lookup({"ollama": "C:/ollama.exe", "winget": "C:/winget.exe"}),
    )
    assert outcome.installed is True
    assert outcome.already_installed is True
    assert installer.calls == []


def test_install_without_consent_runs_nothing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    installer = _Installer()
    outcome = install_runtime(
        consent=False,
        run=installer,
        platform=RuntimeHostPlatform.WINDOWS,
        which=_lookup({"winget": "C:/winget.exe"}),
    )
    assert outcome.installed is False
    assert outcome.installer is RuntimeInstaller.WINGET
    assert outcome.precondition_verdict is not None
    assert (
        outcome.precondition_verdict.failed_condition_id == ProvisioningPreconditionCondition.RUNTIME_INSTALL_CONSENTED
    )
    assert installer.calls == []


def test_install_refuses_where_no_installer_exists() -> None:
    installer = _Installer()
    outcome = install_runtime(
        consent=True,
        run=installer,
        platform=RuntimeHostPlatform.LINUX,
        which=_lookup({}),
    )
    assert outcome.installed is False
    assert outcome.precondition_verdict is not None
    assert (
        outcome.precondition_verdict.failed_condition_id
        == ProvisioningPreconditionCondition.RUNTIME_INSTALLER_AVAILABLE
    )
    assert installer.calls == []


def test_consented_install_runs_the_located_installer_and_confirms_the_binary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    installer = _Installer(creates=tmp_path / "Programs" / "Ollama" / "ollama.exe")
    outcome = install_runtime(
        consent=True,
        run=installer,
        platform=RuntimeHostPlatform.WINDOWS,
        which=_lookup({"winget": "C:/winget.exe"}),
    )
    assert outcome.installed is True
    assert outcome.already_installed is False
    assert installer.calls == [(RuntimeInstaller.WINGET, Path("C:/winget.exe"))]


def test_an_install_that_exits_zero_without_producing_the_binary_is_not_installed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    outcome = install_runtime(
        consent=True,
        run=_Installer(exit_code=0),
        platform=RuntimeHostPlatform.WINDOWS,
        which=_lookup({"winget": "C:/winget.exe"}),
    )
    assert outcome.installed is False
    assert outcome.facts["executable_located"] is False
    assert outcome.precondition_verdict is not None
    assert (
        outcome.precondition_verdict.failed_condition_id == ProvisioningPreconditionCondition.RUNTIME_INSTALL_SUCCEEDED
    )


def test_a_failed_installer_exit_is_reported(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    outcome = install_runtime(
        consent=True,
        run=_Installer(exit_code=1603),
        platform=RuntimeHostPlatform.WINDOWS,
        which=_lookup({"winget": "C:/winget.exe"}),
    )
    assert outcome.installed is False
    assert outcome.installer_exit_code == 1603
