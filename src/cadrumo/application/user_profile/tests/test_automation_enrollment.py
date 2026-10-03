"""Pure consent contracts: deterministic identity, bounded requests and safe projections."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from pydantic import BaseModel, ValidationError

from cadrumo.application.user_profile.access_contracts import (
    AccessAction,
    AccessScope,
    AccessSession,
    ProfileAccessBinding,
    SessionKind,
    SessionState,
)
from cadrumo.application.user_profile.automation_administration import (
    enrollment_receipt,
    enrollment_review_digest,
    reconcile_automation_receipt,
)
from cadrumo.application.user_profile.automation_custody_port import AutomationCustodyCode, AutomationCustodyError
from cadrumo.application.user_profile.automation_enrollment import (
    EnrollmentControlState,
    EnrollmentKind,
    EnrollmentProposal,
    EnrollmentRecord,
    EnrollmentRequester,
    EnrollmentStage,
)
from cadrumo.core.hashing import canonical_json_bytes

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def changed[T: BaseModel](model: T, **changes: object) -> T:
    return model.__class__.model_validate(
        {**{name: getattr(model, name) for name in model.__class__.model_fields}, **changes}
    )


@pytest.fixture
def record() -> EnrollmentRecord:
    now = datetime(2026, 9, 26, tzinfo=UTC)
    return EnrollmentRecord(
        request_id=uuid4(),
        binding=ProfileAccessBinding(
            profile_id=uuid4(),
            installation_id=uuid4(),
            os_owner_id="synthetic-owner",
            custody_generation=1,
            dek_epoch=uuid4(),
        ),
        requester=EnrollmentRequester(
            runtime_boot_id=uuid4(), connection_id=uuid4(), client_id=uuid4(), destination_id=uuid4()
        ),
        proposal=EnrollmentProposal(
            kind=EnrollmentKind.ENROLL,
            scope=AccessScope(
                operations=frozenset({"example.read", "example.write"}),
                actions=frozenset(AccessAction),
                disclosures=frozenset(),
                periods=None,
                allow_period_independent=True,
                allow_delegation=False,
            ),
            expires_at=now + timedelta(days=365),
            key_expires_at=now + timedelta(days=100),
            unattended=True,
            allow_os_lock=False,
        ),
        created_at=now,
        expires_at=now + timedelta(minutes=5),
        stage=EnrollmentStage.REQUESTED,
        grant_id=uuid4(),
    )


@pytest.mark.parametrize("field", ["client_id", "approved", "password", "dek", "api_key", "proof"])
def test_agent_cannot_submit_identity_consent_or_secret_fields(record: EnrollmentRecord, field: str) -> None:
    data = {**record.proposal.model_dump(mode="json"), field: "UNTRUSTED-INPUT-SENTINEL"}
    with pytest.raises(ValidationError) as failure:
        EnrollmentProposal.model_validate_json(canonical_json_bytes(data))
    assert "UNTRUSTED-INPUT-SENTINEL" not in str(failure.value)


@pytest.mark.parametrize("field", ["runtime_boot_id", "connection_id", "client_id", "destination_id"])
def test_consent_digest_binds_exact_recipient_provenance(record: EnrollmentRecord, field: str) -> None:
    substituted = changed(record, requester=changed(record.requester, **{field: uuid4()}))
    assert enrollment_review_digest(record) != enrollment_review_digest(substituted)


def test_review_digest_binds_proposal_and_custody_but_not_publication_progress(record: EnrollmentRecord) -> None:
    staged = changed(record, stage=EnrollmentStage.CANDIDATE, candidate_key_id=uuid4(), credential_reference=uuid4())
    assert enrollment_review_digest(staged) == enrollment_review_digest(record)
    assert enrollment_review_digest(
        changed(record, binding=changed(record.binding, custody_generation=2))
    ) != enrollment_review_digest(record)
    assert enrollment_review_digest(
        changed(record, proposal=changed(record.proposal, scope=changed(record.proposal.scope, actions=frozenset())))
    ) != enrollment_review_digest(record)
    assert enrollment_review_digest(
        EnrollmentRecord.model_validate_json(record.model_dump_json())
    ) == enrollment_review_digest(record)
    receipt = enrollment_receipt(staged).model_dump_json()
    for value in (record.binding.os_owner_id, str(record.binding.installation_id), str(record.requester.connection_id)):
        assert value not in receipt


@pytest.mark.parametrize("duration", [timedelta(), timedelta(minutes=5, seconds=1)])
def test_request_window_is_bounded(record: EnrollmentRecord, duration: timedelta) -> None:
    with pytest.raises(ValidationError):
        changed(record, expires_at=record.created_at + duration)


@pytest.mark.parametrize("kind", [EnrollmentKind.RENEW, EnrollmentKind.CHANGE_SCOPE])
def test_non_key_change_cannot_implicitly_extend_a_key(record: EnrollmentRecord, kind: EnrollmentKind) -> None:
    with pytest.raises(ValidationError):
        changed(record.proposal, kind=kind, target_grant_id=uuid4())
    proposal = changed(record.proposal, kind=kind, target_grant_id=uuid4(), key_expires_at=None)
    assert proposal.key_expires_at is None


@pytest.mark.parametrize("stage", [EnrollmentStage.CANDIDATE, EnrollmentStage.COMPLETE])
def test_enrollment_cannot_claim_progress_without_delivery_binding(
    record: EnrollmentRecord, stage: EnrollmentStage
) -> None:
    with pytest.raises(ValidationError):
        changed(record, stage=stage)


@pytest.mark.parametrize("mismatch", [None, "grant", "client", "destination", "profile", "child", "pending"])
def test_terminal_receipt_recovery_is_limited_to_current_root_principal(
    record: EnrollmentRecord, mismatch: str | None
) -> None:
    """Admission is independently proved by native tests; this owns receipt scope."""
    record = changed(
        record,
        requester=changed(record.requester, destination_id=record.requester.client_id),
        stage=EnrollmentStage.COMPLETE,
        candidate_key_id=uuid4(),
        credential_reference=uuid4(),
    )
    session = AccessSession(
        session_id=uuid4(),
        binding=record.binding,
        profile_lock_generation=0,
        runtime_boot_id=uuid4(),
        connection_id=uuid4(),
        client_id=record.requester.client_id,
        kind=SessionKind.API_KEY,
        state=SessionState.ACTIVE,
        scope=record.proposal.scope,
        grant_id=record.grant_id,
        grant_generation=2,
        key_id=record.candidate_key_id,
        key_generation=1,
        issued_at=record.expires_at,
        expires_at=record.expires_at + timedelta(minutes=5),
        issued_monotonic=100.0,
    )
    if mismatch == "grant":
        session = changed(session, grant_id=uuid4())
    elif mismatch == "client":
        session = changed(session, client_id=uuid4())
    elif mismatch == "destination":
        record = changed(record, requester=changed(record.requester, destination_id=uuid4()))
    elif mismatch == "profile":
        session = changed(session, binding=changed(session.binding, profile_id=uuid4()))
    elif mismatch == "child":
        session = changed(session, parent_session_id=uuid4())
    elif mismatch == "pending":
        record = changed(record, stage=EnrollmentStage.CANDIDATE)
    state = EnrollmentControlState(
        revision=1,
        binding=record.binding,
        profile_lock_generation=0,
        automation_enabled=True,
        grants=(),
        requests=(record,),
    )
    if mismatch is None:
        recovered = reconcile_automation_receipt(state=state, session=session, request_id=record.request_id)
        assert recovered.model_dump() == enrollment_receipt(record).model_dump()
        assert str(record.requester.connection_id) not in recovered.model_dump_json()
    else:
        with pytest.raises(AutomationCustodyError) as failure:
            reconcile_automation_receipt(state=state, session=session, request_id=record.request_id)
        assert failure.value.reason is AutomationCustodyCode.CREDENTIAL_REJECTED
