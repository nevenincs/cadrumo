"""Single application authority for portable profile-bundle publication.

Both operator purposes -- portable transfer and the subject-access request --
share this one service and one bundle schema; only their typed
:class:`ProfileBundleExportPurpose` metadata differs. Publication is staged so a
crash in any window recovers honestly: the service serializes to a restrictive
temporary file, fsyncs it, records a durable ``PREPARED`` operation-state
journal OUTSIDE the target artifact, atomically replaces the target, fsyncs the
parent directory, and only then emits the completion event. A crash after
``PREPARED`` but before publication is reconciled as prepared, never as
complete, and the completion event never fires for an artifact that was not
durably published. The sealed recovery archive is a separate surface and is not
folded in here.
"""

from __future__ import annotations

import os
import secrets
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from ...core import fsync_parent_dir
from ...core.atomic_write import atomic_write_hardened_bytes
from ...core.locks import exclusive_file_lock
from ...core.time import now
from ...domain.user_profile import ProfileExportError, ProfileNotFoundError
from ._bundle_export_contracts import (
    ProfileBundleExportPurpose,
    ProfileBundleExportRequest,
    ProfileBundleExportResult,
    ProfileBundleExportTarget,
    ProfileBundleExportTransport,
    bundle_data_categories,
)
from ._bundle_export_operation import (
    ProfileBundleExportJournalNotFoundError,
    ProfileBundleExportJournalRepository,
    ProfileBundleExportOperation,
    ProfileBundleExportOperationStatus,
    derive_export_operation_id,
)

if TYPE_CHECKING:
    from ...domain.buckets import BucketEventHistoryRepositoryProtocol
    from ...domain.user_profile import UserProfilePortableExport
    from ..workflow import ProfileBucketPointer

_STAGED_TEMP_SUFFIX = ".export-tmp"

# Reconcile takes each target lock non-blocking: a lock a live export already
# holds means an in-flight publication, not a crash orphan, so reconcile skips
# it rather than waiting.
_RECONCILE_LOCK_TIMEOUT_S = 0.0


@dataclass(frozen=True)
class PreparedProfileExport:
    """In-memory handle to one staged, journalled, not-yet-published export."""

    operation: ProfileBundleExportOperation
    staged_path: Path
    pointer: ProfileBucketPointer
    bundle: UserProfilePortableExport
    request: ProfileBundleExportRequest


def export_profile_bundle(request: ProfileBundleExportRequest) -> ProfileBundleExportResult:
    """Resolve, serialize, atomically publish, and record one profile export.

    Holds one exclusive lock on the resolved target for the whole publication so
    a concurrent export to the same file is excluded, then composes
    :func:`prepare_profile_export` and :func:`publish_prepared_export`.
    """
    journal = ProfileBundleExportJournalRepository()
    try:
        with exclusive_file_lock(request.destination):
            prepared = prepare_profile_export(request, journal=journal)
            return publish_prepared_export(prepared, journal=journal)
    except ProfileExportError:
        raise
    except OSError as exc:
        raise ProfileExportError(
            "portable profile export could not publish its destination",
            context={"destination": str(request.destination)},
        ) from exc


def prepare_profile_export(
    request: ProfileBundleExportRequest,
    *,
    journal: ProfileBundleExportJournalRepository | None = None,
) -> PreparedProfileExport:
    """Serialize the bundle to a restrictive staged temp and record PREPARED.

    Serializes the profile bundle, renders the transport payload, stages it to a
    ``0o600`` sibling temporary file, fsyncs it, and writes a durable
    ``PREPARED`` operation-state journal before any target replacement. A crash
    after this call leaves a recoverable ``PREPARED`` record and an orphan
    staged temp, never a published-looking target.
    """
    from ._orchestration import _profile_export_runtime

    repository = journal or ProfileBundleExportJournalRepository()
    target = ProfileBundleExportTarget(destination=request.destination)
    pointer = _resolve_export_profile(request.profile_name)
    _refuse_link_target(request.destination)
    with _profile_export_runtime(pointer.bucket_id):
        bundle = _serialize_export_bundle(pointer.bucket_id)
        payload = _render_export_payload(bundle, request=request)
    staged_path = _stage_export_tempfile(request.destination, payload.encode("utf-8"))
    try:
        categories = bundle_data_categories(bundle)
        occurred_at = now().replace(microsecond=0)
        operation = ProfileBundleExportOperation(
            operation_id=derive_export_operation_id(
                profile_id=pointer.bucket_id,
                target_identity=target.identity,
                purpose=request.purpose,
            ),
            status=ProfileBundleExportOperationStatus.PREPARED,
            profile_id=pointer.bucket_id,
            display_name=pointer.label,
            target_identity=target.identity,
            destination=str(request.destination),
            staged_path=str(staged_path),
            purpose=request.purpose,
            transport=request.transport,
            bundle_schema_version=bundle.bundle_schema_version,
            data_categories=categories,
            started_at=occurred_at,
            updated_at=occurred_at,
        )
        repository.save(operation)
    except BaseException:
        staged_path.unlink(missing_ok=True)
        raise
    return PreparedProfileExport(
        operation=operation,
        staged_path=staged_path,
        pointer=pointer,
        bundle=bundle,
        request=request,
    )


def publish_prepared_export(
    prepared: PreparedProfileExport,
    *,
    journal: ProfileBundleExportJournalRepository | None = None,
) -> ProfileBundleExportResult:
    """Atomically replace the target, fsync, then emit the completion event.

    Captures any pre-existing target, replaces it with the staged temp, fsyncs
    the parent directory, then emits the ``PROFILE_EXPORTED`` completion event.
    If the completion event fails, the target is restored to its captured state
    and the journal removed, so no completion event is recorded for a target
    that is not durably left published. On success the operation journal is
    removed.
    """
    repository = journal or ProfileBundleExportJournalRepository()
    request = prepared.request
    destination = request.destination
    from ._orchestration import _profile_export_runtime

    previous_target = _capture_export_target(destination)
    os.replace(prepared.staged_path, destination)
    fsync_parent_dir(destination)
    try:
        with _profile_export_runtime(prepared.pointer.bucket_id) as event_repository:
            _record_profile_export(
                pointer=prepared.pointer,
                bundle=prepared.bundle,
                request=request,
                repository=event_repository,
            )
    except Exception as exc:
        try:
            _restore_export_target(destination, previous_target)
        except Exception as compensation_exc:
            _safe_delete_journal(repository, prepared.operation.operation_id)
            raise ProfileExportError(
                "profile export audit failed and its destination could not be restored",
                context={
                    "destination": str(destination),
                    "audit_error": type(exc).__name__,
                    "compensation_error": type(compensation_exc).__name__,
                },
            ) from compensation_exc
        _safe_delete_journal(repository, prepared.operation.operation_id)
        raise ProfileExportError(
            "profile export audit failed; its destination was restored",
            context={
                "destination": str(destination),
                "audit_error": type(exc).__name__,
            },
        ) from exc
    _safe_delete_journal(repository, prepared.operation.operation_id)
    return ProfileBundleExportResult(
        profile_id=prepared.pointer.bucket_id,
        display_name=prepared.pointer.label,
        destination=destination,
        bundle_schema_version=prepared.bundle.bundle_schema_version,
        purpose=request.purpose,
        transport=request.transport,
        data_categories=prepared.operation.data_categories,
    )


def reconcile_prepared_exports(
    *,
    journal: ProfileBundleExportJournalRepository | None = None,
) -> tuple[ProfileBundleExportOperation, ...]:
    """Reconcile crash-interrupted exports honestly in a fresh process.

    Each ``PREPARED`` operation is reconciled only while holding the SAME
    per-destination lock a live :func:`export_profile_bundle` holds across its
    whole publication. An operation whose target lock cannot be acquired without
    waiting is an in-flight export, not a crash orphan, and is skipped -- so a
    reconcile running concurrently with a live same-target export can never
    unlink its live staged temp or delete its journal (which would fail the live
    ``os.replace``). Under the lock the operation is re-read: a still-``PREPARED``
    operation is reported as prepared -- never upgraded to complete -- its orphan
    staged temporary file is removed, and its journal is cleared. No completion
    event is ever emitted here, so a crash between ``PREPARED`` and publication
    can never surface a premature ``PROFILE_EXPORTED`` event for an artifact that
    was not durably published.
    """
    from ...core.locks_errors import LockAcquisitionError

    repository = journal or ProfileBundleExportJournalRepository()
    reconciled: list[ProfileBundleExportOperation] = []
    for operation in repository.prepared():
        destination = Path(operation.destination)
        if not destination.parent.exists():
            # No live export can be staging beside a missing parent directory,
            # so the journal is a bare orphan; clear it without a target lock.
            repository.delete(operation.operation_id)
            reconciled.append(operation)
            continue
        try:
            with exclusive_file_lock(destination, timeout=_RECONCILE_LOCK_TIMEOUT_S):
                current = _reload_prepared_operation(repository, operation.operation_id)
                if current is None:
                    continue
                _remove_orphan_staged_temp(current)
                repository.delete(current.operation_id)
                reconciled.append(current)
        except LockAcquisitionError:
            continue
    return tuple(reconciled)


def _reload_prepared_operation(
    repository: ProfileBundleExportJournalRepository,
    operation_id: str,
) -> ProfileBundleExportOperation | None:
    """Re-read an operation under its target lock; ``None`` if no longer prepared."""
    try:
        current = repository.load(operation_id)
    except ProfileBundleExportJournalNotFoundError:
        return None
    if current.status is not ProfileBundleExportOperationStatus.PREPARED:
        return None
    return current


def _resolve_export_profile(profile_name: str | None) -> ProfileBucketPointer:
    from ...core import resolve_active_bucket_id
    from ..workflow import read_profile_bucket, read_profile_bucket_by_id

    if profile_name is not None:
        pointer = read_profile_bucket(profile_name)
        missing_identity = profile_name
    else:
        active = resolve_active_bucket_id()
        pointer = read_profile_bucket_by_id(active) if active is not None else None
        missing_identity = active or "active"
    if pointer is None:
        raise ProfileNotFoundError(
            "profile export target does not exist",
            context={"profile": missing_identity},
        )
    return pointer


def _serialize_export_bundle(bucket_id: str) -> UserProfilePortableExport:
    from ._bundle import serialize_profile_bundle

    return serialize_profile_bundle(bucket_id=bucket_id)


def _render_export_payload(
    bundle: UserProfilePortableExport,
    *,
    request: ProfileBundleExportRequest,
) -> str:
    if request.transport is ProfileBundleExportTransport.CLEARTEXT_LOCAL:
        if request.passphrase is not None:
            raise ProfileExportError("cleartext profile export cannot carry a passphrase")
        return bundle.model_dump_json(indent=2)
    if request.passphrase is None:
        raise ProfileExportError("passphrase-encrypted profile export requires a passphrase")
    from ._bundle_encryption import encrypt_profile_bundle_for_passphrase

    encrypted = encrypt_profile_bundle_for_passphrase(
        bundle,
        passphrase=request.passphrase.get_secret_value(),
    )
    return encrypted.model_dump_json(indent=2)


def _stage_export_tempfile(destination: Path, data: bytes) -> Path:
    """Stage ``data`` into a restrictive ``0o600`` sibling of ``destination``.

    Distinct from the one-shot :func:`atomic_write_hardened_bytes` because the
    durable ``PREPARED`` journal must land between the fsynced temp and the
    atomic replace; this stages and fsyncs the temp only, leaving the replace to
    :func:`publish_prepared_export`. Uses ``O_EXCL`` plus the platform inherit /
    binary flags so a stray pre-existing temp is refused and newline bytes are
    never CRLF-translated on Windows.
    """
    destination.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = destination.with_name(f"{destination.name}.{os.getpid()}.{secrets.token_hex(4)}{_STAGED_TEMP_SUFFIX}")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    flags |= getattr(os, "O_NOINHERIT", 0)
    flags |= getattr(os, "O_CLOEXEC", 0)
    flags |= getattr(os, "O_BINARY", 0)
    created = False
    try:
        fd = os.open(tmp_path, flags, 0o600)
        created = True
        try:
            view = memoryview(data)
            offset = 0
            while offset < len(view):
                written = os.write(fd, view[offset:])
                if written <= 0:
                    raise OSError("profile export staged write made no progress")
                offset += written
            os.fsync(fd)
        finally:
            os.close(fd)
    except BaseException:
        if created:
            tmp_path.unlink(missing_ok=True)
        raise
    return tmp_path


def _refuse_link_target(path: Path) -> None:
    if path.is_symlink():
        raise ProfileExportError(
            "portable profile export refuses a symbolic-link destination",
            context={"destination": str(path)},
        )
    if path.exists() and not path.is_file():
        raise ProfileExportError(
            "portable profile export destination must be a regular file",
            context={"destination": str(path)},
        )


def _capture_export_target(path: Path) -> tuple[bool, bytes, int]:
    """Capture an existing regular target so a failed audit can restore it."""
    if path.is_symlink():
        raise ProfileExportError(
            "portable profile export refuses a symbolic-link destination",
            context={"destination": str(path)},
        )
    if not path.exists():
        return False, b"", 0o600
    if not path.is_file():
        raise ProfileExportError(
            "portable profile export destination must be a regular file",
            context={"destination": str(path)},
        )
    return True, path.read_bytes(), path.stat().st_mode & 0o777


def _restore_export_target(path: Path, snapshot: tuple[bool, bytes, int]) -> None:
    """Compensate a published target after its audit event fails."""
    existed, contents, mode = snapshot
    if existed:
        atomic_write_hardened_bytes(path, contents, mode=mode)
        return
    path.unlink(missing_ok=True)
    fsync_parent_dir(path)


def _remove_orphan_staged_temp(operation: ProfileBundleExportOperation) -> None:
    """Delete a reconciled operation's orphan staged temp, never its target."""
    staged = Path(operation.staged_path)
    if str(staged) == operation.destination or not staged.name.endswith(_STAGED_TEMP_SUFFIX):
        return
    if staged.is_symlink():
        return
    staged.unlink(missing_ok=True)


def _safe_delete_journal(repository: ProfileBundleExportJournalRepository, operation_id: str) -> None:
    try:
        repository.delete(operation_id)
    except OSError:
        from ...core.logging import get_logger

        get_logger(__name__).debug("profile export journal cleanup failed", exc_info=True)


def _record_profile_export(
    *,
    pointer: ProfileBucketPointer,
    bundle: UserProfilePortableExport,
    request: ProfileBundleExportRequest,
    repository: BucketEventHistoryRepositoryProtocol,
) -> None:
    from ...domain.buckets import (
        BucketEvent,
        BucketEventObjectType,
        BucketEventType,
        append_bucket_event,
        derive_bucket_event_id,
    )

    occurred_at = now().replace(microsecond=0)
    payload = {
        "display_name": pointer.label,
        "out": str(request.destination),
        "purpose": request.purpose.value,
        "schema_version": str(bundle.bundle_schema_version),
        "transport": request.transport.value,
    }
    event_id = derive_bucket_event_id(
        bucket_id=pointer.bucket_id,
        event_type=BucketEventType.PROFILE_EXPORTED,
        occurred_at=occurred_at,
        actor="operator",
        object_type=BucketEventObjectType.PROFILE,
        object_id=pointer.bucket_id,
        payload=payload,
    )
    event = BucketEvent(
        event_id=event_id,
        bucket_id=pointer.bucket_id,
        event_type=BucketEventType.PROFILE_EXPORTED,
        occurred_at=occurred_at,
        actor="operator",
        object_type=BucketEventObjectType.PROFILE,
        object_id=pointer.bucket_id,
        payload_version=1,
        payload=payload,
    )
    repository.save(append_bucket_event(repository.load(), event))


__all__ = [
    "PreparedProfileExport",
    "ProfileBundleExportPurpose",
    "ProfileBundleExportRequest",
    "ProfileBundleExportResult",
    "ProfileBundleExportTarget",
    "ProfileBundleExportTransport",
    "bundle_data_categories",
    "export_profile_bundle",
    "prepare_profile_export",
    "publish_prepared_export",
    "reconcile_prepared_exports",
]
