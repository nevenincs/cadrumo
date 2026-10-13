"""The scope of a key the person issues for an agent over MCP.

The person names the key's use and any data categories beyond the profile's
own values, which an agent key always reads and writes back; every other axis
of the grant follows from that use. The grant consents to whole categories
and to every operation an agent may run, not to lists of projections and
operations, so it stays small enough to review and hold many of, and a
projection or operation registered later is covered too.

The categories name no destination here: the runtime mints the requesting
connection's client identity when it prepares the enrollment, the grant is
bound to that identity, and every connection that later presents the key is
admitted as that identity. Binding the categories to the minted destination
therefore releases results to whichever local MCP client presents the key,
and to nothing else.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from ..operations.person_acts import operation_is_persons_act
from ..operations.registry import OperationPublicContractSetV1
from .access_contracts import (
    GRANT_DEFAULT_VALIDITY,
    AccessAction,
    AccessScope,
    DisclosureCategory,
    DisclosureCategoryGrant,
)
from .automation_enrollment import EnrollmentKind, EnrollmentProposal


class AutomationKeyUse(StrEnum):
    """What the person issues a key for."""

    AGENT = "agent"


AGENT_REQUIRED_CATEGORIES: frozenset[DisclosureCategory] = frozenset(
    {DisclosureCategory.PROFILE_VALUES, DisclosureCategory.OPERATION_METADATA}
)
"""Granted to every agent key: an agent operates the profile and observes its own operations."""

AGENT_OPTIONAL_CATEGORIES: tuple[DisclosureCategory, ...] = (DisclosureCategory.TAX_VALUES,)
"""The data categories a person may add to an agent key."""


def registered_disclosure_projections(contracts: OperationPublicContractSetV1) -> frozenset[str]:
    """Return every projection an operation contract may disclose, as the owner's ceiling counts them."""
    return frozenset(
        schema.schema_id
        for contract in contracts.definitions
        for schema in (
            contract.result_schema,
            contract.review_projection_schema,
            contract.workspace_refresh_target_schema,
        )
        if schema is not None
    )


def agent_operations(contracts: OperationPublicContractSetV1) -> frozenset[str]:
    """Return every registered operation an agent may run: all but the person's own acts."""
    return frozenset(
        contract.definition_id
        for contract in contracts.definitions
        if not operation_is_persons_act(
            contract.definition_id, ephemeral_secret_required=contract.ephemeral_secret_required
        )
    )


@dataclass(frozen=True, slots=True)
class AgentKeyScope:
    """The destination-free scope of an agent key, ready to bind to the minted destination."""

    actions: frozenset[AccessAction]
    categories: frozenset[DisclosureCategory]

    def bind(self, destination_id: UUID) -> AccessScope:
        """Grant every agent operation, and each category to the runtime-minted destination."""
        return AccessScope(
            operations=frozenset(),
            actions=self.actions,
            disclosures=frozenset(),
            periods=None,
            allow_period_independent=True,
            allow_delegation=False,
            disclosure_categories=frozenset(
                DisclosureCategoryGrant(destination_id=destination_id, category=category)
                for category in self.categories
            ),
            all_agent_operations=True,
        )


def agent_key_scope(categories: Iterable[DisclosureCategory] = ()) -> AgentKeyScope:
    """Scope a key for an agent to every agent operation, its profile values and the added categories.

    The agent works at parity inside the profile, so it may run every operation
    an agent may run, with every action. A category outside
    ``AGENT_OPTIONAL_CATEGORIES`` and the always-granted ones is refused.
    """
    added = frozenset(categories) - AGENT_REQUIRED_CATEGORIES
    if not added <= frozenset(AGENT_OPTIONAL_CATEGORIES):
        raise ValueError("an agent key adds only its optional data categories")
    return AgentKeyScope(
        actions=frozenset(AccessAction),
        categories=AGENT_REQUIRED_CATEGORIES | added,
    )


def agent_key_proposal(scope: AgentKeyScope, *, destination_id: UUID, now: datetime) -> EnrollmentProposal:
    """Propose the first enrollment of an agent key, bound to the minted destination.

    API-key admission needs an unattended grant, which the person approves on
    the protected channel; it never continues while the OS is locked. The grant
    and its key run for the default validity.
    """
    expires_at = now + GRANT_DEFAULT_VALIDITY
    return EnrollmentProposal(
        kind=EnrollmentKind.ENROLL,
        scope=scope.bind(destination_id),
        expires_at=expires_at,
        key_expires_at=expires_at,
        unattended=True,
        allow_os_lock=False,
    )


__all__ = [
    "AGENT_OPTIONAL_CATEGORIES",
    "AGENT_REQUIRED_CATEGORIES",
    "AgentKeyScope",
    "AutomationKeyUse",
    "agent_key_proposal",
    "agent_key_scope",
    "agent_operations",
    "registered_disclosure_projections",
]
