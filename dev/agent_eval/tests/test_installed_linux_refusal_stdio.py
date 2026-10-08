"""Installed Linux MCP preserves public stdio when native custody refuses admission.

The encrypted profile is synthetic. Both console processes use their native
runtime composition, with no login or credential-store override. The installed
Linux factory selects its explicit Secret Service adapter. A read of one fresh
reference establishes missing, unavailable or locked custody without a native
write or enumeration. This does not establish a desktop login lifecycle.
"""

from __future__ import annotations

import asyncio
import subprocess
import sys
import sysconfig
from contextlib import ExitStack
from importlib.metadata import version
from pathlib import Path
from uuid import uuid4

import pytest
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

from cadrumo.adapters.local_runtime.installation import runtime_installation
from cadrumo.adapters.local_runtime.posix import posix_owner_uid
from cadrumo.adapters.local_runtime.posix_endpoint import PosixRuntimeEndpoint
from cadrumo.adapters.persistence.storage.custody.automation_native_identity import CLIENT_NAMESPACE
from cadrumo.adapters.persistence.storage.custody.automation_secret_store import native_automation_secret_store
from cadrumo.adapters.persistence.storage.custody.linux_secret_service_store import (
    LinuxSecretServiceAutomationSecretStore,
)
from cadrumo.adapters.persistence.storage.profile_persistence_composition import composed_profile_persistence_ports
from cadrumo.adapters.persistence.storage.tests.profile_capsule_runtime import publish_test_profile_capsule
from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_profile_storage_root
from cadrumo.application.user_profile.automation_custody_port import (
    AutomationCustodyCode,
    AutomationCustodyError,
    NativeSecretBackend,
)
from cadrumo.entrypoints.runtime.tests.test_installed_runtime import connect, launch

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.serial,
    pytest.mark.skipif(sys.platform != "linux", reason="requires the installed native Linux consoles"),
]


@pytest.fixture
def anyio_backend() -> str:
    """Use the asyncio backend required by the bounded SDK session."""
    return "asyncio"


@pytest.mark.anyio
async def test_installed_linux_native_reference_refusal_preserves_public_stdio(tmp_path: Path) -> None:
    executable = Path(sysconfig.get_path("scripts")) / "cadrumo-mcp"
    assert executable.is_file(), "the installed MCP entry point is required"
    profile_id, reference = uuid4(), uuid4()
    native_store = native_automation_secret_store(NativeSecretBackend.LINUX_DBUS)
    assert native_store.backend is NativeSecretBackend.LINUX_DBUS
    assert isinstance(native_store, LinuxSecretServiceAutomationSecretStore)
    try:
        existing = native_store.read(CLIENT_NAMESPACE, str(reference))
    except AutomationCustodyError as error:
        assert error.reason in {AutomationCustodyCode.UNAVAILABLE, AutomationCustodyCode.NEEDS_USER}
        denial = error.reason.value
    else:
        assert existing is None, "the fresh synthetic reference must be absent"
        denial = AutomationCustodyCode.MISSING.value
    with isolated_profile_storage_root(tmp_path=tmp_path) as storage_root, ExitStack() as resources:
        storage_root.mkdir(parents=True, exist_ok=True)
        endpoint = PosixRuntimeEndpoint(storage_root=storage_root)
        resources.callback(endpoint.close)
        runtime_installation(
            storage_root=storage_root,
            os_owner_id=str(posix_owner_uid()),
            storage_identity=endpoint.storage_identity,
        )
        with composed_profile_persistence_ports():
            publish_test_profile_capsule(profile_id, label="Installed Linux MCP synthetic refusal", root=storage_root)
        startup_log_path = tmp_path / "installed-linux-runtime-startup.stderr"
        startup_log = resources.enter_context(startup_log_path.open("wb"))
        _scope, process = launch(resources, storage_root, endpoint.storage_identity, startup_stderr=startup_log)
        assert isinstance(process, subprocess.Popen)
        try:
            connection = connect(endpoint)
        except BaseException as error:
            # Keep the readiness error and cleanup owner. Read a finite excerpt
            # using a separate descriptor so the child's log offset is intact.
            try:
                child_exit_status = process.poll()
            except OSError:
                error.add_note("installed runtime child exit status could not be read")
            else:
                error.add_note(f"installed runtime child exit status: {child_exit_status!r} (None means still running)")
            try:
                with startup_log_path.open("rb") as captured:
                    size = captured.seek(0, 2)
                    captured.seek(max(0, size - 8192))
                    startup_stderr = captured.read(8192).decode("utf-8", errors="replace")
            except OSError:
                error.add_note("installed runtime startup stderr could not be read")
            else:
                error.add_note(f"installed runtime startup stderr (last 8192 bytes):\n{startup_stderr}")
            raise
        resources.callback(connection.close)

        # The same never-written reference must retain the exact native
        # preflight refusal through the installed MCP process.
        parameters = StdioServerParameters(
            command=str(executable.resolve(strict=True)),
            args=["--profile-id", str(profile_id), "--credential-reference", str(reference)],
            cwd=storage_root,
            env={
                "CADRUMO_LOCAL_STORAGE_ROOT": str(storage_root),
                "CADRUMO_MCP_REQUIRED_VERSION": version("cadrumo"),
                "PYDANTIC_DISABLE_PLUGINS": "__all__",
            },
        )
        async with asyncio.timeout(120):
            with (tmp_path / "installed-linux-mcp-refusal.stderr").open("w", encoding="utf-8") as error_log:
                async with (
                    stdio_client(parameters, errlog=error_log) as (reader, writer),
                    ClientSession(reader, writer, read_timeout_seconds=60) as client,
                ):
                    await client.initialize()
                    names = {tool.name for tool in (await client.list_tools()).tools}
                    assert {
                        "status",
                        "authority",
                        "authenticate",
                        "search",
                        "describe",
                        "execute",
                        "observe",
                        "result",
                        "result_page",
                    } <= names
                    status_call = await client.call_tool("status", {})
                    assert status_call.is_error is False
                    status = status_call.structured_content
                    assert isinstance(status, dict)
                    assert status == {
                        "outcome": "status",
                        "profile_id": str(profile_id),
                        "authenticated": False,
                        "denial": denial,
                    }
                    refusal = {"outcome": "refused", "code": denial}
                    for name, arguments in (
                        ("search", {"query": "auth.local-read"}),
                        ("describe", {"definition_id": "auth.local-read"}),
                        (
                            "execute",
                            {
                                "definition_id": "auth.local-read",
                                "subject_ref": f"profile:{profile_id}",
                                "payload": {"profile_id": str(profile_id), "kind": "status"},
                            },
                        ),
                        ("observe", {"observation": {}}),
                        ("result", {"result": {}}),
                        ("result_page", {"result": {}, "page": {}}),
                    ):
                        private = await client.call_tool(name, arguments)
                        assert private.is_error is True, name
                        assert private.structured_content == refusal, name
                    public = await client.call_tool("authority", {"query": "modelos"})
                    assert public.is_error is False
                    assert isinstance(public.structured_content, dict)
                    assert public.structured_content["outcome"] == "published"
                    retried = await client.call_tool("authenticate", {"credential_reference": str(reference)})
                    assert retried.is_error is True
                    assert retried.structured_content == refusal
                    after = await client.call_tool("status", {})
                    assert after.is_error is False
                    assert after.structured_content == status
                    assert str(reference) not in repr(after.structured_content)
