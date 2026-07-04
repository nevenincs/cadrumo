"""Inventory calculation-source readiness.

Declares whether inventory may act as a calculation source that feeds registry
bindings. Inventory is currently an application service (:class:`InventoryService`)
over the profile inventory; its movements and valuations are not yet persisted
through the canonical secure-storage revision boundary, so enrolling inventory as a
live calculation source would resolve bindings against non-canonical state. Until
that persistence is hardened, inventory readiness is NOT ready and the aggregation
resolver must refuse visibly (a blocked-readiness diagnostic) rather than resolve a
silent blank.

The readiness is a pure, context-independent fact: inventory is unready regardless
of the modelo or period being calculated.
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
    """Return the current inventory calculation-source readiness.

    Inventory is not yet a calculation source: its movements and valuations are
    served by an application service over profile inventory and are not persisted
    through the canonical secure-storage revision boundary, so a resolver enrolled
    today would read non-canonical state. The surface is provisioned but blocked
    until inventory persistence is hardened.

    Returns:
        An :class:`InventorySourceReadiness` with ``ready = False`` and the blocking
        reason, until inventory persistence is canonical.
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
