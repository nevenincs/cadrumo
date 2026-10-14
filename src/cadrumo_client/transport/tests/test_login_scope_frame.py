"""A requested API-key scope remains explicit in the bounded login frame."""

from __future__ import annotations

import json
import struct
from typing import cast
from uuid import UUID, uuid4

import pytest

from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.user_profile.access_contracts import AccessAction, AccessDenialCode, AccessScope
from cadrumo.application.user_profile.view_operation import PROFILE_VIEW_OPERATION_DEFINITION_ID
from cadrumo.core.hashing import canonical_json_bytes

from ...contracts.contracts import RefusalCode, RefusalError
from ...contracts.profile_access import AccessRefusal, ProfileLogin, Request
from ..frame_io import DOCUMENT_FRAME_KIND, decode_document, document_frame
from ..framing import VerifiedConnection
from ..frontend_client import FrontendClient
from ..frontend_client_contracts import FrontendRefusedError

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]

_HEADER_BYTES = 5
_SCOPE = AccessScope(
    operations=frozenset({PROFILE_VIEW_OPERATION_DEFINITION_ID}),
    actions=frozenset({AccessAction.SUBMIT, AccessAction.OBSERVE, AccessAction.RESULT}),
    disclosures=frozenset(),
    periods=frozenset(),
    allow_period_independent=False,
    allow_delegation=False,
    disclosure_categories=frozenset(),
    allow_changes_records=False,
    allow_network=False,
)


def _document_without_scope(
    request_id: UUID, profile_id: UUID, method: str, frontend: OperationFrontendProjection
) -> dict[str, object]:
    """Every member of a login document with no requested narrowing scope."""
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
        ("api_key", OperationFrontendProjection.EXTERNAL_CLIENT),
    ],
)
def test_a_login_without_scope_keeps_the_existing_bounded_document(
    method: str, frontend: OperationFrontendProjection
) -> None:
    request_id, profile_id = uuid4(), uuid4()
    request = ProfileLogin.model_validate(
        {"request_id": request_id, "profile_id": profile_id, "method": method, "frontend": frontend}
    )
    expected = canonical_json_bytes(_document_without_scope(request_id, profile_id, method, frontend))

    assert document_frame(request) == DOCUMENT_FRAME_KIND + struct.pack("!I", len(expected)) + expected
    decoded = decode_document(expected, Request).root
    assert decoded == request
    assert isinstance(decoded, ProfileLogin)
    assert decoded.scope is None


def test_a_login_scope_round_trips_with_exact_operations_and_no_disclosures() -> None:
    request_id, profile_id = uuid4(), uuid4()
    frontend = OperationFrontendProjection.EXTERNAL_CLIENT
    request = ProfileLogin(
        request_id=request_id,
        profile_id=profile_id,
        method="api_key",
        frontend=frontend,
        scope=_SCOPE,
    )
    payload = document_frame(request)[_HEADER_BYTES:]

    expected = _document_without_scope(request_id, profile_id, "api_key", frontend) | {
        "scope": _SCOPE.model_dump(mode="json")
    }
    assert json.loads(payload) == expected
    decoded = decode_document(payload, Request).root
    assert decoded == request
    assert isinstance(decoded, ProfileLogin)
    assert decoded.scope == _SCOPE


@pytest.mark.parametrize(
    "malformed",
    [
        7,
        [],
        {"operations": ["invalid operation id"]},
        {"operations": [PROFILE_VIEW_OPERATION_DEFINITION_ID], "unknown": True},
    ],
)
def test_a_malformed_scope_member_is_an_invalid_frame(malformed: object) -> None:
    document = _document_without_scope(uuid4(), uuid4(), "api_key", OperationFrontendProjection.EXTERNAL_CLIENT)
    payload = canonical_json_bytes(document | {"scope": malformed})

    with pytest.raises(RefusalError) as refused:
        decode_document(payload, Request)
    assert refused.value.reason is RefusalCode.INVALID_FRAME


def test_a_removed_surface_member_is_an_invalid_frame() -> None:
    document = _document_without_scope(uuid4(), uuid4(), "api_key", OperationFrontendProjection.EXTERNAL_CLIENT)
    payload = canonical_json_bytes(document | {"surface": "read-only-local"})

    with pytest.raises(RefusalError) as refused:
        decode_document(payload, Request)
    assert refused.value.reason is RefusalCode.INVALID_FRAME


class _RefusingConnection:
    """Keep each login document the client sends and refuse the admission."""

    def __init__(self) -> None:
        self.logins: list[ProfileLogin] = []

    def login(self, request: ProfileLogin, secret: bytearray, *, deadline: float) -> AccessRefusal:
        assert secret
        assert deadline > 0
        self.logins.append(request)
        return AccessRefusal(
            request_id=request.request_id,
            runtime_boot_id=uuid4(),
            connection_id=uuid4(),
            code=AccessDenialCode.AUTHENTICATION_REQUIRED,
        )


@pytest.mark.parametrize("scope", [None, _SCOPE])
def test_the_frontend_client_reuses_its_exact_explicit_scope(scope: AccessScope | None) -> None:
    connection = _RefusingConnection()
    client = FrontendClient(
        cast(VerifiedConnection, connection),
        profile_id=uuid4(),
        frontend=OperationFrontendProjection.EXTERNAL_CLIENT,
        scope=scope,
    )

    for _attempt in range(2):
        with pytest.raises(FrontendRefusedError):
            client.login_api_key(bytearray(b"synthetic-key"))

    assert [request.scope for request in connection.logins] == [scope, scope]
    assert {request.frontend for request in connection.logins} == {OperationFrontendProjection.EXTERNAL_CLIENT}
