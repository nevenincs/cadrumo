"""Readiness facts for the inventory calculation source.

The strict-frozen record and context-independent readiness check distinguishes
the completed encrypted schema-v3 inventory persistence boundary from the still
missing calculation-source connection. It does not resolve calculation values,
adapt or enroll a source, participate in the source mesh, or emit diagnostics.
Its source identity is the canonical
:attr:`~core.BindingSourceKind.INVENTORY` member.

See Also:
    :class:`~application.inventory.InventoryService`
        Application service for encrypted schema-v3 inventory state that is not
        yet enrolled as canonical calculation-source state.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from ...core import STRICT_FROZEN_CONFIG, BindingSourceKind


class InventorySourceReadiness(BaseModel):
    """Whether inventory is ready to act as a calculation source."""

    model_config = STRICT_FROZEN_CONFIG

    ready: bool
    source_kind: BindingSourceKind
    reason: str = Field(min_length=1, max_length=512)


def inventory_source_readiness() -> InventorySourceReadiness:
    """Return the context-independent inventory-source readiness fact.

    Encrypted schema-v3 persistence is complete for movements, valuation inputs,
    complete acquisition cost, and closing authority. Readiness remains false
    until the inventory resolver, source-mesh enrollment, registry bindings,
    orchestration, and ownership refusal path are connected.

    Returns:
        An :class:`~application.inventory.InventorySourceReadiness` with
        ``ready = False`` plus the raw source token and reason.
    """
    return InventorySourceReadiness(
        ready=False,
        source_kind=BindingSourceKind.INVENTORY,
        reason=(
            "inventory encrypted schema-v3 persistence is complete for movements, valuation inputs, "
            "complete acquisition cost, and closing authority; calculation-source readiness remains false "
            "until the canonical inventory resolver, source-mesh enrollment, registry bindings, "
            "calculation orchestration, and source-ownership refusal path are connected"
        ),
    )


__all__ = [
    "InventorySourceReadiness",
    "inventory_source_readiness",
]
