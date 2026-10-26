"""MCP exposes bounded, freshly authorized registered result pages."""

from __future__ import annotations

import base64
import json
from collections.abc import Callable
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import NoReturn, cast, override
from uuid import UUID, uuid4

import pytest
from pydantic import JsonValue

from cadrumo.adapters.outbound.components.role_image import DEVELOPMENT_ROLE_IMAGE_VARIABLE
from cadrumo.application.auth.auth_read_contracts import AUTH_READ_OPERATION_DEFINITION_ID
from cadrumo.application.auth.read_operation import build_auth_read_definition, build_auth_read_registration
from cadrumo.application.operations.error_detail import (
    OperationErrorContextEntryV1,
    OperationErrorDetailKind,
    OperationErrorDetailV1,
    operation_error_detail_schema,
)
from cadrumo.application.operations.frontend_projection import (
    OperationNoPendingInteractionV1,
    OperationPublicProjectionV1,
)
from cadrumo.application.operations.frontend_requests import (
    OperationObservationRefusalCode,
    OperationObservationRefusalV1,
    OperationObservationSuccessV1,
    OperationPublicEventPageV1,
    OperationResultProjectionRefusalCode,
    OperationResultProjectionRefusalV1,
    OperationResultProjectionRequestV1,
    OperationResultProjectionSuccessV1,
)
from cadrumo.application.operations.persistence.replay import OperationReplayStatus
from cadrumo.application.operations.registry import (
    OperationFrontendProjection,
    OperationPublicDefinitionDescriptionV1,
    OperationRegistry,
)
from cadrumo.application.operations.schema_identity import OperationSchemaIdentityV1
from cadrumo.application.operator_actions.projection import PreconditionVerdictSnapshot
from cadrumo.application.provisioning_browser import browser_not_provisioned_verdict
from cadrumo.application.provisioning_contracts import (
    LOCAL_AI_PROVISION_ACTION_ID,
    ProvisioningPreconditionCondition,
    provisioning_setup_verdict,
)
from cadrumo.core.hashing import canonical_json_bytes, sha256_hex
from cadrumo.core.operations import (
    OperationEffect,
    OperationLifecycle,
    OperationTerminalCondition,
    profile_operation_subject,
)
from cadrumo.tests.components_role_dispatch import RoleReplay
from cadrumo_client.contracts.operation_access import OperationObserve, OperationObserved
from cadrumo_client.contracts.projection_pages import (
    PROJECTION_PAGE_BYTES,
    ProjectionPage,
    ProjectionPageRequest,
    project_document_page,
)
from cadrumo_client.transport.frontend_client import FrontendClient
from cadrumo_client.transport.frontend_client_contracts import FrontendRefusedError

from ..runtime_adapter import RuntimeMcpAdapter
from ..server import build_server
from .components_role import role_replay_fixture
from .session import connected_server_and_client_session

__all__ = ["role_replay_fixture"]

pytestmark = [pytest.mark.integration, pytest.mark.hex_core]

# Two UTF-8 bytes per character: more than one page, fewer than two.
_DOCUMENT: dict[str, JsonValue] = {"outcome": "succeeded", "projection": {"records": "ñ" * 20_000}}


def _result() -> OperationResultProjectionRequestV1:
    return OperationResultProjectionRequestV1(
        operation_id=sha256_hex(b"mcp-result-page-operation"),
        terminal_revision=4,
        definition_contract_digest=sha256_hex(b"mcp-result-page-contract"),
        result_schema=OperationSchemaIdentityV1(
            schema_id="test.mcp.result", schema_version=1, schema_fingerprint=sha256_hex(b"mcp-result-page-schema")
        ),
    )


class _PageClient:
    def __init__(self, profile_id: UUID, *, document: dict[str, JsonValue] | None = None) -> None:
        self.profile_id = profile_id
        self.frontend = OperationFrontendProjection.EXTERNAL_CLIENT
        self.session_id = uuid4()
        self.calls: list[tuple[OperationResultProjectionRequestV1, ProjectionPageRequest]] = []
        self.deny_continuation = False
        self.closed = False
        self.document = _DOCUMENT if document is None else document

    def read_result_page(
        self, result: OperationResultProjectionRequestV1, page: ProjectionPageRequest, *, deadline: float
    ) -> ProjectionPage:
        assert deadline > 0
        self.calls.append((result, page))
        if page.offset and self.deny_continuation:
            raise FrontendRefusedError("grant_inactive")
        return project_document_page(self.document, page)

    def read_result_document(
        self, result: OperationResultProjectionRequestV1, *, deadline: float
    ) -> dict[str, JsonValue]:
        assert deadline > 0
        return self.document

    def close(self) -> None:
        self.closed = True


@pytest.mark.anyio
async def test_result_page_tool_retrieves_complete_bounded_public_projection() -> None:
    profile_id = uuid4()
    client = _PageClient(profile_id)
    adapter = RuntimeMcpAdapter(profile_id=profile_id, client=cast(FrontendClient, client))
    result = _result()
    try:
        async with connected_server_and_client_session(build_server(adapter)) as sdk:
            names = {tool.name for tool in (await sdk.list_tools()).tools}
            assert "result_page" in names and "result" in names
            first = await sdk.call_tool(
                "result_page",
                {"result": result.model_dump(mode="json"), "page": ProjectionPageRequest().model_dump(mode="json")},
            )
            assert first.is_error is False
            assert first.structured_content is not None
            first_document = first.structured_content
            assert first_document["outcome"] == "reply"
            first_page = ProjectionPage.model_validate(first_document["page"])
            assert len(first_page.decode()) == PROJECTION_PAGE_BYTES
            second = await sdk.call_tool(
                "result_page",
                {
                    "result": result.model_dump(mode="json"),
                    "page": ProjectionPageRequest(
                        offset=len(first_page.decode()), expected_digest=first_page.document_digest
                    ).model_dump(mode="json"),
                },
            )
            assert second.is_error is False
            assert second.structured_content is not None
            second_page = ProjectionPage.model_validate(second.structured_content["page"])
            assert second_page.document_digest == first_page.document_digest
            encoded = first_page.decode() + second_page.decode()
            assert encoded == canonical_json_bytes(_DOCUMENT)
            assert sha256_hex(encoded) == first_page.document_digest
            assert client.calls == [
                (result, ProjectionPageRequest()),
                (
                    result,
                    ProjectionPageRequest(offset=PROJECTION_PAGE_BYTES, expected_digest=first_page.document_digest),
                ),
            ]
    finally:
        await adapter.close()
    assert client.closed


def _refusal_document() -> dict[str, JsonValue]:
    refusal = OperationResultProjectionRefusalV1(
        code=OperationResultProjectionRefusalCode.STALE_OPERATION_REVISION,
        requested_version=None,
        diagnostic_ref=None,
    )
    return cast(dict[str, JsonValue], refusal.model_dump(mode="json"))


@pytest.mark.anyio
async def test_result_page_marks_complete_typed_refusal_as_error_like_result() -> None:
    profile_id = uuid4()
    document = _refusal_document()
    client = _PageClient(profile_id, document=document)
    adapter = RuntimeMcpAdapter(profile_id=profile_id, client=cast(FrontendClient, client))
    request = _result().model_dump(mode="json")
    try:
        async with connected_server_and_client_session(build_server(adapter)) as sdk:
            whole = await sdk.call_tool("result", {"result": request})
            paged = await sdk.call_tool(
                "result_page", {"result": request, "page": ProjectionPageRequest().model_dump(mode="json")}
            )
            assert whole.is_error is True and paged.is_error is True
            assert whole.structured_content is not None and paged.structured_content is not None
            assert whole.structured_content == {
                "outcome": "reply",
                "document": document,
                "code": OperationResultProjectionRefusalCode.STALE_OPERATION_REVISION.value,
            }
            assert paged.structured_content["outcome"] == "reply"
            page = ProjectionPage.model_validate(paged.structured_content["page"])
            assert page.offset == 0 and len(page.decode()) == page.total_bytes
            assert sha256_hex(page.decode()) == page.document_digest
            refusal = OperationResultProjectionRefusalV1.model_validate_json(page.decode())
            assert refusal.code is OperationResultProjectionRefusalCode.STALE_OPERATION_REVISION
            assert refusal.model_dump(mode="json") == whole.structured_content["document"]
    finally:
        await adapter.close()
    assert client.closed


@pytest.mark.anyio
@pytest.mark.parametrize(
    "defect", ["invalid_code", "noncanonical", "duplicate_member", "wrong_digest", "incomplete", "continuation"]
)
async def test_result_page_does_not_infer_refusal_from_unverified_document_or_fragment(defect: str) -> None:
    document = _refusal_document()
    encoded = canonical_json_bytes(document)
    offset = 0
    if defect == "invalid_code":
        encoded = canonical_json_bytes(document | {"code": "not_a_registered_refusal"})
    elif defect == "noncanonical":
        encoded = json.dumps(document, indent=2).encode("utf-8")
    elif defect == "duplicate_member":
        encoded = b'{"outcome":"refused",' + encoded[1:]
    elif defect == "incomplete":
        encoded = encoded.ljust(PROJECTION_PAGE_BYTES + 1, b" ")
    elif defect == "continuation":
        encoded = b" " * PROJECTION_PAGE_BYTES + encoded
        offset = PROJECTION_PAGE_BYTES
    released = ProjectionPage(
        offset=offset,
        total_bytes=len(encoded),
        document_digest=sha256_hex(b"another-document") if defect == "wrong_digest" else sha256_hex(encoded),
        encoded=base64.b64encode(encoded[offset : offset + PROJECTION_PAGE_BYTES]).decode("ascii"),
    )

    class ReturnedPageClient(_PageClient):
        @override
        def read_result_page(
            self, result: OperationResultProjectionRequestV1, page: ProjectionPageRequest, *, deadline: float
        ) -> ProjectionPage:
            assert deadline > 0
            self.calls.append((result, page))
            return released

    profile_id = uuid4()
    client = ReturnedPageClient(profile_id)
    adapter = RuntimeMcpAdapter(profile_id=profile_id, client=cast(FrontendClient, client))
    requested_page = ProjectionPageRequest(offset=offset, expected_digest=released.document_digest if offset else None)
    try:
        async with connected_server_and_client_session(build_server(adapter)) as sdk:
            response = await sdk.call_tool(
                "result_page",
                {"result": _result().model_dump(mode="json"), "page": requested_page.model_dump(mode="json")},
            )
            assert response.is_error is False
            assert response.structured_content == {"outcome": "reply", "page": released.model_dump(mode="json")}
            assert len(client.calls) == 1
    finally:
        await adapter.close()
    assert client.closed


@pytest.mark.anyio
async def test_result_page_refuses_malformed_continuation_before_dispatch() -> None:
    profile_id = uuid4()
    client = _PageClient(profile_id)
    adapter = RuntimeMcpAdapter(profile_id=profile_id, client=cast(FrontendClient, client))
    try:
        refusal = await adapter.call(
            "result_page", {"result": _result().model_dump(mode="json"), "page": {"offset": PROJECTION_PAGE_BYTES}}
        )
        assert refusal == {
            "outcome": "refused",
            "code": "invalid_request",
            "faults": [{"field": "request", "reason": "invalid_value"}],
        }
        assert client.calls == []
    finally:
        await adapter.close()


@pytest.mark.anyio
async def test_result_page_continuation_refusal_releases_no_page() -> None:
    profile_id = uuid4()
    client = _PageClient(profile_id)
    adapter = RuntimeMcpAdapter(profile_id=profile_id, client=cast(FrontendClient, client))
    result = _result()
    try:
        first = await adapter.call(
            "result_page",
            {"result": result.model_dump(mode="json"), "page": ProjectionPageRequest().model_dump(mode="json")},
        )
        first_page = ProjectionPage.model_validate(first["page"])
        client.deny_continuation = True
        refused = await adapter.call(
            "result_page",
            {
                "result": result.model_dump(mode="json"),
                "page": ProjectionPageRequest(
                    offset=PROJECTION_PAGE_BYTES, expected_digest=first_page.document_digest
                ).model_dump(mode="json"),
            },
        )
        assert refused == {"outcome": "refused", "code": "grant_inactive"}
        assert "page" not in refused and "encoded" not in repr(refused)
        assert len(client.calls) == 2
    finally:
        await adapter.close()


def _unused_ports(*_args: object, **_kwargs: object) -> NoReturn:
    raise AssertionError("contract description must not construct executor ports")


def _auth_registry() -> OperationRegistry:
    definition = build_auth_read_definition(_unused_ports)
    registration = build_auth_read_registration(definition)
    return OperationRegistry(definitions=(definition,), public_registrations=(registration,))


def _observed_operation_id() -> str:
    return _result().operation_id


def _settled_request(registry: OperationRegistry) -> OperationResultProjectionRequestV1:
    """The request a caller would assemble from an observation and a description."""
    contract = registry.lookup_public_contract(AUTH_READ_OPERATION_DEFINITION_ID)
    assert contract.result_schema is not None
    return OperationResultProjectionRequestV1(
        operation_id=_observed_operation_id(),
        terminal_revision=4,
        definition_contract_digest=contract.definition_contract_digest,
        result_schema=contract.result_schema,
    )


class _ObservedClient(_PageClient):
    """A lease whose runtime observes one settled operation of a real public contract."""

    def __init__(self, profile_id: UUID, registry: OperationRegistry) -> None:
        super().__init__(profile_id)
        self.registry = registry
        self.refusal: OperationObservationRefusalCode | None = None
        self.observations: list[OperationObserve] = []
        self.described: list[str] = []
        self.document_requests: list[OperationResultProjectionRequestV1] = []

    def operation(self, request: OperationObserve, *, deadline: float) -> OperationObserved:
        assert deadline > 0
        self.observations.append(request)
        observation: OperationObservationRefusalV1 | OperationObservationSuccessV1
        if self.refusal is not None:
            observation = OperationObservationRefusalV1(code=self.refusal, requested_version=None, diagnostic_ref=None)
        else:
            observation = self._settled()
        return OperationObserved(
            request_id=request.request_id, runtime_boot_id=uuid4(), connection_id=uuid4(), observation=observation
        )

    def describe(self, definition_id: str, *, deadline: float) -> OperationPublicDefinitionDescriptionV1:
        assert deadline > 0
        self.described.append(definition_id)
        return self.registry.describe_public_definition(definition_id)

    @override
    def read_result_document(
        self, result: OperationResultProjectionRequestV1, *, deadline: float
    ) -> dict[str, JsonValue]:
        self.document_requests.append(result)
        return super().read_result_document(result, deadline=deadline)

    def _settled(self) -> OperationObservationSuccessV1:
        contract = self.registry.lookup_public_contract(AUTH_READ_OPERATION_DEFINITION_ID)
        moment = datetime(2026, 9, 29, tzinfo=UTC)
        projection = OperationPublicProjectionV1(
            operation_id=_observed_operation_id(),
            definition_id=AUTH_READ_OPERATION_DEFINITION_ID,
            subject_ref=profile_operation_subject(str(self.profile_id)),
            revision=4,
            anchor_cursor=0,
            definition_contract=contract,
            contract_set_digest=self.registry.public_contract_set.contract_set_digest,
            lifecycle=OperationLifecycle.TERMINAL,
            terminal_condition=OperationTerminalCondition.SUCCEEDED,
            effect=OperationEffect.NONE,
            phase_code=None,
            started_at=moment,
            updated_at=moment,
            progress=None,
            close_policy=contract.close_policy,
            cancellation=contract.cancellation,
            cancellable_now=False,
            cancellation_requested=False,
            cancellation_acknowledged=False,
            execution_deadline_at=None,
            cleanup_deadline_at=None,
            pending_interaction=OperationNoPendingInteractionV1(),
            result_ref="f" * 64,
            refusal_ref=None,
            failure_error_code=None,
            diagnostic_ref=None,
        )
        return OperationObservationSuccessV1(
            projection=projection,
            event_page=OperationPublicEventPageV1(
                operation_id=projection.operation_id,
                anchor_cursor=0,
                requested_cursor=0,
                status=OperationReplayStatus.CAUGHT_UP,
                events=(),
                next_cursor=0,
                restart_cursor=None,
            ),
        )


@pytest.mark.anyio
async def test_result_by_operation_id_alone_reads_what_the_full_request_reads() -> None:
    profile_id = uuid4()
    registry = _auth_registry()
    client = _ObservedClient(profile_id, registry)
    adapter = RuntimeMcpAdapter(profile_id=profile_id, client=cast(FrontendClient, client))
    expected = _settled_request(registry)
    complete = expected.model_dump(mode="json")
    named = {"operation_id": expected.operation_id}
    try:
        full = await adapter.call("result", {"result": complete})
        assert client.observations == []
        alone = await adapter.call("result", {"result": named})
        assert alone == full == {"outcome": "reply", "document": _DOCUMENT}
        assert client.document_requests == [expected, expected]
        observed = [(call.observation.operation_id, call.observation.after_cursor) for call in client.observations]
        assert observed == [(expected.operation_id, 0)]
        page = ProjectionPageRequest().model_dump(mode="json")
        full_page = await adapter.call("result_page", {"result": complete, "page": page})
        alone_page = await adapter.call("result_page", {"result": named, "page": page})
        assert alone_page == full_page
        assert client.calls == [(expected, ProjectionPageRequest())] * 2
        # The contract read for the first lookup serves the second.
        assert client.described == [AUTH_READ_OPERATION_DEFINITION_ID]
    finally:
        await adapter.close()


@pytest.mark.anyio
async def test_result_fills_only_what_the_caller_left_out() -> None:
    profile_id = uuid4()
    registry = _auth_registry()
    client = _ObservedClient(profile_id, registry)
    adapter = RuntimeMcpAdapter(profile_id=profile_id, client=cast(FrontendClient, client))
    expected = _settled_request(registry)
    try:
        await adapter.call("result", {"result": {"operation_id": expected.operation_id, "terminal_revision": 3}})
    finally:
        await adapter.close()
    assert client.document_requests == [expected.model_copy(update={"terminal_revision": 3})]


@pytest.mark.anyio
async def test_result_by_operation_id_reports_a_refused_observation_without_reading() -> None:
    profile_id = uuid4()
    client = _ObservedClient(profile_id, _auth_registry())
    client.refusal = OperationObservationRefusalCode.UNKNOWN_OPERATION
    adapter = RuntimeMcpAdapter(profile_id=profile_id, client=cast(FrontendClient, client))
    try:
        refused = await adapter.call("result", {"result": {"operation_id": _observed_operation_id()}})
    finally:
        await adapter.close()
    assert refused == {"outcome": "refused", "code": "unknown_operation"}
    assert client.document_requests == [] and client.described == []


@pytest.mark.anyio
async def test_result_refuses_a_malformed_operation_id_before_observing() -> None:
    profile_id = uuid4()
    client = _ObservedClient(profile_id, _auth_registry())
    adapter = RuntimeMcpAdapter(profile_id=profile_id, client=cast(FrontendClient, client))
    try:
        refused = await adapter.call("result", {"result": {"operation_id": "not-an-operation"}})
        missing = await adapter.call("result", {"result": {"terminal_revision": 4}})
    finally:
        await adapter.close()
    for reply in (refused, missing):
        assert reply["outcome"] == "refused" and reply["code"] == "invalid_request"
        assert reply["faults"] and all(fault["field"] == "request" for fault in reply["faults"])
        assert "not-an-operation" not in json.dumps(reply)
    assert client.observations == []


_DETAIL = OperationErrorDetailV1(
    kind=OperationErrorDetailKind.REGISTERED_ERROR,
    error_code="REFUSED_MODELO_CALCULATION_BLOCKED",
    message_key="application.modelo.calc_diagnostic.unresolved_binding.what",
    context=(
        OperationErrorContextEntryV1(key="action", value="verify"),
        OperationErrorContextEntryV1(key="box", value="05"),
    ),
)


def _not_successful() -> dict[str, JsonValue]:
    refusal = OperationResultProjectionRefusalV1(
        code=OperationResultProjectionRefusalCode.OPERATION_NOT_SUCCESSFUL, requested_version=1, diagnostic_ref=None
    )
    return cast(dict[str, JsonValue], refusal.model_dump(mode="json"))


class _StoppedClient(_ObservedClient):
    """A lease whose runtime settled the operation refused, with or without a recorded detail."""

    def __init__(
        self,
        profile_id: UUID,
        registry: OperationRegistry,
        *,
        detail: str,
        recorded: OperationErrorDetailV1 = _DETAIL,
    ) -> None:
        super().__init__(profile_id, registry)
        self.detail = detail
        self.recorded = recorded

    @override
    def read_result_document(
        self, result: OperationResultProjectionRequestV1, *, deadline: float
    ) -> dict[str, JsonValue]:
        assert deadline > 0
        self.document_requests.append(result)
        if result.result_schema != operation_error_detail_schema():
            return _not_successful()
        if self.detail == "denied":
            raise FrontendRefusedError("disclosure_denied")
        if self.detail == "absent":
            unavailable = OperationResultProjectionRefusalV1(
                code=OperationResultProjectionRefusalCode.RESULT_PROJECTION_UNAVAILABLE,
                requested_version=1,
                diagnostic_ref=None,
            )
            return cast(dict[str, JsonValue], unavailable.model_dump(mode="json"))
        released = OperationResultProjectionSuccessV1[OperationErrorDetailV1](
            result_schema=operation_error_detail_schema(),
            definition_contract_digest=result.definition_contract_digest,
            projection=self.recorded,
        )
        return cast(dict[str, JsonValue], released.model_dump(mode="json"))


@pytest.mark.anyio
async def test_the_result_of_a_stopped_operation_carries_what_it_recorded_about_why() -> None:
    profile_id = uuid4()
    registry = _auth_registry()
    client = _StoppedClient(profile_id, registry, detail="recorded")
    adapter = RuntimeMcpAdapter(profile_id=profile_id, client=cast(FrontendClient, client))
    expected = _settled_request(registry)
    try:
        async with connected_server_and_client_session(build_server(adapter)) as sdk:
            alone = await sdk.call_tool("result", {"result": {"operation_id": expected.operation_id}})
            full = await sdk.call_tool("result", {"result": expected.model_dump(mode="json")})
    finally:
        await adapter.close()

    # The operation has no result, so the call still reads as an error, and the reason travels beside it.
    assert alone.is_error is True and full.is_error is True
    assert alone.structured_content == full.structured_content
    assert alone.structured_content == {
        "outcome": "reply",
        "document": _not_successful(),
        "code": "operation_not_successful",
        "error_detail": _DETAIL.model_dump(mode="json"),
    }
    detail_request = expected.model_copy(update={"result_schema": operation_error_detail_schema()})
    assert client.document_requests == [expected, detail_request] * 2


@pytest.mark.anyio
async def test_a_feature_stopped_for_a_missing_dependency_names_its_recovery_action(
    role_replay: Callable[..., RoleReplay],
) -> None:
    # The browser's quick row, read through the components role, can set it up.
    replay = role_replay(status=["status_quick"])
    # The refusal the browser item raises when no build is installed, as a live read records it.
    verdict = browser_not_provisioned_verdict({"chromium_installed": False})
    recorded = _DETAIL.model_copy(update={"precondition_verdict_json": verdict.model_dump_json()})
    profile_id = uuid4()
    client = _StoppedClient(profile_id, _auth_registry(), detail="recorded", recorded=recorded)
    adapter = RuntimeMcpAdapter(profile_id=profile_id, client=cast(FrontendClient, client))
    try:
        stopped = await adapter.call("result", {"result": {"operation_id": _observed_operation_id()}})
    finally:
        await adapter.close()
    # The agent reads the refusal and its recovery from the top level, beside the document.
    assert stopped["code"] == "operation_not_successful"
    assert stopped["recovery_action_id"] == "operator.provision.browser"
    assert stopped["error_detail"] == recorded.model_dump(mode="json")
    assert "setup_held" not in stopped
    assert replay.commands() == [("status",)]


class _LanguageClient(_StoppedClient):
    """A stopped-operation lease whose profile names no language, so a held row is worded in the default one."""

    def read_profile_view(self, page_kinds: tuple[object, ...]) -> SimpleNamespace:
        del page_kinds
        return SimpleNamespace(items=lambda _kind: (), record_revision=1, content_digest="0" * 64)


_HELD_BROWSER = "Navegador para la web de la Agencia Tributaria: Esta versión de Cadrumo no lo incluye."


@pytest.mark.anyio
async def test_a_stopped_feature_whose_item_setup_cannot_act_names_the_rows_sentence_instead(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Without a built binary every item reads blocked as not in this build: no setup is offered for it.
    monkeypatch.delenv(DEVELOPMENT_ROLE_IMAGE_VARIABLE, raising=False)
    verdict = browser_not_provisioned_verdict({"chromium_installed": False})
    recorded = _DETAIL.model_copy(update={"precondition_verdict_json": verdict.model_dump_json()})
    profile_id = uuid4()
    client = _LanguageClient(profile_id, _auth_registry(), detail="recorded", recorded=recorded)
    adapter = RuntimeMcpAdapter(profile_id=profile_id, client=cast(FrontendClient, client))
    try:
        stopped = await adapter.call("result", {"result": {"operation_id": _observed_operation_id()}})
    finally:
        await adapter.close()
    assert "recovery_action_id" not in stopped
    assert stopped["setup_held"] == [
        {
            "recovery_action_id": "operator.provision.browser",
            "item_id": "browser",
            "state": "blocked",
            "sentence": _HELD_BROWSER,
        }
    ]


@pytest.mark.anyio
async def test_a_stopped_feature_that_needs_the_local_ai_points_to_the_desktop_app_and_offers_no_action(
    role_replay: Callable[..., RoleReplay],
) -> None:
    # The local AI's quick row, read through the components role, points to the desktop app.
    replay = role_replay(status=["status_quick"])
    verdict = provisioning_setup_verdict(
        ProvisioningPreconditionCondition.ROLE_MODEL_INSTALLED,
        facts={"role": "text_extraction", "role_model_installed": False},
        action_id=LOCAL_AI_PROVISION_ACTION_ID,
    )
    recorded = _DETAIL.model_copy(update={"precondition_verdict_json": verdict.model_dump_json()})
    profile_id = uuid4()
    client = _LanguageClient(profile_id, _auth_registry(), detail="recorded", recorded=recorded)
    adapter = RuntimeMcpAdapter(profile_id=profile_id, client=cast(FrontendClient, client))
    try:
        stopped = await adapter.call("result", {"result": {"operation_id": _observed_operation_id()}})
    finally:
        await adapter.close()
    assert "recovery_action_id" not in stopped
    assert stopped["setup_held"] == [
        {
            "recovery_action_id": "operator.provision.local_ai",
            "item_id": "local_ai",
            "state": "absent",
            "sentence": "IA local: Aún no está configurado. Configúrala en la aplicación de escritorio de Cadrumo.",
        }
    ]
    assert replay.commands() == [("status",)]


def _succeeded_with_refused_files() -> dict[str, JsonValue]:
    """A succeeded import whose result refused two files for want of the browser and read a third."""
    snapshot = PreconditionVerdictSnapshot.from_verdict(browser_not_provisioned_verdict({"chromium_installed": False}))
    refused = {"precondition_verdict": cast(JsonValue, snapshot.model_dump(mode="json"))}
    return {
        "outcome": "success",
        "projection": {
            "imported_files": [{"name": "read.csv", "precondition_verdict": None}],
            "refused_files": [{"name": "a.pdf", **refused}, {"name": "b.pdf", **refused}],
        },
    }


@pytest.mark.anyio
async def test_a_succeeded_result_lifts_the_recovery_its_verdicts_name_once(
    role_replay: Callable[..., RoleReplay],
) -> None:
    replay = role_replay(status=["status_quick"])
    profile_id = uuid4()
    client = _ObservedClient(profile_id, _auth_registry())
    client.document = _succeeded_with_refused_files()
    adapter = RuntimeMcpAdapter(profile_id=profile_id, client=cast(FrontendClient, client))
    try:
        reply = await adapter.call("result", {"result": {"operation_id": _observed_operation_id()}})
    finally:
        await adapter.close()
    assert reply["document"] == _succeeded_with_refused_files()
    assert reply["recovery_action_ids"] == ["operator.provision.browser"]
    assert "recovery_action_id" not in reply and "setup_held" not in reply
    # Both refused files name the same item, whose row was read once.
    assert replay.commands() == [("status",)]


@pytest.mark.anyio
async def test_a_succeeded_result_offers_nothing_while_the_setup_status_cannot_be_read(
    role_replay: Callable[..., RoleReplay],
) -> None:
    role_replay(unstartable=True)
    profile_id = uuid4()
    client = _ObservedClient(profile_id, _auth_registry())
    client.document = _succeeded_with_refused_files()
    adapter = RuntimeMcpAdapter(profile_id=profile_id, client=cast(FrontendClient, client))
    try:
        reply = await adapter.call("result", {"result": {"operation_id": _observed_operation_id()}})
    finally:
        await adapter.close()
    assert reply["outcome"] == "reply"
    assert "recovery_action_ids" not in reply and "setup_held" not in reply


@pytest.mark.anyio
async def test_a_succeeded_result_without_verdicts_starts_no_role(role_replay: Callable[..., RoleReplay]) -> None:
    replay = role_replay(status=["status_quick"])
    profile_id = uuid4()
    client = _ObservedClient(profile_id, _auth_registry())
    adapter = RuntimeMcpAdapter(profile_id=profile_id, client=cast(FrontendClient, client))
    try:
        reply = await adapter.call("result", {"result": {"operation_id": _observed_operation_id()}})
    finally:
        await adapter.close()
    assert reply["outcome"] == "reply" and "recovery_action_ids" not in reply
    assert replay.launches == []


@pytest.mark.anyio
async def test_a_stopped_operation_without_a_recovery_names_none() -> None:
    profile_id = uuid4()
    client = _StoppedClient(profile_id, _auth_registry(), detail="recorded")
    adapter = RuntimeMcpAdapter(profile_id=profile_id, client=cast(FrontendClient, client))
    try:
        stopped = await adapter.call("result", {"result": {"operation_id": _observed_operation_id()}})
    finally:
        await adapter.close()
    assert "error_detail" in stopped and "recovery_action_id" not in stopped


@pytest.mark.anyio
@pytest.mark.parametrize("detail", ["absent", "denied"])
async def test_a_stopped_operation_with_no_readable_detail_leaves_only_its_refusal(detail: str) -> None:
    profile_id = uuid4()
    registry = _auth_registry()
    client = _StoppedClient(profile_id, registry, detail=detail)
    adapter = RuntimeMcpAdapter(profile_id=profile_id, client=cast(FrontendClient, client))
    try:
        stopped = await adapter.call("result", {"result": {"operation_id": _observed_operation_id()}})
    finally:
        await adapter.close()
    assert stopped == {"outcome": "reply", "document": _not_successful(), "code": "operation_not_successful"}
    assert len(client.document_requests) == 2


@pytest.mark.anyio
async def test_a_caller_that_asks_for_the_detail_itself_is_answered_by_one_read() -> None:
    profile_id = uuid4()
    registry = _auth_registry()
    client = _StoppedClient(profile_id, registry, detail="recorded")
    adapter = RuntimeMcpAdapter(profile_id=profile_id, client=cast(FrontendClient, client))
    named = {
        "operation_id": _observed_operation_id(),
        "result_schema": operation_error_detail_schema().model_dump(mode="json"),
    }
    try:
        asked = await adapter.call("result", {"result": named})
    finally:
        await adapter.close()
    assert asked["outcome"] == "reply" and "error_detail" not in asked
    assert asked["document"]["projection"] == _DETAIL.model_dump(mode="json")
    assert len(client.document_requests) == 1


@pytest.mark.anyio
async def test_a_refusal_that_is_not_about_the_operation_stopping_reads_no_detail() -> None:
    profile_id = uuid4()
    client = _ObservedClient(profile_id, _auth_registry())
    client.document = _refusal_document()
    adapter = RuntimeMcpAdapter(profile_id=profile_id, client=cast(FrontendClient, client))
    try:
        stale = await adapter.call("result", {"result": {"operation_id": _observed_operation_id()}})
    finally:
        await adapter.close()
    assert stale == {"outcome": "reply", "document": _refusal_document(), "code": "stale_operation_revision"}
    assert len(client.document_requests) == 1


@pytest.mark.anyio
async def test_a_refused_document_with_an_unregistered_code_lifts_no_code() -> None:
    profile_id = uuid4()
    client = _ObservedClient(profile_id, _auth_registry())
    client.document = _refusal_document() | {"code": "OPERATION_NOT_SUCCESSFUL"}
    adapter = RuntimeMcpAdapter(profile_id=profile_id, client=cast(FrontendClient, client))
    try:
        refused = await adapter.call("result", {"result": {"operation_id": _observed_operation_id()}})
    finally:
        await adapter.close()
    assert "code" not in refused and "recovery_action_id" not in refused
