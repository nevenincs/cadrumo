"""A lease carries its exact explicit operation scope for as long as it lives.

The session authority, the session and lineage policy, the operation access
policy and the profile operation registry are real. The host and custody ports
are held in memory: they supply fixed trusted facts, one enrolled key, one
verified sign-in and no worker, which is everything a lease needs to be
admitted, refreshed and delegated.
"""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from threading import RLock
from typing import cast
from uuid import UUID

import pytest
from pydantic import SecretBytes

from cadrumo.application.operations.registry import OperationFrontendProjection, OperationRegistry
from cadrumo.application.user_profile.access_contracts import (
    AccessAction,
    AccessDenialCode,
    AccessEvaluationContext,
    AccessScope,
    AccessSession,
    ApiKeyRecord,
    AuthorityState,
    AutomationGrant,
    Availability,
    LoginEligibility,
    OperationAccessPolicy,
    OperationAccessRequest,
    OsLockState,
    OsLoginContext,
    ProfileAccessBinding,
    ProfileAccessState,
    SessionKind,
)
from cadrumo.application.user_profile.access_errors import ProfileAccessRefusedError
from cadrumo.application.user_profile.automation_custody_port import AutomationCustodyPort, AutomationCustodySnapshot
from cadrumo.application.user_profile.automation_enrollment import AutomationKeyIssuer
from cadrumo.application.user_profile.login_session import ProfileLoginOutcome
from cadrumo.application.user_profile.operations import (
    USER_PROFILE_OPERATION_DEFINITIONS,
    build_user_profile_operation_registrations,
)
from cadrumo.application.user_profile.profile_operation_contracts import PROFILE_FIELD_MUTATION_OPERATION_DEFINITION_ID
from cadrumo.application.user_profile.view_operation import PROFILE_VIEW_OPERATION_DEFINITION_ID
from cadrumo.core.time.utc import UtcInstant

from ..session_authority import ProfileSessionAuthority
from ..session_authority_contracts import SessionAuthorityFacts, SessionAuthorityOwner

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_READ = PROFILE_VIEW_OPERATION_DEFINITION_ID
_WRITE = PROFILE_FIELD_MUTATION_OPERATION_DEFINITION_ID
_ALLOWED = "allowed"
_OPERATION_DENIED = AccessDenialCode.OPERATION_DENIED.value

_NOW = datetime(2026, 10, 10, 12, tzinfo=UTC)
_BOOT = UUID("5cc00000-0000-4000-8000-000000000001")
_CONNECTION = UUID("5cc00000-0000-4000-8000-000000000002")
_RECIPIENT_CONNECTION = UUID("5cc00000-0000-4000-8000-000000000003")
_CLIENT = UUID("5cc00000-0000-4000-8000-000000000004")
_GRANT = UUID("5cc00000-0000-4000-8000-000000000005")
_KEY = UUID("5cc00000-0000-4000-8000-000000000006")
_LOGIN = "login-a"
_SIGN_IN_IDLE_DEADLINE = _NOW + timedelta(minutes=14)
_BINDING = ProfileAccessBinding(
    profile_id=UUID("5cc00000-0000-4000-8000-000000000007"),
    installation_id=UUID("5cc00000-0000-4000-8000-000000000008"),
    os_owner_id="synthetic-owner",
    custody_generation=1,
    dek_epoch=UUID("5cc00000-0000-4000-8000-000000000009"),
)
_SCOPE = AccessScope(
    operations=frozenset({_READ, _WRITE}),
    actions=frozenset(AccessAction),
    disclosures=frozenset(),
    periods=frozenset(),
    allow_period_independent=True,
    allow_delegation=True,
)
_READ_ONLY_SCOPE = _SCOPE.model_copy(
    update={
        "operations": frozenset({_READ}),
        "actions": frozenset({AccessAction.SUBMIT, AccessAction.OBSERVE, AccessAction.RESULT}),
        "allow_delegation": True,
        "allow_changes_records": False,
        "allow_network": False,
    }
)
_GRANT_RECORD = AutomationGrant(
    grant_id=_GRANT,
    binding=_BINDING,
    client_id=_CLIENT,
    generation=1,
    profile_lock_generation=0,
    state=AuthorityState.ACTIVE,
    scope=_SCOPE,
    valid_from=_NOW - timedelta(days=1),
    expires_at=_NOW + timedelta(days=364),
    unattended=True,
    allow_os_lock=True,
)
_KEY_RECORD = ApiKeyRecord(
    key_id=_KEY,
    grant_id=_GRANT,
    binding=_BINDING,
    generation=1,
    state=AuthorityState.ACTIVE,
    valid_from=_GRANT_RECORD.valid_from,
    expires_at=_GRANT_RECORD.expires_at,
)


class _Host:
    """The trusted host port: fixed profile and login facts for whichever connection asks."""

    def __init__(self) -> None:
        self._guard = RLock()

    @contextmanager
    def admission_guard(self) -> Generator[None]:
        with self._guard:
            yield

    def facts(self, connection_id: UUID) -> SessionAuthorityFacts:
        return SessionAuthorityFacts(
            ProfileAccessState(
                binding=_BINDING,
                lock_generation=0,
                globally_locked=False,
                automation_enabled=True,
                scope=_SCOPE,
                storage=Availability.AVAILABLE,
                automation_custody=Availability.AVAILABLE,
            ),
            AccessEvaluationContext(
                now=_NOW,
                monotonic_now=100.0,
                clock_rollback_detected=False,
                runtime_boot_id=_BOOT,
                connection_id=connection_id,
                authenticated_client_id=_CLIENT,
                login_contexts=(
                    OsLoginContext(
                        login_id=_LOGIN,
                        os_owner_id=_BINDING.os_owner_id,
                        active=True,
                        lock_state=OsLockState.UNLOCKED,
                        unattended=LoginEligibility.ELIGIBLE,
                        credential_facilities=Availability.AVAILABLE,
                    ),
                ),
                private_work_available=True,
            ),
        )

    @contextmanager
    def prepare_api_admission(self, connection_id: UUID) -> Generator[float]:
        assert connection_id == _CONNECTION
        yield 160.0

    def activate(self, session: AccessSession, dek: bytearray) -> None:
        assert dek

    def retire(self, session_id: UUID) -> None:
        return None

    def share(self, session: AccessSession, parent: AccessSession) -> None:
        assert session.parent_session_id == parent.session_id

    def refresh(self, session: AccessSession) -> None:
        return None

    @contextmanager
    def authenticate_human(self, connection_id: UUID) -> Generator[tuple[ProfileLoginOutcome, str]]:
        """Lend the outcome of a sign-in the worker has already verified for this connection's login."""
        assert connection_id == _CONNECTION
        outcome = ProfileLoginOutcome(
            bucket_id=str(_BINDING.profile_id),
            label="synthetic profile",
            authenticated_at=_NOW - timedelta(minutes=1),
            idle_deadline=_SIGN_IN_IDLE_DEADLINE,
            absolute_deadline=_NOW + timedelta(hours=8),
            session_persisted=True,
            already_authenticated=True,
        )
        yield outcome, _LOGIN

    def human_admission_deadline(self, connection_id: UUID) -> float:
        assert connection_id == _CONNECTION
        return 160.0

    def bind_human(self, session: AccessSession) -> None:
        assert session.originating_login_id == _LOGIN

    def capture_human_sign_in(self, session_id: UUID) -> bool:
        # A resumed sign-in asks for no receipt, so none is pending.
        return False


class _Custody:
    """One active grant and key, and key material that any presented credential unwraps."""

    def snapshot(self) -> AutomationCustodySnapshot:
        return AutomationCustodySnapshot(
            revision=1,
            binding=_BINDING,
            profile_lock_generation=0,
            automation_enabled=True,
            grants=(_GRANT_RECORD,),
            keys=(_KEY_RECORD,),
        )

    @contextmanager
    def unlocked(self, *, credential: SecretBytes, now: UtcInstant) -> Generator[bytearray]:
        assert credential.get_secret_value()
        assert now == _NOW
        yield bytearray(b"k" * 32)


class _Issuer:
    """Route every presented credential to the one enrolled key."""

    def verifier(self, secret: SecretBytes) -> tuple[UUID, str]:
        assert secret.get_secret_value()
        return _KEY, "synthetic-verifier"


def _authority() -> ProfileSessionAuthority:
    return ProfileSessionAuthority(
        binding=_BINDING,
        runtime_boot_id=_BOOT,
        owner=cast(SessionAuthorityOwner, _Host()),
        custody=cast(AutomationCustodyPort, _Custody()),
        issuer=cast(AutomationKeyIssuer, _Issuer()),
    )


def _registry() -> OperationRegistry:
    return OperationRegistry(
        definitions=USER_PROFILE_OPERATION_DEFINITIONS,
        public_registrations=build_user_profile_operation_registrations(USER_PROFILE_OPERATION_DEFINITIONS),
    )


def _admit(authority: ProfileSessionAuthority, scope: AccessScope) -> AccessSession:
    credential = SecretBytes(b"synthetic-key")
    admitted = authority.admit_api_key(connection_id=_CONNECTION, target=_BINDING, credential=credential, scope=scope)
    assert isinstance(admitted, AccessSession), admitted
    return admitted


def _resume(authority: ProfileSessionAuthority) -> AccessSession:
    """Admit the person's sign-in at the exact profile ceiling, with no client narrowing input."""
    admitted = authority.admit_human(connection_id=_CONNECTION)
    assert isinstance(admitted, AccessSession), admitted
    return admitted


def _submission(
    authority: ProfileSessionAuthority, registry: OperationRegistry, session: AccessSession, definition_id: str
) -> str:
    """Put one external client submission to the authority's own operation guard and name its answer."""
    contract = registry.lookup_public_contract(definition_id)
    request = OperationAccessRequest(
        profile_id=_BINDING.profile_id,
        definition_id=definition_id,
        action=AccessAction.SUBMIT,
        frontend=OperationFrontendProjection.EXTERNAL_CLIENT,
        periods=frozenset(),
        period_independent=True,
        destination_id=_CLIENT,
    )
    policy = OperationAccessPolicy(
        definition_id=definition_id,
        definition_contract_digest=contract.definition_contract_digest,
        actions=frozenset(AccessAction) - {AccessAction.COMMIT},
        disclosures=frozenset(),
        periods=None,
        allow_period_independent=True,
        backend=Availability.AVAILABLE,
        published_authority=Availability.AVAILABLE,
        provider=Availability.NOT_REQUIRED,
        transaction_authority_required=False,
    )
    try:
        with authority.operation_guard(
            connection_id=session.connection_id,
            session_id=session.session_id,
            request=request,
            policy=policy,
            registry=registry,
        ):
            return _ALLOWED
    except ProfileAccessRefusedError as refused:
        return refused.reason.value


def test_a_key_lease_without_a_narrowing_request_keeps_its_exact_grant_scope() -> None:
    authority, registry = _authority(), _registry()

    session = _admit(authority, _SCOPE)

    assert session.scope == _SCOPE
    assert _submission(authority, registry, session, _READ) == _ALLOWED
    assert _submission(authority, registry, session, _WRITE) == _ALLOWED


def test_a_key_lease_carries_only_its_requested_real_operation_and_no_disclosure_authority() -> None:
    authority, registry = _authority(), _registry()

    session = _admit(authority, _READ_ONLY_SCOPE)

    assert session.scope == _READ_ONLY_SCOPE
    assert session.scope.operations == frozenset({_READ})
    assert session.scope.disclosures == frozenset()
    assert session.scope.disclosure_categories == frozenset()
    assert _submission(authority, registry, session, _READ) == _ALLOWED
    assert _submission(authority, registry, session, _WRITE) == _OPERATION_DENIED


def test_a_human_sign_in_keeps_profile_scope_without_client_narrowing_input() -> None:
    authority, registry = _authority(), _registry()

    session = _resume(authority)

    # Human sign-in carries the profile authority; a client cannot narrow or widen it in the request.
    assert session.kind is SessionKind.HUMAN
    assert session.grant_id is None and session.key_id is None
    assert session.scope == _SCOPE
    assert session.expires_at == _SIGN_IN_IDLE_DEADLINE
    assert _submission(authority, registry, session, _READ) == _ALLOWED
    assert _submission(authority, registry, session, _WRITE) == _ALLOWED


def test_a_refreshed_key_lease_keeps_its_narrowed_scope() -> None:
    authority, registry = _authority(), _registry()
    session = _admit(authority, _READ_ONLY_SCOPE)

    refreshed = authority.refresh_api_key(connection_id=_CONNECTION, session_id=session.session_id)

    assert isinstance(refreshed, AccessSession), refreshed
    assert refreshed.session_id == session.session_id
    assert refreshed.scope == _READ_ONLY_SCOPE
    assert _submission(authority, registry, refreshed, _READ) == _ALLOWED
    assert _submission(authority, registry, refreshed, _WRITE) == _OPERATION_DENIED


@pytest.mark.parametrize("parent_scope", [_SCOPE, _READ_ONLY_SCOPE])
def test_a_delegated_lease_cannot_expand_its_parent_operation_scope(parent_scope: AccessScope) -> None:
    authority, registry = _authority(), _registry()
    parent = _admit(authority, parent_scope)

    child = authority.delegate(
        connection_id=_CONNECTION,
        parent_session_id=parent.session_id,
        recipient_connection_id=_RECIPIENT_CONNECTION,
        grant_id=_GRANT,
        scope=_SCOPE,
    )

    assert isinstance(child, AccessSession), child
    assert child.parent_session_id == parent.session_id
    assert child.scope == parent_scope
    assert _submission(authority, registry, child, _READ) == _ALLOWED
    assert _submission(authority, registry, child, _WRITE) == (
        _ALLOWED if _WRITE in parent_scope.operations else _OPERATION_DENIED
    )
