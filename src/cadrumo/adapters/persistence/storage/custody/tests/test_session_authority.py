"""Real encrypted-custody admission with explicit lifecycle/native-store doubles.

No installed runtime, native credential backend or OS lifecycle event is proved
by these tests. Ciphertext, password proof, key verification and control recovery
use their production implementations against test-owned synthetic profiles.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from contextvars import copy_context
from datetime import timedelta
from pathlib import Path
from threading import Event
from typing import override
from uuid import UUID, uuid4

import pytest
from pydantic import SecretBytes

from cadrumo.adapters.persistence.storage.custody.automation_crypto import CustodyAutomationKeyIssuer
from cadrumo.adapters.persistence.storage.custody.automation_store import AutomationControlStore
from cadrumo.adapters.persistence.storage.custody.tests.enrollment_support import (
    PROFILE_INPUT,
    AdministrationSubject,
    administration_subject,
    changed,
)
from cadrumo.adapters.persistence.storage.tests.profile_capsule_runtime import profile_authority_contexts
from cadrumo.application.operations.registry import OperationFrontendProjection, OperationRegistry
from cadrumo.application.user_profile.access_administration import (
    AccessAdministrationAction,
    AccessAdministrationRequest,
    evaluate_access_administration,
)
from cadrumo.application.user_profile.access_contracts import (
    ACCESS_LEASE_MAXIMUM,
    AccessAction,
    AccessDenialCode,
    AccessDenied,
    AccessSession,
    AuthorityState,
    Availability,
    OperationAccessPolicy,
    OperationAccessRequest,
    SessionKind,
)
from cadrumo.application.user_profile.access_errors import ProfileAccessRefusedError
from cadrumo.application.user_profile.automation_custody_port import AutomationCustodyCode, AutomationCustodyError
from cadrumo.application.user_profile.automation_enrollment import AdministrationFacts
from cadrumo.application.user_profile.automation_lifecycle import (
    AutomationDenial,
    AutomationDenialKind,
    AutomationDenialReceipt,
)
from cadrumo.application.user_profile.automation_lifecycle_service import (
    AutomationLifecycleService,
    AutomationResumeRequest,
)
from cadrumo.application.user_profile.login_session import (
    ProfileLoginOutcome,
    authenticate_profile_for_invocation,
    logout_active_profile,
)
from cadrumo.application.user_profile.operations import (
    build_user_profile_operation_definitions,
    build_user_profile_operation_registrations,
)
from cadrumo.application.user_profile.session_authority import (
    ProfileSessionAuthority,
    SessionAuthorityFacts,
)
from cadrumo.core.time.utc import UtcInstant

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_persistence_adapter,
    pytest.mark.usefixtures("authority_operation"),
]


class ObservedStore(AutomationControlStore):
    """Capture borrowed-buffer lifetime while preserving real unwrap and wiping."""

    borrowed: bytearray | None = None
    after_unwrap: Callable[[], None] = staticmethod(lambda: None)
    fail_release = False

    @override
    @contextmanager
    def unlocked(self, *, credential: SecretBytes, now: UtcInstant) -> Iterator[bytearray]:
        with super().unlocked(credential=credential, now=now) as material:
            yield material
        if self.fail_release:
            raise RuntimeError("synthetic borrowed material release failure")

    @override
    def unwrap(self, *, credential: SecretBytes, now: UtcInstant) -> bytearray:
        material = super().unwrap(credential=credential, now=now)
        self.borrowed = material
        self.after_unwrap()
        return material


class AdmissionOwner:
    """Synthetic transport, clock and worker host; its login uses real password custody."""

    def __init__(self, subject: AdministrationSubject) -> None:
        self.subject = subject
        self.current = SessionAuthorityFacts(subject.owner.current.profile, subject.owner.current.context)
        self.connections = {self.current.context.connection_id: self.current.context.authenticated_client_id}
        self.guard = subject.owner.guard
        self.active: set[UUID] = set()
        self.activated: list[UUID] = []
        self.retired: list[UUID] = []
        self.login_calls = 0
        self.fail_activation = False
        self.human_bound: set[UUID] = set()
        self.human_released = False
        self.human_login_id = "test-login"
        self.failed_retirements: set[UUID] = set()
        self.fail_human_release = False
        self.refreshed: list[AccessSession] = []
        self.fail_refresh = False

    @contextmanager
    def admission_guard(self) -> Iterator[None]:
        with self.guard:
            yield

    def facts(self, connection_id: UUID) -> SessionAuthorityFacts:
        return SessionAuthorityFacts(
            self.current.profile,
            changed(
                self.current.context,
                connection_id=connection_id,
                authenticated_client_id=self.connections[connection_id],
            ),
        )

    def activate(self, session: AccessSession, dek: bytearray) -> None:
        assert len(dek) == 32 and any(dek)
        assert session.binding == self.current.profile.binding
        if self.fail_activation:
            raise RuntimeError("synthetic activation failure")
        self.active.add(session.session_id)
        self.activated.append(session.session_id)

    def share(self, session: AccessSession, parent: AccessSession) -> None:
        assert parent.session_id in self.active
        self.active.add(session.session_id)

    def refresh(self, session: AccessSession) -> None:
        assert session.session_id in self.active
        if self.fail_refresh:
            raise RuntimeError("synthetic worker refresh failure")
        self.refreshed.append(session)

    def bind_human(self, session: AccessSession) -> None:
        self.human_bound.add(session.session_id)
        self.active.add(session.session_id)

    def retire(self, session_id: UUID) -> None:
        self.active.discard(session_id)
        self.retired.append(session_id)
        if session_id in self.failed_retirements:
            raise RuntimeError("synthetic retirement failure")

    @contextmanager
    def authenticate_human(self, connection_id: UUID) -> Iterator[tuple[ProfileLoginOutcome, str]]:
        self.login_calls += 1
        _, decode = profile_authority_contexts()
        outcome = authenticate_profile_for_invocation(
            name=str(self.current.profile.binding.profile_id),
            passphrase_callback=lambda: PROFILE_INPUT,
            profile_decode_context=decode,
            now=self.current.context.now,
        )
        self.human_bound.clear()
        try:
            yield outcome, self.human_login_id
        finally:
            if not self.human_bound:
                logout_active_profile()
                self.human_released = True
        if self.fail_human_release:
            raise RuntimeError("synthetic human release failure")


class Subject:
    def __init__(self, enrollment: AdministrationSubject) -> None:
        self.enrollment = enrollment
        request = uuid4()
        enrollment.service.request(request, enrollment.proposal)
        enrollment.approve(request)
        record = enrollment.store.enrollment_state().requests[0]
        credential = enrollment.owner.delivery.endpoint.possession(record)
        assert credential is not None
        self.credential = credential
        self.store = ObservedStore(
            root=enrollment.store.root, binding=enrollment.store.binding, secrets_store=enrollment.native
        )
        self.owner = AdmissionOwner(enrollment)
        self.authority = self.new_authority()
        self.connection = self.owner.current.context.connection_id

    def new_authority(self) -> ProfileSessionAuthority:
        return ProfileSessionAuthority(
            binding=self.owner.current.profile.binding,
            runtime_boot_id=self.owner.current.context.runtime_boot_id,
            owner=self.owner,
            custody=self.store,
            issuer=CustodyAutomationKeyIssuer(),
        )

    def admit(self) -> AccessSession | AccessDenied:
        return self.authority.admit_api_key(
            connection_id=self.connection,
            target=self.owner.current.profile.binding,
            credential=self.credential,
            scope=self.owner.current.profile.scope,
        )

    def advance(self, seconds: float) -> None:
        context = self.owner.current.context
        self.owner.current = SessionAuthorityFacts(
            self.owner.current.profile,
            changed(
                context, now=context.now + timedelta(seconds=seconds), monotonic_now=context.monotonic_now + seconds
            ),
        )


class LifecycleOwner:
    """Explicit host lock-state observations sharing the admission guard."""

    def __init__(self, subject: Subject, session: AccessSession) -> None:
        self.subject, self.session = subject, session

    def administration_guard(self):
        return self.subject.owner.admission_guard()

    def facts(self) -> AdministrationFacts:
        current = self.subject.owner.current
        return AdministrationFacts(
            profile=current.profile, context=current.context, originating_login_id="test-login", session=self.session
        )

    def set_profile_lock(self, *, generation: int, locked: bool) -> None:
        owner = self.subject.owner
        owner.current = SessionAuthorityFacts(
            changed(
                owner.current.profile, lock_generation=generation, globally_locked=locked, automation_enabled=not locked
            ),
            owner.current.context,
        )


def lifecycle(subject: Subject, human: AccessSession) -> AutomationLifecycleService:
    return AutomationLifecycleService(
        custody=subject.store,
        owner=LifecycleOwner(subject, human),
        sessions=subject.authority,
        storage_root=subject.store.root,
    )


@pytest.fixture
def subject(tmp_path: Path) -> Iterator[Subject]:
    with administration_subject(tmp_path) as enrollment:
        # Consent explicitly includes delegation; no test-only bypass of scope policy.
        scope = changed(enrollment.proposal.scope, allow_delegation=True)
        enrollment.proposal = changed(enrollment.proposal, scope=scope)
        facts = enrollment.owner.current
        assert facts.session is not None
        enrollment.owner.current = changed(
            facts, profile=changed(facts.profile, scope=scope), session=changed(facts.session, scope=scope)
        )
        yield Subject(enrollment)


def test_fresh_api_admission_survives_human_expiry_and_has_no_secret_result(subject: Subject) -> None:
    subject.advance(7200)
    session = subject.admit()
    assert isinstance(session, AccessSession)
    assert session.kind is SessionKind.API_KEY and session.originating_login_id is None
    assert session.expires_at - session.issued_at == ACCESS_LEASE_MAXIMUM
    assert subject.owner.login_calls == 0
    assert subject.store.borrowed == bytearray(32)
    assert subject.credential.get_secret_value().decode() not in session.model_dump_json()
    request = AccessAdministrationRequest(
        request_id=uuid4(),
        request_digest="0" * 64,
        profile_id=session.binding.profile_id,
        action=AccessAdministrationAction.ENROLL,
    )
    decision = evaluate_access_administration(
        request=request,
        session=session,
        ancestors=(),
        grant=subject.store.snapshot().grants[0],
        key=subject.store.snapshot().keys[0],
        profile=subject.owner.current.profile,
        context=subject.owner.current.context,
        password_proof=None,
    )
    assert isinstance(decision, AccessDenied)


@pytest.mark.parametrize("mismatch", ["profile", "client", "boot", "login"])
def test_target_and_trusted_context_mismatch_never_install_material(subject: Subject, mismatch: str) -> None:
    target = subject.owner.current.profile.binding
    context = subject.owner.current.context
    if mismatch == "profile":
        target = changed(target, profile_id=uuid4())
    elif mismatch == "client":
        subject.owner.connections[subject.connection] = uuid4()
    elif mismatch == "boot":
        subject.owner.current = SessionAuthorityFacts(
            subject.owner.current.profile, changed(context, runtime_boot_id=uuid4())
        )
    else:
        subject.owner.current = SessionAuthorityFacts(
            subject.owner.current.profile, changed(context, login_contexts=())
        )
    result = subject.authority.admit_api_key(
        connection_id=subject.connection,
        target=target,
        credential=subject.credential,
        scope=subject.owner.current.profile.scope,
    )
    assert isinstance(result, AccessDenied)
    assert not subject.owner.active
    assert subject.store.borrowed is None


def test_wrong_secret_with_correct_key_identity_does_not_authenticate(subject: Subject) -> None:
    raw = subject.credential.get_secret_value()
    prefix, identifier, _ = raw.split(b".")
    subject.credential = SecretBytes(prefix + b"." + identifier + b"." + b"A" * 43)
    with pytest.raises(AutomationCustodyError):
        subject.admit()
    assert not subject.owner.active


@pytest.mark.parametrize("failure", ["publication", "logout", "activation"])
def test_revalidation_and_failed_activation_wipe_borrowed_material(subject: Subject, failure: str) -> None:
    def change_during_unwrap() -> None:
        if failure == "publication":
            state = subject.store.enrollment_state()
            subject.store.publish_enrollment(changed(state, automation_enabled=False))
        elif failure == "logout":
            subject.owner.current = SessionAuthorityFacts(
                subject.owner.current.profile,
                changed(subject.owner.current.context, login_contexts=()),
            )

    subject.store.after_unwrap = change_during_unwrap
    if failure == "activation":
        subject.owner.fail_activation = True
        with pytest.raises(RuntimeError, match="synthetic activation failure"):
            subject.admit()
    else:
        assert isinstance(subject.admit(), AccessDenied)
    assert subject.store.borrowed == bytearray(32)
    assert not subject.owner.active


def test_refresh_uses_live_facts_and_cannot_resurrect_expired_or_disconnected_leases(subject: Subject) -> None:
    session = subject.admit()
    assert isinstance(session, AccessSession)
    subject.advance(240)
    renewed = subject.authority.refresh_api_key(connection_id=subject.connection, session_id=session.session_id)
    assert isinstance(renewed, AccessSession) and renewed.expires_at > session.expires_at
    assert renewed.grant_id == session.grant_id and subject.owner.login_calls == 0
    subject.advance(301)
    refused = subject.authority.refresh_api_key(connection_id=subject.connection, session_id=session.session_id)
    assert isinstance(refused, AccessDenied) and refused.code is AccessDenialCode.SESSION_EXPIRED
    fresh = subject.admit()
    assert isinstance(fresh, AccessSession) and fresh.session_id != session.session_id
    subject.authority.disconnect(subject.connection)
    assert not subject.owner.active
    refused = subject.authority.refresh_api_key(connection_id=subject.connection, session_id=fresh.session_id)
    assert isinstance(refused, AccessDenied)
    assert isinstance(subject.admit(), AccessSession)


def test_revoked_key_and_lost_boot_refuse_refresh(subject: Subject) -> None:
    session = subject.admit()
    assert isinstance(session, AccessSession)
    replacement = subject.new_authority()
    assert isinstance(
        replacement.refresh_api_key(connection_id=subject.connection, session_id=session.session_id), AccessDenied
    )
    state = subject.store.enrollment_state()
    entry = state.grants[0]
    key = entry.keys[0]
    revoked = changed(entry, keys=(changed(key, key=changed(key.key, state=AuthorityState.REVOKED)),))
    subject.store.publish_enrollment(changed(state, grants=(revoked,)))
    result = subject.authority.refresh_api_key(connection_id=subject.connection, session_id=session.session_id)
    assert isinstance(result, AccessDenied) and result.code is AccessDenialCode.KEY_INACTIVE


def test_child_scope_and_budget_are_narrowed_and_disconnect_cascades(subject: Subject) -> None:
    parent = subject.admit()
    assert isinstance(parent, AccessSession) and parent.grant_id is not None
    recipient = uuid4()
    subject.owner.connections[recipient] = parent.client_id
    subject.advance(60)
    child = subject.authority.delegate(
        connection_id=subject.connection,
        parent_session_id=parent.session_id,
        recipient_connection_id=recipient,
        grant_id=parent.grant_id,
        scope=changed(parent.scope, allow_delegation=False, actions=frozenset()),
    )
    assert isinstance(child, AccessSession)
    assert child.parent_session_id == parent.session_id and child.expires_at == parent.expires_at
    assert not child.scope.actions and not child.scope.allow_delegation
    subject.authority.disconnect(subject.connection)
    assert not subject.owner.active
    status = subject.authority.status(
        connection_id=recipient,
        session_id=child.session_id,
        published_authority=Availability.UNAVAILABLE,
        provider=Availability.NOT_REQUIRED,
    )
    assert not isinstance(status, AccessDenied) and not status.credential_authenticated


def test_password_login_remains_independent_of_unavailable_automation(subject: Subject) -> None:
    subject.enrollment.native.unavailable = True
    result = subject.authority.admit_human(connection_id=subject.connection)
    assert isinstance(result, AccessSession) and result.kind is SessionKind.HUMAN
    assert result.originating_login_id == "test-login"
    assert subject.store.borrowed is None
    status = subject.authority.status(
        connection_id=subject.connection,
        session_id=result.session_id,
        published_authority=Availability.UNAVAILABLE,
        provider=Availability.NOT_REQUIRED,
    )
    assert not isinstance(status, AccessDenied) and status.credential_authenticated
    subject.authority.invalidate_login("test-login")
    status = subject.authority.status(
        connection_id=subject.connection,
        session_id=result.session_id,
        published_authority=Availability.UNAVAILABLE,
        provider=Availability.NOT_REQUIRED,
    )
    assert not isinstance(status, AccessDenied) and not status.credential_authenticated


@pytest.mark.parametrize("clock", ["utc", "monotonic"])
def test_observed_clock_rollback_requires_new_admission(subject: Subject, clock: str) -> None:
    session = subject.admit()
    assert isinstance(session, AccessSession)
    subject.advance(60)
    renewed = subject.authority.refresh_api_key(connection_id=subject.connection, session_id=session.session_id)
    assert isinstance(renewed, AccessSession)
    previous = subject.owner.current
    context = previous.context
    if clock == "utc":
        context = changed(context, now=context.now - timedelta(seconds=1))
    else:
        context = changed(context, monotonic_now=context.monotonic_now - 1)
    subject.owner.current = SessionAuthorityFacts(previous.profile, context)
    refused = subject.authority.refresh_api_key(connection_id=subject.connection, session_id=session.session_id)
    assert isinstance(refused, AccessDenied) and refused.code is AccessDenialCode.CLOCK_INVALID
    assert not subject.owner.active
    subject.owner.current = previous
    assert isinstance(
        subject.authority.refresh_api_key(connection_id=subject.connection, session_id=session.session_id), AccessDenied
    )
    assert isinstance(subject.admit(), AccessSession)


def test_attended_logout_is_irreversible_and_does_not_revoke_independent_api(subject: Subject) -> None:
    api = subject.admit()
    human = subject.authority.admit_human(connection_id=subject.connection)
    assert isinstance(api, AccessSession) and api.grant_id is not None
    assert isinstance(human, AccessSession)
    recipient = uuid4()
    subject.owner.connections[recipient] = api.client_id
    child = subject.authority.delegate(
        connection_id=subject.connection,
        parent_session_id=human.session_id,
        recipient_connection_id=recipient,
        grant_id=api.grant_id,
        scope=human.scope,
    )
    assert isinstance(child, AccessSession) and child.kind is SessionKind.ATTENDED
    assert child.originating_login_id == human.originating_login_id
    before = subject.owner.current.context
    other_login = changed(before.login_contexts[0], login_id="another-verified-login")
    subject.owner.current = SessionAuthorityFacts(
        subject.owner.current.profile,
        changed(before, login_contexts=(other_login,)),
    )
    status = subject.authority.status(
        connection_id=recipient,
        session_id=child.session_id,
        published_authority=Availability.AVAILABLE,
        provider=Availability.NOT_REQUIRED,
    )
    assert not isinstance(status, AccessDenied) and not status.credential_authenticated
    assert subject.owner.active == {api.session_id}
    assert isinstance(
        subject.authority.refresh_api_key(connection_id=subject.connection, session_id=api.session_id), AccessSession
    )
    subject.owner.current = SessionAuthorityFacts(subject.owner.current.profile, before)
    status = subject.authority.status(
        connection_id=recipient,
        session_id=child.session_id,
        published_authority=Availability.AVAILABLE,
        provider=Availability.NOT_REQUIRED,
    )
    assert not isinstance(status, AccessDenied) and not status.credential_authenticated


def test_cross_connection_lookup_cannot_disclose_or_retire_victims_session(subject: Subject) -> None:
    session = subject.admit()
    assert isinstance(session, AccessSession)
    other = uuid4()
    subject.owner.connections[other] = uuid4()
    status = subject.authority.status(
        connection_id=other,
        session_id=session.session_id,
        published_authority=Availability.AVAILABLE,
        provider=Availability.NOT_REQUIRED,
    )
    assert isinstance(status, AccessDenied) and status.code is AccessDenialCode.CONNECTION_MISMATCH
    assert isinstance(
        subject.authority.refresh_api_key(connection_id=other, session_id=session.session_id), AccessDenied
    )
    assert subject.owner.active == {session.session_id}


def test_child_expiry_clips_to_remaining_monotonic_parent_budget(subject: Subject) -> None:
    parent = subject.admit()
    assert isinstance(parent, AccessSession) and parent.grant_id is not None
    recipient = uuid4()
    subject.owner.connections[recipient] = parent.client_id
    context = subject.owner.current.context
    subject.owner.current = SessionAuthorityFacts(
        subject.owner.current.profile,
        changed(context, now=context.now + timedelta(seconds=1), monotonic_now=context.monotonic_now + 295),
    )
    child = subject.authority.delegate(
        connection_id=subject.connection,
        parent_session_id=parent.session_id,
        recipient_connection_id=recipient,
        grant_id=parent.grant_id,
        scope=parent.scope,
    )
    assert isinstance(child, AccessSession)
    assert child.expires_at - child.issued_at == timedelta(seconds=5)


def test_failed_human_binding_releases_candidate_custody(subject: Subject) -> None:
    subject.owner.human_login_id = "unverified-origin"
    result = subject.authority.admit_human(connection_id=subject.connection)
    assert isinstance(result, AccessDenied) and result.code is AccessDenialCode.OS_SESSION_UNAVAILABLE
    assert not subject.owner.active and subject.owner.human_released


@pytest.mark.asyncio
async def test_shutdown_fences_all_leases_even_when_one_cleanup_fails(subject: Subject) -> None:
    first, second = subject.admit(), subject.admit()
    assert isinstance(first, AccessSession) and isinstance(second, AccessSession)
    subject.owner.failed_retirements.add(first.session_id)
    with pytest.raises(ExceptionGroup, match="session custody retirement failed"):
        await subject.authority.close()
    assert {first.session_id, second.session_id} <= set(subject.owner.retired)
    assert not subject.owner.active
    refused = subject.admit()
    assert isinstance(refused, AccessDenied) and refused.code is AccessDenialCode.RUNTIME_CHANGED
    with pytest.raises(ExceptionGroup, match="session custody retirement failed"):
        await subject.authority.close()
    assert subject.owner.retired.count(first.session_id) == 2
    assert subject.owner.retired.count(second.session_id) == 1
    subject.owner.failed_retirements.clear()
    await subject.authority.close()
    assert subject.owner.retired.count(first.session_id) == 3
    await subject.authority.close()
    assert subject.owner.retired.count(first.session_id) == 3


@pytest.mark.parametrize("kind", ["api", "human"])
def test_resource_exit_failure_retires_already_accepted_candidate(subject: Subject, kind: str) -> None:
    subject.store.fail_release = True
    subject.owner.fail_human_release = True
    with pytest.raises(RuntimeError, match="release failure"):
        if kind == "api":
            subject.admit()
        else:
            subject.authority.admit_human(connection_id=subject.connection)
    assert not subject.owner.active
    assert subject.owner.retired
    for session_id in subject.owner.retired:
        status = subject.authority.status(
            connection_id=subject.connection,
            session_id=session_id,
            published_authority=Availability.AVAILABLE,
            provider=Availability.NOT_REQUIRED,
        )
        assert not isinstance(status, AccessDenied) and not status.credential_authenticated


def test_current_session_lock_does_not_revoke_key_or_another_connection(subject: Subject) -> None:
    first = subject.admit()
    second = subject.admit()
    assert isinstance(first, AccessSession) and isinstance(second, AccessSession)
    refused = subject.authority.lock_session(
        connection_id=subject.connection, session_id=first.session_id, target_session_id=second.session_id
    )
    assert isinstance(refused, AccessDenied) and refused.code is AccessDenialCode.HUMAN_AUTHORITY_REQUIRED
    locked = subject.authority.lock_session(
        connection_id=subject.connection, session_id=first.session_id, target_session_id=first.session_id
    )
    assert locked == (first.session_id,)
    assert subject.owner.active == {second.session_id}
    fresh = subject.admit()
    assert isinstance(fresh, AccessSession) and fresh.session_id != first.session_id


def test_refresh_updates_worker_deadline_and_failure_retires_the_original_lease(subject: Subject) -> None:
    api = subject.admit()
    assert isinstance(api, AccessSession)
    subject.advance(30)
    refreshed = subject.authority.refresh_api_key(connection_id=subject.connection, session_id=api.session_id)
    assert isinstance(refreshed, AccessSession) and refreshed.expires_at > api.expires_at
    assert subject.owner.refreshed == [refreshed]
    subject.advance(30)
    subject.owner.fail_refresh = True
    with pytest.raises(RuntimeError, match="synthetic worker refresh failure"):
        subject.authority.refresh_api_key(connection_id=subject.connection, session_id=api.session_id)
    assert api.session_id not in subject.owner.active
    assert isinstance(
        subject.authority.refresh_api_key(connection_id=subject.connection, session_id=api.session_id), AccessDenied
    )


@pytest.mark.parametrize("cleanup_failure", [False, True])
def test_key_revocation_fences_all_derived_leases_even_when_worker_cleanup_fails(
    subject: Subject, cleanup_failure: bool
) -> None:
    first, second = subject.admit(), subject.admit()
    human = subject.authority.admit_human(connection_id=subject.connection)
    assert isinstance(first, AccessSession) and isinstance(second, AccessSession) and isinstance(human, AccessSession)
    if cleanup_failure:
        subject.owner.failed_retirements.add(first.session_id)
    result = lifecycle(subject, human).deny(
        AutomationDenial(
            request_id=uuid4(), binding=first.binding, kind=AutomationDenialKind.KEY, target_id=first.key_id
        )
    )
    assert result.access_denied and result.cleanup_pending == cleanup_failure
    assert subject.owner.active == {human.session_id}
    assert isinstance(subject.admit(), AccessDenied)
    assert isinstance(
        subject.authority.refresh_api_key(connection_id=subject.connection, session_id=second.session_id), AccessDenied
    )


def test_global_lock_requires_exact_password_selection_before_new_api_admission(subject: Subject) -> None:
    api = subject.admit()
    human = subject.authority.admit_human(connection_id=subject.connection)
    assert isinstance(api, AccessSession) and api.grant_id is not None and isinstance(human, AccessSession)
    service = lifecycle(subject, human)
    receipt = service.deny(
        AutomationDenial(request_id=uuid4(), binding=api.binding, kind=AutomationDenialKind.PROFILE_LOCK)
    )
    assert receipt.access_denied and not receipt.cleanup_pending and not subject.owner.active
    assert isinstance(subject.admit(), AccessDenied)
    assert isinstance(subject.authority.admit_human(connection_id=subject.connection), AccessDenied)
    selection = AutomationResumeRequest(
        request_id=uuid4(),
        profile_id=api.binding.profile_id,
        lock_generation=subject.owner.current.profile.lock_generation,
        grants=frozenset({api.grant_id}),
    )
    # Key possession is never a replacement for the password proof.
    with pytest.raises(AutomationCustodyError):
        service.resume(selection, password=subject.credential)
    assert not subject.store.snapshot().automation_enabled
    result = service.resume(selection, password=SecretBytes(PROFILE_INPUT.encode()))
    assert result.reactivated_grants == selection.grants
    fresh = subject.admit()
    assert isinstance(fresh, AccessSession) and fresh.session_id != api.session_id
    assert fresh.profile_lock_generation > api.profile_lock_generation
    assert isinstance(
        subject.authority.refresh_api_key(connection_id=subject.connection, session_id=api.session_id), AccessDenied
    )


def test_restricted_session_cannot_revoke_profile_automation(subject: Subject) -> None:
    api = subject.admit()
    assert isinstance(api, AccessSession)
    before = subject.store.snapshot()
    with pytest.raises(AutomationCustodyError):
        lifecycle(subject, api).deny(
            AutomationDenial(request_id=uuid4(), binding=api.binding, kind=AutomationDenialKind.ALL)
        )
    assert subject.store.snapshot() == before and subject.owner.active == {api.session_id}


def test_password_unlock_without_native_store_keeps_automation_denied_until_selected_resume(subject: Subject) -> None:
    api = subject.admit()
    human = subject.authority.admit_human(connection_id=subject.connection)
    assert isinstance(api, AccessSession) and api.grant_id is not None and isinstance(human, AccessSession)
    original = subject.store.snapshot().grants[0]
    service = lifecycle(subject, human)
    subject.enrollment.native.unavailable = True
    receipt = service.deny(
        AutomationDenial(request_id=uuid4(), binding=api.binding, kind=AutomationDenialKind.PROFILE_LOCK)
    )
    assert receipt.access_denied and receipt.cleanup_pending and receipt.profile_lock_generation == 1
    selected = AutomationResumeRequest(
        request_id=uuid4(), profile_id=api.binding.profile_id, lock_generation=1, grants=frozenset({api.grant_id})
    )
    with pytest.raises(AutomationCustodyError):
        service.resume(selected, password=SecretBytes(PROFILE_INPUT.encode()))
    empty = changed(selected, request_id=uuid4(), grants=frozenset())
    with pytest.raises(AutomationCustodyError):
        service.resume(empty, password=subject.credential)
    assert subject.store.profile_lock_state().globally_locked
    result = service.resume(empty, password=SecretBytes(PROFILE_INPUT.encode()))
    assert result.revision is None and not result.reactivated_grants
    assert isinstance(subject.authority.admit_human(connection_id=subject.connection), AccessSession)
    with pytest.raises(AutomationCustodyError) as refusal:
        subject.admit()
    assert refusal.value.reason is AutomationCustodyCode.NEEDS_USER
    restarted = AutomationControlStore(
        root=subject.store.root, binding=subject.store.binding, secrets_store=subject.enrollment.native
    )
    assert restarted.profile_lock_state() == subject.store.profile_lock_state()
    assert not restarted.profile_lock_state().globally_locked
    assert (subject.store.directory / "denial.json").is_file()
    subject.enrollment.native.unavailable = False
    cleanup = restarted.reconcile_denial()
    assert cleanup is not None and not cleanup.cleanup_pending
    assert not restarted.profile_lock_state().globally_locked
    assert isinstance(subject.admit(), AccessDenied)
    result = service.resume(selected, password=SecretBytes(PROFILE_INPUT.encode()))
    assert result.reactivated_grants == selected.grants
    assert isinstance(subject.admit(), AccessSession)
    resumed = subject.store.snapshot().grants[0]
    assert (resumed.scope, resumed.expires_at) == (original.scope, original.expires_at)


def test_host_poll_retires_expired_access_without_a_frontend_request(subject: Subject) -> None:
    api = subject.admit()
    assert isinstance(api, AccessSession)
    subject.advance(301)
    assert subject.authority.revalidate_sessions() == (api.session_id,)
    assert not subject.owner.active
    assert not subject.authority.revalidate_sessions()


def test_host_poll_preserves_password_access_when_automation_storage_is_lost(subject: Subject) -> None:
    api = subject.admit()
    human = subject.authority.admit_human(connection_id=subject.connection)
    assert isinstance(api, AccessSession) and isinstance(human, AccessSession)
    subject.enrollment.native.unavailable = True
    assert subject.authority.revalidate_sessions() == (api.session_id,)
    assert subject.owner.active == {human.session_id}


def test_profile_lock_intent_recovers_local_fence_before_native_store_returns(subject: Subject) -> None:
    human = subject.authority.admit_human(connection_id=subject.connection)
    assert isinstance(human, AccessSession)
    subject.enrollment.native.unavailable = True
    receipt = lifecycle(subject, human).deny(
        AutomationDenial(request_id=uuid4(), binding=human.binding, kind=AutomationDenialKind.PROFILE_LOCK)
    )
    assert receipt.cleanup_pending
    # Simulate loss after denial publication but before the local lock write.
    (subject.store.directory / "profile-lock.json").unlink()
    restarted = AutomationControlStore(
        root=subject.store.root, binding=subject.store.binding, secrets_store=subject.enrollment.native
    )
    state = restarted.profile_lock_state()
    assert state.globally_locked and state.generation == 1
    assert restarted.profile_lock_state() == state


def test_unselected_suspended_grant_stays_suspended_across_another_profile_lock(subject: Subject) -> None:
    api = subject.admit()
    assert isinstance(api, AccessSession) and api.grant_id is not None
    for selected in (frozenset(), frozenset({api.grant_id})):
        human = subject.authority.admit_human(connection_id=subject.connection)
        assert isinstance(human, AccessSession)
        service = lifecycle(subject, human)
        service.deny(AutomationDenial(request_id=uuid4(), binding=api.binding, kind=AutomationDenialKind.PROFILE_LOCK))
        assert subject.store.snapshot().grants[0].state is AuthorityState.SUSPENDED
        service.resume(
            AutomationResumeRequest(
                request_id=uuid4(),
                profile_id=api.binding.profile_id,
                lock_generation=subject.owner.current.profile.lock_generation,
                grants=selected,
            ),
            password=SecretBytes(PROFILE_INPUT.encode()),
        )
        if not selected:
            assert isinstance(subject.admit(), AccessDenied)
    assert isinstance(subject.admit(), AccessSession)


def test_revocation_serializes_against_material_release_and_retires_the_winning_admission(subject: Subject) -> None:
    human = subject.authority.admit_human(connection_id=subject.connection)
    assert isinstance(human, AccessSession)
    service = lifecycle(subject, human)
    unwrapped, release, revoking = Event(), Event(), Event()

    def pause() -> None:
        unwrapped.set()
        assert release.wait(10)

    def revoke() -> AutomationDenialReceipt:
        revoking.set()
        return service.deny(AutomationDenial(request_id=uuid4(), binding=human.binding, kind=AutomationDenialKind.ALL))

    subject.store.after_unwrap = pause
    with ThreadPoolExecutor(max_workers=2) as executor:
        admission = executor.submit(copy_context().run, subject.admit)
        try:
            assert unwrapped.wait(10)
            denial = executor.submit(copy_context().run, revoke)
            assert revoking.wait(10)
            assert not denial.done()
        finally:
            release.set()
        admitted = admission.result(timeout=10)
        assert isinstance(admitted, AccessSession)
        result = denial.result(timeout=10)
    assert isinstance(result, AutomationDenialReceipt)
    assert result.access_denied and not result.cleanup_pending
    assert subject.owner.active == {human.session_id}
    assert admitted.session_id in subject.owner.retired
    assert isinstance(subject.admit(), AccessDenied)


def test_operation_guard_orders_revocation_and_never_enters_after_denial(subject: Subject) -> None:
    """Exercise the real grant/store authority fence, without claiming a domain commit."""
    api = subject.admit()
    human = subject.authority.admit_human(connection_id=subject.connection)
    assert isinstance(api, AccessSession) and isinstance(human, AccessSession)
    service = lifecycle(subject, human)
    definitions = build_user_profile_operation_definitions()
    registry = OperationRegistry(
        definitions=definitions, public_registrations=build_user_profile_operation_registrations(definitions)
    )
    definition_id = "user-profile.field-mutation"
    request = OperationAccessRequest(
        profile_id=api.binding.profile_id,
        definition_id=definition_id,
        action=AccessAction.COMMIT,
        frontend=OperationFrontendProjection.CLI,
        periods=frozenset(),
        period_independent=True,
        destination_id=uuid4(),
    )
    policy = OperationAccessPolicy(
        definition_id=definition_id,
        definition_contract_digest=registry.lookup_public_contract(definition_id).definition_contract_digest,
        actions=frozenset({AccessAction.COMMIT}),
        disclosures=frozenset(),
        periods=None,
        allow_period_independent=True,
        backend=Availability.AVAILABLE,
        published_authority=Availability.AVAILABLE,
        provider=Availability.NOT_REQUIRED,
        transaction_authority_required=False,
    )
    entered, release, revoking = Event(), Event(), Event()
    effects: list[str] = []

    def guarded() -> None:
        with subject.authority.operation_guard(
            connection_id=subject.connection,
            session_id=api.session_id,
            request=request,
            policy=policy,
            registry=registry,
        ):
            entered.set()
            assert release.wait(10)
            effects.append("protected body completed")

    def deny() -> AutomationDenialReceipt:
        revoking.set()
        return service.deny(AutomationDenial(request_id=uuid4(), binding=api.binding, kind=AutomationDenialKind.ALL))

    with ThreadPoolExecutor(max_workers=2) as executor:
        operation = executor.submit(copy_context().run, guarded)
        try:
            assert entered.wait(10)
            denial = executor.submit(copy_context().run, deny)
            assert revoking.wait(10)
            assert not denial.done()
        finally:
            release.set()
        operation.result(timeout=10)
        assert denial.result(timeout=10).access_denied
    with (
        pytest.raises(ProfileAccessRefusedError),
        subject.authority.operation_guard(
            connection_id=subject.connection,
            session_id=api.session_id,
            request=request,
            policy=policy,
            registry=registry,
        ),
    ):
        effects.append("forbidden body")
    assert effects == ["protected body completed"]
