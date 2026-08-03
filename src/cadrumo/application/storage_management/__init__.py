"""Operator-facing read and reclaim operations over the declared storage tree.

The public facade for the ``aeat config storage`` surface. An operator cannot
create or destroy a storage category — the member set is fixed by
:data:`~cadrumo.core.STORAGE_TAXONOMY` — so this package exposes inspection,
materialisation, and a lifecycle-guarded reclaim, and deliberately exposes no
relocation. Reporting where the tree is costs nothing and is reversible; moving
encrypted records away from the key material that opens them is neither.

See Also:
    :data:`~cadrumo.core.STORAGE_TAXONOMY`
        The declaration every operation here reads.
"""

from __future__ import annotations

from ._errors import (
    StorageManagementError,
    StorageReclaimRefusedError,
    StorageReclaimUnconfirmedError,
)
from ._models import (
    StorageInitReport,
    StorageInventoryReport,
    StorageInventoryRow,
    StorageOccupancy,
    StorageReclaimReport,
    StorageTreeCheckReport,
    StorageTreeIssue,
    StorageTreeIssueKind,
)
from ._service import (
    RECLAIMABLE_LIFECYCLES,
    collect_storage_inventory,
    inspect_storage_tree,
    materialise_storage_tree,
    reclaim_storage_category,
    storage_lifecycle_permits_reclaim,
)

__all__ = [
    "RECLAIMABLE_LIFECYCLES",
    "StorageInitReport",
    "StorageInventoryReport",
    "StorageInventoryRow",
    "StorageManagementError",
    "StorageOccupancy",
    "StorageReclaimRefusedError",
    "StorageReclaimReport",
    "StorageReclaimUnconfirmedError",
    "StorageTreeCheckReport",
    "StorageTreeIssue",
    "StorageTreeIssueKind",
    "collect_storage_inventory",
    "inspect_storage_tree",
    "materialise_storage_tree",
    "reclaim_storage_category",
    "storage_lifecycle_permits_reclaim",
]
