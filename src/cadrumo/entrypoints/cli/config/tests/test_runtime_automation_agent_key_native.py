"""The installed MCP server presenting a key the person issued for an agent reads and edits the profile.

The person issues the key with the real ``config profile automation create
--use agent --category tax_values`` command against the installed runtime
process, and approves it with the profile password from a separate signed-in
connection. A fresh ``cadrumo-mcp --profile-id ... --credential-reference ...``
process then reads a profile value, patches the profile, mutates a field and
adds, updates and removes a row, reading each change back, and is refused
everything once the person revokes the key.

Both the runtime and the command keep the key in this logon session's OS
credential store. A logon whose store refuses, such as a Windows network or
SSH logon answering WinError 1312, cannot hold the key at all, so the case is
skipped there under a warning that says it was not verified. The same flow
with the store held by the test runs in
``cadrumo.entrypoints.cli.config.tests.test_runtime_automation_agent_key``.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import sysconfig
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
from contextvars import copy_context
from importlib.metadata import version
from pathlib import Path
from typing import cast
from uuid import UUID

import pytest
from click.testing import Result
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

from cadrumo.adapters.local_runtime.automation_decision import run_automation_decision
from cadrumo.adapters.local_runtime.automation_inventory import read_automation_inventory
from cadrumo.adapters.local_runtime.framing import VerifiedRuntimeConnection
from cadrumo.adapters.local_runtime.frontend_client import RuntimeFrontendClient
from cadrumo.adapters.local_runtime.installation import runtime_installation
from cadrumo.adapters.local_runtime.tests.profile_worker_support import PROFILE_INPUT, worker_profiles
from cadrumo.adapters.local_runtime.windows import WindowsRuntimeEndpoint
from cadrumo.adapters.local_runtime.windows_process import WindowsProcessScope
from cadrumo.adapters.persistence.storage.custody.acceleration_receipt import delete_profile_session
from cadrumo.adapters.persistence.storage.custody.automation_native_identity import CLIENT_NAMESPACE
from cadrumo.adapters.persistence.storage.custody.automation_store_composition import installed_automation_secret_store
from cadrumo.application.auth.auth_read_contracts import AUTH_READ_OPERATION_DEFINITION_ID
from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.runtime.contracts import RuntimeClientHello, RuntimeRefusalCode, RuntimeRefusalError
from cadrumo.application.user_profile.access_contracts import DisclosureCategory
from cadrumo.application.user_profile.automation_enrollment import EnrollmentStage
from cadrumo.application.user_profile.automation_lifecycle import AutomationDenialKind
from cadrumo.application.user_profile.history_operation import PROFILE_HISTORY_OPERATION_DEFINITION_ID
from cadrumo.core.config import override_settings
from cadrumo.core.storage_environment import ChildEnvironmentProfile, child_environment
from cadrumo.entrypoints.cli.tests.cli_runner import invoke_cached_cli
from cadrumo.tests.os_keychain_hook import require_os_credential_store
from cadrumo_harness.mcp.tests.agent_key_reads import edit_profile_and_read_back, settled_result, tool_document

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.os_keychain,
    pytest.mark.skipif(sys.platform != "win32", reason="requires installed Windows MCP and runtime launchers"),
    pytest.mark.usefixtures("authority_operation"),
]

_SCRIPTS = Path(sysconfig.get_path("scripts"))


def _connect(endpoint: WindowsRuntimeEndpoint, profile_id: UUID, *, deadline: float) -> RuntimeFrontendClient:
    raw = VerifiedRuntimeConnection(
        endpoint.connect(timeout=3),
        expected=RuntimeClientHello(product_version=version("cadrumo"), storage_identity=endpoint.storage_identity),
        deadline=deadline,
    )
    return RuntimeFrontendClient(raw, profile_id=profile_id, frontend=OperationFrontendProjection.CLI)


def _await_runtime(endpoint: WindowsRuntimeEndpoint) -> None:
    deadline = time.monotonic() + 60
    while True:
        try:
            VerifiedRuntimeConnection(
                endpoint.connect(timeout=0.2),
                expected=RuntimeClientHello(
                    product_version=version("cadrumo"), storage_identity=endpoint.storage_identity
                ),
                deadline=deadline,
            ).close()
            return
        except RuntimeRefusalError as error:
            if error.reason is not RuntimeRefusalCode.ENDPOINT_NOT_READY or time.monotonic() >= deadline:
                raise
            time.sleep(0.05)


def _person(endpoint: WindowsRuntimeEndpoint, profile_id: UUID) -> RuntimeFrontendClient:
    person = _connect(endpoint, profile_id, deadline=time.monotonic() + 5)
    person.login_password(bytearray(PROFILE_INPUT.encode()), timeout=90)
    return person


async def _agent(root: Path, profile_id: UUID, reference: UUID, revoke: Callable[[], object]) -> None:
    environment = child_environment(ChildEnvironmentProfile.STRICT, root)
    environment["PYTHONIOENCODING"] = "utf-8"
    server = StdioServerParameters(
        command=str((_SCRIPTS / "cadrumo-mcp.exe").resolve(strict=True)),
        args=["--profile-id", str(profile_id), "--credential-reference", str(reference)],
        env=environment,
        cwd=root,
    )
    async with asyncio.timeout(600):
        with (root.parent / "mcp.stderr").open("w", encoding="utf-8") as stderr:
            async with (
                stdio_client(server, errlog=stderr) as (read_stream, write_stream),
                ClientSession(read_stream, write_stream, read_timeout_seconds=120) as sdk,
            ):
                await sdk.initialize()
                status = tool_document(await sdk.call_tool("status", {}))
                assert status["session"] == "key", status
                inside = tool_document(
                    await settled_result(
                        sdk,
                        profile_id,
                        AUTH_READ_OPERATION_DEFINITION_ID,
                        {"profile_id": str(profile_id), "kind": "status"},
                    )
                )
                assert inside["document"]["projection"]["profile_id"] == str(profile_id)
                await edit_profile_and_read_back(sdk, profile_id)
                # Tax values were granted too, so the history that discloses both is released.
                history = tool_document(
                    await settled_result(
                        sdk, profile_id, PROFILE_HISTORY_OPERATION_DEFINITION_ID, {"profile_id": str(profile_id)}
                    )
                )
                assert history["outcome"] == "reply", history
                await asyncio.to_thread(revoke)
                refused = await sdk.call_tool("describe", {"definition_id": AUTH_READ_OPERATION_DEFINITION_ID})
                assert refused.is_error is True
                assert isinstance(refused.structured_content, dict)
                assert refused.structured_content["outcome"] == "refused", refused.structured_content


def test_the_installed_mcp_server_of_a_key_issued_for_an_agent_reads_and_edits_the_profile(tmp_path: Path) -> None:
    require_os_credential_store()
    runtime_executable, mcp_executable = _SCRIPTS / "cadrumo-runtime.exe", _SCRIPTS / "cadrumo-mcp.exe"
    assert runtime_executable.is_file() and mcp_executable.is_file(), "install the development entry points first"
    with worker_profiles(tmp_path) as (root, targets), ExitStack() as cleanup:
        profile_id = targets[-1][0].binding.profile_id
        delete_profile_session(storage_root=root, profile_id=profile_id)
        endpoint = WindowsRuntimeEndpoint(storage_root=root)
        cleanup.callback(endpoint.close)
        runtime_installation(
            storage_root=root, os_owner_id=endpoint.os_owner_id, storage_identity=endpoint.storage_identity
        )
        scope = WindowsProcessScope()
        cleanup.callback(scope.terminate, timeout=5)
        environment = {
            name: value for name, value in os.environ.items() if not name.upper().startswith(("PYTHON", "LD_", "DYLD_"))
        }
        environment["CADRUMO_LOCAL_STORAGE_ROOT"] = str(root)
        scope.launch(
            executable=runtime_executable.resolve(strict=True),
            arguments=(
                "--storage-root",
                str(root),
                "--storage-identity",
                endpoint.storage_identity,
                "--expected-version",
                version("cadrumo"),
            ),
            directory=root,
            environment=environment,
        )
        _await_runtime(endpoint)

        def create() -> Result:
            with override_settings(
                cadrumo_local_storage_root=root, cadrumo_output_language="en", cadrumo_cli_reveal_identifiers=True
            ):
                return invoke_cached_cli(
                    (
                        "--format",
                        "json",
                        "--profile",
                        str(profile_id),
                        "config",
                        "profile",
                        "automation",
                        "create",
                        "--use",
                        "agent",
                        "--category",
                        "tax_values",
                    )
                )

        with ThreadPoolExecutor(max_workers=1) as pool:
            creating = pool.submit(copy_context().run, create)
            person = _person(endpoint, profile_id)
            try:
                deadline = time.monotonic() + 120
                while not (requests := read_automation_inventory(person).projection.requests):
                    assert not creating.done(), creating.result()
                    assert time.monotonic() < deadline, "the request never reached the person"
                    time.sleep(0.5)
                (review,) = requests
                assert {item.category for item in review.proposal.scope.disclosure_categories} == {
                    DisclosureCategory.PROFILE_VALUES,
                    DisclosureCategory.OPERATION_METADATA,
                    DisclosureCategory.TAX_VALUES,
                }
                approved = run_automation_decision(
                    person, review, decision="approve", password=bytearray(PROFILE_INPUT.encode())
                )
                assert approved.receipt.stage is EnrollmentStage.COMPLETE
            finally:
                person.close()
            created = cast(Result, creating.result(timeout=120))
        assert created.exit_code == 0, created.output
        result = json.loads(created.stdout)["result"]
        reference, key_id = UUID(result["credential_reference"]), UUID(result["terminal"]["key_id"])
        cleanup.callback(installed_automation_secret_store().delete, CLIENT_NAMESPACE, str(reference))

        def revoke() -> None:
            person = _person(endpoint, profile_id)
            try:
                person.deny_automation(AutomationDenialKind.KEY, target_id=key_id)
            finally:
                person.close()

        asyncio.run(_agent(root, profile_id, reference, revoke))
