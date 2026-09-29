"""Enrollment safety with real encrypted profiles and staged filesystem publication.

Native stores, lifecycle observations and the authenticated recipient channel are
test doubles. These tests do not claim installed platform or transport acceptance.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import SecretBytes, ValidationError

from cadrumo.adapters.persistence.storage.custody.automation_crypto import generate_api_key
from cadrumo.adapters.persistence.storage.custody.automation_delivery import NativeEnrollmentRecipient
from cadrumo.adapters.persistence.storage.custody.automation_store import CONTROL_NAMESPACE, WRAP_NAMESPACE
from cadrumo.adapters.persistence.storage.custody.tests.enrollment_support import (
    NOW,
    PROFILE_INPUT,
    AdministrationSubject,
    administration_subject,
    changed,
)
from cadrumo.application.user_profile.access_contracts import AuthorityState
from cadrumo.application.user_profile.automation_administration import (
    AutomationAdministrationService,
    enrollment_review_digest,
)
from cadrumo.application.user_profile.automation_custody_port import AutomationCustodyCode, AutomationCustodyError
from cadrumo.application.user_profile.automation_enrollment import EnrollmentKind, EnrollmentProposal, EnrollmentStage

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_persistence_adapter,
    pytest.mark.usefixtures("authority_operation"),
]


@pytest.fixture
def subject(tmp_path: Path) -> Iterator[AdministrationSubject]:
    with administration_subject(tmp_path) as result:
        yield result


def unavailable() -> None:
    raise AutomationCustodyError(AutomationCustodyCode.UNAVAILABLE)


def test_enrollment_is_request_bound_inactive_until_possession_and_idempotent(subject: AdministrationSubject) -> None:
    identity = uuid4()
    receipt = subject.service.request(identity, subject.proposal).receipt
    assert subject.service.request(identity, subject.proposal).receipt == receipt
    assert subject.store.snapshot().grants == ()
    subject.owner.delivery.after_delivery = unavailable
    with pytest.raises(AutomationCustodyError, match="unavailable"):
        subject.approve(identity)
    state = subject.store.enrollment_state()
    record = state.requests[0]
    credential = subject.owner.delivery.endpoint.possession(record)
    assert credential is not None and record.stage is EnrollmentStage.CANDIDATE
    with pytest.raises(AutomationCustodyError, match="credential_rejected"):
        subject.store.unwrap(credential=credential, now=NOW)
    subject.owner.delivery.after_delivery = lambda: None
    # A new service instance reconciles a delivery whose result was lost.
    subject.service = AutomationAdministrationService(
        custody=subject.store, owner=subject.owner, issuer=subject.service.issuer, storage_root=subject.store.root
    )
    completed = subject.approve(identity)
    assert completed.stage is EnrollmentStage.COMPLETE and completed.key_id == record.candidate_key_id
    assert subject.owner.delivery.deliveries == 1
    assert len(subject.store.unwrap(credential=credential, now=NOW)) == 32
    revision = subject.store.snapshot().revision
    assert subject.approve(identity) == completed
    assert subject.store.snapshot().revision == revision
    public = subject.service.inventory().model_dump_json() + completed.model_dump_json()
    assert credential.get_secret_value().decode() not in public
    assert state.grants[0].keys[0].verifier not in public
    assert PROFILE_INPUT not in public


def test_transition_receipts_distinguish_publication_from_idempotent_retry(subject: AdministrationSubject) -> None:
    """A successful retry reports its own effect, not an earlier write's effect."""
    identity = uuid4()
    requested = subject.service.request(identity, subject.proposal)
    assert requested.published
    revision = subject.store.enrollment_state().revision
    repeated = subject.service.request(identity, subject.proposal)
    assert repeated.receipt == requested.receipt and not repeated.published
    assert subject.store.enrollment_state().revision == revision

    approved = subject.service.approve(
        identity,
        review_digest=requested.receipt.review_digest,
        password=SecretBytes(PROFILE_INPUT.encode()),
    )
    assert approved.published and approved.receipt.stage is EnrollmentStage.COMPLETE
    revision = subject.store.enrollment_state().revision
    repeated_approval = subject.service.approve(
        identity,
        review_digest=requested.receipt.review_digest,
        password=SecretBytes(PROFILE_INPUT.encode()),
    )
    assert repeated_approval.receipt == approved.receipt and not repeated_approval.published
    assert subject.store.enrollment_state().revision == revision

    declined_request = subject.service.request(uuid4(), subject.proposal)
    declined = subject.service.decline(
        declined_request.receipt.request_id, review_digest=declined_request.receipt.review_digest
    )
    assert declined.published and declined.receipt.stage is EnrollmentStage.DECLINED
    revision = subject.store.enrollment_state().revision
    repeated_decline = subject.service.decline(
        declined_request.receipt.request_id, review_digest=declined_request.receipt.review_digest
    )
    assert repeated_decline.receipt == declined.receipt and not repeated_decline.published
    assert subject.store.enrollment_state().revision == revision


@pytest.mark.parametrize("after", [False, True])
@pytest.mark.parametrize("namespace", [CONTROL_NAMESPACE, WRAP_NAMESPACE])
def test_failed_candidate_publication_reconciles_before_retry(
    subject: AdministrationSubject, namespace: str, after: bool
) -> None:
    identity = uuid4()
    subject.service.request(identity, subject.proposal)
    subject.native.fail_write, subject.native.commit_before_failure = namespace, after
    with pytest.raises(AutomationCustodyError):
        subject.approve(identity)
    assert subject.owner.delivery.deliveries == 0
    subject.native.fail_write = None
    assert not any(item.state is AuthorityState.ACTIVE for item in subject.store.snapshot().keys)
    assert subject.approve(identity).stage is EnrollmentStage.COMPLETE
    assert subject.owner.delivery.deliveries == 1


@pytest.mark.parametrize("after", [False, True])
def test_activation_failure_reconciles_exact_witness(subject: AdministrationSubject, after: bool) -> None:
    identity = uuid4()
    subject.service.request(identity, subject.proposal)

    def fail_activation() -> None:
        subject.native.fail_write = CONTROL_NAMESPACE
        subject.native.commit_before_failure = after

    subject.owner.delivery.after_possession = fail_activation
    with pytest.raises(AutomationCustodyError):
        subject.approve(identity)
    subject.native.fail_write = None
    subject.owner.delivery.after_possession = lambda: None
    recovered = subject.store.enrollment_state()
    assert (recovered.requests[0].stage is EnrollmentStage.COMPLETE) == after
    assert subject.approve(identity).stage is EnrollmentStage.COMPLETE
    assert subject.owner.delivery.deliveries == 1


def test_missing_candidate_is_replaced_without_reconstructing_secret(subject: AdministrationSubject) -> None:
    identity = uuid4()
    subject.service.request(identity, subject.proposal)
    subject.owner.delivery.before_delivery = unavailable
    with pytest.raises(AutomationCustodyError):
        subject.approve(identity)
    first = subject.store.enrollment_state().requests[0]
    subject.owner.delivery.before_delivery = lambda: None
    result = subject.approve(identity)
    assert result.key_id != first.candidate_key_id
    assert all(item.key_id != first.candidate_key_id for item in subject.store.snapshot().keys)


def test_wrong_possession_never_activates(subject: AdministrationSubject) -> None:
    identity = uuid4()
    subject.service.request(identity, subject.proposal)
    subject.owner.delivery.wrong_possession = generate_api_key()[1]
    with pytest.raises(AutomationCustodyError, match="credential_rejected"):
        subject.approve(identity)
    assert subject.store.snapshot().keys[0].state is AuthorityState.PENDING


@pytest.mark.parametrize(
    "change",
    ["logout", "lock", "expiry", "monotonic", "boot", "scope", "profile", "generation", "connection", "client"],
)
def test_revalidate_after_delivery(subject: AdministrationSubject, change: str) -> None:
    identity = uuid4()
    subject.service.request(identity, subject.proposal)

    def alter_authority() -> None:
        facts = subject.owner.current
        context, profile = facts.context, facts.profile
        if change == "logout":
            context = changed(context, login_contexts=())
        elif change == "lock":
            profile = changed(profile, globally_locked=True)
        elif change == "expiry":
            context = changed(context, now=NOW + timedelta(minutes=5))
        elif change == "monotonic":
            context = changed(context, monotonic_now=310.0)
        elif change == "boot":
            context = changed(context, runtime_boot_id=uuid4())
        elif change == "connection":
            context = changed(context, connection_id=uuid4())
        elif change == "client":
            context = changed(context, authenticated_client_id=uuid4())
        elif change == "scope":
            profile = changed(profile, scope=changed(profile.scope, operations=frozenset()))
        elif change == "profile":
            profile = changed(profile, binding=changed(profile.binding, profile_id=uuid4()))
        elif change == "generation":
            profile = changed(profile, lock_generation=1)
        subject.owner.current = changed(facts, context=context, profile=profile)

    subject.owner.delivery.after_delivery = alter_authority
    with pytest.raises(AutomationCustodyError):
        subject.approve(identity)
    assert subject.store.snapshot().keys[0].state is AuthorityState.PENDING


def test_rotation_failure_preserves_predecessor_then_bounds_overlap(subject: AdministrationSubject) -> None:
    original = subject.service.request(uuid4(), subject.proposal).receipt
    enrolled = subject.approve(original.request_id)
    old_key = subject.store.snapshot().keys[0]
    rotation = changed(
        subject.proposal, kind=EnrollmentKind.ROTATE, target_grant_id=enrolled.grant_id, target_key_id=enrolled.key_id
    )
    receipt = subject.service.request(uuid4(), rotation).receipt
    subject.owner.delivery.after_delivery = unavailable
    with pytest.raises(AutomationCustodyError):
        subject.approve(receipt.request_id)
    assert next(item for item in subject.store.snapshot().keys if item.key_id == old_key.key_id) == old_key
    subject.owner.delivery.after_delivery = lambda: None
    completed = subject.approve(receipt.request_id)
    snapshot = subject.store.snapshot()
    assert completed.key_id != old_key.key_id
    assert next(item for item in snapshot.keys if item.key_id == old_key.key_id).expires_at == NOW + timedelta(
        seconds=60
    )
    assert snapshot.grants[0].expires_at == subject.proposal.expires_at


def test_renewal_and_scope_change_require_exact_consent_and_preserve_key_ceiling(
    subject: AdministrationSubject,
) -> None:
    identity = uuid4()
    subject.service.request(identity, subject.proposal)
    enrolled = subject.approve(identity)
    renewal = changed(
        subject.proposal,
        kind=EnrollmentKind.RENEW,
        key_expires_at=None,
        target_grant_id=enrolled.grant_id,
        expires_at=subject.proposal.expires_at + timedelta(days=5),
    )
    receipt = subject.service.request(uuid4(), renewal).receipt
    with pytest.raises(AutomationCustodyError, match="conflict"):
        subject.service.approve(
            receipt.request_id, review_digest="0" * 64, password=SecretBytes(PROFILE_INPUT.encode())
        )
    completed = subject.approve(receipt.request_id)
    assert completed.key_id is None and subject.store.snapshot().keys[0].expires_at == subject.proposal.key_expires_at
    assert subject.store.snapshot().grants[0].expires_at == renewal.expires_at
    assert subject.store.snapshot().grants[0].generation == 2
    narrowed = changed(renewal, kind=EnrollmentKind.CHANGE_SCOPE, scope=changed(renewal.scope, actions=frozenset()))
    receipt = subject.service.request(uuid4(), narrowed).receipt
    subject.approve(receipt.request_id)
    assert subject.store.snapshot().grants[0].scope == narrowed.scope
    assert subject.store.snapshot().grants[0].generation == 3


def test_request_mismatch_decline_and_unknown_recipient_refuse(subject: AdministrationSubject) -> None:
    identity = uuid4()
    receipt = subject.service.request(identity, subject.proposal).receipt
    with pytest.raises(AutomationCustodyError, match="conflict"):
        subject.service.request(identity, changed(subject.proposal, expires_at=NOW + timedelta(days=400)))
    subject.owner.connected = False
    with pytest.raises(AutomationCustodyError, match="unavailable"):
        subject.approve(identity)
    assert (
        subject.service.decline(identity, review_digest=receipt.review_digest).receipt.stage is EnrollmentStage.DECLINED
    )
    with pytest.raises(AutomationCustodyError, match="credential_rejected"):
        subject.approve(identity)
    assert subject.store.snapshot().keys == ()


@pytest.mark.parametrize("kind", [EnrollmentKind.RENEW, EnrollmentKind.CHANGE_SCOPE])
def test_simple_grant_change_requires_original_live_requester(
    subject: AdministrationSubject, kind: EnrollmentKind
) -> None:
    identity = uuid4()
    subject.service.request(identity, subject.proposal)
    enrolled = subject.approve(identity)
    proposal = changed(
        subject.proposal,
        kind=kind,
        key_expires_at=None,
        target_grant_id=enrolled.grant_id,
        expires_at=subject.proposal.expires_at + timedelta(days=5)
        if kind is EnrollmentKind.RENEW
        else subject.proposal.expires_at,
        scope=changed(subject.proposal.scope, actions=frozenset())
        if kind is EnrollmentKind.CHANGE_SCOPE
        else subject.proposal.scope,
    )
    request = subject.service.request(uuid4(), proposal).receipt
    before = subject.store.snapshot()
    subject.owner.connected = False
    with pytest.raises(AutomationCustodyError, match="unavailable"):
        subject.approve(request.request_id)
    assert subject.store.snapshot() == before
    subject.owner.connected = True
    assert subject.approve(request.request_id).stage is EnrollmentStage.COMPLETE


def test_agent_claims_are_not_authority_and_inventory_requires_human(subject: AdministrationSubject) -> None:
    fields = subject.proposal.model_dump(mode="json")
    fields["client_id"] = str(uuid4())
    with pytest.raises(ValidationError):
        EnrollmentProposal.model_validate_json(__import__("json").dumps(fields))
    subject.owner.current = changed(subject.owner.current, session=None)
    with pytest.raises(AutomationCustodyError, match="needs_user"):
        subject.service.inventory()
    # An authenticated local connection may request, but cannot approve by naming itself.
    receipt = subject.service.request(uuid4(), subject.proposal).receipt
    subject.owner.requesting = changed(subject.owner.requesting, client_id=uuid4())
    with pytest.raises(AutomationCustodyError):
        subject.service.request(receipt.request_id, subject.proposal)


def test_safe_review_digest_survives_canonical_disk_order(subject: AdministrationSubject) -> None:
    receipt = subject.service.request(uuid4(), subject.proposal).receipt
    record = subject.store.enrollment_state().requests[0]
    assert receipt.review_digest == enrollment_review_digest(record)
    assert receipt == subject.service.inventory().requests[0].receipt


def test_protected_reference_survives_connection_replacement_but_not_binding_change(
    subject: AdministrationSubject,
) -> None:
    receipt = subject.service.request(uuid4(), subject.proposal).receipt
    complete = subject.approve(receipt.request_id)
    assert complete.credential_reference is not None
    later = NativeEnrollmentRecipient(
        requester=changed(subject.owner.requesting, connection_id=uuid4(), runtime_boot_id=uuid4()),
        secrets_store=subject.client_native,
    )
    credential = later.credential(complete.credential_reference, binding=subject.store.binding)
    assert len(subject.store.unwrap(credential=credential, now=NOW)) == 32
    for field, value in (
        ("profile_id", uuid4()),
        ("installation_id", uuid4()),
        ("os_owner_id", "different-owner"),
        ("custody_generation", 2),
        ("dek_epoch", uuid4()),
    ):
        with pytest.raises(AutomationCustodyError):
            later.credential(complete.credential_reference, binding=changed(subject.store.binding, **{field: value}))
    wrong_client = NativeEnrollmentRecipient(
        requester=changed(subject.owner.requesting, client_id=uuid4()), secrets_store=subject.client_native
    )
    with pytest.raises(AutomationCustodyError):
        wrong_client.credential(complete.credential_reference, binding=subject.store.binding)


def test_client_possession_is_bound_to_original_review_digest(subject: AdministrationSubject) -> None:
    receipt = subject.service.request(uuid4(), subject.proposal).receipt
    subject.approve(receipt.request_id)
    record = subject.store.enrollment_state().requests[0]
    endpoint = subject.owner.delivery.endpoint
    credential = endpoint.possession(record)
    assert credential is not None
    changed_review = changed(record, request_id=uuid4())
    assert enrollment_review_digest(changed_review) != enrollment_review_digest(record)
    with pytest.raises(AutomationCustodyError, match="credential_rejected"):
        endpoint.possession(changed_review)
    with pytest.raises(AutomationCustodyError, match="conflict"):
        endpoint.deliver(changed_review, credential)


@pytest.mark.parametrize("after", [False, True])
def test_client_native_delivery_failure_reconciles_exact_committed_write(
    subject: AdministrationSubject, after: bool
) -> None:
    from cadrumo.adapters.persistence.storage.custody.automation_store import CLIENT_NAMESPACE

    receipt = subject.service.request(uuid4(), subject.proposal).receipt
    subject.client_native.fail_write = CLIENT_NAMESPACE
    subject.client_native.commit_before_failure = after
    if after:
        result = subject.approve(receipt.request_id)
        assert result.stage is EnrollmentStage.COMPLETE
        assert subject.store.snapshot().keys[0].state is AuthorityState.ACTIVE
        subject.client_native.fail_write = None
        assert subject.approve(receipt.request_id) == result
    else:
        with pytest.raises(AutomationCustodyError):
            subject.approve(receipt.request_id)
        pending = subject.store.enrollment_state().requests[0]
        assert subject.store.snapshot().keys[0].state is AuthorityState.PENDING
        subject.client_native.fail_write = None
        result = subject.approve(receipt.request_id)
        assert result.key_id != pending.candidate_key_id
        assert result.stage is EnrollmentStage.COMPLETE


def test_wrong_password_is_non_oracular_and_has_no_effect(subject: AdministrationSubject) -> None:
    receipt = subject.service.request(uuid4(), subject.proposal).receipt
    revision = subject.store.snapshot().revision
    with pytest.raises(AutomationCustodyError, match="credential_rejected") as error:
        subject.service.approve(
            receipt.request_id, review_digest=receipt.review_digest, password=SecretBytes(b"wrong-synthetic-input")
        )
    assert "wrong-synthetic-input" not in repr(error.value)
    assert subject.store.snapshot().revision == revision and subject.store.snapshot().keys == ()


def test_concurrent_approvals_cannot_activate_displaced_candidate(subject: AdministrationSubject) -> None:
    receipt = subject.service.request(uuid4(), subject.proposal).receipt

    def competing_approval() -> None:
        subject.owner.delivery.before_delivery = lambda: None
        subject.approve(receipt.request_id)

    subject.owner.delivery.before_delivery = competing_approval
    with pytest.raises(AutomationCustodyError, match="conflict"):
        subject.approve(receipt.request_id)
    snapshot = subject.store.snapshot()
    assert len(snapshot.keys) == 1 and snapshot.keys[0].state is AuthorityState.ACTIVE
    assert subject.approve(receipt.request_id).key_id == snapshot.keys[0].key_id


def test_human_approval_uses_separate_connection_and_exact_review(subject: AdministrationSubject) -> None:
    receipt = subject.service.request(uuid4(), subject.proposal).receipt
    facts = subject.owner.current
    context = changed(facts.context, connection_id=uuid4(), authenticated_client_id=uuid4())
    subject.owner.current = changed(facts, context=context, session=None)
    result = subject.approve(receipt.request_id)
    assert result.stage is EnrollmentStage.COMPLETE
    assert subject.store.snapshot().grants[0].client_id == subject.owner.requesting.client_id


@pytest.mark.parametrize("after", [False, True])
@pytest.mark.parametrize("action", ["request", "decline", "renew"])
def test_control_transition_failure_reconciles_and_retry_is_idempotent(
    subject: AdministrationSubject, action: str, after: bool
) -> None:
    identity = uuid4()
    proposal = subject.proposal
    if action != "request":
        first = subject.service.request(identity, proposal).receipt
        if action == "renew":
            enrolled = subject.approve(identity)
            proposal = changed(
                proposal,
                kind=EnrollmentKind.RENEW,
                key_expires_at=None,
                target_grant_id=enrolled.grant_id,
                expires_at=proposal.expires_at + timedelta(days=2),
            )
            identity = uuid4()
            first = subject.service.request(identity, proposal).receipt

    def transition():
        if action == "request":
            return subject.service.request(identity, proposal).receipt
        if action == "decline":
            return subject.service.decline(identity, review_digest=first.review_digest).receipt
        return subject.approve(identity)

    subject.native.fail_write = CONTROL_NAMESPACE
    subject.native.commit_before_failure = after
    with pytest.raises(AutomationCustodyError):
        transition()
    subject.native.fail_write = None
    settled = transition()
    revision = subject.store.snapshot().revision
    assert transition() == settled and subject.store.snapshot().revision == revision
    if action == "decline":
        assert settled.stage is EnrollmentStage.DECLINED and subject.store.snapshot().keys == ()
    elif action == "renew":
        assert settled.stage is EnrollmentStage.COMPLETE
        assert subject.store.snapshot().keys[0].expires_at == subject.proposal.key_expires_at
