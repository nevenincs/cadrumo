"""Inventory noun-group application service per apex ADR §4.2.

Wraps the rich :mod:`aeat.domain.profile.inventory` substrate (FIFO/PMP
valuation per LIS art. 17.1) with a bucket-scoped persistence layer and
canonical operator verbs:

    aeat app ledger inventory list
    aeat app ledger inventory create
    aeat app ledger inventory movement add
    aeat app ledger inventory valuation preview
    aeat app ledger inventory show
    aeat app ledger inventory remove

The verb shape adapts the W71 contract to the inventory domain's natural
sub-noun grammar (actividad + movement + valuation), with a documented
``LIFECYCLE_OPERATIONS_ONLY`` exception in the W76 mounting wave.
"""

from __future__ import annotations

from ._errors import (
    InventoryActividadConflictError,
    InventoryActividadNotFoundError,
    InventoryServiceInputError,
)
from ._service import (
    InventoryActividadSummary,
    InventoryMovementCommand,
    InventoryService,
    InventoryValuationPreview,
)

__all__ = [
    "InventoryActividadConflictError",
    "InventoryActividadNotFoundError",
    "InventoryActividadSummary",
    "InventoryMovementCommand",
    "InventoryService",
    "InventoryServiceInputError",
    "InventoryValuationPreview",
]
