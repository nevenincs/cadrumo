"""A started `cadrumo-mcp` process with no enrolled key reaches the runtime's answer about the sign-in.

In-process tests share one interpreter in which the profile login-session port
is already bound, so they cannot show that the server process binds it itself.
This drives the console script in a fresh process against a real runtime and a
profile with no stored sign-in: the runtime's typed denial must come back, and
the failure of a missing port must not be read as an unavailable runtime.

It needs the normal development environment's installed entry points
(`cadrumo-mcp.exe`, `cadrumo-runtime.exe`) and Windows IPC. The process, its
runtime and its storage are all created and removed by the test.
"""

from __future__ import annotations

import asyncio
import os
import sys
import sysconfig
import time
from contextlib import ExitStack
from importlib.metadata import version
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

from cadrumo.adapters.local_runtime.framing import VerifiedRuntimeConnection
from cadrumo.adapters.local_runtime.installation import runtime_installation
from cadrumo.adapters.local_runtime.windows import WindowsRuntimeEndpoint
from cadrumo.adapters.local_runtime.windows_process import WindowsProcessScope
from cadrumo.adapters.persistence.storage.profile_persistence_composition import composed_profile_persistence_ports
from cadrumo.adapters.persistence.storage.tests.profile_capsule_runtime import publish_test_profile_capsule
from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_profile_storage_root
from cadrumo.application.runtime.contracts import RuntimeClientHello, RuntimeRefusalCode, RuntimeRefusalError
from cadrumo.core.storage_environment import ChildEnvironmentProfile, child_environment
from cadrumo_harness.mcp.protocol_contract import SIGN_IN_REMEDY

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint, pytest.mark.windows_only]


async def _call_status_and_a_profile_tool(
    executable: Path, *, arguments: tuple[str, ...], storage_root: Path
) -> tuple[tuple[bool, dict[str, Any]], tuple[bool, dict[str, Any]]]:
    """Ask a fresh server process for its status and for one tool that needs the profile."""
    environment = child_environment(ChildEnvironmentProfile.STRICT, storage_root)
    environment["PYTHONIOENCODING"] = "utf-8"
    server = StdioServerParameters(
        command=str(executable.resolve(strict=True)), args=list(arguments), env=environment, cwd=storage_root
    )
    async with asyncio.timeout(120):
        with open(os.devnull, "w", encoding="utf-8") as stderr:
            async with (
                stdio_client(server, errlog=stderr) as (read_stream, write_stream),
                ClientSession(read_stream, write_stream, read_timeout_seconds=90) as client,
            ):
                await client.initialize()
                status = await client.call_tool("status", {})
                private = await client.call_tool("observe", {"observation": {}})
    assert isinstance(status.structured_content, dict)
    assert isinstance(private.structured_content, dict)
    return (status.is_error, status.structured_content), (private.is_error, private.structured_content)


@pytest.mark.skipif(sys.platform != "win32", reason="requires installed Windows MCP and runtime launchers")
def test_a_fresh_server_process_with_no_key_and_no_stored_sign_in_answers_authentication_required(
    tmp_path: Path,
) -> None:
    """Both ways of starting without a key resume to the runtime's denial, not to an unavailable runtime."""
    scripts = Path(sysconfig.get_path("scripts"))
    mcp_executable, runtime_executable = scripts / "cadrumo-mcp.exe", scripts / "cadrumo-runtime.exe"
    assert mcp_executable.is_file() and runtime_executable.is_file(), "install the development entry points first"

    profile_id = uuid4()
    with isolated_profile_storage_root(tmp_path=tmp_path) as storage_root, ExitStack() as cleanup:
        storage_root.mkdir(parents=True, exist_ok=True)
        endpoint = WindowsRuntimeEndpoint(storage_root=storage_root)
        cleanup.callback(endpoint.close)
        scope = WindowsProcessScope()
        cleanup.callback(scope.terminate, timeout=5)
        runtime_installation(
            storage_root=storage_root, os_owner_id=endpoint.os_owner_id, storage_identity=endpoint.storage_identity
        )
        with composed_profile_persistence_ports():
            publish_test_profile_capsule(profile_id, label="Installed MCP sign-in resume", root=storage_root)

        runtime_environment = {
            name: value for name, value in os.environ.items() if not name.upper().startswith(("PYTHON", "LD_", "DYLD_"))
        }
        runtime_environment["CADRUMO_LOCAL_STORAGE_ROOT"] = str(storage_root)
        scope.launch(
            executable=runtime_executable.resolve(strict=True),
            arguments=(
                "--storage-root",
                str(storage_root),
                "--storage-identity",
                endpoint.storage_identity,
                "--expected-version",
                version("cadrumo"),
            ),
            directory=storage_root,
            environment=runtime_environment,
        )
        deadline = time.monotonic() + 30
        while True:
            try:
                VerifiedRuntimeConnection(
                    endpoint.connect(timeout=0.2),
                    expected=RuntimeClientHello(
                        product_version=version("cadrumo"), storage_identity=endpoint.storage_identity
                    ),
                    deadline=deadline,
                ).close()
                break
            except RuntimeRefusalError as error:
                if error.reason is not RuntimeRefusalCode.ENDPOINT_NOT_READY or time.monotonic() >= deadline:
                    raise
                time.sleep(0.05)

        for arguments in (("--profile-id", str(profile_id)), ()):
            (status_error, status), (private_error, private) = asyncio.run(
                _call_status_and_a_profile_tool(mcp_executable, arguments=arguments, storage_root=storage_root)
            )
            assert status_error is False, arguments
            assert status == {
                "outcome": "status",
                "profile_id": str(profile_id),
                "authenticated": False,
                "session": "none",
                "surface": "full",
                "denial": "authentication_required",
                # No sign-in is stored, as the command line reports beside the same code.
                "sign_in_reason": "absent",
                "remedy": SIGN_IN_REMEDY,
            }, arguments
            assert private_error is True, arguments
            assert private == {
                "outcome": "refused",
                "code": "authentication_required",
                "sign_in_reason": "absent",
                "remedy": SIGN_IN_REMEDY,
            }, arguments
