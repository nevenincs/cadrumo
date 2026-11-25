"""Session authority human activity, lost-worker custody and suspended-lease recovery.

Explicit lifecycle and native-store doubles stand in for the host; ciphertext,
password proof and key verification use their production implementations.
"""

from __future__ import annotations

from datetime import timedelta
from uuid import uuid4

import pytest

from cadrumo.adapters.persistence.storage.custody.tests.enrollment_support import (
    changed,
)
from cadrumo.application.user_profile.access_contracts import (
    AccessSession,
    LoginEligibility,
    OsLockState,
    SessionKind,
)
from cadrumo.application.user_profile.access_errors import ProfileAccessRefusedError
from cadrumo.application.user_profile.session_retirement import SessionRetirement, SessionRetirementKind
from cadrumo_client.contracts.access_refusals import AccessDenialCode, AccessDenied, ProfileAccessStatus
from cadrumo_client.contracts.access_vocabulary import (
    Availability,
)
from cadrumo_client.contracts.automation_codes import AutomationCustodyCode, AutomationCustodyError

from ..session_authority_contracts import SessionAuthorityFacts
from .session_authority_support import (
    LifecycleOwner,
    Recovery,
    Subject,
    attended_tree,
    lock_native_login,
    read_guard,
    session_published,
)

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_persistence_adapter,
    pytest.mark.usefixtures("authority_operation"),
]


def test_human_activity_keeps_original_issuance_alive_beyond_four_hours(subject: Subject) -> None:
    human = subject.authority.admit_human(connection_id=subject.connection)
    assert isinstance(human, AccessSession)
    idle_window = human.expires_at - human.issued_at
    step = min(idle_window.total_seconds() / 2, 600)
    while subject.owner.current.context.now <= human.issued_at + timedelta(hours=5):
        subject.advance(step)
        renewed = subject.authority.note_human_activity(
            connection_id=subject.connection, session_id=human.session_id, idle_window=idle_window
        )
        assert isinstance(renewed, AccessSession)
        assert renewed.issued_at == human.issued_at
        assert renewed.session_id == human.session_id
        assert renewed.expires_at > subject.owner.current.context.now
    assert session_published(subject, human.session_id)
    assert subject.owner.login_calls == 1
    assert not subject.owner.retired


def test_human_activity_debounces_input_but_later_input_refreshes_worker(subject: Subject) -> None:
    human = subject.authority.admit_human(connection_id=subject.connection)
    assert isinstance(human, AccessSession)
    idle_window = human.expires_at - human.issued_at
    for _ in range(5):
        subject.advance(1)
        assert (
            subject.authority.note_human_activity(
                connection_id=subject.connection, session_id=human.session_id, idle_window=idle_window
            )
            == human
        )
    assert not subject.owner.refreshed
    subject.advance(60)
    renewed = subject.authority.note_human_activity(
        connection_id=subject.connection, session_id=human.session_id, idle_window=idle_window
    )
    assert isinstance(renewed, AccessSession)
    assert renewed.expires_at == subject.owner.current.context.now + idle_window
    assert subject.owner.refreshed == [renewed]
    assert renewed.issued_at == human.issued_at


def test_human_activity_cannot_revive_an_idle_expired_session(subject: Subject) -> None:
    human = subject.authority.admit_human(connection_id=subject.connection)
    assert isinstance(human, AccessSession)
    idle_window = human.expires_at - human.issued_at
    subject.advance(idle_window.total_seconds() + 1)
    result = subject.authority.note_human_activity(
        connection_id=subject.connection, session_id=human.session_id, idle_window=idle_window
    )
    assert isinstance(result, AccessDenied)
    assert not session_published(subject, human.session_id)
    assert human.session_id not in subject.owner.active
    assert not subject.owner.refreshed


def test_human_activity_from_another_connection_cannot_refresh_or_retire_the_session(subject: Subject) -> None:
    human = subject.authority.admit_human(connection_id=subject.connection)
    assert isinstance(human, AccessSession)
    foreign = uuid4()
    subject.owner.connections[foreign] = human.client_id
    subject.advance(60)
    result = subject.authority.note_human_activity(
        connection_id=foreign, session_id=human.session_id, idle_window=human.expires_at - human.issued_at
    )
    assert isinstance(result, AccessDenied) and result.code is AccessDenialCode.CONNECTION_MISMATCH
    assert not subject.owner.refreshed
    assert not subject.owner.retired
    assert session_published(subject, human.session_id)


def test_human_activity_after_logout_cannot_restore_authority(subject: Subject) -> None:
    human = subject.authority.admit_human(connection_id=subject.connection)
    assert isinstance(human, AccessSession)
    subject.authority.retire_human_sessions()
    subject.advance(60)
    result = subject.authority.note_human_activity(
        connection_id=subject.connection, session_id=human.session_id, idle_window=human.expires_at - human.issued_at
    )
    assert isinstance(result, AccessDenied) and result.code is AccessDenialCode.AUTHENTICATION_REQUIRED
    assert not subject.owner.active
    assert not subject.owner.refreshed
    assert subject.owner.login_calls == 1


def test_human_activity_renews_live_sibling_without_refreshing_api_authority(subject: Subject) -> None:
    human = subject.authority.admit_human(connection_id=subject.connection)
    assert isinstance(human, AccessSession)
    other = uuid4()
    subject.owner.connections[other] = human.client_id
    sibling = subject.authority.admit_human(connection_id=other)
    api = subject.admit()
    assert isinstance(sibling, AccessSession) and isinstance(api, AccessSession)
    subject.advance(60)
    renewed = subject.authority.note_human_activity(
        connection_id=subject.connection, session_id=human.session_id, idle_window=human.expires_at - human.issued_at
    )
    assert isinstance(renewed, AccessSession)
    refreshed = {session.session_id: session for session in subject.owner.refreshed}
    assert set(refreshed) == {human.session_id, sibling.session_id}
    assert refreshed[sibling.session_id].expires_at == renewed.expires_at
    assert refreshed[sibling.session_id].issued_at == sibling.issued_at
    refused = subject.authority.note_human_activity(
        connection_id=subject.connection, session_id=api.session_id, idle_window=timedelta(minutes=15)
    )
    assert isinstance(refused, AccessDenied) and refused.code is AccessDenialCode.PERSON_ACT_REQUIRED


def test_unknown_native_observation_denies_activity_without_retirement_and_recovers(subject: Subject) -> None:
    human = subject.authority.admit_human(connection_id=subject.connection)
    assert isinstance(human, AccessSession)
    subject.advance(60)
    before = subject.owner.current.context
    uncertain = changed(before.login_contexts[0], lock_state=OsLockState.UNKNOWN, unattended=LoginEligibility.UNKNOWN)
    subject.owner.current = SessionAuthorityFacts(
        subject.owner.current.profile, changed(before, login_contexts=(uncertain,))
    )
    result = subject.authority.note_human_activity(
        connection_id=subject.connection, session_id=human.session_id, idle_window=human.expires_at - human.issued_at
    )
    assert isinstance(result, AccessDenied) and result.code is AccessDenialCode.OS_SESSION_UNAVAILABLE
    status = subject.authority.status(
        connection_id=subject.connection,
        session_id=human.session_id,
        published_authority=Availability.AVAILABLE,
        provider=Availability.NOT_REQUIRED,
    )
    assert isinstance(status, ProfileAccessStatus)
    assert status.denial is AccessDenialCode.OS_SESSION_UNAVAILABLE
    assert status.credential_authenticated
    assert subject.owner.active == {human.session_id}
    assert not subject.owner.retired
    assert not subject.owner.refreshed
    subject.owner.current = SessionAuthorityFacts(subject.owner.current.profile, before)
    assert session_published(subject, human.session_id)
    renewed = subject.authority.note_human_activity(
        connection_id=subject.connection, session_id=human.session_id, idle_window=human.expires_at - human.issued_at
    )
    assert isinstance(renewed, AccessSession) and renewed.expires_at > human.expires_at
    assert subject.owner.login_calls == 1
    lock_native_login(subject)
    refused = subject.authority.note_human_activity(
        connection_id=subject.connection, session_id=human.session_id, idle_window=human.expires_at - human.issued_at
    )
    assert isinstance(refused, AccessDenied)
    assert human.session_id in subject.owner.retired
    subject.owner.current = SessionAuthorityFacts(subject.owner.current.profile, before)
    assert not session_published(subject, human.session_id)


def test_lost_worker_custody_still_retires_every_session_as_custody_unavailable(subject: Subject) -> None:
    """No lost custody survives a sweep: the attended child goes with its parent and the API session."""
    retired: list[SessionRetirement] = []
    subject.authority._retired = retired.append
    api, human, child, _ = attended_tree(subject)
    subject.owner.facts_failure = AutomationCustodyError(AutomationCustodyCode.UNAVAILABLE)
    subject.owner.lost = True

    assert set(subject.authority.revalidate_sessions()) == {api.session_id, human.session_id, child.session_id}
    assert not subject.owner.active
    assert {item.session_id for item in retired} == {api.session_id, human.session_id, child.session_id}
    assert {item.reason for item in retired} == {AccessDenialCode.CUSTODY_UNAVAILABLE}


def test_briefly_unobservable_worker_keeps_every_session_until_it_answers(subject: Subject) -> None:
    """A busy worker is not lost custody: the sweep keeps the tree, including the attended child, and retries."""
    retired: list[SessionRetirement] = []
    subject.authority._retired = retired.append
    api, human, child, _ = attended_tree(subject)
    subject.owner.facts_failure = AutomationCustodyError(AutomationCustodyCode.UNAVAILABLE)

    assert subject.authority.revalidate_sessions() == ()
    assert not retired
    assert {api.session_id, human.session_id, child.session_id} <= subject.owner.active

    subject.owner.facts_failure = None
    assert subject.authority.revalidate_sessions() == ()
    assert not retired

    subject.owner.facts_failure = AutomationCustodyError(AutomationCustodyCode.UNAVAILABLE)
    subject.owner.lost = True
    assert set(subject.authority.revalidate_sessions()) == {api.session_id, human.session_id, child.session_id}
    assert {item.reason for item in retired} == {AccessDenialCode.CUSTODY_UNAVAILABLE}


def test_worker_loss_suspends_every_lease_and_refuses_with_the_remaining_window(
    subject: Subject, recovery: Recovery
) -> None:
    api, human, child, _ = attended_tree(subject)

    assert recovery.lose_worker() == ()
    assert not recovery.retired
    assert {lease.session_id for batch in recovery.suspended for lease in batch} == {
        api.session_id,
        human.session_id,
        child.session_id,
    }
    status = recovery.status(human)
    assert isinstance(status, ProfileAccessStatus)
    assert status.session_id == human.session_id and status.session_expires_at == human.expires_at
    assert status.denial is AccessDenialCode.CUSTODY_RECOVERING
    assert status.recovery_remaining_seconds == 120 and not status.credential_authenticated

    recovery.clock.now += 30.5
    refused = subject.authority.refresh_api_key(connection_id=subject.connection, session_id=api.session_id)
    assert refused == AccessDenied(code=AccessDenialCode.CUSTODY_RECOVERING, recovery_remaining_seconds=90)
    with pytest.raises(ProfileAccessRefusedError) as raised, read_guard(subject, api):
        pytest.fail("a suspended lease granted an operation")
    assert raised.value.reason is AccessDenialCode.CUSTODY_RECOVERING
    assert raised.value.recovery_remaining_seconds == 90


def test_unrebound_leases_retire_as_custody_unavailable_when_the_window_ends(
    subject: Subject, recovery: Recovery
) -> None:
    api, human, child, _ = attended_tree(subject)
    recovery.lose_worker()

    recovery.clock.now += 119
    assert subject.authority.revalidate_sessions() == ()
    recovery.clock.now += 1
    assert set(subject.authority.revalidate_sessions()) == {api.session_id, human.session_id, child.session_id}
    assert {item.reason for item in recovery.retired} == {AccessDenialCode.CUSTODY_UNAVAILABLE}
    status = recovery.status(human)
    assert not isinstance(status, ProfileAccessStatus) or status.denial is not AccessDenialCode.CUSTODY_RECOVERING
    fresh = subject.authority.admit_human(connection_id=subject.connection)
    assert isinstance(fresh, AccessSession) and fresh.session_id != human.session_id


def test_a_lease_whose_own_deadline_passes_in_the_window_retires_at_that_deadline(
    subject: Subject, recovery: Recovery
) -> None:
    api = subject.admit()
    assert isinstance(api, AccessSession)
    recovery.lose_worker()
    subject.advance((api.expires_at - subject.owner.current.context.now).total_seconds())

    assert subject.authority.revalidate_sessions() == (api.session_id,)
    assert [item.reason for item in recovery.retired] == [AccessDenialCode.SESSION_EXPIRED]


def test_human_rebind_on_the_same_connection_keeps_the_identity_and_never_renews(
    subject: Subject, recovery: Recovery
) -> None:
    human = subject.authority.admit_human(connection_id=subject.connection)
    assert isinstance(human, AccessSession)
    subject.advance(100)
    recovery.lose_worker()
    subject.advance(10)

    rebound = subject.authority.admit_human(connection_id=subject.connection)

    assert isinstance(rebound, AccessSession)
    assert rebound.session_id == human.session_id and rebound.client_id == human.client_id
    assert rebound.expires_at <= human.expires_at
    assert rebound.issued_at == subject.owner.current.context.now
    assert human.session_id in subject.owner.human_bound
    assert recovery.live(rebound)
    assert not recovery.retired


def test_a_proof_from_another_connection_is_an_ordinary_sign_in_and_rebinds_nothing(
    subject: Subject, recovery: Recovery
) -> None:
    human = subject.authority.admit_human(connection_id=subject.connection)
    assert isinstance(human, AccessSession)
    recovery.lose_worker()
    other = uuid4()
    subject.owner.connections[other] = human.client_id

    fresh = subject.authority.admit_human(connection_id=other)

    assert isinstance(fresh, AccessSession) and fresh.session_id != human.session_id
    status = recovery.status(human)
    assert isinstance(status, ProfileAccessStatus) and status.denial is AccessDenialCode.CUSTODY_RECOVERING


def test_attended_child_returns_with_its_parent_while_its_connection_is_open(
    subject: Subject, recovery: Recovery
) -> None:
    api, human, child, recipient = attended_tree(subject)
    recovery.lose_worker()
    # The API lease's connection is the person's; only the key can rebind it.
    rebound = subject.authority.admit_human(connection_id=subject.connection)

    assert isinstance(rebound, AccessSession) and rebound.session_id == human.session_id
    assert recovery.live(child)
    assert child.session_id in subject.owner.active
    assert {lease.session_id for batch in recovery.rebound for lease in batch} >= {child.session_id}
    status = recovery.status(api)
    assert isinstance(status, ProfileAccessStatus) and status.denial is AccessDenialCode.CUSTODY_RECOVERING
    assert recipient in subject.owner.connections


def test_attended_child_whose_connection_closed_does_not_return(subject: Subject, recovery: Recovery) -> None:
    _, human, child, recipient = attended_tree(subject)
    recovery.lose_worker()
    subject.authority.disconnect(recipient)

    rebound = subject.authority.admit_human(connection_id=subject.connection)

    assert isinstance(rebound, AccessSession) and rebound.session_id == human.session_id
    # The retirement names whose lease ended: a delegated child's, not the person's.
    assert {item.session_kind for item in recovery.retired if item.session_id == child.session_id} == {
        SessionKind.ATTENDED
    }
    assert child.session_id not in subject.owner.active


def test_children_of_a_parent_that_never_rebinds_retire_with_it(subject: Subject, recovery: Recovery) -> None:
    _, human, child, _ = attended_tree(subject)
    recovery.lose_worker()
    recovery.clock.now += 120

    retired = set(subject.authority.revalidate_sessions())

    assert {human.session_id, child.session_id} <= retired


def test_api_key_lease_rebinds_only_when_its_key_is_presented_again(subject: Subject, recovery: Recovery) -> None:
    api = subject.admit()
    assert isinstance(api, AccessSession)
    recovery.lose_worker()

    refused = subject.authority.admit_human(connection_id=subject.connection)
    assert isinstance(refused, AccessDenied) and refused.code is AccessDenialCode.CUSTODY_RECOVERING
    status = recovery.status(api)
    assert isinstance(status, ProfileAccessStatus) and status.denial is AccessDenialCode.CUSTODY_RECOVERING

    rebound = subject.admit()

    assert isinstance(rebound, AccessSession)
    assert rebound.session_id == api.session_id and rebound.expires_at <= api.expires_at
    assert api.session_id in subject.owner.active
    assert recovery.live(rebound)


def test_api_key_rebind_rechecks_the_grant(subject: Subject, recovery: Recovery) -> None:
    api = subject.admit()
    assert isinstance(api, AccessSession)
    recovery.lose_worker()
    LifecycleOwner(subject, api).set_profile_lock(generation=subject.owner.current.profile.lock_generation, locked=True)

    refused = subject.admit()

    assert isinstance(refused, AccessDenied)
    assert api.session_id not in subject.owner.active


def test_a_second_loss_within_the_repeat_interval_retires_everything_at_once(
    subject: Subject, recovery: Recovery
) -> None:
    human = subject.authority.admit_human(connection_id=subject.connection)
    assert isinstance(human, AccessSession)
    recovery.lose_worker()
    rebound = subject.authority.admit_human(connection_id=subject.connection)
    assert isinstance(rebound, AccessSession) and rebound.session_id == human.session_id
    recovery.clock.now += 599

    assert recovery.lose_worker() == (human.session_id,)
    assert len(recovery.suspended) == 1
    assert [item.reason for item in recovery.retired] == [AccessDenialCode.CUSTODY_UNAVAILABLE]
    status = recovery.status(human)
    assert not isinstance(status, ProfileAccessStatus) or status.denial is not AccessDenialCode.CUSTODY_RECOVERING


def test_a_loss_after_the_repeat_interval_opens_a_new_window(subject: Subject, recovery: Recovery) -> None:
    human = subject.authority.admit_human(connection_id=subject.connection)
    assert isinstance(human, AccessSession)
    recovery.lose_worker()
    assert isinstance(subject.authority.admit_human(connection_id=subject.connection), AccessSession)
    recovery.clock.now += 600

    assert recovery.lose_worker() == ()
    assert len(recovery.suspended) == 2


def test_sign_out_during_suspension_ends_the_session_with_no_rebind(subject: Subject, recovery: Recovery) -> None:
    human = subject.authority.admit_human(connection_id=subject.connection)
    assert isinstance(human, AccessSession)
    recovery.lose_worker()

    subject.authority.require_human_sign_out(connection_id=subject.connection, session_id=human.session_id)
    assert subject.authority.retire_human_sessions() == (human.session_id,)

    assert [item.kind for item in recovery.retired] == [SessionRetirementKind.SIGNED_OUT]
    fresh = subject.authority.admit_human(connection_id=subject.connection)
    assert isinstance(fresh, AccessSession) and fresh.session_id != human.session_id


def test_another_connection_cannot_sign_out_a_suspended_session(subject: Subject, recovery: Recovery) -> None:
    human = subject.authority.admit_human(connection_id=subject.connection)
    assert isinstance(human, AccessSession)
    recovery.lose_worker()
    other = uuid4()
    subject.owner.connections[other] = human.client_id

    with pytest.raises(ProfileAccessRefusedError) as raised:
        subject.authority.require_human_sign_out(connection_id=other, session_id=human.session_id)
    assert raised.value.reason is AccessDenialCode.HUMAN_AUTHORITY_REQUIRED


def test_positive_os_lock_during_suspension_ends_the_session_with_no_rebind(
    subject: Subject, recovery: Recovery
) -> None:
    human = subject.authority.admit_human(connection_id=subject.connection)
    assert isinstance(human, AccessSession)
    recovery.lose_worker()

    assert subject.authority.retire_human_sessions(
        reason=AccessDenialCode.OS_LOCKED, kind=SessionRetirementKind.REVOKED
    ) == (human.session_id,)

    assert [item.reason for item in recovery.retired] == [AccessDenialCode.OS_LOCKED]
    fresh = subject.authority.admit_human(connection_id=subject.connection)
    assert isinstance(fresh, AccessSession) and fresh.session_id != human.session_id


def test_own_session_lock_during_suspension_ends_it_with_no_rebind(subject: Subject, recovery: Recovery) -> None:
    human = subject.authority.admit_human(connection_id=subject.connection)
    assert isinstance(human, AccessSession)
    recovery.lose_worker()

    locked = subject.authority.lock_session(
        connection_id=subject.connection, session_id=human.session_id, target_session_id=human.session_id
    )

    assert locked == (human.session_id,)
    fresh = subject.authority.admit_human(connection_id=subject.connection)
    assert isinstance(fresh, AccessSession) and fresh.session_id != human.session_id


def test_profile_lock_generation_advance_retires_suspended_leases_at_once(subject: Subject, recovery: Recovery) -> None:
    api, human, child, _ = attended_tree(subject)
    recovery.lose_worker()
    LifecycleOwner(subject, human).set_profile_lock(
        generation=subject.owner.current.profile.lock_generation + 1, locked=False
    )

    assert set(subject.authority.revalidate_sessions()) == {api.session_id, human.session_id, child.session_id}
    assert AccessDenialCode.PROFILE_LOCKED in {item.reason for item in recovery.retired}


def test_logout_of_the_originating_os_login_retires_suspended_human_leases(
    subject: Subject, recovery: Recovery
) -> None:
    human = subject.authority.admit_human(connection_id=subject.connection)
    assert isinstance(human, AccessSession)
    recovery.lose_worker()
    subject.owner.current = SessionAuthorityFacts(
        subject.owner.current.profile,
        changed(subject.owner.current.context, login_contexts=()),
    )

    assert subject.authority.revalidate_sessions() == (human.session_id,)
    fresh = subject.authority.admit_human(connection_id=subject.connection)
    assert isinstance(fresh, AccessDenied)


def test_without_a_replacement_owner_a_lost_worker_still_retires_every_lease(subject: Subject) -> None:
    retired: list[SessionRetirement] = []
    subject.authority._retired = retired.append
    api, human, child, _ = attended_tree(subject)
    subject.owner.worker_lost = True
    subject.owner.facts_failure = AutomationCustodyError(AutomationCustodyCode.UNAVAILABLE)
    subject.owner.lost = True

    assert set(subject.authority.revalidate_sessions()) == {api.session_id, human.session_id, child.session_id}
    assert {item.reason for item in retired} == {AccessDenialCode.CUSTODY_UNAVAILABLE}
