"""Caller-owned phases for protected automation enrollment approval."""

from __future__ import annotations

import secrets
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from pydantic import SecretBytes

from ...core.identity.digest import ContentDigest
from ...core.time.utc import UtcInstant
from .access_administration import AccessAdministrationAction, FreshPasswordAuthorization
from .access_contracts import (
    KEY_ROTATION_MAXIMUM_OVERLAP,
    ApiKeyRecord,
    AuthorityState,
    AutomationGrant,
)
from .access_policy import scope_is_subset
from .automation_administration import (
    authorize_enrollment,
    enrollment_receipt,
    find_enrollment,
    prove_enrollment_approval,
    replace_enrollment_model,
    require_enrollment_review,
    require_live_enrollment,
    target_enrollment_grant,
    updated_enrollment_state,
    validate_enrollment_state,
)
from .automation_custody_port import AutomationCustodyCode, AutomationCustodyError, AutomationKeyVerifier
from .automation_enrollment import (
    EnrollmentControlState,
    EnrollmentGrant,
    EnrollmentKind,
    EnrollmentRecord,
    EnrollmentStage,
    EnrollmentTransition,
    ProtectedEnrollmentRecipient,
)

if TYPE_CHECKING:
    from .automation_administration_service import AutomationAdministrationService


def _candidate_grant(
    record: EnrollmentRecord, state: EnrollmentControlState, entry: EnrollmentGrant | None
) -> AutomationGrant:
    if entry is not None:
        return entry.grant
    return AutomationGrant(
        grant_id=record.grant_id,
        binding=record.binding,
        client_id=record.requester.client_id,
        generation=1,
        profile_lock_generation=state.profile_lock_generation,
        state=AuthorityState.PENDING,
        scope=record.proposal.scope,
        valid_from=record.created_at,
        expires_at=record.proposal.expires_at,
        unattended=record.proposal.unattended,
        allow_os_lock=record.proposal.allow_os_lock,
    )


def _candidate_key(
    grant: AutomationGrant,
    key_id: UUID,
    expires_at: UtcInstant,
    instant: UtcInstant,
) -> ApiKeyRecord:
    return ApiKeyRecord(
        key_id=key_id,
        grant_id=grant.grant_id,
        binding=grant.binding,
        generation=1,
        state=AuthorityState.PENDING,
        valid_from=instant,
        expires_at=expires_at,
    )


def _candidate_entry(
    grant: AutomationGrant,
    record: EnrollmentRecord,
    entry: EnrollmentGrant | None,
    key: ApiKeyRecord,
    verifier: str,
) -> EnrollmentGrant:
    keys = () if entry is None else tuple(item for item in entry.keys if item.key.key_id != record.candidate_key_id)
    return EnrollmentGrant(grant=grant, keys=(*keys, AutomationKeyVerifier(key=key, verifier=verifier)))


def _verified_candidate(
    entry: EnrollmentGrant,
    record: EnrollmentRecord,
    key_id: UUID,
    verifier: str,
    instant: UtcInstant,
) -> AutomationKeyVerifier:
    candidate = next((item for item in entry.keys if item.key.key_id == record.candidate_key_id), None)
    if (
        candidate is None
        or key_id != candidate.key.key_id
        or not secrets.compare_digest(verifier, candidate.verifier)
        or candidate.key.state is not AuthorityState.PENDING
        or instant >= candidate.key.expires_at
    ):
        raise AutomationCustodyError(AutomationCustodyCode.CREDENTIAL_REJECTED)
    return candidate


def _activated_entry(
    entry: EnrollmentGrant, candidate: AutomationKeyVerifier, record: EnrollmentRecord, instant: UtcInstant
) -> EnrollmentGrant:
    keys = tuple(
        replace_enrollment_model(item, key=replace_enrollment_model(item.key, state=AuthorityState.ACTIVE))
        if item == candidate
        else replace_enrollment_model(
            item,
            key=replace_enrollment_model(
                item.key,
                expires_at=min(item.key.expires_at, instant + KEY_ROTATION_MAXIMUM_OVERLAP),
            ),
        )
        if item.key.key_id == record.proposal.target_key_id
        else item
        for item in entry.keys
    )
    active_grant = replace_enrollment_model(entry.grant, state=AuthorityState.ACTIVE)
    return replace_enrollment_model(entry, grant=active_grant, keys=keys)


class ApprovalSession:
    """One approval's proof and delivery custody across explicit publication phases.

    The caller constructs this object before dispatching any phase to a thread,
    completes that thread before close, and closes on every outcome. No private
    proof, candidate or DEK is a result or a serialized operation operand.
    """

    def __init__(
        self, service: AutomationAdministrationService, *, request_id: UUID, review_digest: ContentDigest
    ) -> None:
        """Hold only one exact request's transient approval facts."""
        self._service = service
        self._request_id = request_id
        self._review_digest = review_digest
        self._stage = "new"
        self._record: EnrollmentRecord | None = None
        self.prove_enrollment_approval: FreshPasswordAuthorization | None = None
        self._dek: SecretBytes | None = None
        self._recipient: ProtectedEnrollmentRecipient | None = None
        self._candidate_id: UUID | None = None
        self._candidate_secret: SecretBytes | None = None
        self._candidate_verifier: str | None = None
        self._possession: SecretBytes | None = None
        self._key_id: UUID | None = None
        self._verifier: str | None = None

    def _require(self, stage: str) -> None:
        if self._stage != stage:
            raise ValueError("approval phase is out of order or closed")

    def _owned(self) -> tuple[EnrollmentRecord, FreshPasswordAuthorization, SecretBytes]:
        record, proof, dek = self._record, self.prove_enrollment_approval, self._dek
        if record is None or proof is None or dek is None:
            raise ValueError("approval has no current prepared proof")
        return record, proof, dek

    def prepare(self, password: SecretBytes) -> None:
        """Prove the current profile password before any COMMIT section."""
        self._require("new")
        service = self._service
        state, facts = validate_enrollment_state(service.custody, service.owner, require_enabled=True)
        record = find_enrollment(state, self._request_id)
        require_enrollment_review(record, self._review_digest)
        require_live_enrollment(record, facts)
        proof, dek = prove_enrollment_approval(record, password, facts, service.storage_root)
        self._record, self.prove_enrollment_approval, self._dek = record, proof, dek
        self._stage = "prepared"

    def commit_review(self) -> EnrollmentTransition | None:
        """Recheck consent and publish a simple grant change, if applicable."""
        self._require("prepared")
        service = self._service
        original, proof, dek = self._owned()
        with service.owner.administration_guard():
            state, facts = validate_enrollment_state(service.custody, service.owner, require_enabled=True)
            authorize_enrollment(original, AccessAdministrationAction.APPROVE, facts, proof)
            record = find_enrollment(state, self._request_id)
            require_enrollment_review(record, self._review_digest)
            require_live_enrollment(record, facts)
            if record.stage is EnrollmentStage.COMPLETE:
                self._stage = "done"
                return EnrollmentTransition(receipt=enrollment_receipt(record), published=False)
            entry = target_enrollment_grant(state, record)
            if not scope_is_subset(record.proposal.scope, facts.profile.scope):
                raise AutomationCustodyError(AutomationCustodyCode.CREDENTIAL_REJECTED)
            if record.proposal.kind in {EnrollmentKind.RENEW, EnrollmentKind.CHANGE_SCOPE}:
                if entry is None:
                    raise AutomationCustodyError(AutomationCustodyCode.MISSING)
                # These changes have no delivery phase. Resolve the original
                # verified requester here so disconnect, expiry or revocation
                # cannot leave an inactive request as a portable capability.
                service.owner.recipient(record.requester)
                grant = replace_enrollment_model(
                    entry.grant,
                    scope=record.proposal.scope,
                    expires_at=record.proposal.expires_at,
                    generation=entry.grant.generation + 1,
                )
                record = replace_enrollment_model(record, stage=EnrollmentStage.COMPLETE)
                updated_entry = replace_enrollment_model(entry, grant=grant)
                service.custody.publish_enrollment(
                    updated_enrollment_state(state, record, updated_entry), fresh_dek=dek
                )
                self._stage = "done"
                return EnrollmentTransition(receipt=enrollment_receipt(record), published=True)
            self._record = record
            self._stage = "candidate_required"
            return None

    def inspect_recipient(self) -> bool:
        """Resolve client possession and prepare a fresh secret outside COMMIT."""
        self._require("candidate_required")
        record = self._record
        if record is None:
            raise ValueError("approval has no reviewed candidate")
        recipient = self._service.owner.recipient(record.requester)
        possession = recipient.possession(record) if record.candidate_key_id is not None else None
        self._recipient, self._possession = recipient, possession
        if possession is None:
            self._candidate_id, self._candidate_secret = self._service.issuer.generate()
            _, self._candidate_verifier = self._service.issuer.verifier(self._candidate_secret)
        self._stage = "recipient_checked"
        return possession is None

    def publish_candidate(self) -> EnrollmentTransition:
        """CAS one unusable candidate under a fresh lifecycle and custody guard."""
        self._require("recipient_checked")
        service = self._service
        record, proof, dek = self._owned()
        candidate_id, verifier = self._candidate_id, self._candidate_verifier
        if self._possession is not None or candidate_id is None or verifier is None:
            raise ValueError("approval has no fresh candidate to publish")
        with service.owner.administration_guard():
            state, facts = validate_enrollment_state(service.custody, service.owner, require_enabled=True)
            authorize_enrollment(record, AccessAdministrationAction.APPROVE, facts, proof)
            if find_enrollment(state, self._request_id) != record:
                raise AutomationCustodyError(AutomationCustodyCode.CONFLICT)
            require_enrollment_review(record, self._review_digest)
            require_live_enrollment(record, facts)
            entry = target_enrollment_grant(state, record)
            key_expires_at = record.proposal.key_expires_at
            if key_expires_at is None or key_expires_at <= facts.context.now:
                raise AutomationCustodyError(AutomationCustodyCode.CREDENTIAL_REJECTED)
            grant = _candidate_grant(record, state, entry)
            key = _candidate_key(grant, candidate_id, key_expires_at, facts.context.now)
            entry = _candidate_entry(grant, record, entry, key, verifier)
            record = replace_enrollment_model(
                record, stage=EnrollmentStage.CANDIDATE, candidate_key_id=candidate_id, credential_reference=uuid4()
            )
            service.custody.publish_enrollment(updated_enrollment_state(state, record, entry), fresh_dek=dek)
            self._record = record
            self._stage = "candidate_published"
            return EnrollmentTransition(receipt=enrollment_receipt(record), published=True)

    def deliver_and_verify(self) -> None:
        """Use exact recipient possession outside every publication guard."""
        if self._stage not in {"recipient_checked", "candidate_published"}:
            raise ValueError("approval phase is out of order or closed")
        recipient, record = self._recipient, self._record
        if recipient is None or record is None:
            raise ValueError("approval has no bound recipient")
        if self._stage == "candidate_published":
            secret = self._candidate_secret
            if secret is None:
                raise ValueError("approval has no candidate secret")
            recipient.deliver(record, secret)
            self._candidate_secret = None
            possession = recipient.possession(record)
        else:
            possession = self._possession
        if possession is None:
            raise AutomationCustodyError(AutomationCustodyCode.CREDENTIAL_REJECTED)
        self._key_id, self._verifier = self._service.issuer.verifier(possession)
        self._possession = None
        self._stage = "verified"

    def activate(self) -> EnrollmentTransition:
        """CAS the proven candidate active after fresh authority and exact-record checks."""
        self._require("verified")
        service = self._service
        record, proof, _dek = self._owned()
        key_id, verifier = self._key_id, self._verifier
        if key_id is None or verifier is None:
            raise ValueError("approval has no verified candidate")
        with service.owner.administration_guard():
            state, facts = validate_enrollment_state(service.custody, service.owner, require_enabled=True)
            require_live_enrollment(record, facts)
            authorize_enrollment(record, AccessAdministrationAction.APPROVE, facts, proof)
            if find_enrollment(state, self._request_id) != record or not scope_is_subset(
                record.proposal.scope, facts.profile.scope
            ):
                raise AutomationCustodyError(AutomationCustodyCode.CONFLICT)
            require_enrollment_review(record, self._review_digest)
            entry = target_enrollment_grant(state, record)
            if entry is None:
                raise AutomationCustodyError(AutomationCustodyCode.MISSING)
            candidate = _verified_candidate(entry, record, key_id, verifier, facts.context.now)
            entry = _activated_entry(entry, candidate, record, facts.context.now)
            record = replace_enrollment_model(record, stage=EnrollmentStage.COMPLETE)
            service.custody.publish_enrollment(updated_enrollment_state(state, record, entry))
            self._stage = "done"
            return EnrollmentTransition(receipt=enrollment_receipt(record), published=True)

    def close(self) -> None:
        """Release every caller-owned proof and delivery reference after threads settle."""
        self._stage = "closed"
        self._record = None
        self.prove_enrollment_approval = None
        self._dek = None
        self._recipient = None
        self._candidate_id = None
        self._candidate_secret = None
        self._candidate_verifier = None
        self._possession = None
        self._key_id = None
        self._verifier = None
