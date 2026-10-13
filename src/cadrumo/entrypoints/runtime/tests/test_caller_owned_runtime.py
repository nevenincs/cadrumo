"""A caller-owned runtime serves the explicitly configured root for the life of its standard input.

These tests start the installed ``cadrumo-runtime`` launcher with
``--configured-root`` on a synthetic root, read its readiness line, shake hands
over real native IPC and end it by closing standard input. Refusals are checked
to leave the refused root uncreated.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import sysconfig
import threading
import time
from collections.abc import Generator
from contextlib import contextmanager
from importlib.metadata import version
from pathlib import Path

import pytest

from cadrumo.adapters.local_runtime.framing import VerifiedRuntimeConnection
from cadrumo.adapters.local_runtime.posix_endpoint import PosixRuntimeEndpoint
from cadrumo.adapters.local_runtime.windows import WindowsRuntimeEndpoint
from cadrumo.application.runtime.contracts import (
    RuntimeClientHello,
    RuntimeExitReason,
    RuntimeRefusalCode,
    RuntimeRefusalError,
)
from cadrumo.core.storage_environment import host_installed_default_root

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.skipif(
        sys.platform not in {"win32", "linux", "darwin"}, reason="requires supported native installed runtime transport"
    ),
]

_STARTUP_TIMEOUT_SECONDS = 60
_ROOT_VARIABLES = ("CADRUMO_LOCAL_STORAGE_ROOT", "CADRUMO_STORAGE_ROOT")


def _environment(root: Path | None) -> dict[str, str]:
    environment = {name: value for name, value in os.environ.items() if name.upper() not in _ROOT_VARIABLES}
    # Native IPC acceptance is independent of the test runner's desktop session.
    environment["CADRUMO_DEV_RUNTIME_SESSION_OVERRIDE"] = "1"
    if root is not None:
        environment["CADRUMO_LOCAL_STORAGE_ROOT"] = str(root)
    return environment


@contextmanager
def _caller_owned(environment: dict[str, str], directory: Path) -> Generator[subprocess.Popen[bytes]]:
    name = "cadrumo-runtime.exe" if sys.platform == "win32" else "cadrumo-runtime"
    executable = Path(sysconfig.get_path("scripts")) / name
    assert executable.is_file(), "install the current project entrypoints before installed acceptance"
    process = subprocess.Popen(  # noqa: S603 -- exact installed console executable; no shell or private operands.
        (str(executable), "--configured-root"),
        cwd=directory,
        env=environment,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        yield process
    finally:
        if process.poll() is None:
            process.kill()
        process.communicate(timeout=10)


def _ready_line(process: subprocess.Popen[bytes]) -> bytes:
    output = process.stdout
    assert output is not None
    lines: list[bytes] = []
    reader = threading.Thread(target=lambda: lines.append(output.readline()), daemon=True)
    reader.start()
    reader.join(_STARTUP_TIMEOUT_SECONDS)
    assert lines, "the runtime announced no readiness before its startup deadline"
    return lines[0]


def _endpoint(root: Path) -> WindowsRuntimeEndpoint | PosixRuntimeEndpoint:
    return (
        WindowsRuntimeEndpoint(storage_root=root)
        if sys.platform == "win32"
        else PosixRuntimeEndpoint(storage_root=root)
    )


def test_the_runtime_announces_readiness_serves_the_configured_root_and_stops_when_input_closes(
    tmp_path: Path,
) -> None:
    root = tmp_path / "caller-root"
    with _caller_owned(_environment(root), tmp_path) as process:
        announcement = json.loads(_ready_line(process))
        endpoint = _endpoint(root)
        try:
            assert announcement == {
                "kind": "runtime_ready",
                "pid": announcement["pid"],
                "product_version": version("cadrumo"),
                "storage_identity": endpoint.storage_identity,
            }
            # Readiness means a client deriving the endpoint from the same root connects at once.
            VerifiedRuntimeConnection(
                endpoint.connect(timeout=1),
                expected=RuntimeClientHello(
                    product_version=version("cadrumo"), storage_identity=endpoint.storage_identity
                ),
                deadline=time.monotonic() + 10,
            ).close()
        finally:
            endpoint.close()
        assert process.stdin is not None
        process.stdin.close()
        assert process.wait(timeout=_STARTUP_TIMEOUT_SECONDS) == RuntimeExitReason.SUPERVISOR_STOP
        assert process.stdout is not None
        assert process.stdout.read() == b"", "standard output carries only the readiness line"
    with pytest.raises(RuntimeRefusalError) as refusal:
        _endpoint(root).connect(timeout=0.2)
    assert refusal.value.reason is RuntimeRefusalCode.ENDPOINT_NOT_READY


def test_without_an_explicit_root_the_runtime_refuses_and_creates_nothing(tmp_path: Path) -> None:
    with _caller_owned(_environment(None), tmp_path) as process:
        _output, errors = process.communicate(timeout=_STARTUP_TIMEOUT_SECONDS)
        assert process.returncode == RuntimeExitReason.ROOT_MISMATCH
        assert errors.decode().strip().splitlines()[-1] == RuntimeRefusalCode.ROOT_MISMATCH.value


@pytest.mark.parametrize("relation", ["same", "inside", "containing"])
def test_a_root_overlapping_the_installed_default_is_refused_untouched(tmp_path: Path, relation: str) -> None:
    home = tmp_path / "home"
    home.mkdir()
    environment = _environment(None)
    for name in ("LOCALAPPDATA", "APPDATA", "USERPROFILE", "HOME", "XDG_DATA_HOME"):
        environment[name] = str(home)
    default = host_installed_default_root(environment)
    root = {"same": default, "inside": default / "nested", "containing": default.parent}[relation]
    environment["CADRUMO_LOCAL_STORAGE_ROOT"] = str(root)
    before = sorted(home.rglob("*"))
    with _caller_owned(environment, tmp_path) as process:
        process.communicate(timeout=_STARTUP_TIMEOUT_SECONDS)
        assert process.returncode == RuntimeExitReason.ROOT_MISMATCH
    assert sorted(home.rglob("*")) == before
