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
    """
    return (
        child.operations <= parent.operations
        and child.actions <= parent.actions
        and all(parent.discloses(item) for item in child.disclosures)
        and child.disclosure_categories <= parent.disclosure_categories
        and (parent.periods is None or (child.periods is not None and child.periods <= parent.periods))
        and (not child.allow_period_independent or parent.allow_period_independent)
        and (not child.allow_delegation or parent.allow_delegation)
    )


def intersect_scopes(scopes: tuple[AccessScope, ...]) -> AccessScope:
    """Intersect explicit permissions; an empty authority chain grants nothing.

    A listed disclosure survives when every scope lists it or grants its
    category. Category grants survive only where every scope grants them, so
    intersecting with a resolved, listed scope leaves only listed disclosures.
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
    operations, actions, periods = first.operations, first.actions, first.periods
    categories = first.disclosure_categories
    for scope in rest:
        operations &= scope.operations
        actions &= scope.actions
        categories &= scope.disclosure_categories
        if scope.periods is not None:
            periods = scope.periods if periods is None else periods & scope.periods
    listed = frozenset(item for scope in scopes for item in scope.disclosures)
    return AccessScope(
        operations=operations,
        actions=actions,
        disclosures=frozenset(item for item in listed if all(scope.discloses(item) for scope in scopes)),
        periods=periods,
        allow_period_independent=all(scope.allow_period_independent for scope in scopes),
        allow_delegation=all(scope.allow_delegation for scope in scopes),
        disclosure_categories=categories,
    )
