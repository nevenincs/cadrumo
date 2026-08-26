"""Operator-facing read and reclaim operations over the declared storage tree.

The public facade for the ``aeat config storage`` surface. Operators inspect
four stable areas while the internal taxonomy remains free to evolve. This
package exposes inspection, materialisation, and lifecycle-guarded reclaim, and
deliberately exposes no relocation.

See Also:
    :data:`~cadrumo.core.STORAGE_TAXONOMY`
        The declaration every operation here reads.
"""

from __future__ import annotations

from ._models import (
    StorageAreaDisposition,
    StorageAreaInventoryReport,
    StorageAreaInventoryRow,
    StorageCheckIssueKind,
    StorageInitReport,
    StorageOccupancy,
    StorageReclaimReport,
    StorageTreeCheckReport,
    StorageTreeIssue,
    StorageTreeIssueKind,
)
from ._service import (
    RECLAIMABLE_LIFECYCLES,
    collect_storage_area_inventory,
    inspect_storage_tree,
    materialise_storage_tree,
    reclaim_storage_area,
    storage_lifecycle_permits_reclaim,
)
from .errors import (
    StorageManagementError,
    StorageReclaimRefusedError,
    StorageReclaimUnconfirmedError,
)

__all__ = [
    "RECLAIMABLE_LIFECYCLES",
    "StorageAreaDisposition",
    "StorageAreaInventoryReport",
    "StorageAreaInventoryRow",
    "StorageCheckIssueKind",
    "StorageInitReport",
    "StorageManagementError",
    "StorageOccupancy",
    "StorageReclaimRefusedError",
    "StorageReclaimReport",
    "StorageReclaimUnconfirmedError",
    "StorageTreeCheckReport",
    "StorageTreeIssue",
    "StorageTreeIssueKind",
    "collect_storage_area_inventory",
    "inspect_storage_tree",
    "materialise_storage_tree",
    "reclaim_storage_area",
    "storage_lifecycle_permits_reclaim",
]
