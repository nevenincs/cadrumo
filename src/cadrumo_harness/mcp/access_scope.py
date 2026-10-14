"""Turn protocol surface policy into an explicit generic operation ceiling."""

from cadrumo.application.user_profile.access_contracts import AccessAction, AccessScope

from .surface_facts import OPERATION_SURFACE_FACTS
from .surfaces import McpSurface


def surface_scope(surface: McpSurface) -> AccessScope:
    """Return the surface's finite operation list and effect constraints."""
    return AccessScope(
        operations=frozenset(
            facts.definition_id for facts in OPERATION_SURFACE_FACTS if surface.admits(facts.definition_id)
        ),
        actions=frozenset(AccessAction) if surface.changes_records else frozenset(AccessAction) - {AccessAction.COMMIT},
        disclosures=frozenset(),
        periods=None,
        allow_period_independent=True,
        allow_delegation=False,
        allow_changes_records=surface.changes_records,
        allow_network=surface.reaches_network,
    )
