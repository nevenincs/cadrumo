"""Derive current registered access ceilings for profile sessions."""

from __future__ import annotations

from uuid import UUID

from cadrumo.application.operations.disclosure_projections import registered_disclosure_projections
from cadrumo.application.operations.frontend_requests import OPERATION_OBSERVATION_PROJECTION_ID
from cadrumo.application.operations.registry import OperationPublicContractSetV1
from cadrumo.application.user_profile.access_contracts import AutomationGrant
from cadrumo.application.user_profile.automation_custody_port import AutomationCustodySnapshot
from cadrumo_client.contracts.access_vocabulary import (
    AccessAction,
    AccessScope,
    DisclosureCategory,
    DisclosureCategoryGrant,
    DisclosurePermission,
)


def _delegated_permissions(
    grants: tuple[AutomationGrant, ...], projections: frozenset[str]
) -> frozenset[DisclosurePermission]:
    permissions = frozenset(permission for grant in grants for permission in grant.scope.disclosures) | frozenset(
        DisclosurePermission(destination_id=item.destination_id, projection_id=projection, category=item.category)
        for grant in grants
        for item in grant.scope.disclosure_categories
        for projection in projections
    )
    return permissions


def delegated_profile_scope(
    contracts: OperationPublicContractSetV1, snapshot: AutomationCustodySnapshot, client_id: UUID
) -> AccessScope:
    """Intersect live delegated grants with currently registered operations."""
    registered = frozenset(str(item.definition_id) for item in contracts.definitions)
    grants = tuple(grant for grant in snapshot.grants if grant.client_id == client_id)
    projections = registered_disclosure_projections(contracts) | {OPERATION_OBSERVATION_PROJECTION_ID}
    permissions = _delegated_permissions(grants, projections)
    operations = registered & frozenset(item for grant in grants for item in grant.scope.operations)
    return _scope(operations, permissions, frozenset())


def person_profile_scope(contracts: OperationPublicContractSetV1, client_id: UUID) -> AccessScope:
    """Build the current person-owner ceiling for a connection."""
    registered = frozenset(str(item.definition_id) for item in contracts.definitions)
    permissions = frozenset(
        DisclosurePermission(destination_id=client_id, projection_id=projection, category=category)
        for projection in registered_disclosure_projections(contracts)
        for category in DisclosureCategory
    )
    categories = frozenset(
        DisclosureCategoryGrant(destination_id=client_id, category=category) for category in DisclosureCategory
    )
    permissions |= frozenset(
        (
            DisclosurePermission(
                destination_id=client_id,
                projection_id=OPERATION_OBSERVATION_PROJECTION_ID,
                category=DisclosureCategory.OPERATION_METADATA,
            ),
        )
    )
    return _scope(registered, permissions, categories)


def _scope(
    operations: frozenset[str],
    permissions: frozenset[DisclosurePermission],
    categories: frozenset[DisclosureCategoryGrant],
) -> AccessScope:
    return AccessScope(
        operations=operations,
        actions=frozenset(AccessAction),
        disclosures=permissions,
        periods=None,
        allow_period_independent=True,
        allow_delegation=True,
        disclosure_categories=categories,
    )
