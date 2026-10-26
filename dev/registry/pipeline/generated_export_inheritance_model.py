"""Typed attestation for an exact generated export storage baseline."""

from __future__ import annotations

from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict, Field

from cadrumo.domain.calculations.registry.ids import RevisionId, SourceRefId
from cadrumo.domain.calculations.registry.schema_exports import ExportLayoutDefinition


class GeneratedExportInheritance(BaseModel):
    """Child-local proof that one physical delta hydrates from one pinned edition."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    baseline_revision_id: RevisionId
    baseline_revision_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    baseline_manifest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    baseline_layout_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    baseline_source_ref: SourceRefId
    baseline_source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


@dataclass(frozen=True, slots=True)
class GeneratedExportInheritanceContext:
    """Attested immediate baseline and every pinned earlier storage ancestor."""

    attestation: GeneratedExportInheritance
    baseline_layout: ExportLayoutDefinition
    baseline_context: GeneratedExportInheritanceContext | None = None

    @property
    def pinned_ancestors(self) -> tuple[tuple[str, str], ...]:
        """Return oldest-first revision IDs and exact complete-tree digests."""
        older = () if self.baseline_context is None else self.baseline_context.pinned_ancestors
        return (
            *older,
            (str(self.attestation.baseline_revision_id), self.attestation.baseline_revision_sha256),
        )
