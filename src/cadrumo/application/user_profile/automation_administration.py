"""Request-bound automation consent and recoverable protected delivery.

Operation executors own invocation; the existing custody store owns durability.
No secret is retained in an enrollment record, receipt or operation operand.
After an ambiguous failure, read the protected witness before choosing a retry.
"""

from __future__ import annotations

import secrets
from pathlib import Path
from uuid import UUID, uuid4

from pydantic import BaseModel, SecretBytes

from ...core.hashing import canonical_json_bytes, sha256_hex
from ...core.identity.digest import ContentDigest
from .access_administration import (
    AccessAdministrationAction,
    AccessAdministrationRequest,
    FreshPasswordAuthorization,
    evaluate_access_administration,
)
from .access_contracts import (
    AccessDenied,
    AccessSession,
    AuthorityState,
    AutomationGrant,
    Availability,
    SessionKind,
)
from .access_projections import project_api_key, project_automation_grant
from .automation_custody_port import AutomationCustodyCode, AutomationCustodyError
from .automation_enrollment import (
    AdministrationFacts,
    AutomationInventory,
    AutomationInventoryOwner,
    AutomationReceiptProjection,
    EnrollmentControlState,
    EnrollmentCustodyPort,
    EnrollmentGrant,
    EnrollmentKind,
    EnrollmentProposal,
    EnrollmentReceipt,
    EnrollmentRecord,
    EnrollmentReview,
    EnrollmentStage,
)
from .automation_password import prove_automation_administration


def replace_enrollment_model[T: BaseModel](model: T, **changes: object) -> T:
    """Return the validated model with only the named fields changed."""
    model_type = model.__class__
    return model_type.model_validate({**{name: getattr(model, name) for name in model_type.model_fields}, **changes})


def enrollment_review_digest(record: EnrollmentRecord) -> ContentDigest:
    """Bind immutable consent, with deterministic encoding of the scope allow sets."""
    proposal = record.proposal.model_dump(mode="json")
    scope = record.proposal.scope.model_dump(mode="json")
    for name in ("operations", "actions", "disclosures", "periods"):
        if scope[name] is not None:
            scope[name] = sorted(scope[name], key=canonical_json_bytes)
    proposal["scope"] = scope
    return sha256_hex(
        canonical_json_bytes(
            {
                "purpose": "cadrumo.automation-consent/v1",
                "request_id": str(record.request_id),
                "binding": record.binding.model_dump(mode="json"),
                "requester": record.requester.model_dump(mode="json"),
                "proposal": proposal,
                "created_at": record.created_at.isoformat(),
                "expires_at": record.expires_at.isoformat(),
                "grant_id": str(record.grant_id),
            }
        )
    )


def enrollment_receipt(record: EnrollmentRecord) -> EnrollmentReceipt:
    """Return only identities and progress; never return key bytes or verifiers."""
    return EnrollmentReceipt(
        request_id=record.request_id,
        profile_id=record.binding.profile_id,
        stage=record.stage,
        review_digest=enrollment_review_digest(record),
        grant_id=record.grant_id,
        key_id=record.candidate_key_id,
        credential_reference=record.credential_reference,
    )


def reconcile_automation_receipt(
    *, state: EnrollmentControlState, session: AccessSession, request_id: UUID
) -> AutomationReceiptProjection:
    """Recover only a terminal receipt belonging to this live root-key principal.

    The caller retains the session authority's admission fence through the read
    and output, and revalidates the lease before release. This does not recover
    a recipient, publish a request or return a proposal or credential.
    """
    if not _is_root_key_session(session):
        raise AutomationCustodyError(AutomationCustodyCode.CREDENTIAL_REJECTED)
    record = next((item for item in state.requests if item.request_id == request_id), None)
    if record is None or not _receipt_matches_session(state, session, record):
        raise AutomationCustodyError(AutomationCustodyCode.CREDENTIAL_REJECTED)
    return AutomationReceiptProjection.model_validate(enrollment_receipt(record).model_dump())


def _is_root_key_session(session: AccessSession) -> bool:
    return session.kind is SessionKind.API_KEY and session.parent_session_id is None and session.grant_id is not None


def _receipt_matches_session(state: EnrollmentControlState, session: AccessSession, record: EnrollmentRecord) -> bool:
    return (
        state.binding == session.binding
        and record.binding == session.binding
        and record.requester.client_id == session.client_id
        and record.requester.destination_id == session.client_id
        and record.grant_id == session.grant_id
        and record.stage in {EnrollmentStage.COMPLETE, EnrollmentStage.DECLINED}
    )


def validate_enrollment_state(
    custody: EnrollmentCustodyPort, owner: AutomationInventoryOwner, *, require_enabled: bool
) -> tuple[EnrollmentControlState, AdministrationFacts]:
    """Keep every custody and lifecycle fence shared by reads and writes."""
    state, facts = custody.enrollment_state(), owner.facts()
    if not _state_matches_profile(state, facts) or not _profile_is_available(state, facts, require_enabled):
        raise AutomationCustodyError(AutomationCustodyCode.NEEDS_USER)
    return state, facts


def _state_matches_profile(state: EnrollmentControlState, facts: AdministrationFacts) -> bool:
    return (
        state.binding == facts.profile.binding
        and state.profile_lock_generation == facts.profile.lock_generation
        and state.automation_enabled == facts.profile.automation_enabled
    )


def _profile_is_available(state: EnrollmentControlState, facts: AdministrationFacts, require_enabled: bool) -> bool:
    return (
        (not require_enabled or state.automation_enabled)
        and not facts.profile.globally_locked
        and facts.context.private_work_available
        and not facts.context.clock_rollback_detected
        and facts.profile.storage is Availability.AVAILABLE
        and facts.profile.automation_custody is Availability.AVAILABLE
    )


def inspect_automation_inventory(
    *, custody: EnrollmentCustodyPort, owner: AutomationInventoryOwner
) -> AutomationInventory:
    """Release exact consent and grant facts only under fresh human authority."""
    with owner.administration_guard():
        state, facts = validate_enrollment_state(custody, owner, require_enabled=False)
        request = AccessAdministrationRequest(
            request_id=uuid4(),
            profile_id=state.binding.profile_id,
            action=AccessAdministrationAction.INSPECT,
            request_digest="0" * 64,
        )
        decision = evaluate_access_administration(
            request=request,
            session=facts.session,
            ancestors=(),
            grant=None,
            key=None,
            profile=facts.profile,
            context=facts.context,
        )
        if isinstance(decision, AccessDenied):
            raise AutomationCustodyError(AutomationCustodyCode.NEEDS_USER)
        return AutomationInventory(
            grants=tuple(project_automation_grant(item.grant) for item in state.grants),
            keys=tuple(project_api_key(key.key) for item in state.grants for key in item.keys),
            requests=tuple(
                EnrollmentReview(
                    receipt=enrollment_receipt(item),
                    client_id=item.requester.client_id,
                    destination_id=item.requester.destination_id,
                    proposal=item.proposal,
                    expires_at=item.expires_at,
                )
                for item in state.requests
            ),
        )


def find_enrollment(state: EnrollmentControlState, identity: UUID) -> EnrollmentRecord:
    """Resolve the exact request identity or report the custody missing code."""
    record = next((item for item in state.requests if item.request_id == identity), None)
    if record is None:
        raise AutomationCustodyError(AutomationCustodyCode.MISSING)
    return record


def require_live_enrollment(record: EnrollmentRecord, facts: AdministrationFacts) -> None:
    """Reject a request outside its current profile, runtime, time or stage."""
    if (
        record.binding != facts.profile.binding
        or record.requester.runtime_boot_id != facts.context.runtime_boot_id
        or not record.created_at <= facts.context.now < record.expires_at
        or record.stage is EnrollmentStage.DECLINED
    ):
        raise AutomationCustodyError(AutomationCustodyCode.CREDENTIAL_REJECTED)


def require_enrollment_review(record: EnrollmentRecord, digest: ContentDigest) -> None:
    """Compare the immutable review digest in constant time."""
    if not secrets.compare_digest(enrollment_review_digest(record), digest):
        raise AutomationCustodyError(AutomationCustodyCode.CONFLICT)


def authorize_enrollment(
    record: EnrollmentRecord,
    action: AccessAdministrationAction,
    facts: AdministrationFacts,
    proof: FreshPasswordAuthorization | None = None,
) -> None:
    """Apply the current profile decision for this request and action."""
    request = AccessAdministrationRequest(
        request_id=record.request_id,
        profile_id=record.binding.profile_id,
        action=action,
        request_digest=enrollment_review_digest(record),
    )
    decision = evaluate_access_administration(
        request=request,
        session=facts.session,
        ancestors=(),
        grant=None,
        key=None,
        profile=facts.profile,
        context=facts.context,
        password_proof=proof,
    )
    if isinstance(decision, AccessDenied):
        raise AutomationCustodyError(AutomationCustodyCode.NEEDS_USER)


def prove_enrollment_approval(
    record: EnrollmentRecord, password: SecretBytes, facts: AdministrationFacts, storage_root: Path
) -> tuple[FreshPasswordAuthorization, SecretBytes]:
    """Verify fresh password proof against this exact consent request."""
    if record.binding != facts.profile.binding:
        raise AutomationCustodyError(AutomationCustodyCode.CONFLICT)
    return prove_automation_administration(
        request=AccessAdministrationRequest(
            request_id=record.request_id,
            profile_id=record.binding.profile_id,
            action=AccessAdministrationAction.APPROVE,
            request_digest=enrollment_review_digest(record),
        ),
        facts=facts,
        password=password,
        storage_root=storage_root,
        deadline=record.expires_at,
    )


def target_enrollment_grant(state: EnrollmentControlState, record: EnrollmentRecord) -> EnrollmentGrant | None:
    """Validate and return the grant addressed by this request kind."""
    if record.proposal.kind is EnrollmentKind.ENROLL:
        return _enrollment_target(state, record)
    entry = _existing_target_entry(state, record)
    _validate_existing_target(state, record, entry)
    return entry


def _enrollment_target(state: EnrollmentControlState, record: EnrollmentRecord) -> EnrollmentGrant | None:
    entry = next((item for item in state.grants if item.grant.grant_id == record.grant_id), None)
    if entry is not None and entry.grant.state is not AuthorityState.PENDING:
        raise AutomationCustodyError(AutomationCustodyCode.CONFLICT)
    return entry


def _existing_target_entry(state: EnrollmentControlState, record: EnrollmentRecord) -> EnrollmentGrant:
    entry = next((item for item in state.grants if item.grant.grant_id == record.grant_id), None)
    if (
        entry is None
        or entry.grant.state is not AuthorityState.ACTIVE
        or entry.grant.client_id != record.requester.client_id
    ):
        raise AutomationCustodyError(AutomationCustodyCode.CREDENTIAL_REJECTED)
    return entry


def _validate_existing_target(state: EnrollmentControlState, record: EnrollmentRecord, entry: EnrollmentGrant) -> None:
    proposal, grant = record.proposal, entry.grant
    _validate_target_grant_facts(state, proposal, grant)
    if proposal.kind is not EnrollmentKind.CHANGE_SCOPE and proposal.scope != grant.scope:
        raise AutomationCustodyError(AutomationCustodyCode.CONFLICT)
    if proposal.kind is not EnrollmentKind.RENEW and proposal.expires_at != grant.expires_at:
        raise AutomationCustodyError(AutomationCustodyCode.CONFLICT)
    if proposal.kind is EnrollmentKind.RENEW and proposal.expires_at <= grant.expires_at:
        raise AutomationCustodyError(AutomationCustodyCode.CONFLICT)
    if proposal.kind is EnrollmentKind.ROTATE and not _target_key_is_active(entry, proposal.target_key_id):
        raise AutomationCustodyError(AutomationCustodyCode.CREDENTIAL_REJECTED)


def _validate_target_grant_facts(
    state: EnrollmentControlState, proposal: EnrollmentProposal, grant: AutomationGrant
) -> None:
    if (
        grant.profile_lock_generation != state.profile_lock_generation
        or proposal.unattended != grant.unattended
        or proposal.allow_os_lock != grant.allow_os_lock
    ):
        raise AutomationCustodyError(AutomationCustodyCode.CONFLICT)


def _target_key_is_active(entry: EnrollmentGrant, target_key_id: UUID | None) -> bool:
    return any(item.key.key_id == target_key_id and item.key.state is AuthorityState.ACTIVE for item in entry.keys)


def updated_enrollment_state(
    state: EnrollmentControlState, record: EnrollmentRecord, entry: EnrollmentGrant | None = None
) -> EnrollmentControlState:
    """Build immutable control state with the request and optional grant update."""
    return replace_enrollment_model(
        state,
        requests=tuple(record if item.request_id == record.request_id else item for item in state.requests),
        grants=state.grants
        if entry is None
        else (*tuple(item for item in state.grants if item.grant.grant_id != entry.grant.grant_id), entry),
    )
