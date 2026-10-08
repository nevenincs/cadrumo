"""One authenticated MCP request journey through the encrypted native worker."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import cast
from uuid import UUID

import pytest
from mcp.types import CallToolResult
from pydantic import JsonValue

from cadrumo.adapters.local_runtime import runtime_credentials
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
from cadrumo.application.operations.registry import (
    OperationPublicDefinitionContractV1,
)
from cadrumo.application.user_profile.access_contracts import (
    AccessAction,
    AccessScope,
    DisclosureCategory,
    DisclosurePermission,
)
from cadrumo.core.hashing import canonical_json_bytes
from cadrumo.core.operations import (
    OperationEffect,
    OperationLifecycle,
    OperationTerminalCondition,
    profile_operation_subject,
)
from cadrumo.entrypoints.cli.tests.native_api_cli_support import NativeApiCliSession, native_api_cli_session
from cadrumo_harness.mcp.runtime_adapter import RuntimeMcpAdapter
from cadrumo_harness.mcp.server import build_server
from cadrumo_harness.mcp.tests.session import connected_server_and_client_session

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows profile workers"),
]


def _scope_for_destination(client_id: UUID) -> AccessScope:
    return AccessScope(
        operations=frozenset({AUTH_READ_OPERATION_DEFINITION_ID}),
        actions=frozenset(
            {
                AccessAction.SUBMIT,
                AccessAction.START,
                AccessAction.RESUME,
                AccessAction.OBSERVE,
                AccessAction.RESULT,
            }
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
    value = result.structured_content
    assert isinstance(value, dict)
    return cast(dict[str, JsonValue], value)


def _safe_failure_observations(session: NativeApiCliSession[None]) -> tuple[tuple[object, ...], ...]:
    return tuple(
        (
            item.stage,
            item.exception_type,
            item.traceback_locations,
            item.nested_leaves,
            item.request_type,
            item.response_type,
            item.definition_id,
            item.operation_exchange,
            item.action,
            item.phase,
            item.reason,
        )
        for item in session.runtime_failure_events
    )


@pytest.mark.anyio
async def test_authenticated_mcp_discovers_executes_observes_and_reads_native_result(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The SDK authentication tool admits the exact profile before a native operation."""
    with native_api_cli_session(
        tmp_path,
        scope_for_destination=_scope_for_destination,
        prepare_profile=lambda _profile_id, _root: None,
    ) as enrolled:
        # Substitute only the native secret-store composition. MCP credential
        # resolution, runtime transport, profile worker, and operation services
        # remain production implementations.
        monkeypatch.setattr(
            runtime_credentials,
            "installed_automation_secret_store",
            lambda: enrolled._client_native,
        )
        adapter = RuntimeMcpAdapter(profile_id=enrolled.profile_id, client=None)
        first_session_id: UUID | None = None
        try:
            async with connected_server_and_client_session(build_server(adapter)) as sdk:
                tools = (await sdk.list_tools()).tools
                names = [tool.name for tool in tools]
                assert len(names) == len(set(names))
                assert {"authenticate", "status", "search", "describe", "execute", "observe", "result"} <= set(names)

                unauthenticated = await sdk.call_tool("status", {})
                assert unauthenticated.is_error is False
                assert _structured(unauthenticated) == {
                    "outcome": "status",
                    "profile_id": str(enrolled.profile_id),
                    "authenticated": False,
                    "denial": "authentication_required",
                }
                private_before_auth = await sdk.call_tool("search", {"query": AUTH_READ_OPERATION_DEFINITION_ID})
                assert private_before_auth.is_error is True
                assert _structured(private_before_auth) == {
                    "outcome": "refused",
                    "code": "authentication_required",
                }

                authenticated = await sdk.call_tool(
                    "authenticate",
                    {"credential_reference": str(enrolled.credential_reference)},
                )
                authenticated_result = _structured(authenticated)
                if authenticated.is_error:
                    pytest.fail(
                        "native MCP admission failed; "
                        f"safe result={authenticated_result!r}; "
                        f"sanitized runtime failures={_safe_failure_observations(enrolled)!r}",
                        pytrace=False,
                    )
                assert authenticated_result["outcome"] == "authenticated"
                admitted_status = authenticated_result["status"]
                assert isinstance(admitted_status, dict)
                assert admitted_status["profile_id"] == str(enrolled.profile_id)
                assert admitted_status["credential_authenticated"] is True
                first_session_value = admitted_status["session_id"]
                assert isinstance(first_session_value, str)
                first_session_id = UUID(first_session_value)
                assert str(enrolled.credential_reference) not in repr(authenticated_result)

                wrong_reference_id = UUID(int=enrolled.credential_reference.int ^ 1)
                wrong_reference = await sdk.call_tool(
                    "authenticate",
                    {"credential_reference": str(wrong_reference_id)},
                )
                assert wrong_reference.is_error is True
                assert _structured(wrong_reference) == {"outcome": "refused", "code": "missing"}
                assert adapter.client is not None and adapter.client.session_id == first_session_id
                still_admitted = await sdk.call_tool("status", {})
                still_admitted_result = _structured(still_admitted)
                if still_admitted_result["outcome"] != "status":
                    prior_session_retained = (
                        adapter.client is not None and adapter.client.session_id == first_session_id
                    )
                    pytest.fail(
                        "previous native MCP session failed after a missing candidate reference; "
                        f"safe result={still_admitted_result!r}; "
                        f"previous session retained={prior_session_retained}; "
                        f"sanitized runtime failures={_safe_failure_observations(enrolled)!r}",
                        pytrace=False,
                    )
                still_admitted_status = still_admitted_result["status"]
                assert isinstance(still_admitted_status, dict)
                assert still_admitted_status["profile_id"] == str(enrolled.profile_id)
                assert still_admitted_status["session_id"] == str(first_session_id)
                assert still_admitted_status["credential_authenticated"] is True

                search = await sdk.call_tool("search", {"query": AUTH_READ_OPERATION_DEFINITION_ID})
                assert search.is_error is False
                found = _structured(search)
                assert found["outcome"] == "found"
                operations_value = found["operations"]
                assert isinstance(operations_value, list)
                operations: list[dict[str, JsonValue]] = []
                for item in operations_value:
                    assert isinstance(item, dict)
                    operations.append(item)
                assert [item["definition_id"] for item in operations] == [AUTH_READ_OPERATION_DEFINITION_ID]

                described = await sdk.call_tool("describe", {"definition_id": AUTH_READ_OPERATION_DEFINITION_ID})
                assert described.is_error is False
                description = _structured(described)["description"]
                assert isinstance(description, dict)
                contract = OperationPublicDefinitionContractV1.model_validate_json(
                    canonical_json_bytes(description["contract"])
                )
                assert contract.definition_id == AUTH_READ_OPERATION_DEFINITION_ID
                assert contract.result_schema is not None
                request_schema = description["request_json_schema"]
                assert isinstance(request_schema, dict)
                request_properties = cast(dict[str, JsonValue], request_schema["properties"])
                assert {"profile_id", "kind"} <= set(request_properties)
                kind_schema = cast(dict[str, JsonValue], request_properties["kind"])
                kind_reference = kind_schema["$ref"]
                assert isinstance(kind_reference, str)
                definitions = request_schema["$defs"]
                assert isinstance(definitions, dict)
                kind_declaration = definitions[kind_reference.rsplit("/", maxsplit=1)[-1]]
                assert isinstance(kind_declaration, dict)
                kind_values = kind_declaration["enum"]
                assert isinstance(kind_values, list)
                assert "status" in kind_values

                request = AuthReadRequest(profile_id=enrolled.profile_id, kind="status")
                submitted = await sdk.call_tool(
                    "execute",
                    {
                        "definition_id": AUTH_READ_OPERATION_DEFINITION_ID,
                        "subject_ref": profile_operation_subject(str(enrolled.profile_id)),
                        "payload": request.model_dump(mode="json"),
                    },
                )
                assert submitted.is_error is False
                submission = _structured(submitted)
                assert submission["outcome"] == "submitted"
                receipt_value = submission["receipt"]
                assert isinstance(receipt_value, dict)
                receipt = OperationSubmissionReceiptV1.model_validate_json(canonical_json_bytes(receipt_value))

                observation_request = OperationObservationRequestV1(
                    operation_id=receipt.operation_id,
                    after_cursor=0,
                    page_limit=32,
                )
                terminal_observation: OperationObservationSuccessV1 | None = None
                for _attempt in range(80):
                    observed = await sdk.call_tool(
                        "observe", {"observation": observation_request.model_dump(mode="json")}
                    )
                    assert observed.is_error is False
                    reply = _structured(observed)["reply"]
                    assert isinstance(reply, dict)
                    observation_result = OperationObservationSuccessV1.model_validate_json(
                        canonical_json_bytes(reply["observation"])
                    )
                    if observation_result.projection.lifecycle is OperationLifecycle.TERMINAL:
                        terminal_observation = observation_result
                        break
                    await asyncio.sleep(0.05)
                assert terminal_observation is not None
                projection = terminal_observation.projection
                assert projection.operation_id == receipt.operation_id
                assert projection.definition_id == AUTH_READ_OPERATION_DEFINITION_ID
                assert projection.terminal_condition is OperationTerminalCondition.SUCCEEDED
                assert projection.effect is OperationEffect.NONE

                result_request = OperationResultProjectionRequestV1(
                    operation_id=receipt.operation_id,
                    terminal_revision=projection.revision,
                    definition_contract_digest=contract.definition_contract_digest,
                    result_schema=contract.result_schema,
                )
                result = await sdk.call_tool("result", {"result": result_request.model_dump(mode="json")})
                assert result.is_error is False
                document = _structured(result)["document"]
                assert isinstance(document, dict)
                result_projection = OperationResultProjectionSuccessV1[AuthReadProjection].model_validate_json(
                    canonical_json_bytes(document)
                )
                assert result_projection.definition_contract_digest == contract.definition_contract_digest
                assert result_projection.projection.profile_id == enrolled.profile_id
                assert result_projection.projection.kind == "status"
                assert result_projection.projection.status is not None
        finally:
            await adapter.close()

        assert first_session_id is not None
        reconnected_adapter = RuntimeMcpAdapter(profile_id=enrolled.profile_id, client=None)
        try:
            async with connected_server_and_client_session(build_server(reconnected_adapter)) as sdk:
                reauthenticated = await sdk.call_tool(
                    "authenticate",
                    {"credential_reference": str(enrolled.credential_reference)},
                )
                assert reauthenticated.is_error is False
                reauthenticated_result = _structured(reauthenticated)
                assert reauthenticated_result["outcome"] == "authenticated"
                reauthenticated_status = reauthenticated_result["status"]
                assert isinstance(reauthenticated_status, dict)
                assert reauthenticated_status["profile_id"] == str(enrolled.profile_id)
                assert reauthenticated_status["credential_authenticated"] is True
                reauthenticated_session_value = reauthenticated_status["session_id"]
                assert isinstance(reauthenticated_session_value, str)
                assert UUID(reauthenticated_session_value) != first_session_id

                status = await sdk.call_tool("status", {})
                assert status.is_error is False
                status_result = _structured(status)
                assert status_result["outcome"] == "status"
                readback_status = status_result["status"]
                assert isinstance(readback_status, dict)
                assert readback_status["session_id"] == reauthenticated_session_value
        finally:
            await reconnected_adapter.close()
