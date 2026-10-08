"""Revoked native automation fences every private MCP route on its live connection."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import cast
from uuid import UUID

import pytest
from mcp.types import CallToolResult
from pydantic import JsonValue

from cadrumo.adapters.local_runtime import runtime_credentials
from cadrumo.adapters.persistence.storage.custody.acceleration_receipt import delete_profile_session
from cadrumo.application.auth.auth_read_contracts import (
    AUTH_READ_OPERATION_DEFINITION_ID,
    AUTH_READ_RESULT_SCHEMA_ID,
    AuthReadProjection,
    AuthReadRequest,
)
from cadrumo.application.operations.frontend_requests import (
    OPERATION_OBSERVATION_PROJECTION_ID,
    OperationObservationRequestV1,
    OperationObservationSuccessV1,
    OperationResultProjectionRequestV1,
    OperationResultProjectionSuccessV1,
    OperationSubmissionReceiptV1,
)
from cadrumo.application.operations.registry import OperationPublicDefinitionContractV1
from cadrumo.application.runtime.projection_pages import ProjectionPage, ProjectionPageRequest
from cadrumo.application.user_profile.access_contracts import (
    AccessAction,
    AccessScope,
    DisclosureCategory,
    DisclosurePermission,
    ProfileAccessStatus,
)
from cadrumo.core.hashing import canonical_json_bytes
from cadrumo.core.operations import (
    OperationEffect,
    OperationLifecycle,
    OperationTerminalCondition,
    profile_operation_subject,
)
from cadrumo.core.redaction.rules import CLI_PROFILE_ID_PLACEHOLDER
from cadrumo.core.time.clock import now
from cadrumo.entrypoints.cli.tests.native_api_cli_support import native_api_cli_session
from cadrumo_harness.mcp.runtime_adapter import RuntimeMcpAdapter
from cadrumo_harness.mcp.server import build_server
from cadrumo_harness.mcp.tests.session import connected_server_and_client_session

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows profile workers"),
]

_REVOKED_CODES = frozenset({"key_inactive", "grant_inactive", "session_inactive", "connection_mismatch"})


def _scope(client_id: UUID) -> AccessScope:
    return AccessScope(
        operations=frozenset({AUTH_READ_OPERATION_DEFINITION_ID}),
        actions=frozenset(
            {AccessAction.SUBMIT, AccessAction.START, AccessAction.RESUME, AccessAction.OBSERVE, AccessAction.RESULT}
        ),
        disclosures=frozenset(
            {
                DisclosurePermission(
                    destination_id=client_id,
                    projection_id=OPERATION_OBSERVATION_PROJECTION_ID,
                    category=DisclosureCategory.OPERATION_METADATA,
                ),
                DisclosurePermission(
                    destination_id=client_id,
                    projection_id=AUTH_READ_RESULT_SCHEMA_ID,
                    category=DisclosureCategory.PROFILE_VALUES,
                ),
            }
        ),
        periods=frozenset(),
        allow_period_independent=True,
        allow_delegation=False,
    )


def _structured(result: CallToolResult) -> dict[str, JsonValue]:
    assert isinstance(result.structured_content, dict)
    return cast(dict[str, JsonValue], result.structured_content)


def _successful_cli(output: str, *, command: str) -> dict[str, JsonValue]:
    document = json.loads(output)
    assert isinstance(document, dict)
    assert document["command"] == command
    assert document["status"] in {"success", "warning"}
    result = document["result"]
    assert isinstance(result, dict)
    return cast(dict[str, JsonValue], result)


def _assert_access_fenced(response: CallToolResult) -> None:
    assert response.is_error is True, _structured(response)
    value = _structured(response)
    assert value["outcome"] == "refused", value
    assert value["code"] in _REVOKED_CODES, value


@pytest.mark.anyio
async def test_native_mcp_automation_revocation_fences_live_discovery_execution_and_result_release(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Human all-automation denial takes effect for all routes and fresh admission."""
    with native_api_cli_session(
        tmp_path,
        scope_for_destination=_scope,
        prepare_profile=lambda _profile_id, _root: None,
    ) as enrolled:
        # The fixture controls OS-login observation and a synthetic native
        # secret store. The application owner, encrypted profile, worker,
        # runtime transport, human denial, and MCP client remain real.
        monkeypatch.setattr(runtime_credentials, "installed_automation_secret_store", lambda: enrolled._client_native)
        adapter = RuntimeMcpAdapter(profile_id=enrolled.profile_id, client=None)
        try:
            async with connected_server_and_client_session(build_server(adapter)) as sdk:
                authenticated = await sdk.call_tool(
                    "authenticate", {"credential_reference": str(enrolled.credential_reference)}
                )
                assert authenticated.is_error is False, _structured(authenticated)
                assert _structured(authenticated)["outcome"] == "authenticated"
                authenticated_status = ProfileAccessStatus.model_validate_json(
                    canonical_json_bytes(_structured(authenticated)["status"])
                )
                assert authenticated_status.session_id is not None

                request = AuthReadRequest(profile_id=enrolled.profile_id, kind="status")
                subject_ref = profile_operation_subject(str(enrolled.profile_id))
                execute_args = {
                    "definition_id": AUTH_READ_OPERATION_DEFINITION_ID,
                    "subject_ref": subject_ref,
                    "payload": request.model_dump(mode="json"),
                }
                found = await sdk.call_tool("search", {"query": AUTH_READ_OPERATION_DEFINITION_ID})
                assert found.is_error is False, _structured(found)
                assert _structured(found)["outcome"] == "found"
                described = await sdk.call_tool("describe", {"definition_id": AUTH_READ_OPERATION_DEFINITION_ID})
                assert described.is_error is False, _structured(described)
                description = _structured(described)["description"]
                assert isinstance(description, dict)
                contract = OperationPublicDefinitionContractV1.model_validate_json(
                    canonical_json_bytes(description["contract"])
                )
                assert contract.result_schema is not None

                submitted = await sdk.call_tool("execute", execute_args)
                assert submitted.is_error is False, _structured(submitted)
                receipt_value = _structured(submitted)["receipt"]
                assert isinstance(receipt_value, dict)
                receipt = OperationSubmissionReceiptV1.model_validate_json(canonical_json_bytes(receipt_value))
                observation = OperationObservationRequestV1(
                    operation_id=receipt.operation_id, after_cursor=0, page_limit=32
                )
                terminal: OperationObservationSuccessV1 | None = None
                for _ in range(80):
                    observed = await sdk.call_tool("observe", {"observation": observation.model_dump(mode="json")})
                    assert observed.is_error is False, _structured(observed)
                    reply = _structured(observed)["reply"]
                    assert isinstance(reply, dict)
                    candidate = OperationObservationSuccessV1.model_validate_json(
                        canonical_json_bytes(reply["observation"])
                    )
                    if candidate.projection.lifecycle is OperationLifecycle.TERMINAL:
                        terminal = candidate
                        break
                    await asyncio.sleep(0.05)
                assert terminal is not None
                assert terminal.projection.terminal_condition is OperationTerminalCondition.SUCCEEDED
                assert terminal.projection.effect is OperationEffect.NONE
                result_request = OperationResultProjectionRequestV1(
                    operation_id=receipt.operation_id,
                    terminal_revision=terminal.projection.revision,
                    definition_contract_digest=contract.definition_contract_digest,
                    result_schema=contract.result_schema,
                )
                result_args = {"result": result_request.model_dump(mode="json")}
                released = await sdk.call_tool("result", result_args)
                assert released.is_error is False, _structured(released)
                document = _structured(released)["document"]
                result = OperationResultProjectionSuccessV1[AuthReadProjection].model_validate_json(
                    canonical_json_bytes(document)
                )
                assert result.definition_contract_digest == contract.definition_contract_digest
                assert result.projection.profile_id == enrolled.profile_id
                assert result.projection.kind == "status"
                assert result.projection.status is not None
                page_args = {"result": result_args["result"], "page": ProjectionPageRequest().model_dump(mode="json")}
                paged = await sdk.call_tool("result_page", page_args)
                assert paged.is_error is False, _structured(paged)
                page = ProjectionPage.model_validate(_structured(paged)["page"])
                assert page.decode() == canonical_json_bytes(document)

                still_admitted = await sdk.call_tool("status", {})
                assert still_admitted.is_error is False, _structured(still_admitted)
                status_value = _structured(still_admitted)["status"]
                status = ProfileAccessStatus.model_validate_json(canonical_json_bytes(status_value))
                assert status.denial is None
                assert status.session_id == authenticated_status.session_id
                assert status.session_expires_at is not None and status.session_expires_at > now()

                delete_profile_session(storage_root=tmp_path / "cadrumo-storage", profile_id=enrolled.profile_id)
                denied_output = await asyncio.to_thread(
                    enrolled.invoke_password, "config", "profile", "automation", "deny", "all"
                )
                assert denied_output.exit_code == 0, denied_output.output
                denied = _successful_cli(denied_output.stdout, command="config.profile.automation.deny")
                assert denied["profile_id"] == CLI_PROFILE_ID_PLACEHOLDER
                assert denied["kind"] == "all"
                assert denied["target_id"] is None
                receipt_document = denied["receipt"]
                assert isinstance(receipt_document, dict)
                assert receipt_document["profile_id"] == CLI_PROFILE_ID_PLACEHOLDER
                assert receipt_document["access_denied"] is True

                _assert_access_fenced(await sdk.call_tool("search", {"query": AUTH_READ_OPERATION_DEFINITION_ID}))
                _assert_access_fenced(
                    await sdk.call_tool("describe", {"definition_id": AUTH_READ_OPERATION_DEFINITION_ID})
                )
                _assert_access_fenced(await sdk.call_tool("execute", execute_args))
                _assert_access_fenced(
                    await sdk.call_tool("observe", {"observation": observation.model_dump(mode="json")})
                )
                _assert_access_fenced(await sdk.call_tool("result", result_args))
                _assert_access_fenced(await sdk.call_tool("result_page", page_args))
                assert str(enrolled.credential_reference) not in repr(denied)
        finally:
            await adapter.close()

        fresh_adapter = RuntimeMcpAdapter(profile_id=enrolled.profile_id, client=None)
        try:
            async with connected_server_and_client_session(build_server(fresh_adapter)) as sdk:
                refused = await sdk.call_tool(
                    "authenticate", {"credential_reference": str(enrolled.credential_reference)}
                )
                assert refused.is_error is True, _structured(refused)
                response = _structured(refused)
                assert response["outcome"] == "refused"
                assert response["code"] in {"missing", "key_inactive", "grant_inactive"}
                assert str(enrolled.credential_reference) not in repr(response)
        finally:
            await fresh_adapter.close()
