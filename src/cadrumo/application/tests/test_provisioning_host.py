"""Real-behaviour tests for detecting the local model runtime.

The runtime endpoint is a real loopback server or a real closed port. The
executable lookup is the injected port the application layer declares; its
doubles stand in for the operating system, never for the logic under test.
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
    current_runtime_platform,
    locate_runtime_executable,
    probe_runtime_host,
    read_runtime_version,
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


def test_version_is_read_from_a_real_endpoint_and_absent_from_a_closed_one() -> None:
    with _runtime(up=True) as chat_url, override_settings(cadrumo_llm_ollama_chat_url=chat_url):
        assert read_runtime_version() == "0.9.0"
    with override_settings(cadrumo_llm_ollama_chat_url=_CLOSED_ENDPOINT):
        assert read_runtime_version() is None


def test_host_probe_names_install_when_nothing_is_located(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    with override_settings(cadrumo_llm_ollama_chat_url=_CLOSED_ENDPOINT):
        status = probe_runtime_host(platform=RuntimeHostPlatform.WINDOWS, which=_lookup({}))
    assert status.available is False
    assert status.executable_located is False
    assert "installer" not in status.facts
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
