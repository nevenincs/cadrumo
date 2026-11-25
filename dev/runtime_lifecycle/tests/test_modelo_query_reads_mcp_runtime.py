"""Native MCP disclosure of scoped modelo queries and validated binding values."""

from __future__ import annotations

import asyncio
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast
from uuid import UUID

import pytest
from click.testing import Result
from mcp import ClientSession
from mcp.types import CallToolResult
from pydantic import BaseModel, JsonValue

from cadrumo.application.auth.operation_definitions import AUTH_SESSION_ACQUIRE_OPERATION_DEFINITION_ID
from cadrumo.application.modelo.operation_shared import MODELO_WORK_FILE_OPERATION_DEFINITION_ID
from cadrumo.application.modelo.query_read_contracts import (
    ModeloBindingsListProjection,
    ModeloBindingsListRequest,
    ModeloBindingsResolveRequest,
    ModeloReadinessOperationRequest,
    ModeloRequiresProjection,
)
from cadrumo.application.modelo.typed_query_contracts import (
    ModeloBindingsResolveTypedProjection,
    ModeloReadinessSummaryProjection,
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
from cadrumo.application.operations.registry import OperationPublicDefinitionContractV1
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
)
from cadrumo.domain.calculations.registry.tests.authored_editions import filing_year_envelope
from cadrumo.entrypoints.tests.modelo_query_operation_test_support import (
    ModeloQueryConformanceCase,
    prepare_modelo_query_conformance_case,
)
from cadrumo_client.contracts.access_vocabulary import (
    AccessAction,
    AccessScope,
    DisclosureCategory,
    DisclosurePermission,
)
from cadrumo_client.contracts.projection_pages import ProjectionPage, ProjectionPageRequest
from cadrumo_client.transport import credentials
from cadrumo_mcp.mcp.runtime_adapter import RuntimeMcpAdapter
from cadrumo_mcp.mcp.server import build_server
from cadrumo_mcp.mcp.tests.session import connected_server_and_client_session
from cadrumo_runtime.host.tests.frontend.cli.native_api_cli_support import NativeApiCliSession, native_api_cli_session

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


def _structured(result: CallToolResult) -> dict[str, JsonValue]:
    assert isinstance(result.structured_content, dict)
    return cast(dict[str, JsonValue], result.structured_content)


_RESULT_MODELS: dict[type[BaseModel], type[OperationResultProjectionSuccessV1[Any]]] = {
    ModeloBindingsListProjection: OperationResultProjectionSuccessV1[ModeloBindingsListProjection],
    ModeloRequiresProjection: OperationResultProjectionSuccessV1[ModeloRequiresProjection],
    ModeloBindingsResolveTypedProjection: OperationResultProjectionSuccessV1[ModeloBindingsResolveTypedProjection],
    ModeloReadinessSummaryProjection: OperationResultProjectionSuccessV1[ModeloReadinessSummaryProjection],
}


def _scope(client_id: UUID, period: Period) -> AccessScope:
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
        periods=frozenset({period}),
        allow_period_independent=False,
        allow_delegation=False,
    )


def _prepare(profile_id: UUID, authority_operation: PinnedAuthorityOperation) -> tuple[ModeloQueryConformanceCase, ...]:
    return tuple(
        prepare_modelo_query_conformance_case(definition_id, profile_id=profile_id, operation=authority_operation)
        for definition_id in _PUBLIC_IDS
    )


async def _submit(
    sdk: ClientSession, definition_id: str, profile_id: UUID, request: BaseModel
) -> tuple[CallToolResult, OperationSubmissionReceiptV1]:
    submitted = await sdk.call_tool(
        "execute",
        {
            "definition_id": definition_id,
            "subject_ref": profile_operation_subject(str(profile_id)),
            "payload": request.model_dump(mode="json"),
        },
    )
    assert submitted.is_error is False, _structured(submitted)
    receipt_value = _structured(submitted)["receipt"]
    assert isinstance(receipt_value, dict)
    return submitted, OperationSubmissionReceiptV1.model_validate_json(canonical_json_bytes(receipt_value))


async def _wait_for_terminal(
    sdk: ClientSession, receipt: OperationSubmissionReceiptV1
) -> tuple[OperationObservationSuccessV1, CallToolResult]:
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
        observation = OperationObservationSuccessV1.model_validate_json(canonical_json_bytes(reply["observation"]))
        if observation.projection.lifecycle is OperationLifecycle.TERMINAL:
            return observation, observed
        await asyncio.sleep(0.05)
    pytest.fail("the operation never reached a terminal observation", pytrace=False)


async def _assert_stale_revision_refused(
    sdk: ClientSession, result_request: OperationResultProjectionRequestV1, terminal: OperationObservationSuccessV1
) -> None:
    stale = result_request.model_copy(update={"terminal_revision": terminal.projection.revision + 1})
    for tool_name in ("result", "result_page"):
        arguments = {"result": stale.model_dump(mode="json")}
        if tool_name == "result_page":
            arguments["page"] = ProjectionPageRequest().model_dump(mode="json")
        refused_result = await sdk.call_tool(tool_name, arguments)
        assert refused_result.is_error is True
        if tool_name == "result_page":
            page = ProjectionPage.model_validate(_structured(refused_result)["page"])
            assert page.offset == 0 and page.total_bytes == len(page.decode())
            refusal = OperationResultProjectionRefusalV1.model_validate_json(page.decode())
        else:
            refusal = OperationResultProjectionRefusalV1.model_validate_json(
                canonical_json_bytes(_structured(refused_result)["document"])
            )
        assert refusal.code is OperationResultProjectionRefusalCode.STALE_OPERATION_REVISION


async def _release_and_check(
    sdk: ClientSession,
    enrolled: NativeApiCliSession[tuple[ModeloQueryConformanceCase, ...]],
    definition_id: str,
    case: ModeloQueryConformanceCase,
    authenticated: CallToolResult,
    published: CallToolResult,
) -> None:
    described = await sdk.call_tool("describe", {"definition_id": definition_id})
    assert described.is_error is False, _structured(described)
    description = _structured(described)["description"]
    assert isinstance(description, dict)
    contract = OperationPublicDefinitionContractV1.model_validate_json(canonical_json_bytes(description["contract"]))
    assert contract.definition_id == definition_id
    assert contract.result_schema is not None
    submitted, receipt = await _submit(sdk, definition_id, enrolled.profile_id, case.request)
    terminal, observed = await _wait_for_terminal(sdk, receipt)
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
    released = _RESULT_MODELS[type(case.expected_projection)].model_validate_json(canonical_json_bytes(document))
    assert released.definition_contract_digest == contract.definition_contract_digest
    assert released.projection == case.expected_projection
    assert released.projection.authority_generation == _structured(published)["logical_generation"]
    projection_document = document["projection"]
    assert isinstance(projection_document, dict)
    assert set(projection_document) == set(type(released.projection).model_fields)
    public_output = canonical_json_bytes(
        [reply.model_dump(mode="json") for reply in (authenticated, described, submitted, observed, result)]
    )
    if enrolled._credential.get_secret_value() in public_output:
        pytest.fail("local API credential reached a general MCP response", pytrace=False)
    await _assert_stale_revision_refused(sdk, result_request, terminal)
    if isinstance(released.projection, ModeloReadinessSummaryProjection):
        disclosed = released.projection.model_dump(mode="json")
        assert "profile_refusal" not in disclosed
        assert "registry_refusal" not in disclosed
        assert all("detail" not in issue for issue in disclosed["ledger_issues"])


async def _assert_invalid_override_refused_without_echo(
    sdk: ClientSession, enrolled: NativeApiCliSession[tuple[ModeloQueryConformanceCase, ...]]
) -> None:
    typed_case = enrolled.prepared[2]
    assert isinstance(typed_case.request, ModeloBindingsResolveRequest)
    first_override = typed_case.request.overrides[0]
    unsafe_value = "not-a-decimal-sensitive-input"
    invalid_request = typed_case.request.model_copy(
        update={"overrides": (first_override.model_copy(update={"value": unsafe_value}),)}
    )
    _invalid, invalid_receipt = await _submit(
        sdk, "modelo.bindings.resolve.typed", enrolled.profile_id, invalid_request
    )
    refused, _observed = await _wait_for_terminal(sdk, invalid_receipt)
    assert refused.projection.terminal_condition is OperationTerminalCondition.REFUSED
    assert refused.projection.effect is OperationEffect.NONE
    assert unsafe_value not in str(refused.model_dump(mode="json"))


async def _assert_stale_readiness_revision_refused(
    sdk: ClientSession,
    enrolled: NativeApiCliSession[tuple[ModeloQueryConformanceCase, ...]],
    authority_operation: PinnedAuthorityOperation,
) -> None:
    readiness_case = enrolled.prepared[-1]
    assert isinstance(readiness_case.request, ModeloReadinessOperationRequest)
    assert isinstance(readiness_case.expected_projection, ModeloReadinessSummaryProjection)
    stale_revision = next(
        revision.id
        for revision in authority_operation.modelo_directory("303").revisions
        if str(revision.id) != readiness_case.expected_projection.revision_id
        and revision.valid_from.year < readiness_case.request.filing_year
    )
    stale_input = readiness_case.request.model_copy(update={"revision_id": stale_revision})
    _submitted_stale, stale_receipt = await _submit(sdk, "modelo.readiness.summary", enrolled.profile_id, stale_input)
    stale_terminal, _observed = await _wait_for_terminal(sdk, stale_receipt)
    assert stale_terminal.projection.terminal_condition is OperationTerminalCondition.REFUSED
    assert stale_terminal.projection.effect is OperationEffect.NONE


@pytest.mark.anyio
async def test_native_mcp_discloses_only_scoped_typed_modelo_queries(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    authority_operation: PinnedAuthorityOperation,
    run_cadrumo_cli: Callable[..., Result],
) -> None:
    """Release full canonical rows only for the exact enrolled profile and period."""
    seeded: list[tuple[ModeloQueryConformanceCase, ...]] = []

    def prepare(profile_id: UUID, _root: Path) -> tuple[ModeloQueryConformanceCase, ...]:
        seeded.append(_prepare(profile_id, authority_operation))
        return seeded[0]

    def scope_for(client_id: UUID) -> AccessScope:
        # The period the seeded work unit lives in is the only one the key may read.
        listed = seeded[0][0].request
        assert isinstance(listed, ModeloBindingsListRequest)
        assert listed.year is not None and listed.period_code is not None
        return _scope(client_id, Period.from_year_and_code(listed.year, listed.period_code))

    with native_api_cli_session(
        tmp_path,
        invoke_cli=run_cadrumo_cli,
        scope_for_destination=scope_for,
        prepare_profile=prepare,
    ) as enrolled:
        monkeypatch.setattr(credentials, "installed_automation_secret_store", lambda: enrolled._client_native)
        adapter = RuntimeMcpAdapter(profile_id=enrolled.profile_id, client=None)
        try:
            async with connected_server_and_client_session(build_server(adapter)) as sdk:
                # What serve does with the key the launch configuration names; no tool takes one.
                await adapter.bootstrap_reference(enrolled.credential_reference)
                authenticated = await sdk.call_tool("status", {})
                assert authenticated.is_error is False, _structured(authenticated)
                assert _structured(authenticated)["session"] == "key", _structured(authenticated)

                list_case = enrolled.prepared[0]
                assert isinstance(list_case.request, ModeloBindingsListRequest)
                published = await sdk.call_tool(
                    "authority",
                    {
                        "query": "describe",
                        "modelo": "303",
                        "filing_year": list_case.request.year,
                        "period": list_case.request.period_code,
                    },
                )
                assert published.is_error is False, _structured(published)
                assert _structured(published)["logical_generation"] == authority_operation.pin().logical_generation

                other_year = next(year for year in filing_year_envelope().years if year != list_case.request.year)
                wrong_period_request = list_case.request.model_copy(update={"year": other_year})
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
                    await _release_and_check(sdk, enrolled, definition_id, case, authenticated, published)
                await _assert_invalid_override_refused_without_echo(sdk, enrolled)
                await _assert_stale_readiness_revision_refused(sdk, enrolled, authority_operation)
        finally:
            await adapter.close()
