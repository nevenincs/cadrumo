"""Shared set algebra for profile and session access scopes.

Membership runs on the scopes' own sets, which keep each item's hash, so the
work grows with what one scope lists beyond another and never with every pair
of a listed item and a scope.
"""

from __future__ import annotations

from cadrumo_client.contracts.access_vocabulary import AccessScope, DisclosurePermission

from ..operations.models import OperationDefinitionId


def scope_is_subset(child: AccessScope, parent: AccessScope) -> bool:
    """Prove narrowing in every dimension, including disclosure destinations.

    A listed disclosure narrows a parent that lists it or grants its whole
    category; a category grant narrows only a parent that grants the same
    category to the same destination, since no list proves a category whole.
    Operations follow the same rule: a listed operation narrows a parent that
    lists it, and that grant narrows only a
    parent that grants it too.
    """
    return (
        child.operations <= parent.operations
        and child.actions <= parent.actions
        and all(_category_covers(parent, item) for item in child.disclosures - parent.disclosures)
        and child.disclosure_categories <= parent.disclosure_categories
        and (parent.periods is None or (child.periods is not None and child.periods <= parent.periods))
        and (not child.allow_period_independent or parent.allow_period_independent)
        and (not child.allow_delegation or parent.allow_delegation)
        and (not child.allow_changes_records or parent.allow_changes_records)
        and (not child.allow_network or parent.allow_network)
    )


def intersect_scopes(scopes: tuple[AccessScope, ...]) -> AccessScope:
    """Intersect explicit permissions; an empty authority chain grants nothing.

    A listed disclosure survives when every scope lists it or grants its
    category, and a listed operation when every scope lists it or grants every
    permitted operation. Category and operation grants survive only where every
    scope grants them, so intersecting with a resolved, listed scope leaves
    only listed permissions.
    """
    if not scopes:
        return _no_authority()
    first, *rest = scopes
    return _intersect(
        scopes,
        operations=first.operations.intersection(*(scope.operations for scope in rest)),
        listed=frozenset[DisclosurePermission]().union(*(scope.disclosures for scope in scopes)),
    )


def intersect_scopes_within(
    scopes: tuple[AccessScope, ...],
    *,
    operations: frozenset[OperationDefinitionId],
    disclosures: frozenset[DisclosurePermission],
) -> AccessScope:
    """Intersect as ``intersect_scopes`` does, keeping only the named operations and disclosures.

    Every other axis is the whole intersection, and a named operation or
    disclosure survives exactly when it survives the whole intersection. One
    access names its operation and the disclosures its policy needs, so a
    refusal read from this scope is the one the whole intersection gives, while
    the work grows with what the access names and not with what the scopes list.
    """
    if not scopes:
        return _no_authority()
    return _intersect(
        scopes,
        operations=operations.intersection(*(scope.operations for scope in scopes)),
        listed=frozenset[DisclosurePermission]().union(*(disclosures & scope.disclosures for scope in scopes)),
    )


def _no_authority() -> AccessScope:
    return AccessScope(
        operations=frozenset(),
        actions=frozenset(),
        disclosures=frozenset(),
        periods=frozenset(),
        allow_period_independent=False,
        allow_delegation=False,
    )


def _intersect(
    scopes: tuple[AccessScope, ...],
    *,
    operations: frozenset[OperationDefinitionId],
    listed: frozenset[DisclosurePermission],
) -> AccessScope:
    """Keep each listed disclosure every scope lists or covers by category, with every other axis whole."""
    first, *rest = scopes
    actions, periods = first.actions, first.periods
    categories = first.disclosure_categories
    for scope in rest:
        actions &= scope.actions
        categories &= scope.disclosure_categories
        if scope.periods is not None:
            periods = scope.periods if periods is None else periods & scope.periods
    disclosures = listed
    for scope in scopes:
        # A refused item leaves the set, so each listed item is refused at most once.
        refused = frozenset(item for item in disclosures - scope.disclosures if not _category_covers(scope, item))
        if refused:
            disclosures -= refused
    return AccessScope(
        operations=operations,
        actions=actions,
        disclosures=disclosures,
        periods=periods,
        allow_period_independent=all(scope.allow_period_independent for scope in scopes),
        allow_delegation=all(scope.allow_delegation for scope in scopes),
        disclosure_categories=categories,
        allow_changes_records=all(scope.allow_changes_records for scope in scopes),
        allow_network=all(scope.allow_network for scope in scopes),
    )


def _category_covers(scope: AccessScope, permission: DisclosurePermission) -> bool:
    """Whether one of the scope's category grants consents to a permission it does not list."""
    return any(grant.covers(permission) for grant in scope.disclosure_categories)
