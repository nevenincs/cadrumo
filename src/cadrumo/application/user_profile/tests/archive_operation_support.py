"""Inward archive fixtures detecting preparation, writer and remote admission timing."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import cast
from uuid import UUID

from ....core.operations import profile_operation_subject
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ...modelo.tests.m036_operation_support import PROFILE_ID, CommitFence, Events, Operands
from ...operations.owner import OperationExecutorContext
from ..archive_operation_ports import (
    ArchiveLocalWriter,
    ArchiveProviderHandoff,
    ProfileArchiveOperationPorts,
    ProfileArchivePushReport,
)
from ..bundle_export import ProfileBundleExportReconciliation
from ..capsule_archive import ProfileCapsuleArchiveReceipt


def empty_push_report(*, dry_run: bool) -> ProfileArchivePushReport:
    """A canonical empty-selection report, with no fabricated provider outcome."""
    return ProfileArchivePushReport(
        profile=str(PROFILE_ID),
        root_folder_id="synthetic-root",
        dry_run=dry_run,
        namespace_filter=None,
        limit=None,
        pushed_total=0,
        skipped_total=0,
        failed_total=0,
        manifest_pushed_total=0,
        manifest_failed_total=0,
        manifest_degraded_total=0,
        pushed_by_namespace=(),
        skipped_by_namespace=(),
        manifest_pushed_by_namespace=(),
        failed_objects=(),
        failed_manifests=(),
        degraded_manifests=(),
        cleanup_failed_objects=(),
    )


class Subject:
    """One real published pin with synthetic observable inward effect ports."""

    def __init__(self, operation: PinnedAuthorityOperation) -> None:
        self.operation = operation
        self.fence = CommitFence()
        self.events = Events()
        self.operands = Operands()
        self.writes = 0
        self.remote_calls = 0
        self.fail_after_write = False
        self.fail_remote = False
        self.no_remote = False
        self.ports = ProfileArchiveOperationPorts(PROFILE_ID, operation, self.export, self.push, self.reconcile)

    def export(self, target: Path, *, write: ArchiveLocalWriter) -> ProfileCapsuleArchiveReceipt:
        assert not self.fence.active, "archive preparation must remain outside COMMIT"

        def publish() -> None:
            assert self.fence.active, "only the actual durable writer holds COMMIT"
            self.writes += 1
            if self.fail_after_write:
                raise OSError("synthetic writer committed before raising")

        write(publish)
        return ProfileCapsuleArchiveReceipt(
            bucket_id=str(PROFILE_ID), target=str(target), archive_schema_version=1, recovery_enrolled=False
        )

    def push(
        self,
        *,
        namespace_filter: str | None,
        limit: int | None,
        dry_run: bool,
        before_handoff: ArchiveProviderHandoff,
        write: ArchiveLocalWriter,
    ) -> ProfileArchivePushReport:
        assert not self.fence.active
        if not dry_run and not self.no_remote:
            before_handoff()
            assert not self.fence.active, "release COMMIT before remote I/O"
            self.remote_calls += 1
            if self.fail_remote:
                raise OSError("synthetic uncertain provider transmission")
        return empty_push_report(dry_run=dry_run)

    def reconcile(self, *, write: ArchiveLocalWriter) -> ProfileBundleExportReconciliation:
        assert not self.fence.active
        return ProfileBundleExportReconciliation(reconciled=(), failures=())

    def compose(self, *, profile_id: UUID, operation: PinnedAuthorityOperation) -> ProfileArchiveOperationPorts:
        assert profile_id == PROFILE_ID and operation is self.operation
        return self.ports

    def context(self, definition_id: str) -> OperationExecutorContext:
        return cast(
            OperationExecutorContext,
            SimpleNamespace(
                identity=SimpleNamespace(
                    definition_id=definition_id, subject_ref=profile_operation_subject(str(PROFILE_ID))
                ),
                authority_operation=self.operation,
                cancellation=self.fence,
                events=self.events,
                operands=self.operands,
            ),
        )
