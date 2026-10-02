"""Installed runtime startup over real native ownership and IPC.

Synthetic roots contain no taxpayer profiles. Test-owned Windows jobs or POSIX
process groups clean up the installed launchers after every assertion outcome.
This cleanup does not establish private worker or platform lifecycle acceptance.
"""

from __future__ import annotations

import os
import select
import signal
import socket
import subprocess
import sys
import sysconfig
import time
from contextlib import ExitStack, suppress
from importlib.metadata import version
from pathlib import Path
from typing import BinaryIO
from uuid import uuid4

import pytest

from cadrumo.adapters.local_runtime.framing import VerifiedRuntimeConnection
from cadrumo.adapters.local_runtime.posix import PosixRuntimeEndpoint, posix_owner_uid
from cadrumo.adapters.local_runtime.windows import WindowsRuntimeEndpoint
from cadrumo.adapters.local_runtime.windows_process import WindowsOwnedProcess, WindowsProcessScope
from cadrumo.application.runtime.contracts import RuntimeClientHello, RuntimeRefusalCode, RuntimeRefusalError
from cadrumo.application.runtime.transport import RuntimeStatusRequest

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.skipif(
        sys.platform not in {"win32", "linux", "darwin"}, reason="requires supported native installed runtime transport"
    ),
]

type _Endpoint = WindowsRuntimeEndpoint | PosixRuntimeEndpoint
type _Process = WindowsOwnedProcess | subprocess.Popen[bytes]
type _Launch = tuple[WindowsProcessScope | None, _Process]


def _terminate(launch: _Launch) -> None:
    scope, process = launch
    if scope is not None:
        scope.terminate(timeout=3)
    elif isinstance(process, subprocess.Popen) and sys.platform in {"linux", "darwin"}:
        # The unreaped direct child pins this process-group identity across the
        # exit race. Public startup launches no private workers or detached jobs.
        if process.poll() is None:
            with suppress(ProcessLookupError):
                os.killpg(process.pid, signal.SIGKILL)
        process.wait(timeout=3)


def _active(launch: _Launch) -> bool:
    scope, process = launch
    if scope is not None:
        return bool(scope.active_process_ids())
    assert isinstance(process, subprocess.Popen)
    return process.poll() is None


def _wait(process: _Process, *, timeout: float) -> int:
    try:
        return process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        raise RuntimeRefusalError(RuntimeRefusalCode.DEADLINE_EXCEEDED) from None


def launch(
    resources: ExitStack,
    root: Path,
    identity: str,
    *,
    cohort: str | None = None,
    startup_stderr: BinaryIO | None = None,
) -> _Launch:
    name = "cadrumo-runtime.exe" if sys.platform == "win32" else "cadrumo-runtime"
    executable = Path(sysconfig.get_path("scripts")) / name
    assert executable.is_file(), "install the current project entrypoints before installed acceptance"
    environment = os.environ.copy()
    # The isolated bootstrap must not let this path replace application modules.
    environment["PYTHONPATH"] = str(root / "untrusted-imports")
    arguments = (
        "--storage-root",
        str(root),
        "--storage-identity",
        identity,
        "--expected-version",
        cohort or version("cadrumo"),
        "--managed-session",
    )
    if sys.platform == "win32":
        if startup_stderr is not None:
            raise ValueError("startup stderr capture requires a POSIX launcher")
        scope = WindowsProcessScope()
        resources.callback(scope.terminate, timeout=3)
        return scope, scope.launch(executable=executable, arguments=arguments, directory=root, environment=environment)
    process = subprocess.Popen(  # noqa: S603 -- exact installed console executable; no shell or private operands.
        (str(executable), *arguments),
        cwd=root,
        env=environment,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL if startup_stderr is None else startup_stderr,
        close_fds=True,
        start_new_session=True,
    )
    launched = None, process
    resources.callback(_terminate, launched)
    return launched


def connect(endpoint: _Endpoint) -> VerifiedRuntimeConnection:
    deadline = time.monotonic() + 20
    while True:
        try:
            channel = endpoint.connect(timeout=0.2)
            return VerifiedRuntimeConnection(
                channel,
                expected=RuntimeClientHello(
                    product_version=version("cadrumo"), storage_identity=endpoint.storage_identity
                ),
                deadline=deadline,
            )
        except RuntimeRefusalError as error:
            if error.reason is not RuntimeRefusalCode.ENDPOINT_NOT_READY or time.monotonic() >= deadline:
                raise
            time.sleep(0.05)


def test_installed_launches_converge_and_restart_changes_boot_identity(tmp_path: Path) -> None:
    endpoint = (
        WindowsRuntimeEndpoint(storage_root=tmp_path)
        if sys.platform == "win32"
        else PosixRuntimeEndpoint(storage_root=tmp_path)
    )
    clients: list[VerifiedRuntimeConnection] = []
    with ExitStack() as resources:
        resources.callback(endpoint.close)
        launches = [launch(resources, tmp_path, endpoint.storage_identity) for _ in range(3)]
        for _ in launches:
            client = connect(endpoint)
            resources.callback(client.close)
            clients.append(client)
        statuses = [
            client.status(RuntimeStatusRequest(request_id=uuid4()), deadline=time.monotonic() + 3) for client in clients
        ]
        assert len({item.runtime_boot_id for item in statuses}) == 1
        assert len({item.connection_id for item in statuses}) == 3
        deadline = time.monotonic() + 3
        while sum(_active(launched) for launched in launches) != 1 and time.monotonic() < deadline:
            time.sleep(0.02)
        assert sum(_active(launched) for launched in launches) == 1
        for launched in launches:
            _scope, process = launched
            if _active(launched):
                with pytest.raises(RuntimeRefusalError) as waiting:
                    _wait(process, timeout=0)
                assert waiting.value.reason is RuntimeRefusalCode.DEADLINE_EXCEEDED
            else:
                assert _wait(process, timeout=0) == 2
        first_boot = statuses[0].runtime_boot_id
        for client in clients:
            client.close()
        clients.clear()
        for launched in launches:
            _terminate(launched)
        launch(resources, tmp_path / ".", endpoint.storage_identity)
        fresh = connect(endpoint)
        resources.callback(fresh.close)
        clients.append(fresh)
        status = fresh.status(RuntimeStatusRequest(request_id=uuid4()), deadline=time.monotonic() + 3)
        assert status.runtime_boot_id != first_boot
        assert not tuple(tmp_path.iterdir()), "transport startup must not initialize private profile storage"


@pytest.mark.parametrize("mismatch", ["version", "root"])
def test_installed_mismatch_exits_without_claiming_endpoint(tmp_path: Path, mismatch: str) -> None:
    endpoint = (
        WindowsRuntimeEndpoint(storage_root=tmp_path)
        if sys.platform == "win32"
        else PosixRuntimeEndpoint(storage_root=tmp_path)
    )
    with ExitStack() as resources:
        resources.callback(endpoint.close)
        _scope, process = launch(
            resources,
            tmp_path,
            "0" * 64 if mismatch == "root" else endpoint.storage_identity,
            cohort="unsupported-cohort" if mismatch == "version" else None,
        )
        assert _wait(process, timeout=20) == 2
        with pytest.raises(RuntimeRefusalError) as refusal:
            endpoint.connect(timeout=0.2)
        assert refusal.value.reason is RuntimeRefusalCode.ENDPOINT_NOT_READY
        endpoint.listen()
        assert not tuple(tmp_path.iterdir()), "refused startup must not initialize private profile storage"


@pytest.mark.skipif(sys.platform != "linux", reason="requires installed Linux Unix-socket ownership")
def test_installed_runtime_refuses_foreign_endpoint_without_contact_or_replacement(tmp_path: Path) -> None:
    endpoint = PosixRuntimeEndpoint(storage_root=tmp_path)
    namespace = Path("/").joinpath("tmp", f"cdr-{posix_owner_uid()}")
    endpoint_path = namespace / f"{endpoint.storage_identity[:32]}.sock"
    foreign_path = namespace / f"foreign-{uuid4().hex}.sock"
    with ExitStack() as resources:
        resources.callback(endpoint.close)
        foreign = resources.enter_context(socket.socket(socket.AF_UNIX, socket.SOCK_STREAM))
        foreign.bind(str(foreign_path))
        resources.callback(foreign_path.unlink)
        foreign.listen(1)
        endpoint_path.symlink_to(foreign_path)
        resources.callback(endpoint_path.unlink)

        with pytest.raises(RuntimeRefusalError) as initial:
            endpoint.connect(timeout=0.2)
        assert initial.value.reason is RuntimeRefusalCode.ENDPOINT_UNTRUSTED

        _scope, process = launch(resources, tmp_path, endpoint.storage_identity)
        assert _wait(process, timeout=20) == 2
        with pytest.raises(RuntimeRefusalError) as after_refusal:
            endpoint.connect(timeout=0.2)
        assert after_refusal.value.reason is RuntimeRefusalCode.ENDPOINT_UNTRUSTED
        assert endpoint_path.is_symlink() and os.readlink(endpoint_path) == str(foreign_path)
        assert foreign_path.is_socket()
        assert not select.select([foreign], [], [], 0)[0], "the foreign listener must receive no protocol connection"
