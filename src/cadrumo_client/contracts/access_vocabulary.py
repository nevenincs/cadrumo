"""The access vocabulary operations declare and the runtime evaluates: actions, disclosures, scopes, policies.

The product declares what each operation needs in these terms, and the runtime
evaluates sessions against them. Neither side owns them as authority: a scope
or policy is a statement of what may happen, never a credential.
"""

from __future__ import annotations

from collections import Counter
from enum import StrEnum
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from cadrumo.application.operations.models import OperationDefinitionId
from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.operations.schema_identity import OperationPublicSchemaId
from cadrumo.core.hashing import canonical_json_bytes, sha256_hex
from cadrumo.core.identity.digest import ContentDigest
from cadrumo.core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from cadrumo.core.period import Period


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
    allow_changes_records: bool = True
    allow_network: bool = True

    def permits(self, operation: str) -> bool:
        """Whether this exact operation is explicitly permitted."""
        return operation in self.operations

    def discloses(self, permission: DisclosurePermission) -> bool:
        """Whether this scope consents to one explicit permission, listed or by its category."""
        return permission in self.disclosures or any(item.covers(permission) for item in self.disclosure_categories)


DISCLOSURE_PAGE_ENTRIES = 100
"""The most disclosure entries one page read releases; a frame holds them with room to spare."""


def ordered_disclosures(disclosures: frozenset[DisclosurePermission]) -> tuple[DisclosurePermission, ...]:
    """Order a scope's disclosures as every summary digest and page read sees them, by category first."""
    return tuple(
        sorted(disclosures, key=lambda item: (item.category.value, item.projection_id, str(item.destination_id)))
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


class Availability(StrEnum):
    """Independent readiness axis; authentication cannot promote it."""

    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    NEEDS_USER = "needs_user"
    UNSUPPORTED = "unsupported"
    NOT_REQUIRED = "not_required"


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
