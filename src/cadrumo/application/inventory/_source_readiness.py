"""Readiness facts for the inventory calculation source.

The strict-frozen record and context-independent readiness check describe only
whether inventory state crosses the canonical secure-storage revision boundary.
They do not resolve calculation values, adapt or enroll a source, participate
in the source mesh, or emit diagnostics. The raw ``inventory`` source token is
not a :class:`~core.BindingSourceKind` member.

See Also:
    :class:`~application.inventory.InventoryService`
        Application service for the inventory state whose persistence is not
        yet canonical calculation-source state.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from ...core import STRICT_FROZEN_CONFIG

INVENTORY_SOURCE_KIND = "inventory"


class InventorySourceReadiness(BaseModel):
    """Whether inventory is ready to act as a calculation source."""

    model_config = STRICT_FROZEN_CONFIG

    ready: bool
    source_kind: str = Field(min_length=1, max_length=64)
    reason: str = Field(min_length=1, max_length=512)


def inventory_source_readiness() -> InventorySourceReadiness:
    """Return the context-independent inventory-source readiness fact.

    The result remains not ready because inventory movements and valuations are
    not persisted through the canonical secure-storage revision boundary.

    Returns:
        An :class:`~application.inventory.InventorySourceReadiness` with
        ``ready = False`` plus the raw source token and reason.
    """
    return InventorySourceReadiness(
        ready=False,
        source_kind=INVENTORY_SOURCE_KIND,
        reason=(
            "inventory is not yet a calculation source: its movements and "
            "valuations are not persisted through the canonical secure-storage "
            "revision boundary"
        ),
    )


__all__ = [
    "INVENTORY_SOURCE_KIND",
    "InventorySourceReadiness",
    "inventory_source_readiness",
]
