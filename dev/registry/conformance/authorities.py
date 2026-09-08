"""Canonical live filing-proof authority composition for the closure command."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from cadrumo.application.filing.export_proof import FilingExportProofAuthority
from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.authority import (
    ValidatedRegistryAuthority,
    bundled_authority,
)

from ..filing_export_proof import canonical_two_channel_filing_export_proof_authority

__all__ = [
    "RegistryClosureAuthorities",
    "canonical_live_registry_closure_authorities",
]


@dataclass(frozen=True, slots=True)
class RegistryClosureAuthorities:
    """One coherent registry authority and its filing-proof port."""

    registry: ValidatedRegistryAuthority
    filing_export: FilingExportProofAuthority | None

    def __post_init__(self) -> None:
        """Refuse a filing authority that does not implement its proof protocol."""
        if self.filing_export is not None and not isinstance(self.filing_export, FilingExportProofAuthority):
            raise TypeError("filing-export closure authority does not implement its proof protocol")


def canonical_live_registry_closure_authorities(
    repository_root: Path,
) -> RegistryClosureAuthorities:
    """Return current live authorities without inventing absent proof entries."""
    resolved_root = repository_root.resolve(strict=True)
    registry = bundled_authority()
    filing = canonical_two_channel_filing_export_proof_authority(
        workspace_root=resolved_root,
        registry_root=bundled_path("registry", "aeat"),
        source_root=bundled_path(),
        authority=registry,
        secure_replay_source=None,
        secure_replay_custody=None,
    )
    return RegistryClosureAuthorities(registry=registry, filing_export=filing)
