"""Inventory noun-group application service.

Wraps the rich :mod:`domain.contribuyente.inventory` substrate (FIFO /
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

Persistence is owned by :class:`InventoryService`, which stores the
:class:`domain.contribuyente.inventory.InventoryLedgerDocument`
through
:class:`adapters.persistence.profile.inventory.InventoryLedgerRepository`
and emits bucket-scoped inventory events for audit-significant verbs. Movement
commands are converted into
:class:`domain.contribuyente.inventory.MovementRecord` rows, while
valuation previews delegate FIFO/PMP math to
:func:`domain.contribuyente.inventory.compute_inventory_valuation`.

See Also:
    :class:`InventoryService`
        Application service that owns persistence, command validation, and
        bucket-event emission.
    :class:`InventoryLedgerResult`
        Return contract for ledger create, show, movement, and remove verbs.
    :class:`InventoryMovementCommand`
        Application command projected into a domain movement row.
    :class:`InventoryValuationPreviewResult`
        Result contract for report-only valuation previews.
    :class:`domain.contribuyente.inventory.InventoryLedger`
        Canonical domain ledger valued by the inventory substrate.
"""

from __future__ import annotations

from ._service import (
    InventoryActividadSummary,
    InventoryLedgerResult,
    InventoryMovementCommand,
    InventoryService,
    InventoryValuationPreview,
    InventoryValuationPreviewResult,
    inventory_ledger_repository_for_bucket,
)
from ._source_readiness import (
    InventorySourceReadiness,
    inventory_source_readiness,
)
from .errors import (
    InventoryActividadConflictError,
    InventoryActividadNotFoundError,
    InventoryServiceInputError,
)

__all__ = [
    "InventoryActividadConflictError",
    "InventoryActividadNotFoundError",
    "InventoryActividadSummary",
    "InventoryLedgerResult",
    "InventoryMovementCommand",
    "InventoryService",
    "InventoryServiceInputError",
    "InventorySourceReadiness",
    "InventoryValuationPreview",
    "InventoryValuationPreviewResult",
    "inventory_ledger_repository_for_bucket",
    "inventory_source_readiness",
]
