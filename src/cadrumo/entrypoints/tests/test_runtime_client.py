"""Installed frontend composition connects to its exact native owner without credentials."""

from __future__ import annotations

import asyncio
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from importlib.metadata import version
from pathlib import Path
from threading import Event
from uuid import uuid4

import pytest

from cadrumo.adapters.local_runtime.runtime_client import open_installed_runtime_client
from cadrumo.adapters.local_runtime.server import RuntimeTransportServer
from cadrumo.adapters.local_runtime.windows import WindowsRuntimeEndpoint
from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from cadrumo.application.runtime.profile_access import RuntimeAccessRefusal, RuntimeSessionRequest
from cadrumo.core.config import override_settings

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows runtime ownership and pipes"),
]


@pytest.mark.parametrize("cohort", ["installed", "wrong"])
def test_installed_client_accepts_only_the_matching_native_cohort(tmp_path: Path, cohort: str) -> None:
    endpoint = WindowsRuntimeEndpoint(storage_root=tmp_path)
    stop = Event()
    host = RuntimeTransportServer(
        endpoint,
        product_version=version("cadrumo") if cohort == "installed" else "another-installed-cohort",
        stop=stop,
    )
    with override_settings(cadrumo_local_storage_root=tmp_path), ThreadPoolExecutor(max_workers=1) as pool:
        running = pool.submit(host.serve)
        try:
            assert host.ready.wait(3)
            profile_id = uuid4()
            if cohort == "wrong":
                with pytest.raises(RuntimeRefusalError) as refusal:
                    asyncio.run(
                        open_installed_runtime_client(
                            profile_id=profile_id, frontend=OperationFrontendProjection.CLI, timeout=3
                        )
                    )
                assert refusal.value.reason is RuntimeRefusalCode.VERSION_MISMATCH
            else:
                client = asyncio.run(
                    open_installed_runtime_client(
                        profile_id=profile_id, frontend=OperationFrontendProjection.CLI, timeout=3
                    )
                )
                try:
                    assert client.profile_id == profile_id
                    assert client.frontend is OperationFrontendProjection.CLI
                    status = client._connection.session(
                        RuntimeSessionRequest(
                            action="session_status", request_id=uuid4(), profile_id=uuid4(), session_id=uuid4()
                        ),
                        deadline=time.monotonic() + 3,
                    )
                    assert status.runtime_boot_id == host.identity.boot_id
                    assert isinstance(status, RuntimeAccessRefusal)
                    assert status.code is RuntimeRefusalCode.UNAVAILABLE
                finally:
                    client.close()
        finally:
            stop.set()
            running.result(timeout=8)
            endpoint.close()


def test_unprovisioned_root_has_no_implicit_runtime_owner(tmp_path: Path) -> None:
    with override_settings(cadrumo_local_storage_root=tmp_path), pytest.raises(RuntimeRefusalError) as refusal:
        asyncio.run(
            open_installed_runtime_client(profile_id=uuid4(), frontend=OperationFrontendProjection.MCP, timeout=3)
        )
    assert refusal.value.reason is RuntimeRefusalCode.UNAVAILABLE
    endpoint = WindowsRuntimeEndpoint(storage_root=tmp_path)
    try:
        endpoint.listen()
    finally:
        endpoint.close()
