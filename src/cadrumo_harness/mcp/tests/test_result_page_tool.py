"""MCP exposes bounded, freshly authorized registered result pages."""

from __future__ import annotations

import base64
import json
from typing import cast, override
from uuid import UUID, uuid4

import pytest
from pydantic import JsonValue

from cadrumo.adapters.local_runtime.frontend_client import RuntimeFrontendClient
from cadrumo.adapters.local_runtime.frontend_client_contracts import RuntimeFrontendRefusedError
from cadrumo.application.operations.frontend_requests import (
    OperationResultProjectionRefusalCode,
    OperationResultProjectionRefusalV1,
    OperationResultProjectionRequestV1,
)
from cadrumo.application.operations.registry import OperationFrontendProjection, OperationSchemaIdentityV1
from cadrumo.application.runtime.projection_pages import (
    PROJECTION_PAGE_BYTES,
    ProjectionPage,
    ProjectionPageRequest,
    project_document_page,
)
from cadrumo.core.hashing import canonical_json_bytes, sha256_hex
from cadrumo_harness.mcp.runtime_adapter import RuntimeMcpAdapter
from cadrumo_harness.mcp.server import build_server
from cadrumo_harness.mcp.tests.session import connected_server_and_client_session

pytestmark = [pytest.mark.integration, pytest.mark.hex_core]

_DOCUMENT: dict[str, JsonValue] = {"outcome": "succeeded", "projection": {"records": "ñ" * 10_000}}


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
        self.frontend = OperationFrontendProjection.MCP
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
            raise RuntimeFrontendRefusedError("grant_inactive")
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
    adapter = RuntimeMcpAdapter(profile_id=profile_id, client=cast(RuntimeFrontendClient, client))
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
            assert len(first_page.decode()) == 16_384
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
                (result, ProjectionPageRequest(offset=16_384, expected_digest=first_page.document_digest)),
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
    adapter = RuntimeMcpAdapter(profile_id=profile_id, client=cast(RuntimeFrontendClient, client))
    request = _result().model_dump(mode="json")
    try:
        async with connected_server_and_client_session(build_server(adapter)) as sdk:
            whole = await sdk.call_tool("result", {"result": request})
            paged = await sdk.call_tool(
                "result_page", {"result": request, "page": ProjectionPageRequest().model_dump(mode="json")}
            )
            assert whole.is_error is True and paged.is_error is True
            assert whole.structured_content is not None and paged.structured_content is not None
            assert whole.structured_content == {"outcome": "reply", "document": document}
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
    adapter = RuntimeMcpAdapter(profile_id=profile_id, client=cast(RuntimeFrontendClient, client))
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
    adapter = RuntimeMcpAdapter(profile_id=profile_id, client=cast(RuntimeFrontendClient, client))
    try:
        refusal = await adapter.call(
            "result_page", {"result": _result().model_dump(mode="json"), "page": {"offset": 16_384}}
        )
        assert refusal == {"outcome": "refused", "code": "invalid_request"}
        assert client.calls == []
    finally:
        await adapter.close()


@pytest.mark.anyio
async def test_result_page_continuation_refusal_releases_no_page() -> None:
    profile_id = uuid4()
    client = _PageClient(profile_id)
    adapter = RuntimeMcpAdapter(profile_id=profile_id, client=cast(RuntimeFrontendClient, client))
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
                "page": ProjectionPageRequest(offset=16_384, expected_digest=first_page.document_digest).model_dump(
                    mode="json"
                ),
            },
        )
        assert refused == {"outcome": "refused", "code": "grant_inactive"}
        assert "page" not in refused and "encoded" not in repr(refused)
        assert len(client.calls) == 2
    finally:
        await adapter.close()
