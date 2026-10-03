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
        _validate_namespace_count_order(
            (self.pushed_by_namespace, self.skipped_by_namespace, self.manifest_pushed_by_namespace)
        )
        _validate_outcome_counts(self)
        _validate_dry_run_outcomes(self)
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


def _validate_namespace_count_order(rows_by_kind: tuple[tuple[ArchiveNamespaceCount, ...], ...]) -> None:
    for rows in rows_by_kind:
        keys = tuple(row.namespace for row in rows)
        if keys != tuple(sorted(set(keys))):
            raise ValueError("mirror namespace counts must be sorted and unique")


def _validate_outcome_counts(report: ProfileArchivePushReport) -> None:
    if not _aggregate_counts_match(report) or not _failure_counts_match(report):
        raise ValueError("mirror report counts disagree with its complete outcomes")


def _aggregate_counts_match(report: ProfileArchivePushReport) -> bool:
    return (
        report.pushed_total == sum(row.count for row in report.pushed_by_namespace)
        and report.skipped_total == sum(row.count for row in report.skipped_by_namespace)
        and report.manifest_pushed_total == len(report.manifest_pushed_by_namespace)
    )


def _failure_counts_match(report: ProfileArchivePushReport) -> bool:
    return (
        report.failed_total == len(report.failed_objects)
        and report.manifest_failed_total == len(report.failed_manifests)
        and report.manifest_degraded_total == len(report.degraded_manifests)
    )


def _validate_dry_run_outcomes(report: ProfileArchivePushReport) -> None:
    if report.dry_run and (_has_provider_mutations(report) or _has_provider_failures(report)):
        raise ValueError("dry mirror preview must not contain provider outcomes")


def _has_provider_mutations(report: ProfileArchivePushReport) -> bool:
    return bool(report.pushed_by_namespace or report.manifest_pushed_by_namespace)


def _has_provider_failures(report: ProfileArchivePushReport) -> bool:
    return bool(
        report.failed_objects or report.failed_manifests or report.degraded_manifests or report.cleanup_failed_objects
    )


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
