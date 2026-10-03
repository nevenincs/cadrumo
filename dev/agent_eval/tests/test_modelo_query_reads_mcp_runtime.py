"""Native MCP disclosure of scoped modelo queries and validated binding values."""

from __future__ import annotations

import asyncio
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import cast
from uuid import UUID

import pytest
from mcp.types import CallToolResult
from pydantic import JsonValue

from cadrumo.adapters.local_runtime import runtime_credentials
from cadrumo.application.auth.operation_definitions import AUTH_SESSION_ACQUIRE_OPERATION_DEFINITION_ID
from cadrumo.application.modelo.mcp_query_operation import (
    ModeloBindingsResolveTypedProjection,
    ModeloReadinessSummaryProjection,
)
from cadrumo.application.modelo.operation_definitions import MODELO_WORK_FILE_OPERATION_DEFINITION_ID
from cadrumo.application.modelo.query_read_operation import (
    ModeloBindingsListProjection,
    ModeloBindingsListRequest,
    ModeloBindingsResolveRequest,
    ModeloRequiresProjection,
)
from cadrumo.application.operations.frontend_requests import (
    OPERATION_OBSERVATION_PROJECTION_ID,
    OperationObservationRequestV1,
    OperationObservationSuccessV1,
    OperationResultProjectionRefusalCode,
    OperationResultProjectionRefusalV1,
    OperationResultProjectionRequestV1,
    OperationResultProjectionSuccessV1,
    OperationSubmissionReceiptV1,
)
from cadrumo.application.operations.registry import OperationFrontendProjection, OperationPublicDefinitionContractV1
from cadrumo.application.runtime.projection_pages import ProjectionPageRequest
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
from cadrumo.core.period import Period
from cadrumo.domain.calculations.registry.authority import (
    PinnedAuthorityOperation,
    bundled_indexed_authority,
)
from cadrumo.entrypoints.cli.tests.native_api_cli_support import native_api_cli_session
from cadrumo.entrypoints.tests.modelo_query_operation_test_support import (
    ModeloQueryConformanceCase,
    prepare_modelo_query_conformance_case,
)
from cadrumo_harness.mcp.runtime_adapter import RuntimeMcpAdapter
from cadrumo_harness.mcp.server import build_server
from cadrumo_harness.mcp.tests.session import connected_server_and_client_session

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows profile workers"),
]

_PUBLIC_IDS = (
    "modelo.bindings.list",
    "modelo.requires",
    "modelo.bindings.resolve.typed",
    "modelo.readiness.summary",
)
_GRANTED_IDS = (
    *_PUBLIC_IDS,
    "modelo.bindings.resolve",
    "modelo.readiness",
    AUTH_SESSION_ACQUIRE_OPERATION_DEFINITION_ID,
    MODELO_WORK_FILE_OPERATION_DEFINITION_ID,
)
_PERIOD = Period.from_year_and_code(2025, "1T")


@pytest.fixture
def authority_operation() -> Iterator[PinnedAuthorityOperation]:
    with bundled_indexed_authority().operation() as operation:
        yield operation


def _structured(result: CallToolResult) -> dict[str, JsonValue]:
    assert isinstance(result.structured_content, dict)
    return cast(dict[str, JsonValue], result.structured_content)


@pytest.mark.anyio
async def test_native_mcp_discloses_only_scoped_typed_modelo_queries(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """Release full canonical rows only for the exact enrolled profile and period."""

    def scope(client_id: UUID) -> AccessScope:
        return AccessScope(
            operations=frozenset(_GRANTED_IDS),
            actions=frozenset(
                {
                    AccessAction.SUBMIT,
                    AccessAction.START,
                    AccessAction.RESUME,
                    AccessAction.OBSERVE,
                    AccessAction.RESULT,
                    AccessAction.CANCEL,
                    AccessAction.DETACH,
                }
            ),
            disclosures=frozenset(
                {
                    DisclosurePermission(
                        destination_id=client_id,
                        projection_id=OPERATION_OBSERVATION_PROJECTION_ID,
                        category=DisclosureCategory.OPERATION_METADATA,
                    ),
                    *(
                        DisclosurePermission(
                            destination_id=client_id,
                            projection_id=f"{definition_id}.result",
                            category=DisclosureCategory.PROFILE_VALUES,
                        )
                        for definition_id in _PUBLIC_IDS[:2]
                    ),
                    *(
                        DisclosurePermission(
                            destination_id=client_id,
                            projection_id=f"{definition_id}.result",
                            category=DisclosureCategory.TAX_VALUES,
                        )
                        for definition_id in _PUBLIC_IDS[2:]
                    ),
                }
            ),
            periods=frozenset({_PERIOD}),
            allow_period_independent=False,
            allow_delegation=False,
        )

    def prepare(profile_id: UUID, _root: Path) -> tuple[ModeloQueryConformanceCase, ...]:
        return tuple(
            prepare_modelo_query_conformance_case(definition_id, profile_id=profile_id, operation=authority_operation)
            for definition_id in _PUBLIC_IDS
        )

    with native_api_cli_session(tmp_path, scope_for_destination=scope, prepare_profile=prepare) as enrolled:
        monkeypatch.setattr(runtime_credentials, "installed_automation_secret_store", lambda: enrolled._client_native)
        adapter = RuntimeMcpAdapter(profile_id=enrolled.profile_id, client=None)
        try:
            async with connected_server_and_client_session(build_server(adapter)) as sdk:
                authenticated = await sdk.call_tool(
                    "authenticate", {"credential_reference": str(enrolled.credential_reference)}
                )
                assert authenticated.is_error is False, _structured(authenticated)
                assert _structured(authenticated)["outcome"] == "authenticated"

                published = await sdk.call_tool(
                    "authority", {"query": "describe", "modelo": "303", "filing_year": 2025, "period": "1T"}
                )
                assert published.is_error is False, _structured(published)
                assert _structured(published)["logical_generation"] == authority_operation.pin().logical_generation

                for denied_id in ("modelo.bindings.resolve", "modelo.readiness"):
                    denied = await sdk.call_tool("describe", {"definition_id": denied_id})
                    assert denied.is_error is True
                    assert _structured(denied) == {"outcome": "refused", "code": "frontend_denied"}

                list_case = enrolled.prepared[0]
                assert isinstance(list_case.request, ModeloBindingsListRequest)
                wrong_period_request = list_case.request.model_copy(update={"year": 2026})
                denied_period = await sdk.call_tool(
                    "execute",
                    {
                        "definition_id": "modelo.bindings.list",
                        "subject_ref": profile_operation_subject(str(enrolled.profile_id)),
                        "payload": wrong_period_request.model_dump(mode="json"),
                    },
                )
                assert denied_period.is_error is True
                assert _structured(denied_period) == {"outcome": "refused", "code": "period_denied"}

                for definition_id, case in zip(_PUBLIC_IDS, enrolled.prepared, strict=True):
                    described = await sdk.call_tool("describe", {"definition_id": definition_id})
                    assert described.is_error is False, _structured(described)
                    description = _structured(described)["description"]
                    assert isinstance(description, dict)
                    contract = OperationPublicDefinitionContractV1.model_validate_json(
                        canonical_json_bytes(description["contract"])
                    )
                    assert contract.definition_id == definition_id
                    assert contract.result_schema is not None
                    assert OperationFrontendProjection.MCP in contract.permitted_frontends
                    submitted = await sdk.call_tool(
                        "execute",
                        {
                            "definition_id": definition_id,
                            "subject_ref": profile_operation_subject(str(enrolled.profile_id)),
                            "payload": case.request.model_dump(mode="json"),
                        },
                    )
                    assert submitted.is_error is False, _structured(submitted)
                    receipt_value = _structured(submitted)["receipt"]
                    assert isinstance(receipt_value, dict)
                    receipt = OperationSubmissionReceiptV1.model_validate_json(canonical_json_bytes(receipt_value))

                    terminal: OperationObservationSuccessV1 | None = None
                    for _ in range(80):
                        observed = await sdk.call_tool(
                            "observe",
                            {
                                "observation": OperationObservationRequestV1(
                                    operation_id=receipt.operation_id,
                                    after_cursor=0,
                                    page_limit=32,
                                ).model_dump(mode="json")
                            },
                        )
                        assert observed.is_error is False, _structured(observed)
                        reply = _structured(observed)["reply"]
                        assert isinstance(reply, dict)
                        observation = OperationObservationSuccessV1.model_validate_json(
                            canonical_json_bytes(reply["observation"])
                        )
                        if observation.projection.lifecycle is OperationLifecycle.TERMINAL:
                            terminal = observation
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
                    result = await sdk.call_tool("result", {"result": result_request.model_dump(mode="json")})
                    assert result.is_error is False, _structured(result)
                    document = _structured(result)["document"]
                    assert isinstance(document, dict)
                    if isinstance(case.expected_projection, ModeloBindingsListProjection):
                        released = OperationResultProjectionSuccessV1[ModeloBindingsListProjection].model_validate_json(
                            canonical_json_bytes(document)
                        )
                    elif isinstance(case.expected_projection, ModeloRequiresProjection):
                        released = OperationResultProjectionSuccessV1[ModeloRequiresProjection].model_validate_json(
                            canonical_json_bytes(document)
                        )
                    elif isinstance(case.expected_projection, ModeloBindingsResolveTypedProjection):
                        released = OperationResultProjectionSuccessV1[
                            ModeloBindingsResolveTypedProjection
                        ].model_validate_json(canonical_json_bytes(document))
                    else:
                        assert isinstance(case.expected_projection, ModeloReadinessSummaryProjection)
                        released = OperationResultProjectionSuccessV1[
                            ModeloReadinessSummaryProjection
                        ].model_validate_json(canonical_json_bytes(document))
                    assert released.definition_contract_digest == contract.definition_contract_digest
                    assert released.projection == case.expected_projection
                    assert released.projection.authority_generation == _structured(published)["logical_generation"]
                    assert set(document["projection"]) == set(type(released.projection).model_fields)
                    public_output = canonical_json_bytes(
                        [
                            reply.model_dump(mode="json")
                            for reply in (authenticated, described, submitted, observed, result)
                        ]
                    )
                    if enrolled._credential.get_secret_value() in public_output:
                        pytest.fail("local API credential reached a general MCP response", pytrace=False)
                    stale = result_request.model_copy(update={"terminal_revision": terminal.projection.revision + 1})
                    for tool_name in ("result", "result_page"):
                        arguments = {"result": stale.model_dump(mode="json")}
                        if tool_name == "result_page":
                            arguments["page"] = ProjectionPageRequest().model_dump(mode="json")
                        refused_result = await sdk.call_tool(tool_name, arguments)
                        refusal_document = _structured(refused_result).get("document")
                        if refusal_document is None:
                            assert refused_result.is_error is True
                            assert _structured(refused_result) == {
                                "outcome": "refused",
                                "code": "stale_operation_revision",
                            }
                        else:
                            refusal = OperationResultProjectionRefusalV1.model_validate_json(
                                canonical_json_bytes(refusal_document)
                            )
                            assert refusal.code is OperationResultProjectionRefusalCode.STALE_OPERATION_REVISION
                    if isinstance(released.projection, ModeloReadinessSummaryProjection):
                        disclosed = released.projection.model_dump(mode="json")
                        assert "profile_refusal" not in disclosed
                        assert "registry_refusal" not in disclosed
                        assert all("detail" not in issue for issue in disclosed["ledger_issues"])
                        for prohibited_id in (
                            AUTH_SESSION_ACQUIRE_OPERATION_DEFINITION_ID,
                            MODELO_WORK_FILE_OPERATION_DEFINITION_ID,
                        ):
                            denied = await sdk.call_tool(
                                "execute",
                                {
                                    "definition_id": prohibited_id,
                                    "subject_ref": profile_operation_subject(str(enrolled.profile_id)),
                                    "payload": {},
                                },
                            )
                            assert denied.is_error is True
                            assert _structured(denied) == {"outcome": "refused", "code": "frontend_denied"}

                typed_case = enrolled.prepared[2]
                assert isinstance(typed_case.request, ModeloBindingsResolveRequest)
                first_override = typed_case.request.overrides[0]
                unsafe_value = "not-a-decimal-sensitive-input"
                invalid_request = typed_case.request.model_copy(
                    update={"overrides": (first_override.model_copy(update={"value": unsafe_value}),)}
                )
                invalid = await sdk.call_tool(
                    "execute",
                    {
                        "definition_id": "modelo.bindings.resolve.typed",
                        "subject_ref": profile_operation_subject(str(enrolled.profile_id)),
                        "payload": invalid_request.model_dump(mode="json"),
                    },
                )
                assert invalid.is_error is False, _structured(invalid)
                invalid_receipt_value = _structured(invalid)["receipt"]
                assert isinstance(invalid_receipt_value, dict)
                invalid_receipt = OperationSubmissionReceiptV1.model_validate_json(
                    canonical_json_bytes(invalid_receipt_value)
                )
                refused: OperationObservationSuccessV1 | None = None
                for _ in range(80):
                    observed = await sdk.call_tool(
                        "observe",
                        {
                            "observation": OperationObservationRequestV1(
                                operation_id=invalid_receipt.operation_id,
                                after_cursor=0,
                                page_limit=32,
                            ).model_dump(mode="json")
                        },
                    )
                    assert observed.is_error is False, _structured(observed)
                    reply = _structured(observed)["reply"]
                    assert isinstance(reply, dict)
                    candidate = OperationObservationSuccessV1.model_validate_json(
                        canonical_json_bytes(reply["observation"])
                    )
                    if candidate.projection.lifecycle is OperationLifecycle.TERMINAL:
                        refused = candidate
                        break
                    await asyncio.sleep(0.05)
                assert refused is not None
                assert refused.projection.terminal_condition is OperationTerminalCondition.REFUSED
                assert refused.projection.effect is OperationEffect.NONE
                assert unsafe_value not in str(refused.model_dump(mode="json"))
        finally:
            await adapter.close()
