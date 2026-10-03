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
from cadrumo.domain.calculations.registry.authority_store import AUTHORITY_DESCRIPTOR_FILENAME, AuthorityDescriptor

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows runtime ownership and pipes"),
]


def _publish_descriptor(root: Path, logical_generation: str) -> Path:
    """Select a published generation the way a republish does: by its descriptor alone."""
    root.mkdir()
    descriptor = AuthorityDescriptor(
        database=f"authority-{'1' * 64}.sqlite3",
        database_size=1,
        database_sha256="1" * 64,
        logical_generation=logical_generation,
    )
    (root / AUTHORITY_DESCRIPTOR_FILENAME).write_bytes(descriptor.to_bytes())
    return root


@pytest.mark.parametrize("cohort", ["installed", "wrong", "republished"])
def test_installed_client_accepts_only_the_matching_native_cohort(tmp_path: Path, cohort: str) -> None:
    """The cohort is the package version and, when both sides name one, the published authority generation."""
    endpoint = WindowsRuntimeEndpoint(storage_root=tmp_path)
    stop = Event()
    host = RuntimeTransportServer(
        endpoint,
        product_version=version("cadrumo") if cohort != "wrong" else "another-installed-cohort",
        stop=stop,
        # The runtime admitted its generation at boot; the frontend reads the republished one.
        authority_generation="a" * 64,
    )
    authority_root = _publish_descriptor(tmp_path / "authority", "b" * 64 if cohort == "republished" else "a" * 64)
    with (
        override_settings(cadrumo_local_storage_root=tmp_path, cadrumo_authority_root=authority_root),
        ThreadPoolExecutor(max_workers=1) as pool,
    ):
        running = pool.submit(host.serve)
        try:
            assert host.ready.wait(3)
            profile_id = uuid4()
            if cohort != "installed":
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
