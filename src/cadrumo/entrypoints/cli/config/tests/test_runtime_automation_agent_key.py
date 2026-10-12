"""A key the person issues for an agent releases its data categories to the MCP client presenting it.

The person runs ``config profile automation create --use agent`` and approves
the request with the profile password from a separate signed-in connection.
The agent's MCP server then presents the delivered key by reference only,
reads a profile value back, patches the profile, mutates a field and adds,
updates and removes a row, reading each change back, is refused a value
outside the key's categories, and is refused everything once the person
revokes the key.

The command line, the runtime, the native transport, the session authority,
the profile worker, the profile's custody and the MCP server are real. The
native credential store on both sides, the native login the runtime observes
and the MCP SDK's transport (memory) are ports held by the test, so this runs
on a logon session whose credential store refuses; the installed processes and
the real store are exercised by ``test_runtime_automation_agent_key_native``.
"""

from __future__ import annotations

import asyncio
import json
import sys
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from contextvars import copy_context
from importlib.metadata import version
from pathlib import Path
from threading import Event
from typing import cast
from uuid import UUID, uuid4

import pytest
from click.testing import Result

from cadrumo.adapters.local_runtime import runtime_credentials
from cadrumo.adapters.local_runtime.automation_decision import run_automation_decision
from cadrumo.adapters.local_runtime.automation_inventory import read_automation_inventory
from cadrumo.adapters.local_runtime.framing import VerifiedRuntimeConnection
from cadrumo.adapters.local_runtime.frontend_client import RuntimeFrontendClient
from cadrumo.adapters.local_runtime.installation import runtime_installation
from cadrumo.adapters.local_runtime.tests.profile_worker_support import PROFILE_INPUT, owner_id, worker_profiles
from cadrumo.adapters.local_runtime.windows import WindowsRuntimeEndpoint
from cadrumo.adapters.persistence.storage.custody.acceleration_receipt import delete_profile_session
from cadrumo.adapters.persistence.storage.custody.automation_profile import current_automation_profile_binding
from cadrumo.adapters.persistence.storage.custody.automation_store import AutomationControlStore
from cadrumo.adapters.persistence.storage.custody.tests.automation_support import MemoryNativePort
from cadrumo.application.auth.auth_read_contracts import AUTH_READ_OPERATION_DEFINITION_ID
from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.runtime.contracts import RuntimeClientHello
from cadrumo.application.user_profile.access_contracts import (
    Availability,
    DisclosureCategory,
    LoginEligibility,
    OsLockState,
    OsLoginContext,
)
from cadrumo.application.user_profile.automation_enrollment import EnrollmentStage
from cadrumo.application.user_profile.automation_lifecycle import AutomationDenialKind
from cadrumo.application.user_profile.history_operation import PROFILE_HISTORY_OPERATION_DEFINITION_ID
from cadrumo.core.config import override_settings
from cadrumo.entrypoints.cli.config import runtime_automation_request
from cadrumo.entrypoints.cli.tests.cli_runner import invoke_cached_cli
from cadrumo.entrypoints.runtime.profile_connections import RuntimeProfileConnections
from cadrumo_harness.mcp.runtime_adapter import RuntimeMcpAdapter
from cadrumo_harness.mcp.server import build_server
from cadrumo_harness.mcp.tests.agent_key_reads import edit_profile_and_read_back, settled_result, tool_document
from cadrumo_harness.mcp.tests.session import connected_server_and_client_session

from .....adapters.local_runtime.tests.retained_server import RetainedRuntimeTransportServer

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows profile workers"),
    pytest.mark.usefixtures("authority_operation"),
]


class _LoginObservation:
    login_id = "cli-automation-agent-key-login"

    def observe(self, *, credential_facilities: Availability) -> OsLoginContext:
        return OsLoginContext(
            login_id=self.login_id,
            os_owner_id=owner_id(),
            active=True,
            lock_state=OsLockState.UNLOCKED,
            unattended=LoginEligibility.ELIGIBLE,
            credential_facilities=credential_facilities,
        )


def _human(endpoint: WindowsRuntimeEndpoint, profile_id: UUID) -> RuntimeFrontendClient:
    """The person's own signed-in connection, separate from the requesting command."""
    raw = VerifiedRuntimeConnection(
        endpoint.connect(timeout=3),
        expected=RuntimeClientHello(product_version=version("cadrumo"), storage_identity=endpoint.storage_identity),
        deadline=time.monotonic() + 3,
    )
    human = RuntimeFrontendClient(raw, profile_id=profile_id, frontend=OperationFrontendProjection.CLI)
    human.login_password(bytearray(PROFILE_INPUT.encode()), timeout=90)
    return human


async def _agent_reads(profile_id: UUID, reference: UUID, revoke: Callable[[], object]) -> None:
    adapter = RuntimeMcpAdapter(profile_id=profile_id, client=None)
    try:
        await adapter.bootstrap_reference(reference)
        async with connected_server_and_client_session(build_server(adapter)) as sdk:
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

            # The profile history discloses profile and tax values together; tax values were not chosen.
            outside = await settled_result(
                sdk, profile_id, PROFILE_HISTORY_OPERATION_DEFINITION_ID, {"profile_id": str(profile_id)}
            )
            assert outside.is_error is True
            assert isinstance(outside.structured_content, dict)
            assert outside.structured_content["outcome"] == "refused", outside.structured_content

            await asyncio.to_thread(revoke)
            revoked = await sdk.call_tool("describe", {"definition_id": AUTH_READ_OPERATION_DEFINITION_ID})
            assert revoked.is_error is True
            assert isinstance(revoked.structured_content, dict)
            assert revoked.structured_content["outcome"] == "refused", revoked.structured_content
    finally:
        await adapter.close()


def test_a_key_issued_for_an_agent_on_the_command_line_reads_its_category_back_over_mcp(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with worker_profiles(tmp_path) as (root, targets):
        profile_id = targets[-1][0].binding.profile_id
        delete_profile_session(storage_root=root, profile_id=profile_id)
        endpoint = WindowsRuntimeEndpoint(storage_root=root)
        installation = runtime_installation(
            storage_root=root, os_owner_id=owner_id(), storage_identity=endpoint.storage_identity
        )
        binding = current_automation_profile_binding(
            profile_id=profile_id,
            installation_id=installation.installation_id,
            os_owner_id=installation.os_owner_id,
            root=root,
        )
        server_native, client_native = MemoryNativePort(), MemoryNativePort()
        monkeypatch.setattr(runtime_automation_request, "installed_automation_secret_store", lambda: client_native)
        monkeypatch.setattr(runtime_credentials, "installed_automation_secret_store", lambda: client_native)
        store = AutomationControlStore(root=root, binding=binding, secrets_store=server_native)
        stop, boot = Event(), uuid4()
        profiles = RuntimeProfileConnections(
            storage_root=root,
            storage_identity=endpoint.storage_identity,
            runtime_boot_id=boot,
            stop=stop,
            capture_login=lambda _channel: _LoginObservation(),
            secret_store=lambda: server_native,
        )
        profiles.prepare_registry()
        server = RetainedRuntimeTransportServer(
            endpoint, product_version=version("cadrumo"), stop=stop, profiles=profiles, boot_id=boot
        )
        with ThreadPoolExecutor(max_workers=2) as pool:
            running = pool.submit(server.serve)
            try:
                assert server.ready.wait(3)

                def invoke_create() -> Result:
                    with override_settings(
                        cadrumo_local_storage_root=root,
                        cadrumo_output_language="en",
                        cadrumo_cli_reveal_identifiers=True,
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
                            )
                        )

                creating = pool.submit(copy_context().run, invoke_create)
                deadline = time.monotonic() + 60
                while not store.enrollment_state().requests and time.monotonic() < deadline:
                    if creating.done():
                        pytest.fail(f"requester exited before a review existed: {creating.result()!r}")
                    time.sleep(0.05)
                human = _human(endpoint, profile_id)
                try:
                    review = read_automation_inventory(human).projection.requests[0]
                    # The person reviews exactly what the agent's key will release, and to whom.
                    scope = review.proposal.scope
                    assert not scope.disclosures
                    assert {item.category for item in scope.disclosure_categories} == {
                        DisclosureCategory.PROFILE_VALUES,
                        DisclosureCategory.OPERATION_METADATA,
                    }
                    assert {item.destination_id for item in scope.disclosure_categories} == {review.destination_id}
                    assert review.destination_id == review.client_id
                    assert review.proposal.unattended and not review.proposal.allow_os_lock
                    approved = run_automation_decision(
                        human, review, decision="approve", password=bytearray(PROFILE_INPUT.encode())
                    )
                    assert approved.receipt.stage is EnrollmentStage.COMPLETE
                finally:
                    human.close()
                created = cast(Result, creating.result(timeout=60))
                assert created.exit_code == 0, created.output
                result = json.loads(created.stdout)["result"]
                assert result["terminal"]["stage"] == "complete"
                reference = UUID(result["credential_reference"])
                key_id = UUID(result["terminal"]["key_id"])

                def revoke() -> None:
                    person = _human(endpoint, profile_id)
                    try:
                        person.deny_automation(AutomationDenialKind.KEY, target_id=key_id)
                    finally:
                        person.close()

                with override_settings(cadrumo_local_storage_root=root):
                    asyncio.run(_agent_reads(profile_id, reference, revoke))
            finally:
                primary = sys.exception()
                stop.set()
                try:
                    running.result(timeout=20)
                except Exception:
                    if primary is None:
                        raise
                finally:
                    endpoint.close()
