"""Inventory noun-group application service.

Wraps the rich :mod:`aeat.domain.contribuyente.inventory` substrate (FIFO /
PMP valuation per LIS art. 17.1) with a bucket-scoped persistence
layer and canonical operator verbs:

    aeat app ledger inventory list
    aeat app ledger inventory create
    aeat app ledger inventory movement add
    aeat app ledger inventory valuation preview

Adapts the mutating-noun-group CRUD contract to the inventory domain's
natural sub-noun grammar (actividad + movement + valuation); this
service carries the documented ``LIFECYCLE_OPERATIONS_ONLY`` exception
to the canonical add / remove / update / view / list spine.
"""

from __future__ import annotations

from ._errors import (
    InventoryActividadConflictError,
    InventoryActividadNotFoundError,
    InventoryServiceInputError,
)
from ._service import (
    InventoryActividadSummary,
    InventoryLedgerResult,
    InventoryMovementCommand,
    InventoryService,
    InventoryValuationPreview,
    InventoryValuationPreviewResult,
)

__all__ = [
    "InventoryActividadConflictError",
    "InventoryActividadNotFoundError",
    "InventoryActividadSummary",
    "InventoryLedgerResult",
    "InventoryMovementCommand",
    "InventoryService",
    "InventoryServiceInputError",
    "InventoryValuationPreview",
    "InventoryValuationPreviewResult",
]
