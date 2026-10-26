"""Own finite fixture projections over real domain and storage kernels."""

from __future__ import annotations

from ..authority import ValidatedRegistryAuthority
from ..errors import RegistrySnapshotError


def project_filing_year(self: ValidatedRegistryAuthority, filing_year: int) -> int:
    """Project an admitted filing year onto the authority's authored horizon."""
    support = self.catalogues.supported_filing_years
    if support is None:
        raise RegistrySnapshotError("the calculation registry declares no supported filing years")
    projected = support.projection_coordinate(filing_year)
    if projected is None:
        ceiling = support.hard_ceiling
        span = f"{support.floor} and later" if ceiling is None else f"{support.floor}..{ceiling}"
        raise RegistrySnapshotError(
            f"filing year {filing_year} is outside the calculation registry's supported span {span}"
        )
    return projected
