"""Canonical live proof-authority composition for the closure command."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from cadrumo.application.registry import FilingExportProofAuthority
from cadrumo.core import SourceConnectivityProofAuthority
from cadrumo.core.resources import bundled_path
from cadrumo.domain.calculations.registry import ValidatedRegistryAuthority, bundled_authority

from ...source_connectivity.live_proof import canonical_live_connected_proof_authority
from ..filing_export_proof import canonical_live_filing_export_proof_authority

__all__ = [
    "RegistryClosureAuthorities",
    "canonical_live_registry_closure_authorities",
]


@dataclass(frozen=True, slots=True)
class RegistryClosureAuthorities:
    """One coherent registry authority and its two independent proof ports."""

    registry: ValidatedRegistryAuthority
    source_connectivity: SourceConnectivityProofAuthority | None
    filing_export: FilingExportProofAuthority | None

    def __post_init__(self) -> None:
        """Refuse structurally incomplete objects at the CLI injection boundary."""
        if self.source_connectivity is not None and not isinstance(
            self.source_connectivity,
            SourceConnectivityProofAuthority,
        ):
            raise TypeError("source-connectivity closure authority does not implement its proof protocol")
        if self.filing_export is not None and not isinstance(self.filing_export, FilingExportProofAuthority):
            raise TypeError("filing-export closure authority does not implement its proof protocol")


@contextmanager
def canonical_live_registry_closure_authorities(
    repository_root: Path,
) -> Iterator[RegistryClosureAuthorities]:
    """Yield current live authorities without inventing absent proof entries."""
    resolved_root = repository_root.resolve(strict=True)
    registry = bundled_authority()
    filing = canonical_live_filing_export_proof_authority(
        workspace_root=resolved_root,
        registry_root=bundled_path("registry", "aeat"),
        source_root=bundled_path(),
        authority=registry,
    )
    with canonical_live_connected_proof_authority(resolved_root) as source:
        yield RegistryClosureAuthorities(
            registry=registry,
            source_connectivity=source,
            filing_export=filing,
        )
