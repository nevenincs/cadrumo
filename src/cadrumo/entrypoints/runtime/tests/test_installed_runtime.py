"""Installed Windows runtime startup over real native ownership and IPC.

Synthetic roots contain no taxpayer profiles. Test-owned jobs guarantee cleanup
of console launchers and interpreter descendants even after a failed assertion.
These jobs do not establish the runtime's future operation containment policy.
"""

from __future__ import annotations

import os
import sys
import sysconfig
import time
from importlib.metadata import version
from pathlib import Path
from uuid import uuid4

import pytest

from cadrumo.adapters.local_runtime.framing import VerifiedRuntimeConnection
from cadrumo.adapters.local_runtime.windows import WindowsRuntimeEndpoint
from cadrumo.adapters.local_runtime.windows_process import WindowsProcessScope
from cadrumo.application.runtime.contracts import RuntimeClientHello, RuntimeRefusalCode, RuntimeRefusalError
from cadrumo.application.runtime.transport import RuntimeStatusRequest

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows installed launcher and cleanup jobs"),
]


def launch(scope: WindowsProcessScope, root: Path, identity: str, *, cohort: str | None = None):
    executable = Path(sysconfig.get_path("scripts")) / "cadrumo-runtime.exe"
    assert executable.is_file(), "install the current project entrypoints before installed acceptance"
    environment = os.environ.copy()
    # The isolated bootstrap must not let this path replace application modules.
    environment["PYTHONPATH"] = str(root / "untrusted-imports")
    return scope.launch(
        executable=executable,
        arguments=(
            "--storage-root",
            str(root),
            "--storage-identity",
            identity,
            "--expected-version",
            cohort or version("cadrumo"),
            "--managed-session",
        ),
        directory=root,
        environment=environment,
    )


def connect(endpoint: WindowsRuntimeEndpoint) -> VerifiedRuntimeConnection:
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
    scopes = [WindowsProcessScope() for _ in range(3)]
    endpoint = WindowsRuntimeEndpoint(storage_root=tmp_path)
    clients: list[VerifiedRuntimeConnection] = []
    try:
        processes = [launch(scope, tmp_path, endpoint.storage_identity) for scope in scopes]
        for _ in scopes:
            clients.append(connect(endpoint))
        statuses = [
            client.status(RuntimeStatusRequest(request_id=uuid4()), deadline=time.monotonic() + 3) for client in clients
        ]
        assert len({item.runtime_boot_id for item in statuses}) == 1
        assert len({item.connection_id for item in statuses}) == 3
        deadline = time.monotonic() + 3
        while sum(bool(scope.active_process_ids()) for scope in scopes) != 1 and time.monotonic() < deadline:
            time.sleep(0.02)
        assert sum(bool(scope.active_process_ids()) for scope in scopes) == 1
        for scope, process in zip(scopes, processes, strict=True):
            if scope.active_process_ids():
                with pytest.raises(RuntimeRefusalError) as waiting:
                    process.wait(timeout=0)
                assert waiting.value.reason is RuntimeRefusalCode.DEADLINE_EXCEEDED
            else:
                assert process.wait(timeout=0) == 2
        first_boot = statuses[0].runtime_boot_id
        for client in clients:
            client.close()
        clients.clear()
        for scope in scopes:
            scope.terminate(timeout=3)
        replacement = WindowsProcessScope()
        scopes.append(replacement)
        launch(replacement, tmp_path / ".", endpoint.storage_identity)
        fresh = connect(endpoint)
        clients.append(fresh)
        status = fresh.status(RuntimeStatusRequest(request_id=uuid4()), deadline=time.monotonic() + 3)
        assert status.runtime_boot_id != first_boot
        assert not tuple(tmp_path.iterdir()), "transport startup must not initialize private profile storage"
    finally:
        for client in clients:
            client.close()
        for scope in scopes:
            scope.terminate(timeout=3)
        endpoint.close()


@pytest.mark.parametrize("mismatch", ["version", "root"])
def test_installed_mismatch_exits_without_claiming_endpoint(tmp_path: Path, mismatch: str) -> None:
    endpoint = WindowsRuntimeEndpoint(storage_root=tmp_path)
    scope = WindowsProcessScope()
    try:
        process = launch(
            scope,
            tmp_path,
            "0" * 64 if mismatch == "root" else endpoint.storage_identity,
            cohort="unsupported-cohort" if mismatch == "version" else None,
        )
        assert process.wait(timeout=20) == 2
        with pytest.raises(RuntimeRefusalError) as refusal:
            endpoint.connect(timeout=0.2)
        assert refusal.value.reason is RuntimeRefusalCode.ENDPOINT_NOT_READY
        endpoint.listen()
    finally:
        scope.terminate(timeout=3)
        endpoint.close()
