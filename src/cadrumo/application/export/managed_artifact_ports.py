"""Profile-bound creation evidence and freshly admitted outbound artifacts."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol, Self
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from ...core.errors.hierarchy import pydantic_validation_boundary
from ...core.hex import Hex64Str
from ...core.models import STRICT_FROZEN_CONFIG


class ManagedArtifactKind(StrEnum):
    """Closed kinds admitted beneath one profile's root."""

    ROOT = "root"
    FOLDER = "folder"
    REVIEW_SHEET = "review_sheet"
    EVIDENCE_PACKAGE = "evidence_package"
    CIPHERTEXT = "ciphertext"
    MIRROR_MANIFEST = "mirror_manifest"
    PROBE = "probe"


class ManagedArtifactPurpose(StrEnum):
    """Technical purposes that cannot produce business input records."""

    ADMISSION = "admission"
    PUBLICATION = "publication"
    RECONCILIATION = "reconciliation"
    BASELINE_VERIFICATION = "baseline_verification"
    BACKUP_INTEGRITY = "backup_integrity"


class ArtifactCreationReceipt(BaseModel):
    """Exact locally retained creation identity, never reconstructed from a marker."""

    model_config = STRICT_FROZEN_CONFIG

    profile_id: UUID
    root_folder_id: str = Field(min_length=1)
    artifact_id: str = Field(min_length=1)
    parent_id: str | None = Field(default=None, min_length=1)
    creation_id: UUID
    kind: ManagedArtifactKind
    publication_id: UUID | None = None

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _identity_shape(self) -> Self:
        if self.kind is ManagedArtifactKind.ROOT:
            if self.artifact_id != self.root_folder_id or self.parent_id is not None:
                raise ValueError("root creation identity must anchor itself without an external parent")
        elif self.parent_id is None or self.artifact_id == self.root_folder_id or self.parent_id == self.artifact_id:
            raise ValueError("child creation identity requires a distinct managed parent")
        return self


@dataclass(frozen=True, slots=True)
class AdmittedArtifact:
    """In-memory admission; adapters must recheck it at each request and retry."""

    receipt: ArtifactCreationReceipt
    purpose: ManagedArtifactPurpose


class ArtifactReceiptStore(Protocol):
    """Exact-profile encrypted custody for identities established by creation."""

    def load(self, artifact_id: str) -> ArtifactCreationReceipt | None:
        """Load a locally recorded identity; unknown provider IDs remain unknown."""
        ...

    def record(self, receipt: ArtifactCreationReceipt) -> None:
        """Persist acknowledged creation without replacing a conflicting identity."""
        ...

    def root_placement(self, root_id: str) -> tuple[str, str, str] | None:
        """Return recorded application parent, its creation marker and My Drive ID."""
        ...


class ManagedArtifactPort(Protocol):
    """Provider-neutral admission and ciphertext/package integrity transport."""

    def admit(self, receipt: ArtifactCreationReceipt, *, purpose: ManagedArtifactPurpose) -> AdmittedArtifact:
        """Check exact custody, profile, kind, marker, trash and known ancestry."""
        ...

    def create(
        self,
        parent: AdmittedArtifact,
        *,
        name: str,
        kind: ManagedArtifactKind,
        publication_id: UUID,
    ) -> ArtifactCreationReceipt:
        """Create a directly parented marked artifact and retain its identity."""
        ...

    def list_children(self, parent: AdmittedArtifact) -> tuple[ArtifactCreationReceipt, ...]:
        """Enumerate admitted children fully; never adopt unknown candidates."""
        ...

    def read_bytes(self, artifact: AdmittedArtifact, *, expected_digest: Hex64Str) -> bytes:
        """Read only for the admitted integrity purpose and verify the digest."""
        ...

    def write_bytes(self, artifact: AdmittedArtifact, payload: bytes, *, expected_digest: Hex64Str) -> None:
        """Publish package/ciphertext bytes after fresh admission and digest verification."""
        ...
