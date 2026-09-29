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
    ACCESS_LEASE_MAXIMUM,
    KEY_ROTATION_MAXIMUM_OVERLAP,
    AccessDenied,
    AccessSession,
    ApiKeyRecord,
    AuthorityState,
    AutomationGrant,
    Availability,
    SessionKind,
)
from .access_policy import scope_is_subset
from .access_projections import project_api_key, project_automation_grant
from .automation_custody_port import AutomationCustodyCode, AutomationCustodyError, AutomationKeyVerifier
from .automation_enrollment import (
    AdministrationFacts,
    AutomationAdministrationOwner,
    AutomationInventory,
    AutomationInventoryOwner,
    AutomationKeyIssuer,
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
    EnrollmentTransition,
    ProtectedEnrollmentRecipient,
)
from .automation_password import prove_automation_administration


def _replace[T: BaseModel](model: T, **changes: object) -> T:
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
    if session.kind is not SessionKind.API_KEY or session.parent_session_id is not None or session.grant_id is None:
        raise AutomationCustodyError(AutomationCustodyCode.CREDENTIAL_REJECTED)
    record = next((item for item in state.requests if item.request_id == request_id), None)
    if (
        state.binding != session.binding
        or record is None
        or record.binding != session.binding
        or record.requester.client_id != session.client_id
        or record.requester.destination_id != session.client_id
        or record.grant_id != session.grant_id
        or record.stage not in {EnrollmentStage.COMPLETE, EnrollmentStage.DECLINED}
    ):
        raise AutomationCustodyError(AutomationCustodyCode.CREDENTIAL_REJECTED)
    return AutomationReceiptProjection.model_validate(enrollment_receipt(record).model_dump())


def _validated_state(
    custody: EnrollmentCustodyPort, owner: AutomationInventoryOwner, *, require_enabled: bool
) -> tuple[EnrollmentControlState, AdministrationFacts]:
    """Keep every custody and lifecycle fence shared by reads and writes."""
    state, facts = custody.enrollment_state(), owner.facts()
    if (
        state.binding != facts.profile.binding
        or state.profile_lock_generation != facts.profile.lock_generation
        or state.automation_enabled != facts.profile.automation_enabled
        or (require_enabled and not state.automation_enabled)
        or facts.profile.globally_locked
        or not facts.context.private_work_available
        or facts.context.clock_rollback_detected
        or facts.profile.storage is not Availability.AVAILABLE
        or facts.profile.automation_custody is not Availability.AVAILABLE
    ):
        raise AutomationCustodyError(AutomationCustodyCode.NEEDS_USER)
    return state, facts


def inspect_automation_inventory(
    *, custody: EnrollmentCustodyPort, owner: AutomationInventoryOwner
) -> AutomationInventory:
    """Release exact consent and grant facts only under fresh human authority."""
    with owner.administration_guard():
        state, facts = _validated_state(custody, owner, require_enabled=False)
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


def _find(state: EnrollmentControlState, identity: UUID) -> EnrollmentRecord:
    record = next((item for item in state.requests if item.request_id == identity), None)
    if record is None:
        raise AutomationCustodyError(AutomationCustodyCode.MISSING)
    return record


def _live(record: EnrollmentRecord, facts: AdministrationFacts) -> None:
    if (
        record.binding != facts.profile.binding
        or record.requester.runtime_boot_id != facts.context.runtime_boot_id
        or not record.created_at <= facts.context.now < record.expires_at
        or record.stage is EnrollmentStage.DECLINED
    ):
        raise AutomationCustodyError(AutomationCustodyCode.CREDENTIAL_REJECTED)


def _review(record: EnrollmentRecord, digest: ContentDigest) -> None:
    if not secrets.compare_digest(enrollment_review_digest(record), digest):
        raise AutomationCustodyError(AutomationCustodyCode.CONFLICT)


def _authorize(
    record: EnrollmentRecord,
    action: AccessAdministrationAction,
    facts: AdministrationFacts,
    proof: FreshPasswordAuthorization | None = None,
) -> None:
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


def _proof(
    record: EnrollmentRecord, password: SecretBytes, facts: AdministrationFacts, storage_root: Path
) -> tuple[FreshPasswordAuthorization, SecretBytes]:
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


def _target(state: EnrollmentControlState, record: EnrollmentRecord) -> EnrollmentGrant | None:
    proposal = record.proposal
    entry = next((item for item in state.grants if item.grant.grant_id == record.grant_id), None)
    if proposal.kind is EnrollmentKind.ENROLL:
        if entry is not None and entry.grant.state is not AuthorityState.PENDING:
            raise AutomationCustodyError(AutomationCustodyCode.CONFLICT)
        return entry
    if (
        entry is None
        or entry.grant.state is not AuthorityState.ACTIVE
        or entry.grant.client_id != record.requester.client_id
    ):
        raise AutomationCustodyError(AutomationCustodyCode.CREDENTIAL_REJECTED)
    grant = entry.grant
    if (
        grant.profile_lock_generation != state.profile_lock_generation
        or proposal.unattended != grant.unattended
        or proposal.allow_os_lock != grant.allow_os_lock
    ):
        raise AutomationCustodyError(AutomationCustodyCode.CONFLICT)
    if proposal.kind is not EnrollmentKind.CHANGE_SCOPE and proposal.scope != grant.scope:
        raise AutomationCustodyError(AutomationCustodyCode.CONFLICT)
    if proposal.kind is not EnrollmentKind.RENEW and proposal.expires_at != grant.expires_at:
        raise AutomationCustodyError(AutomationCustodyCode.CONFLICT)
    if proposal.kind is EnrollmentKind.RENEW and proposal.expires_at <= grant.expires_at:
        raise AutomationCustodyError(AutomationCustodyCode.CONFLICT)
    if proposal.kind is EnrollmentKind.ROTATE and not any(
        item.key.key_id == proposal.target_key_id and item.key.state is AuthorityState.ACTIVE for item in entry.keys
    ):
        raise AutomationCustodyError(AutomationCustodyCode.CREDENTIAL_REJECTED)
    return entry


def _updated(
    state: EnrollmentControlState, record: EnrollmentRecord, entry: EnrollmentGrant | None = None
) -> EnrollmentControlState:
    return _replace(
        state,
        requests=tuple(record if item.request_id == record.request_id else item for item in state.requests),
        grants=state.grants
        if entry is None
        else (*tuple(item for item in state.grants if item.grant.grant_id != entry.grant.grant_id), entry),
    )


class AutomationAdministrationService:
    """One profile's administration, with explicit current owner and recipient ports."""

    def __init__(
        self,
        *,
        custody: EnrollmentCustodyPort,
        owner: AutomationAdministrationOwner,
        issuer: AutomationKeyIssuer,
        storage_root: Path,
    ) -> None:
        """Compose trusted dependencies; never infer authority from active selection."""
        self.custody, self.owner, self.issuer, self.storage_root = custody, owner, issuer, storage_root

    def _state(self) -> tuple[EnrollmentControlState, AdministrationFacts]:
        return _validated_state(self.custody, self.owner, require_enabled=True)

    def request(self, request_id: UUID, proposal: EnrollmentProposal) -> EnrollmentTransition:
        """Create an inactive exact-connection request; repeated IDs cannot retarget."""
        with self.owner.administration_guard():
            state, facts = self._state()
            requester = self.owner.requester()
            if (
                requester.runtime_boot_id != facts.context.runtime_boot_id
                or requester.connection_id != facts.context.connection_id
                or requester.client_id != facts.context.authenticated_client_id
            ):
                raise AutomationCustodyError(AutomationCustodyCode.CREDENTIAL_REJECTED)
            old = next((item for item in state.requests if item.request_id == request_id), None)
            if old is not None:
                if old.proposal != proposal or old.requester != requester:
                    raise AutomationCustodyError(AutomationCustodyCode.CONFLICT)
                return EnrollmentTransition(receipt=enrollment_receipt(old), published=False)
            if (
                not scope_is_subset(proposal.scope, facts.profile.scope)
                or proposal.expires_at <= facts.context.now
                or (proposal.key_expires_at is not None and proposal.key_expires_at <= facts.context.now)
                or any(item.destination_id != requester.destination_id for item in proposal.scope.disclosures)
            ):
                raise AutomationCustodyError(AutomationCustodyCode.CREDENTIAL_REJECTED)
            record = EnrollmentRecord(
                request_id=request_id,
                binding=state.binding,
                requester=requester,
                proposal=proposal,
                created_at=facts.context.now,
                expires_at=facts.context.now + ACCESS_LEASE_MAXIMUM,
                stage=EnrollmentStage.REQUESTED,
                grant_id=proposal.target_grant_id or uuid4(),
            )
            _target(state, record)
            self.custody.publish_enrollment(_replace(state, requests=(*state.requests, record)))
            return EnrollmentTransition(receipt=enrollment_receipt(record), published=True)

    def approval(self, request_id: UUID, *, review_digest: ContentDigest) -> ApprovalSession:
        """Create one caller-owned approval journey before any cancellable work."""
        return ApprovalSession(self, request_id=request_id, review_digest=review_digest)

    def approve(self, request_id: UUID, *, review_digest: ContentDigest, password: SecretBytes) -> EnrollmentTransition:
        """Complete the same staged approval journey for direct application callers."""
        session = self.approval(request_id, review_digest=review_digest)
        try:
            session.prepare(password)
            completed = session.commit_review()
            if completed is not None:
                return completed
            if session.inspect_recipient():
                session.publish_candidate()
            session.deliver_and_verify()
            return session.activate()
        finally:
            session.close()

    def decline(self, request_id: UUID, *, review_digest: ContentDigest) -> EnrollmentTransition:
        """End a pending request; a declined candidate remains unusable."""
        with self.owner.administration_guard():
            state, facts = self._state()
            record = _find(state, request_id)
            _review(record, review_digest)
            _authorize(record, AccessAdministrationAction.DECLINE, facts)
            if record.stage is EnrollmentStage.DECLINED:
                return EnrollmentTransition(receipt=enrollment_receipt(record), published=False)
            if record.stage is EnrollmentStage.COMPLETE:
                raise AutomationCustodyError(AutomationCustodyCode.CONFLICT)
            record = _replace(record, stage=EnrollmentStage.DECLINED)
            self.custody.publish_enrollment(_updated(state, record))
            return EnrollmentTransition(receipt=enrollment_receipt(record), published=True)

    def inventory(self) -> AutomationInventory:
        """Recheck human authority before releasing grant or exact consent details."""
        return inspect_automation_inventory(custody=self.custody, owner=self.owner)


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
        self._proof: FreshPasswordAuthorization | None = None
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
        record, proof, dek = self._record, self._proof, self._dek
        if record is None or proof is None or dek is None:
            raise ValueError("approval has no current prepared proof")
        return record, proof, dek

    def prepare(self, password: SecretBytes) -> None:
        """Prove the current profile password before any COMMIT section."""
        self._require("new")
        service = self._service
        state, facts = _validated_state(service.custody, service.owner, require_enabled=True)
        record = _find(state, self._request_id)
        _review(record, self._review_digest)
        _live(record, facts)
        proof, dek = _proof(record, password, facts, service.storage_root)
        self._record, self._proof, self._dek = record, proof, dek
        self._stage = "prepared"

    def commit_review(self) -> EnrollmentTransition | None:
        """Recheck consent and publish a simple grant change, if applicable."""
        self._require("prepared")
        service = self._service
        original, proof, dek = self._owned()
        with service.owner.administration_guard():
            state, facts = _validated_state(service.custody, service.owner, require_enabled=True)
            _authorize(original, AccessAdministrationAction.APPROVE, facts, proof)
            record = _find(state, self._request_id)
            _review(record, self._review_digest)
            _live(record, facts)
            if record.stage is EnrollmentStage.COMPLETE:
                self._stage = "done"
                return EnrollmentTransition(receipt=enrollment_receipt(record), published=False)
            entry = _target(state, record)
            if not scope_is_subset(record.proposal.scope, facts.profile.scope):
                raise AutomationCustodyError(AutomationCustodyCode.CREDENTIAL_REJECTED)
            if record.proposal.kind in {EnrollmentKind.RENEW, EnrollmentKind.CHANGE_SCOPE}:
                if entry is None:
                    raise AutomationCustodyError(AutomationCustodyCode.MISSING)
                # These changes have no delivery phase. Resolve the original
                # verified requester here so disconnect, expiry or revocation
                # cannot leave an inactive request as a portable capability.
                service.owner.recipient(record.requester)
                grant = _replace(
                    entry.grant,
                    scope=record.proposal.scope,
                    expires_at=record.proposal.expires_at,
                    generation=entry.grant.generation + 1,
                )
                record = _replace(record, stage=EnrollmentStage.COMPLETE)
                service.custody.publish_enrollment(_updated(state, record, _replace(entry, grant=grant)), fresh_dek=dek)
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
            state, facts = _validated_state(service.custody, service.owner, require_enabled=True)
            _authorize(record, AccessAdministrationAction.APPROVE, facts, proof)
            if _find(state, self._request_id) != record:
                raise AutomationCustodyError(AutomationCustodyCode.CONFLICT)
            _review(record, self._review_digest)
            _live(record, facts)
            entry = _target(state, record)
            if record.proposal.key_expires_at is None or record.proposal.key_expires_at <= facts.context.now:
                raise AutomationCustodyError(AutomationCustodyCode.CREDENTIAL_REJECTED)
            grant = (
                entry.grant
                if entry is not None
                else AutomationGrant(
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
            )
            key = ApiKeyRecord(
                key_id=candidate_id,
                grant_id=grant.grant_id,
                binding=grant.binding,
                generation=1,
                state=AuthorityState.PENDING,
                valid_from=facts.context.now,
                expires_at=record.proposal.key_expires_at,
            )
            keys = (
                ()
                if entry is None
                else tuple(item for item in entry.keys if item.key.key_id != record.candidate_key_id)
            )
            entry = EnrollmentGrant(grant=grant, keys=(*keys, AutomationKeyVerifier(key=key, verifier=verifier)))
            record = _replace(
                record, stage=EnrollmentStage.CANDIDATE, candidate_key_id=candidate_id, credential_reference=uuid4()
            )
            service.custody.publish_enrollment(_updated(state, record, entry), fresh_dek=dek)
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
            state, facts = _validated_state(service.custody, service.owner, require_enabled=True)
            _live(record, facts)
            _authorize(record, AccessAdministrationAction.APPROVE, facts, proof)
            if _find(state, self._request_id) != record or not scope_is_subset(
                record.proposal.scope, facts.profile.scope
            ):
                raise AutomationCustodyError(AutomationCustodyCode.CONFLICT)
            _review(record, self._review_digest)
            entry = _target(state, record)
            if entry is None:
                raise AutomationCustodyError(AutomationCustodyCode.MISSING)
            candidate = next((item for item in entry.keys if item.key.key_id == record.candidate_key_id), None)
            if (
                candidate is None
                or key_id != candidate.key.key_id
                or not secrets.compare_digest(verifier, candidate.verifier)
                or candidate.key.state is not AuthorityState.PENDING
                or facts.context.now >= candidate.key.expires_at
            ):
                raise AutomationCustodyError(AutomationCustodyCode.CREDENTIAL_REJECTED)
            keys = tuple(
                _replace(item, key=_replace(item.key, state=AuthorityState.ACTIVE))
                if item == candidate
                else _replace(
                    item,
                    key=_replace(
                        item.key, expires_at=min(item.key.expires_at, facts.context.now + KEY_ROTATION_MAXIMUM_OVERLAP)
                    ),
                )
                if item.key.key_id == record.proposal.target_key_id
                else item
                for item in entry.keys
            )
            entry = _replace(entry, grant=_replace(entry.grant, state=AuthorityState.ACTIVE), keys=keys)
            record = _replace(record, stage=EnrollmentStage.COMPLETE)
            service.custody.publish_enrollment(_updated(state, record, entry))
            self._stage = "done"
            return EnrollmentTransition(receipt=enrollment_receipt(record), published=True)

    def close(self) -> None:
        """Release every caller-owned proof and delivery reference after threads settle."""
        self._stage = "closed"
        self._record = None
        self._proof = None
        self._dek = None
        self._recipient = None
        self._candidate_id = None
        self._candidate_secret = None
        self._candidate_verifier = None
        self._possession = None
        self._key_id = None
        self._verifier = None
