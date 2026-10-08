"""Own finite fixture projections over real domain and storage kernels."""

from __future__ import annotations

from ..errors import ActividadAssetValidationError
from ..lifecycle import AcquisitionLineageReference


def resolve_current_transaction_id(self: AcquisitionLineageReference, replacements: dict[str, str]) -> str:
    """Follow a supplied canonical edit-lineage map without minting an ID.

    The application ledger owns construction of ``replacements``.  Keeping
    this narrow domain operation pure preserves the observed ID on the
    revision while enabling stale-state detection after ID-affecting edits.
    """
    current = self.observed_transaction_id
    seen: set[str] = set()
    while current in replacements:
        if current in seen:
            raise ActividadAssetValidationError("transaction edit lineage contains a cycle")
        seen.add(current)
        current = replacements[current]
    return current
