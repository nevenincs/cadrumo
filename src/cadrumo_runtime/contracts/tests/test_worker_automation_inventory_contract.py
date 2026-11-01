"""Inventory reads have a distinct worker callback and held reply contract."""

from __future__ import annotations

from datetime import timedelta
from uuid import uuid4

import pytest
from pydantic import TypeAdapter, ValidationError

from cadrumo.application.user_profile.automation_enrollment import AutomationInventory
from cadrumo.core.hashing import canonical_json_bytes, sha256_hex
from cadrumo.core.time.clock import now
from cadrumo_client.contracts.access_vocabulary import (
    AccessAction,
)

from ..worker_authorization import (
    WORKER_AUTOMATION_INVENTORY_PERMIT_MAX_BYTES,
    WorkerAuthorityEnvelope,
    WorkerAuthorityRequest,
    WorkerAuthorizationPermit,
    WorkerAuthorizationReply,
    WorkerAuthorizationRequest,
    WorkerAutomationInventoryPermit,
    WorkerAutomationInventoryRequest,
    WorkerAutomationInventoryTransfer,
)
from .inventory_request_support import inventory_request

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_inventory_request_is_separate_from_persisted_authority_union() -> None:
    request = inventory_request()
    encoded = request.model_dump_json()
    parsed = WorkerAuthorityEnvelope.model_validate_json(encoded).root
    assert isinstance(parsed, WorkerAutomationInventoryRequest)
    assert parsed == request
    with pytest.raises(ValidationError):
        TypeAdapter(WorkerAuthorityRequest).validate_json(encoded)

    ordinary = WorkerAuthorizationRequest(
        request_id=request.request_id,
        connection_id=request.connection_id,
        session_id=request.session_id,
        operation_id=request.operation_id,
        request=request.request,
        policy=request.policy,
    )
    assert isinstance(
        WorkerAuthorityEnvelope.model_validate_json(ordinary.model_dump_json()).root, WorkerAuthorizationRequest
    )
    assert TypeAdapter(WorkerAuthorityRequest).validate_json(ordinary.model_dump_json()) == ordinary


def test_inventory_request_refuses_wrong_action_and_definition() -> None:
    request = inventory_request()
    document = request.model_dump(mode="json")
    access = document["request"]
    assert isinstance(access, dict)
    access["action"] = AccessAction.RESULT.value
    with pytest.raises(ValidationError, match="registered START action"):
        WorkerAuthorityEnvelope.model_validate_json(canonical_json_bytes(document))

    access["action"] = AccessAction.START.value
    access["definition_id"] = "user-profile.field-mutation"
    with pytest.raises(ValidationError, match="registered START action"):
        WorkerAuthorityEnvelope.model_validate_json(canonical_json_bytes(document))


def test_inventory_reply_is_a_transfer_announcement_never_an_ordinary_permit() -> None:
    request = inventory_request()
    permit = WorkerAutomationInventoryPermit(
        request_id=request.request_id,
        runtime_boot_id=uuid4(),
        permit_id=uuid4(),
        expires_at=now() + timedelta(seconds=20),
        inventory=AutomationInventory(grants=(), keys=(), requests=()),
    )
    payload = canonical_json_bytes(permit.model_dump(mode="json"))
    transfer = WorkerAutomationInventoryTransfer(
        request_id=permit.request_id,
        runtime_boot_id=permit.runtime_boot_id,
        permit_id=permit.permit_id,
        byte_count=len(payload),
        payload_digest=sha256_hex(payload),
    )
    encoded = transfer.model_dump_json()
    parsed = WorkerAuthorizationReply.model_validate_json(encoded).root
    assert isinstance(parsed, WorkerAutomationInventoryTransfer)
    assert parsed == transfer
    with pytest.raises(ValidationError):
        WorkerAuthorizationPermit.model_validate_json(encoded)
    # The permit itself only travels as the announced chunks, never as a reply frame.
    with pytest.raises(ValidationError):
        WorkerAuthorizationReply.model_validate_json(permit.model_dump_json())

    disguised = transfer.model_dump(mode="json")
    disguised["kind"] = "authorized"
    with pytest.raises(ValidationError):
        WorkerAuthorizationReply.model_validate_json(canonical_json_bytes(disguised))


def test_inventory_transfer_refuses_a_permit_past_its_budget() -> None:
    with pytest.raises(ValidationError):
        WorkerAutomationInventoryTransfer(
            request_id=uuid4(),
            runtime_boot_id=uuid4(),
            permit_id=uuid4(),
            byte_count=WORKER_AUTOMATION_INVENTORY_PERMIT_MAX_BYTES + 1,
            payload_digest="c" * 64,
        )
