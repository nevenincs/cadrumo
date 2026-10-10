"""A login document names an MCP surface only when one was asked for."""

from __future__ import annotations

import json
import struct
from typing import cast
from uuid import UUID, uuid4

import pytest

from cadrumo.application.operations.mcp_surfaces import McpSurfaceName
from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from cadrumo.application.runtime.profile_access import RuntimeAccessRefusal, RuntimeProfileLogin, RuntimeRequest
from cadrumo.application.user_profile.access_contracts import AccessDenialCode
from cadrumo.core.hashing import canonical_json_bytes

from ..framing import VerifiedRuntimeConnection
from ..frontend_client import RuntimeFrontendClient
from ..frontend_client_contracts import RuntimeFrontendRefusedError
from ..runtime_frame_io import DOCUMENT_FRAME_KIND, decode_document, document_frame

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]

_HEADER_BYTES = 5


def _document_before_surfaces(
    request_id: UUID, profile_id: UUID, method: str, frontend: OperationFrontendProjection
) -> dict[str, object]:
    """Every member a login document had before a surface could be named."""
    return {
        "action": "profile_login",
        "frontend": frontend.value,
        "method": method,
        "persist_receipt": False,
        "profile_id": str(profile_id),
        "request_id": str(request_id),
        "scope": None,
    }


@pytest.mark.parametrize(
    ("method", "frontend"),
    [
        ("password", OperationFrontendProjection.CLI),
        ("receipt", OperationFrontendProjection.TUI),
        ("api_key", OperationFrontendProjection.MCP),
    ],
)
def test_a_login_that_names_no_surface_is_the_document_it_was_before(
    method: str, frontend: OperationFrontendProjection
) -> None:
    request_id, profile_id = uuid4(), uuid4()
    request = RuntimeProfileLogin.model_validate(
        {"request_id": request_id, "profile_id": profile_id, "method": method, "frontend": frontend}
    )
    expected = canonical_json_bytes(_document_before_surfaces(request_id, profile_id, method, frontend))

    assert document_frame(request) == DOCUMENT_FRAME_KIND + struct.pack("!I", len(expected)) + expected
    decoded = decode_document(expected, RuntimeRequest).root
    assert decoded == request
    assert isinstance(decoded, RuntimeProfileLogin)
    assert decoded.surface is None


@pytest.mark.parametrize("surface", list(McpSurfaceName))
def test_a_login_that_names_a_surface_carries_the_name_and_is_read_back(surface: McpSurfaceName) -> None:
    request_id, profile_id = uuid4(), uuid4()
    frontend = OperationFrontendProjection.MCP
    request = RuntimeProfileLogin.model_validate(
        {
            "request_id": request_id,
            "profile_id": profile_id,
            "method": "api_key",
            "frontend": frontend,
            "surface": surface.value,
        }
    )
    payload = document_frame(request)[_HEADER_BYTES:]

    named = _document_before_surfaces(request_id, profile_id, "api_key", frontend) | {"surface": surface.value}
    assert json.loads(payload) == named
    decoded = decode_document(payload, RuntimeRequest).root
    assert decoded == request
    assert isinstance(decoded, RuntimeProfileLogin)
    assert decoded.surface == surface.value


@pytest.mark.parametrize("malformed", ["", "x" * 65, 7, ["full"], {"name": "full"}])
def test_a_malformed_surface_member_is_an_invalid_frame(malformed: object) -> None:
    document = _document_before_surfaces(uuid4(), uuid4(), "api_key", OperationFrontendProjection.MCP)
    payload = canonical_json_bytes(document | {"surface": malformed})

    with pytest.raises(RuntimeRefusalError) as refused:
        decode_document(payload, RuntimeRequest)
    assert refused.value.reason is RuntimeRefusalCode.INVALID_FRAME


class _RefusingConnection:
    """Keep each login document the client sends and refuse the admission."""

    def __init__(self) -> None:
        self.logins: list[RuntimeProfileLogin] = []

    def login(self, request: RuntimeProfileLogin, secret: bytearray, *, deadline: float) -> RuntimeAccessRefusal:
        assert secret
        assert deadline > 0
        self.logins.append(request)
        return RuntimeAccessRefusal(
            request_id=request.request_id,
            runtime_boot_id=uuid4(),
            connection_id=uuid4(),
            code=AccessDenialCode.AUTHENTICATION_REQUIRED,
        )


@pytest.mark.parametrize("surface", [None, *McpSurfaceName])
def test_the_frontend_client_names_its_surface_in_every_login(surface: McpSurfaceName | None) -> None:
    connection = _RefusingConnection()
    client = RuntimeFrontendClient(
        cast(VerifiedRuntimeConnection, connection),
        profile_id=uuid4(),
        frontend=OperationFrontendProjection.MCP,
        surface=surface,
    )

    for _attempt in range(2):
        with pytest.raises(RuntimeFrontendRefusedError):
            client.login_api_key(bytearray(b"synthetic-key"))

    expected = None if surface is None else surface.value
    assert [request.surface for request in connection.logins] == [expected, expected]
    assert {request.frontend for request in connection.logins} == {OperationFrontendProjection.MCP}
