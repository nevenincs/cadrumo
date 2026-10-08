"""Sealed enrollment facts and explicit ports for trusted local administration.

None of the private state or connection facts is a frontend request schema.
The runtime supplies connection provenance and the recipient capability. A name
or UUID supplied by an agent cannot construct either authority.
"""

from __future__ import annotations

from contextlib import AbstractContextManager
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Annotated, Protocol, Self
from uuid import UUID

from pydantic import BaseModel, Field, SecretBytes, model_validator

from ...core.identity.digest import ContentDigest
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...core.time.utc import UtcInstant
from .access_contracts import (
    ACCESS_LEASE_MAXIMUM,
    AccessAction,
    AccessEvaluationContext,
    AccessScope,
    AccessSession,
    AuthorityState,
    AutomationGrant,
    DisclosurePermission,
    ProfileAccessBinding,
    ProfileAccessState,
)
from .access_projections import PublicApiKey, PublicAutomationGrant
from .automation_custody_port import AutomationKeyVerifier


class EnrollmentKind(StrEnum):
    """Exactly reviewed grant changes; a rotation never extends grant validity."""

    ENROLL = "enroll"
    ROTATE = "rotate"
    RENEW = "renew"
    CHANGE_SCOPE = "change_scope"


class EnrollmentStage(StrEnum):
    """Durable stages; only COMPLETE can confer usable authority."""

    REQUESTED = "requested"
    CANDIDATE = "candidate"
    COMPLETE = "complete"
    DECLINED = "declined"


class EnrollmentProposal(BaseModel):
    """Private consent operand, submitted only through the ephemeral channel."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    kind: EnrollmentKind
    scope: AccessScope
    expires_at: UtcInstant
    key_expires_at: UtcInstant | None
    unattended: bool
    allow_os_lock: bool
    target_grant_id: UUID | None = None
    target_key_id: UUID | None = None

    @model_validator(mode="after")
    def _targets(self) -> EnrollmentProposal:
        if (self.kind is EnrollmentKind.ENROLL) != (self.target_grant_id is None):
            raise ValueError("grant target does not match enrollment kind")
        if (self.kind is EnrollmentKind.ROTATE) != (self.target_key_id is not None):
            raise ValueError("key target does not match enrollment kind")
        if (self.kind in {EnrollmentKind.ENROLL, EnrollmentKind.ROTATE}) != (self.key_expires_at is not None):
            raise ValueError("key validity must match the reviewed key change")
        if (self.key_expires_at is not None and self.key_expires_at > self.expires_at) or (
            self.allow_os_lock and not self.unattended
        ):
            raise ValueError("invalid enrollment bounds")
        return self


class EnrollmentRequester(BaseModel):
    """Transport-verified recipient, never caller-asserted attribution."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    runtime_boot_id: UUID
    connection_id: UUID
    client_id: UUID
    destination_id: UUID


class EnrollmentRecord(BaseModel):
    """One immutable review plus its recoverable publication progress."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    request_id: UUID
    binding: ProfileAccessBinding
    requester: EnrollmentRequester
    proposal: EnrollmentProposal
    created_at: UtcInstant
    expires_at: UtcInstant
    stage: EnrollmentStage
    grant_id: UUID
    candidate_key_id: UUID | None = None
    credential_reference: UUID | None = None

    @model_validator(mode="after")
    def _stage(self) -> EnrollmentRecord:
        _require_enrollment_request_interval(self.created_at, self.expires_at)
        _require_complete_candidate_delivery_binding(self.candidate_key_id, self.credential_reference)
        _require_candidate_stage_consistency(self.stage, self.proposal.kind, self.candidate_key_id)
        _require_completed_stage_consistency(self.stage, self.proposal.kind, self.candidate_key_id)
        return self


def _require_enrollment_request_interval(created_at: UtcInstant, expires_at: UtcInstant) -> None:
    if not created_at < expires_at <= created_at + ACCESS_LEASE_MAXIMUM:
        raise ValueError("invalid request interval")


def _require_complete_candidate_delivery_binding(
    candidate_key_id: UUID | None, credential_reference: UUID | None
) -> None:
    if (candidate_key_id is None) != (credential_reference is None):
        raise ValueError("incomplete delivery binding")


def _require_candidate_stage_consistency(
    stage: EnrollmentStage, kind: EnrollmentKind, candidate_key_id: UUID | None
) -> None:
    if stage is EnrollmentStage.REQUESTED and candidate_key_id is not None:
        raise ValueError("unstaged candidate")
    if stage is EnrollmentStage.CANDIDATE and (
        kind not in {EnrollmentKind.ENROLL, EnrollmentKind.ROTATE} or candidate_key_id is None
    ):
        raise ValueError("missing candidate delivery binding")


def _require_completed_stage_consistency(
    stage: EnrollmentStage, kind: EnrollmentKind, candidate_key_id: UUID | None
) -> None:
    if stage is EnrollmentStage.COMPLETE and (
        (kind in {EnrollmentKind.ENROLL, EnrollmentKind.ROTATE}) != (candidate_key_id is not None)
    ):
        raise ValueError("completed request has inconsistent delivery binding")


class EnrollmentGrant(BaseModel):
    """Private verifier inventory, without native wrapping keys or DEKs."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    grant: AutomationGrant
    keys: tuple[AutomationKeyVerifier, ...] = Field(repr=False)


class EnrollmentControlState(BaseModel):
    """Trusted application view of one authenticated control-store revision."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    revision: Annotated[int, Field(ge=0)]
    binding: ProfileAccessBinding
    profile_lock_generation: Annotated[int, Field(ge=0)]
    automation_enabled: bool
    grants: tuple[EnrollmentGrant, ...] = Field(repr=False)
    requests: tuple[EnrollmentRecord, ...] = Field(repr=False)


class EnrollmentReceipt(BaseModel):
    """Nonsecret outcome; a credential reference conveys no possession proof."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    request_id: UUID
    profile_id: UUID
    stage: EnrollmentStage
    review_digest: ContentDigest
    grant_id: UUID
    key_id: UUID | None
    credential_reference: UUID | None


@dataclass(frozen=True, slots=True)
class EnrollmentTransition:
    """One call's receipt and whether its guarded publication completed."""

    receipt: EnrollmentReceipt
    published: bool


class EnrollmentReview(BaseModel):
    """Human-authorized exact consent display, excluding transport internals."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    receipt: EnrollmentReceipt
    client_id: UUID
    destination_id: UUID
    proposal: EnrollmentProposal
    expires_at: UtcInstant


class AutomationInventory(BaseModel):
    """Human-only allowlisted inventory, never plaintext journal material."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    grants: tuple[PublicAutomationGrant, ...]
    keys: tuple[PublicApiKey, ...]
    requests: tuple[EnrollmentReview, ...]


class AutomationPeriodProjection(BaseModel):
    """Portable filing coordinate without the domain Period's schema hook."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    filing_year: int
    code: str


class AutomationScopeProjection(BaseModel):
    """Typed public scope with explicit stable ordering for allow sets."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    operations: tuple[str, ...]
    actions: tuple[AccessAction, ...]
    disclosures: tuple[DisclosurePermission, ...]
    periods: tuple[AutomationPeriodProjection, ...] | None
    allow_period_independent: bool
    allow_delegation: bool

    @classmethod
    def from_scope(cls, scope: AccessScope) -> Self:
        """Flatten a domain scope into its stable public ordering."""
        return cls(
            operations=tuple(sorted(scope.operations)),
            actions=tuple(sorted(scope.actions)),
            disclosures=tuple(
                sorted(
                    scope.disclosures, key=lambda item: (str(item.destination_id), item.projection_id, item.category)
                )
            ),
            periods=None
            if scope.periods is None
            else tuple(
                AutomationPeriodProjection(filing_year=item.filing_year, code=str(item.code))
                for item in sorted(scope.periods, key=lambda item: (item.filing_year, str(item.code)))
            ),
            allow_period_independent=scope.allow_period_independent,
            allow_delegation=scope.allow_delegation,
        )


class AutomationGrantProjection(BaseModel):
    """Public grant facts without protected custody bindings."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    grant_id: UUID
    profile_id: UUID
    client_id: UUID
    state: AuthorityState
    scope: AutomationScopeProjection
    valid_from: datetime
    expires_at: datetime
    unattended: bool
    allow_os_lock: bool


class AutomationProposalProjection(BaseModel):
    """Human-visible reviewed consent, using the portable scope shape."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    kind: EnrollmentKind
    scope: AutomationScopeProjection
    expires_at: datetime
    key_expires_at: datetime | None
    unattended: bool
    allow_os_lock: bool
    target_grant_id: UUID | None
    target_key_id: UUID | None


class AutomationKeyProjection(BaseModel):
    """Public key status without possession, verifier or storage locator."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    key_id: UUID
    grant_id: UUID
    profile_id: UUID
    state: AuthorityState
    valid_from: datetime
    expires_at: datetime
    last_used_at: datetime | None


class AutomationReceiptProjection(BaseModel):
    """Public review identity, never a credential-delivery capability."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    request_id: UUID
    profile_id: UUID
    stage: EnrollmentStage
    review_digest: ContentDigest
    grant_id: UUID
    key_id: UUID | None
    credential_reference: UUID | None


class AutomationReviewProjection(BaseModel):
    """One exact review and recipient identity without secret delivery data."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    receipt: AutomationReceiptProjection
    client_id: UUID
    destination_id: UUID
    proposal: AutomationProposalProjection
    expires_at: datetime


class AutomationInventoryProjection(BaseModel):
    """Strict public result projected only from authorized inventory facts."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    grants: tuple[AutomationGrantProjection, ...]
    keys: tuple[AutomationKeyProjection, ...]
    requests: tuple[AutomationReviewProjection, ...]


class AdministrationFacts(BaseModel):
    """Fresh observations supplied by the trusted lifecycle owner."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    profile: ProfileAccessState
    context: AccessEvaluationContext
    originating_login_id: str
    session: AccessSession | None


class AutomationInventoryOwner(Protocol):
    """Reobserve and serialize human authority for inventory inspection."""

    def facts(self) -> AdministrationFacts:
        """Read current fences, login provenance, monotonic clock and connection."""
        ...

    def administration_guard(self) -> AbstractContextManager[None]:
        """Serialize revalidation/publication with lifecycle denial fences."""
        ...


class AutomationAdministrationOwner(AutomationInventoryOwner, Protocol):
    """Inventory authority plus exact requester and protected recipient."""

    def requester(self) -> EnrollmentRequester:
        """Return the requesting connection's verified recipient coordinates."""
        ...

    def recipient(self, requester: EnrollmentRequester) -> ProtectedEnrollmentRecipient:
        """Require this exact live connection, boot, client and destination."""
        ...


class ProtectedEnrollmentRecipient(Protocol):
    """Authenticated client-side delivery capability, distinct from server custody.

    Implementations must use an approved native store or an explicit protected
    channel. The possession response must originate at the bound client after
    protected receipt. Server-side write/read-back alone is not this capability.
    """

    def deliver(self, request: EnrollmentRecord, secret: SecretBytes) -> None:
        """Deliver once to the exact bound recipient; failure can be ambiguous."""
        ...

    def possession(self, request: EnrollmentRecord) -> SecretBytes | None:
        """Return client possession over its protected channel, or known absence."""
        ...


class EnrollmentCustodyPort(Protocol):
    """Existing sealed control store extended with enrollment publication."""

    def enrollment_state(self) -> EnrollmentControlState:
        """Reconcile current state; distinguish pristine from missing/corrupt."""
        ...

    def publish_enrollment(self, state: EnrollmentControlState, *, fresh_dek: SecretBytes | None = None) -> int:
        """CAS the complete state, preserving per-grant protected DEK custody."""
        ...


class AutomationKeyIssuer(Protocol):
    """Canonical cryptographic key codec supplied by custody composition."""

    def generate(self) -> tuple[UUID, SecretBytes]:
        """Generate an independent high-entropy candidate."""
        ...

    def verifier(self, secret: SecretBytes) -> tuple[UUID, str]:
        """Parse and hash the exact versioned credential."""
        ...
