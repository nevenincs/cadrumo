"""Sealed enrollment facts and explicit ports for trusted local administration.

None of the private state or connection facts is a frontend request schema.
The runtime supplies connection provenance and the recipient capability. A name
or UUID supplied by an agent cannot construct either authority.
"""

from __future__ import annotations

from contextlib import AbstractContextManager
from enum import StrEnum
from typing import Annotated, Protocol
from uuid import UUID

from pydantic import BaseModel, Field, SecretBytes, model_validator

from ...core.identity.digest import ContentDigest
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...core.time.utc import UtcInstant
from .access_contracts import (
    ACCESS_LEASE_MAXIMUM,
    AccessEvaluationContext,
    AccessScope,
    AccessSession,
    AutomationGrant,
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
        if not self.created_at < self.expires_at <= self.created_at + ACCESS_LEASE_MAXIMUM:
            raise ValueError("invalid request interval")
        if (self.candidate_key_id is None) != (self.credential_reference is None):
            raise ValueError("incomplete delivery binding")
        if self.stage is EnrollmentStage.REQUESTED and self.candidate_key_id is not None:
            raise ValueError("unstaged candidate")
        if self.stage is EnrollmentStage.CANDIDATE and (
            self.proposal.kind not in {EnrollmentKind.ENROLL, EnrollmentKind.ROTATE} or self.candidate_key_id is None
        ):
            raise ValueError("missing candidate delivery binding")
        if self.stage is EnrollmentStage.COMPLETE and (
            (self.proposal.kind in {EnrollmentKind.ENROLL, EnrollmentKind.ROTATE})
            != (self.candidate_key_id is not None)
        ):
            raise ValueError("completed request has inconsistent delivery binding")
        return self


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


class AdministrationFacts(BaseModel):
    """Fresh observations supplied by the trusted lifecycle owner."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    profile: ProfileAccessState
    context: AccessEvaluationContext
    originating_login_id: str
    session: AccessSession | None


class AutomationAdministrationOwner(Protocol):
    """Reobserve authority and locate an exact authenticated recipient."""

    def facts(self) -> AdministrationFacts:
        """Read current fences, login provenance, monotonic clock and connection."""
        ...

    def requester(self) -> EnrollmentRequester:
        """Return the requesting connection's verified recipient coordinates."""
        ...

    def recipient(self, requester: EnrollmentRequester) -> ProtectedEnrollmentRecipient:
        """Require this exact live connection, boot, client and destination."""
        ...

    def administration_guard(self) -> AbstractContextManager[None]:
        """Serialize revalidation/publication with lifecycle denial fences."""
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
