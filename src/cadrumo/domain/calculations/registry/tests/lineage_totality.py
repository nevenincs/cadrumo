"""Own finite fixture projections over real domain and storage kernels."""

from __future__ import annotations

from ..casilla_lineage_totality import LineageTotalityReport


def is_total(self: LineageTotalityReport) -> bool:
    """Whether every unresolved row is covered and no exception is stale."""
    return not self.uncovered and (not self.stale)
