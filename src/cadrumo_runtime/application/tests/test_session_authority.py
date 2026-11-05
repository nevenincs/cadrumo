"""Real encrypted-custody admission with explicit lifecycle/native-store doubles.

No installed runtime, native credential backend or OS lifecycle event is proved
by these tests. Ciphertext, password proof, key verification and control recovery
use their production implementations against test-owned synthetic profiles.
"""

from __future__ import annotations

import asyncio
from datetime import timedelta
from typing import override
from uuid import uuid4

import pytest
from pydantic import SecretBytes

from cadrumo.adapters.persistence.storage.custody.automation_store import AutomationControlStore
from cadrumo.adapters.persistence.storage.custody.sign_in_generation import SignInGenerationCustody
from cadrumo.adapters.persistence.storage.custody.tests.enrollment_support import (
    PROFILE_INPUT,
    changed,
)
from cadrumo.application.user_profile.access_administration import (
    AccessAdministrationAction,
    AccessAdministrationRequest,
    evaluate_access_administration,
)
from cadrumo.application.user_profile.access_contracts import (
    ACCESS_LEASE_MAXIMUM,
    AccessSession,
    OsLockState,
    SessionKind,
)
from cadrumo.application.user_profile.access_errors import ProfileAccessRefusedError
from cadrumo.application.user_profile.access_projections import project_access_session
from cadrumo.application.user_profile.automation_lifecycle import (
    AutomationDenial,
    AutomationDenialKind,
)
from cadrumo.core.async_cleanup import AsyncResourceCleanupError, await_cancellation_complete, close_async_resources
from cadrumo_client.contracts.access_refusals import AccessDenialCode, AccessDenied, ProfileAccessStatus
from cadrumo_client.contracts.access_vocabulary import (
    AuthorityState,
    Availability,
)
from cadrumo_client.contracts.automation_codes import AutomationCustodyCode, AutomationCustodyError
from cadrumo_client.contracts.automation_lifecycle import AutomationResumeRequest

from ..session_authority_contracts import SessionAuthorityFacts
from .session_authority_support import (
    AdmissionOwner,
    Subject,
    attended_tree,
    lifecycle,
    retry_incomplete_cleanup_then_close,
)

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_persistence_adapter,
    pytest.mark.usefixtures("authority_operation"),
]


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
        attempted = subject.owner.activation_attempt
        assert attempted is not None
        status = subject.authority.status(
            connection_id=subject.connection,
            session_id=attempted,
            published_authority=Availability.AVAILABLE,
            provider=Availability.NEEDS_USER,
        )
        assert isinstance(status, ProfileAccessStatus)
        assert not status.credential_authenticated
        assert status.profile_id is None and status.session_id is None
        assert status.denial is AccessDenialCode.AUTHENTICATION_REQUIRED
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
    subject.owner.current = SessionAuthorityFacts(
        subject.owner.current.profile,
        changed(subject.owner.current.context, login_contexts=()),
    )
    assert subject.authority.revalidate_sessions() == (result.session_id,)
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
    api, human, child, recipient = attended_tree(subject)
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


@pytest.mark.parametrize("lock_state", [OsLockState.LOCKED, OsLockState.UNKNOWN])
def test_attended_login_without_unlocked_evidence_retires_human_but_not_api(
    subject: Subject, lock_state: OsLockState
) -> None:
    api = subject.admit()
    human = subject.authority.admit_human(connection_id=subject.connection)
    assert isinstance(api, AccessSession) and isinstance(human, AccessSession)
    before = subject.owner.current.context
    observed = changed(before.login_contexts[0], lock_state=lock_state)
    subject.owner.current = SessionAuthorityFacts(
        subject.owner.current.profile, changed(before, login_contexts=(observed,))
    )
    status = subject.authority.status(
        connection_id=subject.connection,
        session_id=human.session_id,
        published_authority=Availability.AVAILABLE,
        provider=Availability.NOT_REQUIRED,
    )
    assert not isinstance(status, AccessDenied) and not status.credential_authenticated
    assert subject.owner.active == {api.session_id}
    subject.owner.current = SessionAuthorityFacts(subject.owner.current.profile, before)
    status = subject.authority.status(
        connection_id=subject.connection,
        session_id=human.session_id,
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


def test_failed_worker_preparation_does_not_publish_human_session(subject: Subject) -> None:
    subject.owner.fail_human_bind = True
    with pytest.raises(RuntimeError, match="synthetic worker preparation failure"):
        subject.authority.admit_human(connection_id=subject.connection)
    attempted = subject.owner.human_bind_attempt
    assert attempted is not None
    assert not subject.owner.active and subject.owner.human_released
    status = subject.authority.status(
        connection_id=subject.connection,
        session_id=attempted,
        published_authority=Availability.AVAILABLE,
        provider=Availability.NEEDS_USER,
    )
    assert isinstance(status, ProfileAccessStatus)
    assert not status.credential_authenticated
    assert status.profile_id is None and status.session_id is None
    assert status.denial is AccessDenialCode.AUTHENTICATION_REQUIRED


@pytest.mark.asyncio
async def test_failed_human_binding_preserves_primary_and_retryable_candidate_retirement(subject: Subject) -> None:
    primary = RuntimeError("synthetic original human binding failure")

    class FailedCandidateOwner(AdmissionOwner):
        @override
        def bind_human(self, session: AccessSession) -> None:
            self.failed_retirements.add(session.session_id)
            try:
                super().bind_human(session)
            except RuntimeError:
                raise primary from None

    owner = FailedCandidateOwner(subject.enrollment)
    owner.fail_human_bind = True
    subject.owner = owner
    subject.authority = subject.new_authority()
    with pytest.raises(RuntimeError) as refused:
        subject.authority.admit_human(connection_id=subject.connection)
    assert refused.value is primary
    attempted = owner.human_bind_attempt
    assert attempted is not None
    assert owner.human_released and not owner.active
    cleanup = primary.__dict__.get("async_cleanup_error")
    assert isinstance(cleanup, AsyncResourceCleanupError)
    assert owner.retired.count(attempted) == 1

    await retry_incomplete_cleanup_then_close(subject, owner, cleanup, attempted)


@pytest.mark.asyncio
async def test_cancelled_human_binding_retains_prior_cleanup_and_candidate_retirement(subject: Subject) -> None:
    primary = asyncio.CancelledError("synthetic original human binding cancellation")

    class EarlierOwner:
        def __init__(self) -> None:
            self.calls = 0
            self.failed = True
            self.released = False

        async def close(self) -> None:
            if self.released:
                return
            self.calls += 1
            if self.failed:
                raise RuntimeError("synthetic earlier native close failure")
            self.released = True

    earlier = EarlierOwner()
    with pytest.raises(asyncio.CancelledError) as prior:
        await await_cancellation_complete(
            close_async_resources(earlier, task_name="earlier-human-cleanup", primary_error=None),
            task_name="cancelled-earlier-human-cleanup",
            cancellation=primary,
        )
    assert prior.value is primary
    assert isinstance(primary.__dict__.get("cleanup_error"), AsyncResourceCleanupError)
    assert "async_cleanup_error" not in primary.__dict__
    assert earlier.calls == 1

    class FailedCandidateOwner(AdmissionOwner):
        @override
        def bind_human(self, session: AccessSession) -> None:
            self.failed_retirements.add(session.session_id)
            try:
                super().bind_human(session)
            except RuntimeError:
                raise primary from None

    owner = FailedCandidateOwner(subject.enrollment)
    owner.fail_human_bind = True
    subject.owner = owner
    subject.authority = subject.new_authority()
    with pytest.raises(asyncio.CancelledError) as refused:
        subject.authority.admit_human(connection_id=subject.connection)
    assert refused.value is primary
    attempted = owner.human_bind_attempt
    assert attempted is not None
    assert owner.human_released and not owner.active
    assert owner.retired.count(attempted) == 1
    cleanup = primary.__dict__.get("async_cleanup_error")
    assert isinstance(cleanup, AsyncResourceCleanupError)
    assert primary.__dict__.get("cleanup_error") is cleanup
    owner.failed_retirements.clear()
    earlier.failed = False
    await cleanup.retry_cleanup()
    assert earlier.released and earlier.calls == 2
    assert owner.retired.count(attempted) == 2
    status = subject.authority.status(
        connection_id=subject.connection,
        session_id=attempted,
        published_authority=Availability.AVAILABLE,
        provider=Availability.NOT_REQUIRED,
    )
    assert isinstance(status, ProfileAccessStatus)
    assert not status.credential_authenticated and status.session_id is None
    assert status.denial is AccessDenialCode.AUTHENTICATION_REQUIRED
    await subject.authority.close()
    assert owner.retired.count(attempted) == 2 and earlier.calls == 2


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
    sign_in = SignInGenerationCustody(root=subject.store.root, binding=subject.store.binding)
    before_sign_in = sign_in.establish().current
    # Key possession is never a replacement for the password proof.
    with pytest.raises(AutomationCustodyError):
        service.resume(selection, password=subject.credential)
    assert not subject.store.snapshot().automation_enabled
    assert sign_in.observe().current == before_sign_in
    result = service.resume(selection, password=SecretBytes(PROFILE_INPUT.encode()))
    assert result.reactivated_grants == selection.grants
    after_sign_in = sign_in.observe().current
    assert after_sign_in is not None and after_sign_in.generation == before_sign_in.generation + 1
    assert result.human_sign_in_revocation is not None
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


def test_revalidation_is_due_when_the_earliest_lease_lapses_by_either_clock(subject: Subject) -> None:
    context = subject.owner.current.context
    assert subject.authority.revalidation_due(monotonic_now=context.monotonic_now, wall_now=context.now) is None
    api = subject.admit()
    assert isinstance(api, AccessSession)
    lifetime = (api.expires_at - api.issued_at).total_seconds()
    due = subject.authority.revalidation_due(monotonic_now=context.monotonic_now, wall_now=context.now)
    assert due == api.issued_monotonic + lifetime
    # A wall clock that has run ahead brings the lapse forward; the earlier bound wins.
    ahead = subject.authority.revalidation_due(
        monotonic_now=context.monotonic_now, wall_now=context.now + timedelta(seconds=100)
    )
    assert ahead == context.monotonic_now + lifetime - 100
    subject.advance(lifetime + 1)
    assert subject.authority.revalidate_sessions() == (api.session_id,)
    later = subject.owner.current.context
    assert subject.authority.revalidation_due(monotonic_now=later.monotonic_now, wall_now=later.now) is None


def test_host_poll_preserves_password_access_when_automation_storage_is_lost(subject: Subject) -> None:
    api = subject.admit()
    human = subject.authority.admit_human(connection_id=subject.connection)
    assert isinstance(api, AccessSession) and isinstance(human, AccessSession)
    subject.enrollment.native.unavailable = True
    assert subject.authority.revalidate_sessions() == (api.session_id,)
    assert subject.owner.active == {human.session_id}


def test_session_inventory_requires_current_human_and_revalidates_every_lease(subject: Subject) -> None:
    api = subject.admit()
    human = subject.authority.admit_human(connection_id=subject.connection)
    assert isinstance(api, AccessSession) and isinstance(human, AccessSession)
    inventory = subject.authority.session_inventory(connection_id=subject.connection, session_id=human.session_id)
    assert inventory == tuple(
        project_access_session(item) for item in sorted((api, human), key=lambda item: item.session_id)
    )
    assert tuple(item.session_id for item in inventory) == tuple(sorted((api.session_id, human.session_id)))
    assert not {"connection_id", "runtime_boot_id", "originating_login_id", "issued_monotonic"} & set(
        inventory[0].model_dump()
    )

    with pytest.raises(ProfileAccessRefusedError) as denied:
        subject.authority.session_inventory(connection_id=subject.connection, session_id=api.session_id)
    assert denied.value.reason is AccessDenialCode.HUMAN_AUTHORITY_REQUIRED
    foreign = uuid4()
    subject.owner.connections[foreign] = uuid4()
    with pytest.raises(ProfileAccessRefusedError) as mismatch:
        subject.authority.session_inventory(connection_id=foreign, session_id=human.session_id)
    assert mismatch.value.reason is AccessDenialCode.CONNECTION_MISMATCH

    subject.enrollment.native.unavailable = True
    assert subject.authority.session_inventory(connection_id=subject.connection, session_id=human.session_id) == (
        project_access_session(human),
    )
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
