"""A key for an agent grants whole data categories, bound to the runtime-minted destination."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from cadrumo.application.operations.registry import OperationPublicContractSetV1
from cadrumo.application.user_profile.access_contracts import (
    GRANT_DEFAULT_VALIDITY,
    AccessAction,
    AccessScope,
    DisclosureCategory,
    DisclosureCategoryGrant,
    DisclosurePermission,
)
from cadrumo.application.user_profile.access_policy import intersect_scopes, scope_is_subset
from cadrumo.application.user_profile.automation_agent_key import (
    agent_key_proposal,
    agent_key_scope,
    agent_operations,
)
from cadrumo.application.user_profile.automation_enrollment import EnrollmentKind
from cadrumo.application.user_profile.operations import (
    build_user_profile_operation_definitions,
    build_user_profile_operation_registrations,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_VIEW = "user-profile.view"


@pytest.fixture(scope="module")
def contracts() -> OperationPublicContractSetV1:
    """The real profile operation contracts, without unrelated live families."""
    definitions = build_user_profile_operation_definitions()
    return OperationPublicContractSetV1.build(
        tuple(item.contract for item in build_user_profile_operation_registrations(definitions))
    )


def _scope(
    *, disclosures: frozenset[DisclosurePermission] = frozenset(), categories: frozenset[DisclosureCategoryGrant]
) -> AccessScope:
    return AccessScope(
        operations=frozenset({_VIEW}),
        actions=frozenset({AccessAction.RESULT}),
        disclosures=disclosures,
        periods=None,
        allow_period_independent=True,
        allow_delegation=False,
        disclosure_categories=categories,
    )


def test_an_agent_key_always_reads_profile_values_and_observes_its_operations() -> None:
    scope = agent_key_scope()

    assert scope.categories == {DisclosureCategory.PROFILE_VALUES, DisclosureCategory.OPERATION_METADATA}
    assert scope.actions == frozenset(AccessAction)
    assert DisclosureCategory.TAX_VALUES in agent_key_scope((DisclosureCategory.TAX_VALUES,)).categories


def test_naming_the_always_granted_categories_changes_nothing() -> None:
    assert agent_key_scope((DisclosureCategory.PROFILE_VALUES,)) == agent_key_scope()


def test_an_agent_may_run_every_registered_operation_but_the_persons_own_acts(
    contracts: OperationPublicContractSetV1,
) -> None:
    runnable = agent_operations(contracts)

    assert _VIEW in runnable
    assert "user-profile.patch" in runnable
    assert "user-profile.automation-approve" not in runnable
    assert "user-profile.automation-inventory" not in runnable
    assert not any(
        str(item.definition_id) in runnable for item in contracts.definitions if item.ephemeral_secret_required
    )


def test_the_proposal_grants_every_agent_operation_and_each_category_to_the_minted_destination() -> None:
    scope = agent_key_scope((DisclosureCategory.TAX_VALUES,))
    destination = uuid4()
    issued = datetime(2026, 10, 12, 9, 30, tzinfo=UTC)

    proposal = agent_key_proposal(scope, destination_id=destination, now=issued)

    assert proposal.kind is EnrollmentKind.ENROLL
    assert proposal.target_grant_id is None and proposal.target_key_id is None
    assert proposal.scope.operations == frozenset()
    assert proposal.scope.all_agent_operations is True
    assert proposal.scope.disclosures == frozenset()
    assert proposal.scope.disclosure_categories == {
        DisclosureCategoryGrant(destination_id=destination, category=category) for category in scope.categories
    }
    assert proposal.scope.periods is None
    assert proposal.scope.allow_period_independent is True
    assert proposal.scope.allow_delegation is False
    # A key is admitted with nobody signed in only on an unattended grant; it never runs while the OS is locked.
    assert proposal.unattended is True
    assert proposal.allow_os_lock is False
    assert proposal.expires_at == issued + GRANT_DEFAULT_VALIDITY
    assert proposal.key_expires_at == proposal.expires_at
    # The stored consent stays a few hundred bytes however many operations and projections are registered.
    assert len(proposal.model_dump_json()) < 1024


def test_an_operation_grant_covers_listed_operations_and_narrows_only_under_another() -> None:
    granted = _scope(categories=frozenset()).model_copy(
        update={"operations": frozenset(), "all_agent_operations": True}
    )
    listed = _scope(categories=frozenset())

    assert granted.permits(_VIEW) and granted.permits("anything.registered-later")
    assert scope_is_subset(listed, granted)
    assert not scope_is_subset(granted, listed)
    assert scope_is_subset(granted, granted)
    lease = intersect_scopes((granted, listed))
    assert lease.operations == {_VIEW}
    assert lease.all_agent_operations is False


def test_a_category_grant_covers_listed_permissions_of_its_category_and_destination_only() -> None:
    destination, other = uuid4(), uuid4()
    granted = _scope(
        categories=frozenset(
            {DisclosureCategoryGrant(destination_id=destination, category=DisclosureCategory.PROFILE_VALUES)}
        )
    )
    inside = DisclosurePermission(
        destination_id=destination, projection_id="user-profile.view.result", category=DisclosureCategory.PROFILE_VALUES
    )
    tax = inside.model_copy(update={"category": DisclosureCategory.TAX_VALUES})
    elsewhere = inside.model_copy(update={"destination_id": other})

    assert granted.discloses(inside)
    assert not granted.discloses(tax)
    assert not granted.discloses(elsewhere)
    assert scope_is_subset(_scope(disclosures=frozenset({inside}), categories=frozenset()), granted)
    assert not scope_is_subset(_scope(disclosures=frozenset({tax}), categories=frozenset()), granted)
    # No list proves a category whole, so a category grant never narrows a listed scope.
    assert not scope_is_subset(granted, _scope(disclosures=frozenset({inside}), categories=frozenset()))


def test_intersecting_a_category_grant_with_a_resolved_list_leaves_only_covered_listed_permissions() -> None:
    destination = uuid4()
    grant = DisclosureCategoryGrant(destination_id=destination, category=DisclosureCategory.PROFILE_VALUES)
    inside = DisclosurePermission(
        destination_id=destination, projection_id="user-profile.view.result", category=DisclosureCategory.PROFILE_VALUES
    )
    tax = inside.model_copy(update={"category": DisclosureCategory.TAX_VALUES})

    lease = intersect_scopes(
        (_scope(categories=frozenset({grant})), _scope(disclosures=frozenset({inside, tax}), categories=frozenset()))
    )

    assert lease.disclosures == {inside}
    assert lease.disclosure_categories == frozenset()
