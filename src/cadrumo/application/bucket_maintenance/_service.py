"""Read-only current-capsule bucket maintenance projections.

Lifecycle mutation moved to the custody transaction owner.  This surface keeps
only target locking and read-only observations; archive, restore, bundle
import/export, legacy rename, and manifest-backed lifecycle mutation have no
current implementation and are intentionally not exposed here.
"""

from __future__ import annotations

from collections.abc import Generator, Iterable
from contextlib import ExitStack, contextmanager
from pathlib import Path
from uuid import UUID

from ...adapters.persistence.storage.custody import inventory_committed_profile_custody_capsule
from ...core import StorageCategory, require_active_bucket_id, storage_location
from ...core.hashing import CONTENT_DIGEST_PREFIX
from ...core.paths import directory_byte_total
from ...core.time import now
from ...domain.buckets import BucketDeleteRefusedError
from ...domain.retention import RetentionFloorAssessment
from ...domain.user_profile import ProfileNotFoundError
from .._bucket_deletion_contracts import BucketDeletionFingerprint
from ..filing import FilingRetentionAuthority
from ..profile_custody import default_profile_bucket_storage, default_profile_secure_object_inventory
from ..workflow import read_profile_bucket_by_id
from ._contracts import (
    AssessBucketDeletionCommand,
    BrowseBucketCommand,
    BrowseBucketResult,
    BucketDeletionAssessment,
    BucketDiskUsageSubdirRow,
    BucketNamespaceInventoryRow,
    DiskUsageBucketCommand,
    DiskUsageBucketResult,
)
from ._manifest_digest import validated_bucket_deletion_paths


class BucketMaintenanceService:
    """Expose only non-mutating maintenance operations for current capsules."""

    @contextmanager
    def _mutation_target_lock(
        self,
        *,
        root: Path,
        bucket_id: str,
        wait_seconds: float,
        missing_ok: bool = False,
    ) -> Generator[None]:
        try:
            paths = validated_bucket_deletion_paths(root=root, bucket_id=bucket_id)
        except FileNotFoundError as exc:
            if missing_ok:
                yield
                return
            raise ProfileNotFoundError("profile custody target does not exist") from exc
        except ValueError as exc:
            raise BucketDeleteRefusedError(
                "bucket maintenance refuses a linked custody target",
                context={"bucket_id": bucket_id},
            ) from exc
        storage = default_profile_bucket_storage()
        storage.acquire_lock(paths, wait_seconds=wait_seconds)
        try:
            yield
        finally:
            storage.release_lock(paths)

    @contextmanager
    def deletion_target_locks(
        self,
        *,
        root: Path,
        bucket_ids: Iterable[str],
        wait_seconds: float,
    ) -> Generator[None]:
        """Hold existing target locks in stable UUID order.

        This is intentionally a locking primitive only.  It neither derives a
        profile status nor makes a lifecycle decision from the label
        projection.
        """
        with ExitStack() as stack:
            storage = default_profile_bucket_storage()
            for bucket_id in sorted(set(bucket_ids)):
                try:
                    paths = validated_bucket_deletion_paths(root=root, bucket_id=bucket_id)
                except FileNotFoundError:
                    continue
                except ValueError as exc:
                    raise BucketDeleteRefusedError(
                        "bucket maintenance refuses a linked custody target",
                        context={"bucket_id": bucket_id},
                    ) from exc
                storage.acquire_lock(paths, wait_seconds=wait_seconds)
                stack.callback(storage.release_lock, paths)
            yield

    def assess_deletion(self, command: AssessBucketDeletionCommand) -> BucketDeletionAssessment:
        """Observe one deletion target: existence, label, contents and retention.

        Retention is answered WITHOUT a session, and the distinction matters
        because it is why this surface can answer at all. Producing the filing
        retention position still needs the bucket's key -- it summarises the
        encrypted filing catalogue -- so the filing owner records a plaintext
        snapshot at the two moments a session is held by construction, profile
        creation and filing persistence. A deletion preflight runs against
        profiles it has NOT unlocked, so it reads that snapshot rather than the
        modelo records, which are encrypted under a key nobody here holds.

        ``setup_state`` stays absent for the same reason it always did: it lives
        inside the encrypted profile record and no unauthenticated read can
        reach it. The field is optional on the assessment precisely so this
        surface can decline it rather than guess.
        """
        from ...core.config import load_settings

        root = load_settings().cadrumo_local_storage_root
        try:
            validated_bucket_deletion_paths(root=root, bucket_id=command.bucket_id)
        except FileNotFoundError:
            return BucketDeletionAssessment(bucket_id=command.bucket_id, exists=False)
        except ValueError as exc:
            raise BucketDeleteRefusedError(
                "bucket deletion assessment refuses a linked target",
                context={"bucket_id": command.bucket_id},
            ) from exc
        bucket = read_profile_bucket_by_id(command.bucket_id)
        if bucket is None:
            raise BucketDeleteRefusedError(
                "current custody target has no committed label projection",
                context={"bucket_id": command.bucket_id},
            )
        profile_id = UUID(command.bucket_id)
        return BucketDeletionAssessment(
            bucket_id=command.bucket_id,
            exists=True,
            label=bucket.label,
            fingerprint=_observed_deletion_fingerprint(
                root=root,
                profile_id=profile_id,
                bucket_id=command.bucket_id,
            ),
            retention=_assessed_filing_retention(
                root=root,
                profile_id=profile_id,
                bucket_id=command.bucket_id,
            ),
        )

    def browse(self, command: BrowseBucketCommand) -> BrowseBucketResult:
        """List namespaces for the already-authenticated active capsule only."""
        if require_active_bucket_id() != command.bucket_id:
            raise ProfileNotFoundError("bucket browse requires its authenticated active custody session")
        repository = default_profile_secure_object_inventory()
        namespaces = repository.list_namespaces()
        if command.namespace_filter is not None:
            namespaces = tuple(namespace for namespace in namespaces if command.namespace_filter in namespace)
        rows = tuple(
            BucketNamespaceInventoryRow(namespace=namespace, row_count=len(repository.list_keys(namespace)))
            for namespace in namespaces
        )
        return BrowseBucketResult(bucket_id=command.bucket_id, rows=rows)

    def disk_usage(self, command: DiskUsageBucketCommand) -> DiskUsageBucketResult:
        """Measure fixed custody directories without opening encrypted data."""
        from ...core.config import load_settings

        storage = default_profile_bucket_storage()
        paths = storage.resolve(load_settings().cadrumo_local_storage_root, command.bucket_id)
        manifest = paths.bucket_dir / storage_location(StorageCategory.BUCKET_MANIFEST).relative_path()
        rows: list[BucketDiskUsageSubdirRow] = []
        total_bytes = 0
        for name, directory, extra_files in (
            (storage_location(StorageCategory.BUCKET_DATABASE).subpath, paths.db_dir, (manifest,)),
            (storage_location(StorageCategory.BUCKET_BLOBS).subpath, paths.blobs_dir, ()),
        ):
            byte_count, file_count = directory_byte_total(directory, tolerate_errors=True)
            for extra_file in extra_files:
                if extra_file.is_file():
                    byte_count += extra_file.stat().st_size
                    file_count += 1
            rows.append(BucketDiskUsageSubdirRow(subdir=name, total_bytes=byte_count, file_count=file_count))
            total_bytes += byte_count
        return DiskUsageBucketResult(bucket_id=command.bucket_id, total_bytes=total_bytes, subdirs=tuple(rows))


__all__ = ["BucketMaintenanceService"]
