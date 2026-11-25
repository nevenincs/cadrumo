"""Native MCP disclosure of authorized modelo projections and safe timeline."""

from __future__ import annotations

import asyncio
import sys
from collections.abc import Callable
from pathlib import Path
from typing import cast
from uuid import UUID

import pytest
from click.testing import Result
from mcp import ClientSession
from mcp.types import CallToolResult
from pydantic import BaseModel, JsonValue

from cadrumo.application.modelo.history import assemble_modelo_lifecycle_history
from cadrumo.application.modelo.history_timeline_operation import (
    ModeloHistoryTimelineProjection,
    ModeloHistoryTimelineRequest,
    ModeloTimelineEvent,
)
from cadrumo.application.modelo.projection import project_modelo_100_from_m130
from cadrumo.application.modelo.projection_operation import (
    ModeloCompareOperationProjection,
    ModeloCompareOperationRequest,
    ModeloProjectOperationProjection,
    ModeloProjectOperationRequest,
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
from cadrumo.core.hashing import canonical_json_bytes, sha256_hex
from cadrumo.core.operations import (
    OperationEffect,
    OperationLifecycle,
    OperationTerminalCondition,
    profile_operation_subject,
)
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation
from cadrumo.entrypoints.adapter_composition_ports import build_modelo_history_ports
from cadrumo.entrypoints.adapter_composition_work_ports import build_calculation_action_ports
from cadrumo.entrypoints.tests.modelo_projection_history_conformance_support import (
    prepare_modelo_projection_history_conformance_case,
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
from cadrumo_runtime.host.tests.frontend.cli.native_api_cli_support import native_api_cli_session

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows profile workers"),
]

_PUBLIC_IDS = ("modelo.project", "modelo.compare", "modelo.history.timeline")
type _Expected = ModeloProjectOperationProjection | ModeloCompareOperationProjection | ModeloHistoryTimelineProjection
type _Released = (
    OperationResultProjectionSuccessV1[ModeloProjectOperationProjection]
    | OperationResultProjectionSuccessV1[ModeloCompareOperationProjection]
    | OperationResultProjectionSuccessV1[ModeloHistoryTimelineProjection]
)


def _structured(result: CallToolResult) -> dict[str, JsonValue]:
    assert isinstance(result.structured_content, dict)
    return cast(dict[str, JsonValue], result.structured_content)


def _scope(client_id: UUID) -> AccessScope:
    return AccessScope(
        operations=frozenset((*_PUBLIC_IDS, "modelo.history")),
        actions=frozenset(
            {
                AccessAction.SUBMIT,
                AccessAction.START,
                AccessAction.RESUME,
                AccessAction.OBSERVE,
                AccessAction.RESULT,
                AccessAction.COMMIT,
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
                        category=(
                            DisclosureCategory.OPERATION_METADATA
                            if definition_id == "modelo.history.timeline"
                            else DisclosureCategory.TAX_VALUES
                        ),
                    )
                    for definition_id in _PUBLIC_IDS
                ),
            }
        ),
        periods=None,
        allow_period_independent=True,
        allow_delegation=False,
    )


def _prepare_projections(
    profile_id: UUID, authority_operation: PinnedAuthorityOperation
) -> tuple[
    ModeloProjectOperationProjection,
    ModeloCompareOperationProjection,
    ModeloHistoryTimelineProjection,
]:
    compared = prepare_modelo_projection_history_conformance_case(
        "modelo.compare", profile_id=profile_id, operation=authority_operation
    )
    assert isinstance(compared.expected_projection, ModeloCompareOperationProjection)
    seeded_year = compared.expected_projection.year_a
    projected = project_modelo_100_from_m130(
        year=seeded_year,
        ccaa="madrid",
        bucket_id=str(profile_id),
        ports=build_calculation_action_ports(bucket_id=str(profile_id), operation=authority_operation),
        operation=authority_operation,
    )
    history = assemble_modelo_lifecycle_history(
        "130",
        filing_year=seeded_year,
        period="1T",
        ports=build_modelo_history_ports(bucket_id=str(profile_id), operation=authority_operation),
    )
    timeline = ModeloHistoryTimelineProjection(
        authority_generation=authority_operation.generation.logical_generation,
        profile_id=profile_id,
        modelo=str(history.modelo),
        year=history.filing_year,
        period=history.period,
        count=len(history.events),
        events=tuple(ModeloTimelineEvent.from_event(event) for event in history.events),
    )
    assert timeline.count >= 2
    return (
        ModeloProjectOperationProjection.from_service(
            profile_id, projected, authority_generation=authority_operation.generation.logical_generation
        ),
        compared.expected_projection,
        timeline,
    )


async def _describe_contract(sdk: ClientSession, definition_id: str) -> OperationPublicDefinitionContractV1:
    described = await sdk.call_tool("describe", {"definition_id": definition_id})
    assert described.is_error is False, _structured(described)
    description = _structured(described)["description"]
    assert isinstance(description, dict)
    contract = OperationPublicDefinitionContractV1.model_validate_json(canonical_json_bytes(description["contract"]))
    assert contract.definition_id == definition_id
    assert contract.result_schema is not None
    return contract


async def _execute_to_terminal(
    sdk: ClientSession, definition_id: str, profile_id: UUID, request: BaseModel
) -> tuple[OperationSubmissionReceiptV1, OperationObservationSuccessV1]:
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
    receipt = OperationSubmissionReceiptV1.model_validate_json(canonical_json_bytes(receipt_value))

    terminal: OperationObservationSuccessV1 | None = None
    for _ in range(80):
        observed = await sdk.call_tool(
            "observe",
            {
                "observation": OperationObservationRequestV1(
                    operation_id=receipt.operation_id, after_cursor=0, page_limit=32
                ).model_dump(mode="json")
            },
        )
        assert observed.is_error is False, _structured(observed)
        reply = _structured(observed)["reply"]
        assert isinstance(reply, dict)
        observation = OperationObservationSuccessV1.model_validate_json(canonical_json_bytes(reply["observation"]))
        if observation.projection.lifecycle is OperationLifecycle.TERMINAL:
            terminal = observation
            break
        await asyncio.sleep(0.05)
    assert terminal is not None
    assert terminal.projection.terminal_condition is OperationTerminalCondition.SUCCEEDED
    assert terminal.projection.effect is OperationEffect.NONE
    return receipt, terminal


async def _assert_paged_document_matches(
    sdk: ClientSession, result_request: OperationResultProjectionRequestV1, document: dict[str, JsonValue]
) -> None:
    collected = bytearray()
    continuation = ProjectionPageRequest()
    while True:
        paged = await sdk.call_tool(
            "result_page",
            {
                "result": result_request.model_dump(mode="json"),
                "page": continuation.model_dump(mode="json"),
            },
        )
        assert paged.is_error is False, _structured(paged)
        page_output = _structured(paged)["page"]
        page = ProjectionPage.model_validate(page_output)
        assert page.offset == len(collected)
        collected.extend(page.decode())
        if len(collected) == page.total_bytes:
            break
        continuation = ProjectionPageRequest(offset=len(collected), expected_digest=page.document_digest)
    encoded = bytes(collected)
    assert encoded == canonical_json_bytes(document)
    assert sha256_hex(encoded) == page.document_digest


def _released_projection(document: dict[str, JsonValue], expected: _Expected) -> _Released:
    if isinstance(expected, ModeloProjectOperationProjection):
        project_result_type = OperationResultProjectionSuccessV1[ModeloProjectOperationProjection]
        return project_result_type.model_validate_json(canonical_json_bytes(document))
    if isinstance(expected, ModeloCompareOperationProjection):
        compare_result_type = OperationResultProjectionSuccessV1[ModeloCompareOperationProjection]
        return compare_result_type.model_validate_json(canonical_json_bytes(document))
    timeline_result_type = OperationResultProjectionSuccessV1[ModeloHistoryTimelineProjection]
    return timeline_result_type.model_validate_json(canonical_json_bytes(document))


async def _release_and_check(
    sdk: ClientSession,
    definition_id: str,
    profile_id: UUID,
    request: BaseModel,
    expected: _Expected,
    authority_operation: PinnedAuthorityOperation,
) -> bool:
    """Release one result, check it against ``expected``, and say whether it carries the pinned generation."""
    contract = await _describe_contract(sdk, definition_id)
    assert contract.result_schema is not None
    receipt, terminal = await _execute_to_terminal(sdk, definition_id, profile_id, request)
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
    if definition_id == "modelo.history.timeline":
        await _assert_paged_document_matches(sdk, result_request, document)
    released = _released_projection(document, expected)
    assert released.definition_contract_digest == contract.definition_contract_digest
    assert released.projection == expected
    disclosed = released.projection.model_dump(mode="json")
    return bool(disclosed.get("authority_generation") == authority_operation.pin().logical_generation)


@pytest.mark.anyio
async def test_authorized_mcp_modelo_projection_results_and_history_disclosure_denial(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    authority_operation: PinnedAuthorityOperation,
    run_cadrumo_cli: Callable[..., Result],
) -> None:
    """Only exact destination tax-value results leave the native profile worker."""
    with native_api_cli_session(
        tmp_path,
        invoke_cli=run_cadrumo_cli,
        scope_for_destination=_scope,
        prepare_profile=lambda profile_id, _root: _prepare_projections(profile_id, authority_operation),
    ) as enrolled:
        monkeypatch.setattr(credentials, "installed_automation_secret_store", lambda: enrolled._client_native)
        adapter = RuntimeMcpAdapter(profile_id=enrolled.profile_id, client=None)
        missing_provenance: list[str] = []
        try:
            async with connected_server_and_client_session(build_server(adapter)) as sdk:
                # What serve does with the key the launch configuration names; no tool takes one.
                await adapter.bootstrap_reference(enrolled.credential_reference)
                authenticated = await sdk.call_tool("status", {})
                assert authenticated.is_error is False, _structured(authenticated)
                assert _structured(authenticated)["session"] == "key", _structured(authenticated)

                projected_expected, compared_expected, timeline_expected = enrolled.prepared
                requests = (
                    ModeloProjectOperationRequest(
                        profile_id=enrolled.profile_id, year=projected_expected.year, ccaa="madrid"
                    ),
                    ModeloCompareOperationRequest(
                        profile_id=enrolled.profile_id,
                        modelo="130",
                        years=(compared_expected.year_a, compared_expected.year_b),
                    ),
                    ModeloHistoryTimelineRequest(
                        profile_id=enrolled.profile_id, modelo="130", year=timeline_expected.year, period="1T"
                    ),
                )
                for definition_id, request, expected in zip(_PUBLIC_IDS, requests, enrolled.prepared, strict=True):
                    carries_pin = await _release_and_check(
                        sdk, definition_id, enrolled.profile_id, request, expected, authority_operation
                    )
                    if not carries_pin:
                        missing_provenance.append(definition_id)
        finally:
            await adapter.close()
    if missing_provenance:
        pytest.fail(
            "released modelo results omit pinned publication provenance: " + ", ".join(missing_provenance),
            pytrace=False,
        )
