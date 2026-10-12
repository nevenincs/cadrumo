"""Credential-free contracts for exact-profile delegated authorization.

These are application authority facts, not authentication messages. The lifecycle
owner must load them from verified custody and the authenticated connection; a
client supplying an identical JSON object has proved nothing. No contract stores
a password, API secret, verifier, encryption key or operation response bearer.
"""

from __future__ import annotations

from collections import Counter
from datetime import timedelta
from enum import StrEnum
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from ...core.hashing import canonical_json_bytes, sha256_hex
from ...core.identity.digest import ContentDigest
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...core.period import Period
from ...core.profile_session import ProfileSessionRefusalReason
from ...core.time.utc import UtcInstant
from ..operations.mcp_surfaces import McpSurfaceName
from ..operations.models import OperationDefinitionId
from ..operations.registry import OperationFrontendProjection
from ..operations.schema_identity import OperationPublicSchemaId
from .sign_in_refusals import SignInRefusal

ACCESS_LEASE_MAXIMUM = timedelta(minutes=5)
GRANT_DEFAULT_VALIDITY = timedelta(days=365)
KEY_ROTATION_MAXIMUM_OVERLAP = timedelta(seconds=60)


class ProfileAccessBinding(BaseModel):
    """Immutable custody identity; display labels and active selectors are absent."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    installation_id: UUID
    os_owner_id: Annotated[str, Field(min_length=1, max_length=256)]
    custody_generation: Annotated[int, Field(ge=1)]
    dek_epoch: UUID


class AccessAction(StrEnum):
    """Independently scoped doors on the existing operation services."""

    SUBMIT = "submit"
    START = "start"
    RESUME = "resume"
    OBSERVE = "observe"
    RESULT = "result"
    REVIEW = "review"
    RESPOND = "respond"
    CANCEL = "cancel"
    DETACH = "detach"
    COMMIT = "commit"


class DisclosureCategory(StrEnum):
    """Permitted output categories; credentials and source evidence are absent."""

    OPERATION_METADATA = "operation_metadata"
    PROFILE_VALUES = "profile_values"
    TAX_VALUES = "tax_values"


class DisclosurePermission(BaseModel):
    """Consent for one registered projection/category and one enrolled destination."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    destination_id: UUID
    projection_id: OperationPublicSchemaId
    category: DisclosureCategory


class DisclosureCategoryGrant(BaseModel):
    """Consent for every registered projection in one category, to one enrolled destination.

    A stored grant names the category and not its projections, so a projection
    registered in that category later is covered too. Admission resolves it
    against the live operation registry into explicit permissions; a session's
    lease never carries one.
    """

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    destination_id: UUID
    category: DisclosureCategory

    def covers(self, permission: DisclosurePermission) -> bool:
        """Whether this grant consents to one explicit permission."""
        return permission.destination_id == self.destination_id and permission.category is self.category


class AccessScope(BaseModel):
    """Explicit allow sets; no operation wildcard or implicit all-profile scope.

    ``periods=None`` explicitly permits all periods. An empty set permits none.
    Period-independent work has its own permission, so omitting a tax coordinate
    cannot turn a period-restricted grant into unrestricted access.
    ``disclosure_categories`` consents to whole categories for one destination;
    it is absent from every scope that predates it, which consented to none.
    """

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    operations: frozenset[OperationDefinitionId]
    actions: frozenset[AccessAction]
    disclosures: frozenset[DisclosurePermission]
    periods: frozenset[Period] | None
    allow_period_independent: bool
    allow_delegation: bool
    disclosure_categories: frozenset[DisclosureCategoryGrant] = frozenset[DisclosureCategoryGrant]()

    def discloses(self, permission: DisclosurePermission) -> bool:
        """Whether this scope consents to one explicit permission, listed or by its category."""
        return permission in self.disclosures or any(item.covers(permission) for item in self.disclosure_categories)


DISCLOSURE_PAGE_ENTRIES = 100
"""The most disclosure entries one page read releases; a frame holds them with room to spare."""


def ordered_disclosures(disclosures: frozenset[DisclosurePermission]) -> tuple[DisclosurePermission, ...]:
    """Order a scope's disclosures as every summary digest and page read sees them, by category first."""
    return tuple(
        sorted(disclosures, key=lambda item: (item.category.value, str(item.projection_id), str(item.destination_id)))
    )


def disclosure_digest(ordered: tuple[DisclosurePermission, ...]) -> ContentDigest:
    """Digest the ordered list a page read continues against, so a summary pins what it counted."""
    return sha256_hex(canonical_json_bytes([item.model_dump(mode="json") for item in ordered]))


class DisclosureCategoryCount(BaseModel):
    """How many of a scope's disclosures fall in one category."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    category: DisclosureCategory
    count: Annotated[int, Field(ge=1)]


type DisclosureSummary = Annotated[tuple[DisclosureCategoryCount, ...], Field(max_length=len(DisclosureCategory))]


def summarize_disclosures(ordered: tuple[DisclosurePermission, ...]) -> tuple[DisclosureCategoryCount, ...]:
    """Count an ordered list by category, each category once and in order."""
    counts = Counter(item.category for item in ordered)
    return tuple(
        DisclosureCategoryCount(category=category, count=counts[category])
        for category in sorted(counts, key=lambda item: item.value)
    )


def _require_summary_of(summary: tuple[DisclosureCategoryCount, ...], count: int) -> None:
    categories = [item.category.value for item in summary]
    if categories != sorted(set(categories)):
        raise ValueError("a disclosure summary names each category once, in order")
    if sum(item.count for item in summary) != count:
        raise ValueError("a disclosure summary counts every disclosure once")


class EffectiveScopeSummary(BaseModel):
    """The effective scope a status reply carries, with its disclosures counted and not listed.

    The full disclosure list is read by page against ``disclosure_digest``.
    Summarising grants and enforces nothing: the runtime checks every access
    against the session's whole scope.
    """

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    operations: frozenset[OperationDefinitionId]
    actions: frozenset[AccessAction]
    disclosure_count: Annotated[int, Field(ge=0)]
    disclosure_summary: DisclosureSummary
    disclosure_digest: ContentDigest
    periods: frozenset[Period] | None
    allow_period_independent: bool
    allow_delegation: bool

    @model_validator(mode="after")
    def _summary_counts_the_list(self) -> EffectiveScopeSummary:
        _require_summary_of(self.disclosure_summary, self.disclosure_count)
        return self

    @classmethod
    def summarize(cls, scope: AccessScope) -> EffectiveScopeSummary:
        """Count the scope's disclosures by category and keep every other axis as it is."""
        ordered = ordered_disclosures(scope.disclosures)
        return cls(
            operations=scope.operations,
            actions=scope.actions,
            disclosure_count=len(ordered),
            disclosure_summary=summarize_disclosures(ordered),
            disclosure_digest=disclosure_digest(ordered),
            periods=scope.periods,
            allow_period_independent=scope.allow_period_independent,
            allow_delegation=scope.allow_delegation,
        )


class DisclosurePageRequest(BaseModel):
    """Read the effective scope's disclosures from ``offset``.

    A reader that holds one session across its pages pins them with
    ``expected_digest`` and is refused if the list changed. A person's session
    names its own connection as the destination, so a reader that opens a new
    session for each page, as each run of a command does, reads that session's
    list by offset alone: the order is the same, and only the destination
    differs.
    """

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    offset: Annotated[int, Field(ge=0)] = 0
    expected_digest: ContentDigest | None = None


class DisclosurePage(BaseModel):
    """One bounded run of the ordered disclosure list; ``next_offset`` is absent on the last page.

    Every page carries the count and the summary of the whole list it belongs
    to, which are those a status reply of the same list carries.
    """

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    offset: Annotated[int, Field(ge=0)]
    total: Annotated[int, Field(ge=0)]
    disclosure_summary: DisclosureSummary
    disclosure_digest: ContentDigest
    entries: Annotated[tuple[DisclosurePermission, ...], Field(max_length=DISCLOSURE_PAGE_ENTRIES)]
    next_offset: Annotated[int, Field(ge=1)] | None

    @model_validator(mode="after")
    def _validate_range(self) -> DisclosurePage:
        _require_summary_of(self.disclosure_summary, self.total)
        end = self.offset + len(self.entries)
        if end > self.total or (self.total and not self.entries):
            raise ValueError("a disclosure page lies inside its list and is not empty unless the list is")
        if self.next_offset != (end if end < self.total else None):
            raise ValueError("a disclosure page continues exactly where it ends")
        return self


class AuthorityState(StrEnum):
    """Current lifecycle state, separate from time-derived expiry."""

    PENDING = "pending"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    REVOKED = "revoked"


class AutomationGrant(BaseModel):
    """Verified, non-secret grant facts; persistence/sealing belongs to custody."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    grant_id: UUID
    binding: ProfileAccessBinding
    client_id: UUID
    generation: Annotated[int, Field(ge=1)]
    profile_lock_generation: Annotated[int, Field(ge=0)]
    state: AuthorityState
    scope: AccessScope
    valid_from: UtcInstant
    expires_at: UtcInstant
    unattended: bool
    allow_os_lock: bool

    @model_validator(mode="after")
    def _validate_interval(self) -> AutomationGrant:
        if self.expires_at <= self.valid_from:
            raise ValueError("grant validity must be a positive interval")
        if self.allow_os_lock and not self.unattended:
            raise ValueError("OS-lock permission requires unattended enrollment")
        return self


class ApiKeyRecord(BaseModel):
    """Inventory and validity of one key; never its secret or verifier."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    key_id: UUID
    grant_id: UUID
    binding: ProfileAccessBinding
    generation: Annotated[int, Field(ge=1)]
    state: AuthorityState
    valid_from: UtcInstant
    expires_at: UtcInstant
    last_used_at: UtcInstant | None = None

    @model_validator(mode="after")
    def _validate_interval(self) -> ApiKeyRecord:
        if self.expires_at <= self.valid_from:
            raise ValueError("key validity must be a positive interval")
        return self


class SessionKind(StrEnum):
    """Authority origin, independent of the presenting frontend."""

    HUMAN = "human"
    ATTENDED = "attended"
    API_KEY = "api_key"


class SessionState(StrEnum):
    """One session's state; locking it does not revoke the root credential."""

    ACTIVE = "active"
    LOCKED = "locked"
    REVOKED = "revoked"


def _validate_session_origin(session: AccessSession) -> None:
    if (session.kind is SessionKind.API_KEY) != (session.originating_login_id is None):
        raise ValueError("only human and attended sessions bind an originating OS login")
    if session.originating_login_id is not None and not session.originating_login_id:
        raise ValueError("originating OS login identity must be nonempty")


def _validate_session_lifetime(session: AccessSession) -> None:
    lifetime = session.expires_at - session.issued_at
    if lifetime <= timedelta():
        raise ValueError("session validity must be a positive interval")
    if session.kind is not SessionKind.HUMAN and lifetime > ACCESS_LEASE_MAXIMUM:
        raise ValueError("delegated access exceeds the maximum lease")


def _validate_session_credential_pairs(session: AccessSession) -> None:
    if (session.grant_id is None) != (session.grant_generation is None):
        raise ValueError("grant identity and generation must be paired")
    if (session.key_id is None) != (session.key_generation is None):
        raise ValueError("key identity and generation must be paired")


def _validate_session_kind_lineage(session: AccessSession) -> None:
    if session.kind is SessionKind.HUMAN:
        if session.parent_session_id is not None or session.grant_id is not None or session.key_id is not None:
            raise ValueError("human authority cannot descend from automation")
    elif session.grant_id is None and session.kind is not SessionKind.ATTENDED:
        # An attended child of a person's own session is bounded by that session, not by a grant.
        raise ValueError("delegated sessions require an explicit grant")


def _validate_session_kind_credentials(session: AccessSession) -> None:
    if session.kind is SessionKind.API_KEY and session.key_id is None:
        raise ValueError("API sessions require an authenticated key identity")
    if session.kind is SessionKind.ATTENDED and (session.parent_session_id is None or session.key_id is not None):
        raise ValueError("attended sessions require a parent and no root API key")


def _validate_session_parent_identity(session: AccessSession) -> None:
    if session.parent_session_id == session.session_id:
        raise ValueError("a session cannot parent itself")


def _validate_session_lineage(session: AccessSession) -> None:
    _validate_session_kind_lineage(session)
    _validate_session_kind_credentials(session)
    _validate_session_parent_identity(session)


class AccessSession(BaseModel):
    """Owner-issued lease bound to a boot and connection, never a portable bearer.

    Ancestors are supplied afresh at evaluation. Human deadlines come from the
    login lifecycle and are not extended by automation activity. Delegated leases
    carry both a UTC expiry and an owner-measured monotonic lifetime.
    """

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    session_id: UUID
    binding: ProfileAccessBinding
    profile_lock_generation: Annotated[int, Field(ge=0)]
    runtime_boot_id: UUID
    connection_id: UUID
    client_id: UUID
    kind: SessionKind
    originating_login_id: str | None = None
    state: SessionState
    scope: AccessScope
    parent_session_id: UUID | None = None
    grant_id: UUID | None = None
    grant_generation: Annotated[int, Field(ge=1)] | None = None
    key_id: UUID | None = None
    key_generation: Annotated[int, Field(ge=1)] | None = None
    issued_at: UtcInstant
    expires_at: UtcInstant
    issued_monotonic: Annotated[float, Field(ge=0, allow_inf_nan=False)]
    surface: McpSurfaceName | None = None
    """The MCP surface the connection named at login; ``None`` narrows nothing."""

    @model_validator(mode="after")
    def _validate_origin_and_lease(self) -> AccessSession:
        _validate_session_origin(self)
        _validate_session_lifetime(self)
        _validate_session_credential_pairs(self)
        _validate_session_lineage(self)
        return self


class Availability(StrEnum):
    """Independent readiness axis; authentication cannot promote it."""

    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    NEEDS_USER = "needs_user"
    UNSUPPORTED = "unsupported"
    NOT_REQUIRED = "not_required"


class ProfileAccessState(BaseModel):
    """Fresh authoritative profile policy, supplied by the lifecycle owner."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    binding: ProfileAccessBinding
    lock_generation: Annotated[int, Field(ge=0)]
    globally_locked: bool
    automation_enabled: bool
    scope: AccessScope
    storage: Availability
    automation_custody: Availability


class LoginEligibility(StrEnum):
    """Verified unattended dependencies, not the mere existence of a login."""

    ELIGIBLE = "eligible"
    INELIGIBLE = "ineligible"
    UNKNOWN = "unknown"


class OsLockState(StrEnum):
    """Native screen-lock observation of one login.

    ``LOCKED`` is positive evidence that the login was locked. ``UNKNOWN``
    covers observer errors and incomplete transitions. ``NOT_APPLICABLE``
    identifies a verified native non-desktop logon with no screen-lock surface.
    """

    LOCKED = "locked"
    UNLOCKED = "unlocked"
    NOT_APPLICABLE = "not_applicable"
    UNKNOWN = "unknown"


class OsLoginContext(BaseModel):
    """Fresh native observations supplied only by the trusted lifecycle owner.

    Login IDs identify non-reused login incarnations. The owner permanently
    invalidates dependent sessions on logout/attended lock; a later observation
    cannot reactivate them. Manager presence is deliberately absent.
    """

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    login_id: Annotated[str, Field(min_length=1, max_length=256)]
    os_owner_id: Annotated[str, Field(min_length=1, max_length=256)]
    active: bool
    lock_state: OsLockState
    unattended: LoginEligibility
    credential_facilities: Availability

    @property
    def unlocked(self) -> bool:
        """Admit an unlocked desktop or a verified native logon without a lock surface."""
        return self.lock_state in (OsLockState.UNLOCKED, OsLockState.NOT_APPLICABLE)


class AccessEvaluationContext(BaseModel):
    """Trusted connection and clock observations, not fields accepted from agents.

    ``clock_rollback_detected`` remains latched by the lifecycle owner until fresh
    admission. ``private_work_available`` is the suspend/shutdown admission fence.
    Login observations never derive from agent-supplied claims or manager state.
    """

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    now: UtcInstant
    monotonic_now: Annotated[float, Field(ge=0, allow_inf_nan=False)]
    clock_rollback_detected: bool
    runtime_boot_id: UUID
    connection_id: UUID
    authenticated_client_id: UUID
    login_contexts: tuple[OsLoginContext, ...]
    private_work_available: bool

    @model_validator(mode="after")
    def _unique_logins(self) -> AccessEvaluationContext:
        if len({item.login_id for item in self.login_contexts}) != len(self.login_contexts):
            raise ValueError("OS login observations must have unique identities")
        return self


class OperationAccessRequest(BaseModel):
    """Exact target and domain-resolved coordinates of an operation access.

    The owning operation derives the complete period set from its validated
    operands. Frontends cannot assert that period-bearing work is independent.
    Output categories are supplied by current operation policy, not this request.
    """

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    definition_id: OperationDefinitionId
    action: AccessAction
    frontend: OperationFrontendProjection
    periods: frozenset[Period]
    period_independent: bool
    destination_id: UUID

    @model_validator(mode="after")
    def _validate_period_scope(self) -> OperationAccessRequest:
        if self.period_independent == bool(self.periods):
            raise ValueError("provide exact periods or explicitly period-independent work")
        return self


class OperationAccessPolicy(BaseModel):
    """Current owner-supplied restrictions for an existing registered definition.

    This is an input to evaluation, not an alternative registry. Readiness and
    provider checks come from their owning application boundaries on each call.
    """

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    definition_id: OperationDefinitionId
    definition_contract_digest: ContentDigest
    actions: frozenset[AccessAction]
    disclosures: frozenset[DisclosurePermission]
    periods: frozenset[Period] | None
    allow_period_independent: bool
    backend: Availability
    published_authority: Availability
    provider: Availability
    transaction_authority_required: bool
    requires_human: bool = False
    requires_all_periods: bool = False
    """Profile-wide tax discovery additionally requires an unrestricted period ceiling."""


class AccessDenialCode(StrEnum):
    """Safe refusal facts, with no client input or exception text."""

    AUTHENTICATION_REQUIRED = "authentication_required"
    PROFILE_MISMATCH = "profile_mismatch"
    CUSTODY_CHANGED = "custody_changed"
    PROFILE_LOCKED = "profile_locked"
    AUTOMATION_SUSPENDED = "automation_suspended"
    SESSION_INACTIVE = "session_inactive"
    SESSION_EXPIRED = "session_expired"
    CONNECTION_MISMATCH = "connection_mismatch"
    CLIENT_MISMATCH = "client_mismatch"
    RUNTIME_CHANGED = "runtime_changed"
    CLOCK_INVALID = "clock_invalid"
    PARENT_INVALID = "parent_invalid"
    PRIVILEGE_EXPANSION = "privilege_expansion"
    GRANT_INACTIVE = "grant_inactive"
    GRANT_EXPIRED = "grant_expired"
    KEY_INACTIVE = "key_inactive"
    KEY_EXPIRED = "key_expired"
    OS_SESSION_UNAVAILABLE = "os_session_unavailable"
    OS_LOCKED = "os_locked"
    STORAGE_UNAVAILABLE = "storage_unavailable"
    CUSTODY_UNAVAILABLE = "custody_unavailable"
    OPERATION_UNAVAILABLE = "operation_unavailable"
    SUBJECT_BUSY = "subject_busy"
    """An earlier operation of the same definition on the same subject has not settled."""
    FRONTEND_DENIED = "frontend_denied"
    OPERATION_DENIED = "operation_denied"
    DISCLOSURE_DENIED = "disclosure_denied"
    PERIOD_DENIED = "period_denied"
    BACKEND_UNAVAILABLE = "backend_unavailable"
    AUTHORITY_UNAVAILABLE = "authority_unavailable"
    PROVIDER_REQUIRED = "provider_required"
    RESPONSE_AUTHORITY_REQUIRED = "response_authority_required"
    TRANSACTION_AUTHORITY_REQUIRED = "transaction_authority_required"
    HUMAN_AUTHORITY_REQUIRED = "human_authority_required"
    FRESH_PASSWORD_REQUIRED = "fresh_password_required"  # noqa: S105 -- public refusal code.
    ADMINISTRATION_DENIED = "administration_denied"
    PERSON_ACT_REQUIRED = "person_act_required"
    """The act is the person's own in Cadrumo: signing in, sessions, keys, secrets or work outside the profile."""


class AccessDenied(BaseModel):
    """A typed refusal; existing operator actions supply frontend recovery routes."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    outcome: Literal["denied"] = "denied"
    code: AccessDenialCode
    sign_in: SignInRefusal | None = None


class AccessAllowed(BaseModel):
    """Point-in-time policy result, not a credential or an execution capability."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    outcome: Literal["allowed"] = "allowed"
    profile_id: UUID
    session_id: UUID
    expires_at: UtcInstant


type AccessDecision = Annotated[AccessAllowed | AccessDenied, Field(discriminator="outcome")]


class OperationResponseScopeAllowed(BaseModel):
    """Current profile permission only; the response owner still must prove its bearer."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    outcome: Literal["response_scope_allowed"] = "response_scope_allowed"
    profile_id: UUID
    session_id: UUID
    expires_at: UtcInstant


class ProfileAccessStatus(BaseModel):
    """Non-secret independent status axes; never a cached logged-in authority."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    connected: bool
    credential_authenticated: bool
    profile_id: UUID | None
    session_id: UUID | None
    session_expires_at: UtcInstant | None
    grant_state: AuthorityState | None
    grant_expires_at: UtcInstant | None
    grant_valid: bool
    profile_bound: bool
    storage: Availability
    automation_custody: Availability
    published_authority: Availability
    provider: Availability
    effective_scope: EffectiveScopeSummary
    denial: AccessDenialCode | None
    human_resume_refusal: ProfileSessionRefusalReason | None = None
