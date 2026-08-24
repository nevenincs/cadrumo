"""Read-only current-capsule bucket maintenance projections.

Lifecycle mutation moved to the custody transaction owner.  This surface keeps
only target locking and read-only observations; archive, restore, bundle
import/export, legacy rename, and manifest-backed lifecycle mutation have no
current implementation and are intentionally not exposed here.
"""

from __future__ import annotations

from collections.abc import Generator, Iterable, Mapping
from contextlib import ExitStack, contextmanager
from enum import StrEnum
from pathlib import Path
from uuid import UUID

from ...adapters.persistence.storage import custody
from ...application.filing import FilingRetentionAuthority
from ...core import ActionEvidenceProvenance, NoRecoveryOutcome
from ...core.hashing import CONTENT_DIGEST_PREFIX
from ...core.time import now
from ...domain.buckets import BucketDeleteRefusedError
from ...domain.retention import RetentionFloorAssessment
from ...domain.user_profile import ProfileNotFoundError
from .._bucket_deletion_contracts import BucketDeletionFingerprint
from ..operator_actions import PreconditionVerdict, no_action_precondition_verdict
from ..user_profile import (
    default_profile_bucket_storage,
)
from ..workflow import read_profile_bucket_by_id
from ._contracts import (
    AssessBucketDeletionCommand,
    BucketDeletionAssessment,
)
from ._deletion_paths import validated_bucket_deletion_paths


class BucketDeletionPreconditionCondition(StrEnum):
    """Closed failed-condition identities for deletion-preflight refusals."""

    CUSTODY_TARGET_UNLINKED = "bucket_maintenance.custody.target_unlinked"
    LABEL_PROJECTION_PRESENT = "bucket_maintenance.custody.label_projection_present"
    CAPSULE_INVENTORY_READABLE = "bucket_maintenance.custody.capsule_inventory_readable"
    RETENTION_SNAPSHOT_ASSESSABLE = "bucket_maintenance.filing.retention_snapshot_assessable"


def _bucket_deletion_no_recovery_verdict(
    condition: BucketDeletionPreconditionCondition,
    *,
    facts: Mapping[str, str | int | bool],
) -> PreconditionVerdict:
    """Return a safety outcome for a deletion target with no safe repair verb."""
    return no_action_precondition_verdict(
        condition_id=condition.value,
        facts=facts,
        provenance=ActionEvidenceProvenance.PERSISTED_STATE,
        outcome=NoRecoveryOutcome.SAFETY,
    )


def _bucket_delete_refusal(
    condition: BucketDeletionPreconditionCondition,
    *,
    bucket_id: str,
    facts: Mapping[str, str | int | bool],
) -> BucketDeleteRefusedError:
    """Build the registered refusal carrying its exact typed condition."""
    return BucketDeleteRefusedError(
        translated_message="errors.error.error_storage_bucket",
        context={"bucket_id": bucket_id},
        precondition_verdict=_bucket_deletion_no_recovery_verdict(condition, facts=facts),
    )


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
            raise ProfileNotFoundError(
                translated_message="errors.refused.refused_profile_not_found",
                context={"bucket_id": bucket_id},
            ) from exc
        except ValueError as exc:
            raise _bucket_delete_refusal(
                BucketDeletionPreconditionCondition.CUSTODY_TARGET_UNLINKED,
                bucket_id=str(bucket_id),
                facts={"bucket_id": str(bucket_id), "custody_target_unlinked": False},
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
                    raise _bucket_delete_refusal(
                        BucketDeletionPreconditionCondition.CUSTODY_TARGET_UNLINKED,
                        bucket_id=str(bucket_id),
                        facts={"bucket_id": str(bucket_id), "custody_target_unlinked": False},
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
            raise _bucket_delete_refusal(
                BucketDeletionPreconditionCondition.CUSTODY_TARGET_UNLINKED,
                bucket_id=str(command.bucket_id),
                facts={"bucket_id": str(command.bucket_id), "custody_target_unlinked": False},
            ) from exc
        bucket = read_profile_bucket_by_id(command.bucket_id)
        if bucket is None:
            raise _bucket_delete_refusal(
                BucketDeletionPreconditionCondition.LABEL_PROJECTION_PRESENT,
                bucket_id=str(command.bucket_id),
                facts={"bucket_id": str(command.bucket_id), "custody_record_present": False},
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


def _observed_deletion_fingerprint(
    *,
    root: Path,
    profile_id: UUID,
    bucket_id: str,
) -> BucketDeletionFingerprint:
    """Fold the committed capsule's exact contents into the deletion fingerprint.

    The three facts the contract carries are exactly what the custody inventory
    observes, so this reads that one inventory rather than growing a second
    content fold. The inventory spells its digest ``sha256:``-prefixed while the
    contract's field is the bare hex-64 :data:`~core.identity.ContentDigest`;
    the prefix is stripped rather than the field widened, because the reset
    journal's deletion marker compares against the same bare shape.

    A capsule that cannot be inventoried refuses. The fingerprint is what a
    later resume compares to detect a target changing beneath it, so a
    substituted or omitted value would make that detector silently blind.
    """
    try:
        inventory = custody.inventory_committed_profile_custody_capsule(profile_id, root=root)
    # Broad on purpose: any inventory failure at all must block, never soften.
    except Exception as exc:
        raise _bucket_delete_refusal(
            BucketDeletionPreconditionCondition.CAPSULE_INVENTORY_READABLE,
            bucket_id=bucket_id,
            facts={"bucket_id": bucket_id, "capsule_inventory_readable": False},
        ) from exc
    return BucketDeletionFingerprint(
        digest=inventory.digest.removeprefix(CONTENT_DIGEST_PREFIX),
        file_count=len(inventory.digest_entries),
        total_bytes=sum(entry.size_bytes for entry in inventory.digest_entries),
    )


def _assessed_filing_retention(
    *,
    root: Path,
    profile_id: UUID,
    bucket_id: str,
) -> RetentionFloorAssessment:
    """Return the target's legal retention position, or refuse to guess it.

    Three states reach here and only ONE of them is an answer.

    A RECORDED snapshot listing no filings IS an answer: the filing owner was
    asked, at profile creation, and said this profile has filed nothing. It
    yields an assessment retaining no records, and the target proceeds on the
    retention axis.

    An ABSENT snapshot is not that answer, and conflating the two is the defect
    this whole chain exists to close. Absence means nobody was asked -- the
    snapshot writes are deliberately best-effort, so a swallowed write and a
    never-created profile leave the same empty directory. Reading absence as
    "nothing is retained" would convert every swallowed write into permission
    to erase records Ley 58/2003 (LGT) arts. 66 and 70.2 require kept for four
    years, which is a fail-open on the erasure of taxpayer data.

    A snapshot that EXISTS but cannot be read, does not parse, or does not
    authenticate against its own path and digest is the same non-answer with a
    different cause, and refuses on the same grounds. Its cause is chained so
    the distinction survives into the traceback.

    Both refusals name what could not be assessed rather than reporting a
    generic retention requirement, because the two states have different
    remedies and an operator cannot act on "assessment required".
    """
    try:
        return FilingRetentionAuthority(root=root).assess(profile_id, now=now())
    except FileNotFoundError as exc:
        raise _bucket_delete_refusal(
            BucketDeletionPreconditionCondition.RETENTION_SNAPSHOT_ASSESSABLE,
            bucket_id=bucket_id,
            facts={
                "bucket_id": bucket_id,
                "retention_snapshot_present": False,
                "retention_snapshot_readable": False,
            },
        ) from exc
    # Broad on purpose: every unreadable shape is a non-answer, never a cleared one.
    except Exception as exc:
        raise _bucket_delete_refusal(
            BucketDeletionPreconditionCondition.RETENTION_SNAPSHOT_ASSESSABLE,
            bucket_id=bucket_id,
            facts={
                "bucket_id": bucket_id,
                "retention_snapshot_present": True,
                "retention_snapshot_readable": False,
            },
        ) from exc


__all__ = ["BucketMaintenanceService"]
