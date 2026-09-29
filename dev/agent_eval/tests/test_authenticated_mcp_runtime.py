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

from cadrumo.adapters.local_runtime.frontend_client import RuntimeFrontendClient
from cadrumo.adapters.local_runtime.runtime_credentials import open_installed_credential_client
from cadrumo.application.auth.read_operation import (
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
    OperationFrontendProjection,
    OperationPublicDefinitionContractV1,
)
from cadrumo.application.user_profile.access_contracts import (
    AccessAction,
    AccessScope,
    DisclosureCategory,
    DisclosurePermission,
)
from cadrumo.application.user_profile.automation_custody_port import AutomationSecretStore
from cadrumo.core.hashing import canonical_json_bytes
from cadrumo.core.operations import (
    OperationEffect,
    OperationLifecycle,
    OperationTerminalCondition,
    profile_operation_subject,
)
from cadrumo.entrypoints.cli.tests.native_api_cli_support import NativeApiCliSession, native_api_cli_session
from cadrumo_harness.mcp.server import RuntimeMcpAdapter, build_server
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


async def _admit_mcp_client(
    profile_id: UUID, credential_reference: UUID, native_store: AutomationSecretStore
) -> RuntimeFrontendClient:
    client = await open_installed_credential_client(
        profile_id=profile_id,
        credential_reference=credential_reference,
        frontend=OperationFrontendProjection.MCP,
        secrets_store=native_store,
    )
    assert client.profile_id == profile_id
    assert client.frontend is OperationFrontendProjection.MCP
    return client


@pytest.mark.anyio
async def test_authenticated_mcp_discovers_executes_observes_and_reads_native_result(
    tmp_path: Path,
) -> None:
    """The SDK adapter uses exact protected admission and the real result service."""
    with native_api_cli_session(
        tmp_path,
        scope_for_destination=_scope_for_destination,
        prepare_profile=lambda _profile_id, _root: None,
    ) as enrolled:
        try:
            client = await _admit_mcp_client(
                enrolled.profile_id,
                enrolled.credential_reference,
                enrolled._client_native,
            )
        except Exception as error:
            error_type = f"{type(error).__module__}.{type(error).__qualname__}"
            pytest.fail(
                f"native MCP admission failed ({error_type}); "
                f"sanitized runtime failures={_safe_failure_observations(enrolled)!r}",
                pytrace=False,
            )
        first_session_id = client.session_id
        adapter = RuntimeMcpAdapter(profile_id=enrolled.profile_id, client=client)
        try:
            async with connected_server_and_client_session(build_server(adapter)) as sdk:
                tools = (await sdk.list_tools()).tools
                names = [tool.name for tool in tools]
                assert len(names) == len(set(names))
                assert {"search", "describe", "execute", "observe", "result"} <= set(names)

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

        fresh_client = await _admit_mcp_client(
            enrolled.profile_id,
            enrolled.credential_reference,
            enrolled._client_native,
        )
        assert fresh_client.session_id != first_session_id
        fresh_adapter = RuntimeMcpAdapter(profile_id=enrolled.profile_id, client=fresh_client)
        try:
            async with connected_server_and_client_session(build_server(fresh_adapter)) as sdk:
                status = await sdk.call_tool("status", {})
                assert status.is_error is False
                status_result = _structured(status)
                assert status_result["outcome"] == "status"
                assert status_result["status"] is not None
        finally:
            await fresh_adapter.close()
