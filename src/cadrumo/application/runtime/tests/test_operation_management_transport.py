"""Canonical management requests stay typed across both local wire envelopes."""

from __future__ import annotations

import json
from uuid import UUID

import pytest
from pydantic import ValidationError

from cadrumo.application.operations.frontend_requests import (
    OperationCancellationRequestV1,
    OperationDetachRequestV1,
    OperationResponseApplyRequestV1,
    OperationResponseControlRequestV1,
    OperationResponseRejectRequestV1,
)
from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.runtime.operation_access import RuntimeOperationManage, operation_management_action
from cadrumo.application.runtime.profile_access import RuntimeRequest
from cadrumo.application.runtime.profile_worker import ProfileWorkerManageRequest, ProfileWorkerRequest
from cadrumo.application.user_profile.access_contracts import AccessAction

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


_REQUEST_ID = UUID("10000000-0000-4000-8000-000000000001")
_PROFILE_ID = UUID("10000000-0000-4000-8000-000000000002")
_SESSION_ID = UUID("10000000-0000-4000-8000-000000000003")
_OPERATION_ID = "a" * 64
_INTERACTION_ID = "b" * 64
_RESPONSE = {
    "operation_id": _OPERATION_ID,
    "interaction_id": _INTERACTION_ID,
    "revision": 2,
    "actor_ref": f"session:{_SESSION_ID}",
}


@pytest.mark.parametrize(
    ("management", "expected_type", "expected_action"),
    [
        ({"operation_id": _OPERATION_ID, "expected_revision": 2}, OperationCancellationRequestV1, AccessAction.CANCEL),
        (
            {"operation_id": _OPERATION_ID, "expected_revision": 2, "detach_version": 1},
            OperationDetachRequestV1,
            AccessAction.DETACH,
        ),
        (
            {**_RESPONSE, "response_action": "apply", "responded_at": "2026-09-27T10:00:00Z"},
            OperationResponseApplyRequestV1,
            AccessAction.RESPOND,
        ),
        (
            {**_RESPONSE, "response_action": "reject", "responded_at": "2026-09-27T10:00:00Z"},
            OperationResponseRejectRequestV1,
            AccessAction.RESPOND,
        ),
        (_RESPONSE, OperationResponseControlRequestV1, AccessAction.RESPOND),
    ],
)
def test_management_wire_envelopes_preserve_canonical_variant(
    management: dict[str, object], expected_type: type[object], expected_action: AccessAction
) -> None:
    public = RuntimeRequest.model_validate_json(
        json.dumps(
            {
                "action": "operation_manage",
                "request_id": str(_REQUEST_ID),
                "profile_id": str(_PROFILE_ID),
                "session_id": str(_SESSION_ID),
                "management": management,
            }
        )
    ).root
    internal = ProfileWorkerRequest.model_validate_json(
        json.dumps(
            {
                "action": "operation_manage",
                "request_id": str(_REQUEST_ID),
                "session_id": str(_SESSION_ID),
                "frontend": OperationFrontendProjection.MCP,
                "management": management,
            }
        )
    ).root
    assert isinstance(public, RuntimeOperationManage)
    assert isinstance(internal, ProfileWorkerManageRequest)
    assert isinstance(public.management, expected_type)
    assert isinstance(internal.management, expected_type)
    assert operation_management_action(public.management) is expected_action
    assert operation_management_action(internal.management) is expected_action


def test_management_wire_rejects_incomplete_response_mutation() -> None:
    with pytest.raises(ValidationError):
        RuntimeRequest.model_validate_json(
            json.dumps(
                {
                    "action": "operation_manage",
                    "request_id": str(_REQUEST_ID),
                    "profile_id": str(_PROFILE_ID),
                    "session_id": str(_SESSION_ID),
                    "management": {**_RESPONSE, "response_action": "apply"},
                }
            )
        )
