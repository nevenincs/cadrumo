"""Readiness facts for the inventory calculation source.

The strict-frozen record and context-independent readiness check distinguishes
the connected encrypted schema-v3 inventory source from the still-incomplete
filing row projection. It does not resolve calculation values, render filing
rows, or emit diagnostics. Its source identity is the canonical
:attr:`~core.BindingSourceKind.INVENTORY` member.

See Also:
    :class:`~application.inventory.InventoryService`
        Application service for encrypted schema-v3 inventory state consumed by
        the canonical calculation-source resolver.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from ...core.models import STRICT_FROZEN_CONFIG
from ...core.aggregation import BindingSourceKind


class InventorySourceReadiness(BaseModel):
    """Whether inventory is ready to act as a calculation source."""

    model_config = STRICT_FROZEN_CONFIG

    ready: bool
    source_kind: BindingSourceKind
    reason: str = Field(min_length=1, max_length=512)


def inventory_source_readiness() -> InventorySourceReadiness:
    """Return the context-independent inventory-source readiness fact.

    Encrypted schema-v3 persistence, the canonical resolver, source-mesh
    enrollment, registry row bindings, calculation orchestration, source
    identity, and caller-override refusal are present. Readiness remains false
    until the row bindings are materialized into grounded repeated M100 activity
    casillas and filing-grade rendering and verification are proven end to end.

    Returns:
        An :class:`~application.inventory.InventorySourceReadiness` with
        ``ready = False`` plus the raw source token and reason.
    """
    return InventorySourceReadiness(
        ready=False,
        source_kind=BindingSourceKind.INVENTORY,
        reason=(
            "inventory encrypted schema-v3 persistence, canonical resolution, source-mesh enrollment, "
            "registry row bindings, calculation orchestration, source identity, and caller-override refusal "
            "are connected; filing readiness remains false until grounded repeated M100 activity-row casillas "
            "are materialized, rendered, and verified end to end"
        ),
    )


__all__ = [
    "InventorySourceReadiness",
    "inventory_source_readiness",
]
