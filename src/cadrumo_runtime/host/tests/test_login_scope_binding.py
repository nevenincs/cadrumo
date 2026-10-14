"""A key connection retains the exact operational scope it first requested."""

from __future__ import annotations

from pathlib import Path
from threading import Event
from uuid import UUID, uuid4

import pytest

from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.user_profile.access_contracts import (
    AccessAction,
    AccessScope,
    Availability,
    LoginEligibility,
    OsLockState,
    OsLoginContext,
)
from cadrumo.application.user_profile.automation_custody_port import AutomationCustodyCode, AutomationCustodyError
from cadrumo_client.contracts.login import LoginEvidence
from cadrumo_client.contracts.profile_access import AccessRefusal, ProfileLogin
from cadrumo_client.contracts.transport import ConnectionContext

from ...adapters.tests.test_enrollment_framing import MemoryChannel
from ..profile_connections import RuntimeProfileConnections
from ..profile_host import ProfileConnection

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


class _Login:
    """One active native login retained by the already admitted connection."""

    login_id = "scope-test-login"

    def __init__(self, os_owner_id: str) -> None:
        self.os_owner_id = os_owner_id

    def observe(self, *, credential_facilities: Availability) -> OsLoginContext:
        return OsLoginContext(
            login_id=self.login_id,
            os_owner_id=self.os_owner_id,
            active=True,
            lock_state=OsLockState.UNLOCKED,
            unattended=LoginEligibility.ELIGIBLE,
            credential_facilities=credential_facilities,
        )


def _refuse_capture(_channel: object) -> LoginEvidence:
    raise AssertionError("a scope conflict must not capture a new native login")


def _connections(tmp_path: Path, boot: UUID) -> RuntimeProfileConnections:
    return RuntimeProfileConnections(
        storage_root=tmp_path,
        storage_identity="a" * 64,
        runtime_boot_id=boot,
        stop=Event(),
        capture_login=_refuse_capture,
    )


def _scope(operation_id: str) -> AccessScope:
    """Name one real operation and no disclosure, period, or delegation authority."""
    return AccessScope(
        operations=frozenset({operation_id}),
        actions=frozenset({AccessAction.OBSERVE}),
        disclosures=frozenset(),
        periods=frozenset(),
        allow_period_independent=False,
        allow_delegation=False,
        disclosure_categories=frozenset(),
        allow_changes_records=False,
        allow_network=False,
    )


def _login(profile_id: UUID, *, scope: AccessScope) -> ProfileLogin:
    return ProfileLogin(
        request_id=uuid4(),
        profile_id=profile_id,
        method="api_key",
        frontend=OperationFrontendProjection.EXTERNAL_CLIENT,
        scope=scope,
    )


def _admitted_connection(context: ConnectionContext, profile_id: UUID, scope: AccessScope) -> ProfileConnection:
    return ProfileConnection(
        context,
        login=_Login(context.peer.os_owner_id),
        client_id=uuid4(),
        profile_id=profile_id,
        frontend=OperationFrontendProjection.EXTERNAL_CLIENT,
        method="api_key",
        requested_scope=scope,
    )


def test_a_key_connection_cannot_change_its_requested_scope_after_its_first_login(tmp_path: Path) -> None:
    boot, profile_id = uuid4(), uuid4()
    channel = MemoryChannel()
    context = ConnectionContext(uuid4(), boot, channel.peer)
    connections = _connections(tmp_path, boot)
    operation_ids = tuple(item.definition_id for item in connections.prepare_registry().definitions[:2])
    assert len(operation_ids) == 2 and operation_ids[0] != operation_ids[1]
    original_scope, changed_scope = (_scope(item) for item in operation_ids)
    connection = _admitted_connection(context, profile_id, original_scope)
    connections._connections[context.connection_id] = connection

    same_scope = _login(profile_id, scope=original_scope)
    assert connections._existing_or_captured_connection(context, channel, same_scope) is connection

    changed = _login(profile_id, scope=changed_scope)
    with pytest.raises(AutomationCustodyError) as conflict:
        connections._existing_or_captured_connection(context, channel, changed)
    assert conflict.value.reason is AutomationCustodyCode.CONFLICT

    reply = connections.handle(context, channel, changed)
    assert isinstance(reply, AccessRefusal)
    assert reply.code is AutomationCustodyCode.CONFLICT
    assert connections._connections[context.connection_id] is connection
    assert connection.requested_scope == original_scope
    assert not channel.writes


def test_a_narrow_key_scope_carries_no_disclosure_wildcard(tmp_path: Path) -> None:
    profile_id = uuid4()
    connections = _connections(tmp_path, uuid4())
    operation_id = connections.prepare_registry().definitions[0].definition_id
    scope = _scope(operation_id)

    request = _login(profile_id, scope=scope)

    assert request.scope == scope
    assert request.scope.operations == frozenset({operation_id})
    assert request.scope.disclosures == frozenset()
    assert request.scope.disclosure_categories == frozenset()
    assert request.scope.periods == frozenset()
