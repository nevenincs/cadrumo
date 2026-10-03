"""Shared set algebra for profile and session access scopes."""

from __future__ import annotations

from .access_contracts import (
    AccessScope,
)


def scope_is_subset(child: AccessScope, parent: AccessScope) -> bool:
    """Prove narrowing in every dimension, including disclosure destinations."""
    return (
        child.operations <= parent.operations
        and child.actions <= parent.actions
        and child.disclosures <= parent.disclosures
        and (parent.periods is None or (child.periods is not None and child.periods <= parent.periods))
        and (not child.allow_period_independent or parent.allow_period_independent)
        and (not child.allow_delegation or parent.allow_delegation)
    )


def intersect_scopes(scopes: tuple[AccessScope, ...]) -> AccessScope:
    """Intersect explicit permissions; an empty authority chain grants nothing."""
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
    operations, actions, disclosures, periods = first.operations, first.actions, first.disclosures, first.periods
    for scope in rest:
        operations &= scope.operations
        actions &= scope.actions
        disclosures &= scope.disclosures
        if scope.periods is not None:
            periods = scope.periods if periods is None else periods & scope.periods
    return AccessScope(
        operations=operations,
        actions=actions,
        disclosures=disclosures,
        periods=periods,
        allow_period_independent=all(scope.allow_period_independent for scope in scopes),
        allow_delegation=all(scope.allow_delegation for scope in scopes),
    )
