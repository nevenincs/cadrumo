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
    ApiKeyRecord,
    AuthorityState,
    AutomationGrant,
    Availability,
)
from .access_policy import scope_is_subset
from .access_projections import project_api_key, project_automation_grant
from .automation_custody_port import AutomationCustodyCode, AutomationCustodyError, AutomationKeyVerifier
from .automation_enrollment import (
    AdministrationFacts,
    AutomationAdministrationOwner,
    AutomationInventory,
    AutomationKeyIssuer,
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
        state, facts = self.custody.enrollment_state(), self.owner.facts()
        if (
            state.binding != facts.profile.binding
            or state.profile_lock_generation != facts.profile.lock_generation
            or not state.automation_enabled
            or not facts.profile.automation_enabled
            or facts.profile.globally_locked
            or not facts.context.private_work_available
            or facts.context.clock_rollback_detected
            or facts.profile.storage is not Availability.AVAILABLE
            or facts.profile.automation_custody is not Availability.AVAILABLE
        ):
            raise AutomationCustodyError(AutomationCustodyCode.NEEDS_USER)
        return state, facts

    @staticmethod
    def _find(state: EnrollmentControlState, identity: UUID) -> EnrollmentRecord:
        record = next((item for item in state.requests if item.request_id == identity), None)
        if record is None:
            raise AutomationCustodyError(AutomationCustodyCode.MISSING)
        return record

    @staticmethod
    def _live(record: EnrollmentRecord, facts: AdministrationFacts) -> None:
        if (
            record.binding != facts.profile.binding
            or record.requester.runtime_boot_id != facts.context.runtime_boot_id
            or not record.created_at <= facts.context.now < record.expires_at
            or record.stage is EnrollmentStage.DECLINED
        ):
            raise AutomationCustodyError(AutomationCustodyCode.CREDENTIAL_REJECTED)

    @staticmethod
    def _review(record: EnrollmentRecord, digest: ContentDigest) -> None:
        if not secrets.compare_digest(enrollment_review_digest(record), digest):
            raise AutomationCustodyError(AutomationCustodyCode.CONFLICT)

    def _authorize(
        self,
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
        self, record: EnrollmentRecord, password: SecretBytes, facts: AdministrationFacts
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
            storage_root=self.storage_root,
            deadline=record.expires_at,
        )

    def request(self, request_id: UUID, proposal: EnrollmentProposal) -> EnrollmentReceipt:
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
                return enrollment_receipt(old)
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
            self._target(state, record)
            self.custody.publish_enrollment(_replace(state, requests=(*state.requests, record)))
            return enrollment_receipt(record)

    @staticmethod
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

    @staticmethod
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

    def approve(self, request_id: UUID, *, review_digest: ContentDigest, password: SecretBytes) -> EnrollmentReceipt:
        """Prove exact consent, stage, deliver, prove possession and activate by CAS.

        Retry never reconstructs a secret. A delivered candidate can be proven
        again by its client; a missing candidate is replaced. Fresh proof is
        required on each retry, including recovery after runtime loss.
        """
        state, facts = self._state()
        record = self._find(state, request_id)
        self._review(record, review_digest)
        self._live(record, facts)
        proof, dek = self._proof(record, password, facts)
        with self.owner.administration_guard():
            state, facts = self._state()
            self._authorize(record, AccessAdministrationAction.APPROVE, facts, proof)
            record = self._find(state, request_id)
            self._live(record, facts)
            if record.stage is EnrollmentStage.COMPLETE:
                return enrollment_receipt(record)
            entry = self._target(state, record)
            if not scope_is_subset(record.proposal.scope, facts.profile.scope):
                raise AutomationCustodyError(AutomationCustodyCode.CREDENTIAL_REJECTED)
            if record.proposal.kind in {EnrollmentKind.RENEW, EnrollmentKind.CHANGE_SCOPE}:
                if entry is None:
                    raise AutomationCustodyError(AutomationCustodyCode.MISSING)
                grant = _replace(
                    entry.grant,
                    scope=record.proposal.scope,
                    expires_at=record.proposal.expires_at,
                    generation=entry.grant.generation + 1,
                )
                record = _replace(record, stage=EnrollmentStage.COMPLETE)
                self.custody.publish_enrollment(
                    self._updated(state, record, _replace(entry, grant=grant)), fresh_dek=dek
                )
                return enrollment_receipt(record)
        recipient = self.owner.recipient(record.requester)
        possession = recipient.possession(record) if record.candidate_key_id is not None else None
        if possession is None:
            candidate_id, secret = self.issuer.generate()
            _, verifier = self.issuer.verifier(secret)
            with self.owner.administration_guard():
                state, facts = self._state()
                self._authorize(record, AccessAdministrationAction.APPROVE, facts, proof)
                if self._find(state, request_id) != record:
                    raise AutomationCustodyError(AutomationCustodyCode.CONFLICT)
                self._live(record, facts)
                entry = self._target(state, record)
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
                self.custody.publish_enrollment(self._updated(state, record, entry), fresh_dek=dek)
            recipient.deliver(record, secret)
            del secret
            possession = recipient.possession(record)
        if possession is None:
            raise AutomationCustodyError(AutomationCustodyCode.CREDENTIAL_REJECTED)
        key_id, verifier = self.issuer.verifier(possession)
        del possession
        with self.owner.administration_guard():
            state, facts = self._state()
            self._live(record, facts)
            self._authorize(record, AccessAdministrationAction.APPROVE, facts, proof)
            if self._find(state, request_id) != record or not scope_is_subset(
                record.proposal.scope, facts.profile.scope
            ):
                raise AutomationCustodyError(AutomationCustodyCode.CONFLICT)
            entry = self._target(state, record)
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
            self.custody.publish_enrollment(self._updated(state, record, entry))
            return enrollment_receipt(record)

    def decline(self, request_id: UUID, *, review_digest: ContentDigest) -> EnrollmentReceipt:
        """End a pending request; a declined candidate remains unusable."""
        with self.owner.administration_guard():
            state, facts = self._state()
            record = self._find(state, request_id)
            self._review(record, review_digest)
            self._authorize(record, AccessAdministrationAction.DECLINE, facts)
            if record.stage is EnrollmentStage.DECLINED:
                return enrollment_receipt(record)
            if record.stage is EnrollmentStage.COMPLETE:
                raise AutomationCustodyError(AutomationCustodyCode.CONFLICT)
            record = _replace(record, stage=EnrollmentStage.DECLINED)
            self.custody.publish_enrollment(self._updated(state, record))
            return enrollment_receipt(record)

    def inventory(self) -> AutomationInventory:
        """Recheck human authority before releasing grant or exact consent details."""
        with self.owner.administration_guard():
            state, facts = self._state()
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
