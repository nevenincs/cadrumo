"""Shared set algebra for profile and session access scopes."""

from __future__ import annotations

from .access_contracts import (
    AccessScope,
)


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
        all(parent.permits(item) for item in child.operations)
        and child.actions <= parent.actions
        and all(parent.discloses(item) for item in child.disclosures)
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
        return AccessScope(
            operations=frozenset(),
            actions=frozenset(),
            disclosures=frozenset(),
            periods=frozenset(),
            allow_period_independent=False,
            allow_delegation=False,
        )
    first, *rest = scopes
    actions, periods = first.actions, first.periods
    categories = first.disclosure_categories
    for scope in rest:
        actions &= scope.actions
        categories &= scope.disclosure_categories
        if scope.periods is not None:
            periods = scope.periods if periods is None else periods & scope.periods
    listed = frozenset(item for scope in scopes for item in scope.disclosures)
    named = frozenset(item for scope in scopes for item in scope.operations)
    return AccessScope(
        operations=frozenset(item for item in named if all(scope.permits(item) for scope in scopes)),
        actions=actions,
        disclosures=frozenset(item for item in listed if all(scope.discloses(item) for scope in scopes)),
        periods=periods,
        allow_period_independent=all(scope.allow_period_independent for scope in scopes),
        allow_delegation=all(scope.allow_delegation for scope in scopes),
        disclosure_categories=categories,
        allow_changes_records=all(scope.allow_changes_records for scope in scopes),
        allow_network=all(scope.allow_network for scope in scopes),
    )
