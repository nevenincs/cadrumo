"""Exact-profile archive capabilities and complete credential-free human reports."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Protocol, Self
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from ...core.identity.digest import ContentDigest
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from .bundle_export import ProfileBundleExportReconciliation
from .capsule_archive import ProfileCapsuleArchiveReceipt

type ArchiveLocalWriter = Callable[[Callable[[], None]], None]
type ArchiveProviderHandoff = Callable[[], None]


class ArchiveNamespaceCount(BaseModel):
    """One deterministic immutable replacement for an operational count map."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    namespace: Annotated[str, Field(min_length=1)]
    count: Annotated[int, Field(ge=0)]


class ArchivePushObjectFailure(BaseModel):
    """Canonical mirror failure identity, never an object plaintext or credential."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    namespace: str
    hmac: ContentDigest
    error: str


class ArchivePushManifestFailure(BaseModel):
    """Complete existing human namespace-manifest refusal fact."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    namespace: str
    error: str


class ArchivePushManifestDegradation(BaseModel):
    """Existing inspected mirror degradation, retained only for human disclosure."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    namespace: str
    detail: str


class ProfileArchivePushReport(BaseModel):
    """Complete canonical mirror report with closed immutable count collections."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    profile: str
    root_folder_id: str
    dry_run: bool
    namespace_filter: str | None
    limit: Annotated[int, Field(ge=1)] | None
    pushed_total: Annotated[int, Field(ge=0)]
    skipped_total: Annotated[int, Field(ge=0)]
    failed_total: Annotated[int, Field(ge=0)]
    manifest_pushed_total: Annotated[int, Field(ge=0)]
    manifest_failed_total: Annotated[int, Field(ge=0)]
    manifest_degraded_total: Annotated[int, Field(ge=0)]
    pushed_by_namespace: tuple[ArchiveNamespaceCount, ...]
    skipped_by_namespace: tuple[ArchiveNamespaceCount, ...]
    manifest_pushed_by_namespace: tuple[ArchiveNamespaceCount, ...]
    failed_objects: tuple[ArchivePushObjectFailure, ...]
    failed_manifests: tuple[ArchivePushManifestFailure, ...]
    degraded_manifests: tuple[ArchivePushManifestDegradation, ...]
    cleanup_failed_objects: tuple[ArchivePushObjectFailure, ...]

    @model_validator(mode="after")
    def _complete_counts(self) -> Self:
        for rows in (self.pushed_by_namespace, self.skipped_by_namespace, self.manifest_pushed_by_namespace):
            keys = tuple(row.namespace for row in rows)
            if keys != tuple(sorted(set(keys))):
                raise ValueError("mirror namespace counts must be sorted and unique")
        if (
            self.pushed_total != sum(row.count for row in self.pushed_by_namespace)
            or self.skipped_total != sum(row.count for row in self.skipped_by_namespace)
            or self.manifest_pushed_total != len(self.manifest_pushed_by_namespace)
            or self.failed_total != len(self.failed_objects)
            or self.manifest_failed_total != len(self.failed_manifests)
            or self.manifest_degraded_total != len(self.degraded_manifests)
        ):
            raise ValueError("mirror report counts disagree with its complete outcomes")
        if self.dry_run and (
            self.pushed_by_namespace
            or self.failed_objects
            or self.manifest_pushed_by_namespace
            or self.failed_manifests
            or self.degraded_manifests
            or self.cleanup_failed_objects
        ):
            raise ValueError("dry mirror preview must not contain provider outcomes")
        return self

    def pushed_counts(self) -> dict[str, int]:
        """Restore the existing human transport map without recomputing results."""
        return {row.namespace: row.count for row in self.pushed_by_namespace}

    def skipped_counts(self) -> dict[str, int]:
        """Restore the canonical dry-run/skipped counts."""
        return {row.namespace: row.count for row in self.skipped_by_namespace}

    def manifest_pushed_counts(self) -> dict[str, int]:
        """Restore the complete uploaded manifest counts."""
        return {row.namespace: row.count for row in self.manifest_pushed_by_namespace}


class ProfileArchiveExportPort(Protocol):
    """Export the selected profile through the canonical sealed-container service."""

    def __call__(self, target: Path, *, write: ArchiveLocalWriter) -> ProfileCapsuleArchiveReceipt:
        """Prepare outside the fence, then enter it only for actual container write."""
        ...


class ProfileArchivePushPort(Protocol):
    """Mirror only encrypted rows using the established policy and provider APIs."""

    def __call__(
        self,
        *,
        namespace_filter: str | None,
        limit: int | None,
        dry_run: bool,
        before_handoff: ArchiveProviderHandoff,
    ) -> ProfileArchivePushReport:
        """Require short admission before provider calls; do not retain COMMIT across I/O."""
        ...


class ProfileArchiveReconcilePort(Protocol):
    """Recover only exact-profile journals through the canonical reconciliation."""

    def __call__(self, *, write: ArchiveLocalWriter) -> ProfileBundleExportReconciliation:
        """Fence actual event saves and owned cleanup mutations individually."""
        ...


@dataclass(frozen=True, slots=True)
class ProfileArchiveOperationPorts:
    """Immutable worker identity, published pin and lazily invoked local capabilities."""

    profile_id: UUID
    operation: PinnedAuthorityOperation
    export: ProfileArchiveExportPort
    push: ProfileArchivePushPort
    reconcile: ProfileArchiveReconcilePort


class ProfileArchiveOperationPortsFactory(Protocol):
    """Compose one exact profile without opening remote credentials or sending data."""

    def __call__(self, *, profile_id: UUID, operation: PinnedAuthorityOperation) -> ProfileArchiveOperationPorts:
        """Return the selected profile's canonical archive capabilities."""
        ...
