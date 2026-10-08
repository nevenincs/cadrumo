"""Strict credential-free lifecycle messages at the native protocol boundary."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TypedDict
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.runtime.access_management import (
    RuntimeAutomationDenied,
    RuntimeAutomationDeny,
    RuntimeProfileRecoveryPrepare,
    RuntimeProfileRecoveryPrepared,
    RuntimeProfileResume,
    RuntimeProfileResumed,
    RuntimeSessionInventory,
    RuntimeSessionInventoryReply,
)
from cadrumo.application.runtime.profile_access import RuntimeReply, RuntimeRequest
from cadrumo.application.user_profile.access_contracts import AccessScope, SessionKind, SessionState
from cadrumo.application.user_profile.access_projections import PublicAccessSession
from cadrumo.application.user_profile.automation_lifecycle import AutomationDenialKind, AutomationDenialReceipt
from cadrumo.application.user_profile.automation_lifecycle_service import AutomationResumeReceipt

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


class _ReplyFields(TypedDict):
    request_id: UUID
    runtime_boot_id: UUID
    connection_id: UUID


def test_management_requests_are_closed_and_credential_free() -> None:
    profile_id, session_id, target_id = uuid4(), uuid4(), uuid4()
    deny = RuntimeAutomationDeny(
        request_id=uuid4(),
        profile_id=profile_id,
        session_id=session_id,
        kind=AutomationDenialKind.KEY,
        target_id=target_id,
    )
    recovery = RuntimeProfileRecoveryPrepare(
        request_id=uuid4(), profile_id=profile_id, frontend=OperationFrontendProjection.TUI
    )
    resume = RuntimeProfileResume(
        request_id=uuid4(),
        profile_id=profile_id,
        frontend=OperationFrontendProjection.CLI,
        lock_generation=2,
        grants=frozenset({uuid4()}),
    )
    inventory = RuntimeSessionInventory(request_id=uuid4(), profile_id=profile_id, session_id=session_id)
    for request in (deny, recovery, resume, inventory):
        assert RuntimeRequest.model_validate_json(request.model_dump_json()).root == request
        document = request.model_dump_json()
        assert not any(secret in document for secret in ("password", "api_key", "wrapped_dek", "credential"))
    with pytest.raises(ValidationError):
        RuntimeAutomationDeny.model_validate({**deny.model_dump(), "password": "secret"})
    with pytest.raises(ValidationError):
        RuntimeProfileRecoveryPrepare.model_validate({**recovery.model_dump(), "grants": []})
    with pytest.raises(ValidationError):
        RuntimeProfileResume.model_validate({**resume.model_dump(), "lock_generation": -1})
    with pytest.raises(ValidationError):
        RuntimeRequest.model_validate({**inventory.model_dump(), "action": "unknown"})


@pytest.mark.parametrize("kind", (AutomationDenialKind.KEY, AutomationDenialKind.GRANT))
def test_targeted_denial_requires_exact_target(kind: AutomationDenialKind) -> None:
    base = {"request_id": uuid4(), "profile_id": uuid4(), "session_id": uuid4(), "kind": kind}
    with pytest.raises(ValidationError):
        RuntimeAutomationDeny.model_validate(base)
    assert RuntimeAutomationDeny.model_validate({**base, "target_id": uuid4()}).target_id is not None


@pytest.mark.parametrize("kind", (AutomationDenialKind.ALL, AutomationDenialKind.PROFILE_LOCK))
def test_broad_denial_rejects_target(kind: AutomationDenialKind) -> None:
    base = {"request_id": uuid4(), "profile_id": uuid4(), "session_id": uuid4(), "kind": kind}
    assert RuntimeAutomationDeny.model_validate(base).target_id is None
    with pytest.raises(ValidationError):
        RuntimeAutomationDeny.model_validate({**base, "target_id": uuid4()})


def test_management_replies_are_correlated_and_allowlisted() -> None:
    profile_id, request_id = uuid4(), uuid4()
    identity: _ReplyFields = {"request_id": request_id, "runtime_boot_id": uuid4(), "connection_id": uuid4()}
    denied = RuntimeAutomationDenied(
        **identity,
        receipt=AutomationDenialReceipt(
            request_id=request_id,
            profile_id=profile_id,
            access_denied=True,
            cleanup_pending=True,
            revision=1,
            profile_lock_generation=None,
        ),
    )
    prepared = RuntimeProfileRecoveryPrepared(
        **identity, profile_id=profile_id, lock_generation=3, globally_locked=True
    )
    resumed = RuntimeProfileResumed(
        **identity,
        receipt=AutomationResumeReceipt(
            request_id=request_id,
            profile_id=profile_id,
            revision=2,
            lock_generation=3,
            reactivated_grants=frozenset({uuid4()}),
        ),
    )
    session = PublicAccessSession(
        session_id=uuid4(),
        profile_id=profile_id,
        client_id=uuid4(),
        parent_session_id=None,
        grant_id=None,
        key_id=None,
        kind=SessionKind.HUMAN,
        state=SessionState.ACTIVE,
        scope=AccessScope(
            operations=frozenset(),
            actions=frozenset(),
            disclosures=frozenset(),
            periods=None,
            allow_period_independent=True,
            allow_delegation=False,
        ),
        expires_at=datetime.now(UTC) + timedelta(minutes=10),
    )
    inventory = RuntimeSessionInventoryReply(**identity, sessions=(session,))
    for reply in (denied, prepared, resumed, inventory):
        assert RuntimeReply.model_validate_json(reply.model_dump_json()).root == reply
        assert "password" not in reply.model_dump_json()
    with pytest.raises(ValidationError):
        RuntimeProfileRecoveryPrepared.model_validate({**prepared.model_dump(), "lock_generation": -1})
    with pytest.raises(ValidationError):
        RuntimeProfileRecoveryPrepared.model_validate({**prepared.model_dump(), "grant_ids": [str(uuid4())]})
    with pytest.raises(ValidationError):
        RuntimeSessionInventoryReply.model_validate({**inventory.model_dump(), "credential": "secret"})
    with pytest.raises(ValidationError):
        RuntimeReply.model_validate({**inventory.model_dump(), "kind": "unknown"})
