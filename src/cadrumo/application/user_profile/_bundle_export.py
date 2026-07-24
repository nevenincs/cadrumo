"""Single application authority for portable profile-bundle publication.

Both operator purposes -- portable transfer and the subject-access request --
share this one service and one bundle schema; only their typed
:class:`ProfileBundleExportPurpose` metadata differs. Publication is a
three-phase durable sequence so a crash in any window recovers honestly: the
service serializes to a restrictive temporary file, fsyncs it, records a durable
``PREPARED`` operation-state journal OUTSIDE the target artifact (carrying the
payload digest), atomically replaces the target, fsyncs the parent directory,
transitions the journal to ``COMPLETED``, and only then emits the completion
event before clearing the journal. A durably-published bundle is never
un-published; every crash window is reconciled without loss:

- a ``PREPARED`` operation whose destination does not hold the recorded digest
  never published -- it is cleared as an orphan and no event is emitted;
- a ``PREPARED`` operation whose destination matches the digest, or a
  ``COMPLETED`` operation, published durably -- reconciliation emits its
  ``PROFILE_EXPORTED`` event (idempotently, from the fixed ``event_occurred_at``)
  so no durably-published bundle is ever left without its audit event.

Reconciliation is not an optional maintenance chore: :func:`export_profile_bundle`
runs it before every publication, so the next export an operator performs -- to
any destination, for any profile -- is what clears a previous crash's orphan
journal and its leftover cleartext staged temp.

The sealed recovery archive is a separate surface and is not folded in here.
"""

from __future__ import annotations

import os
import secrets
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from ...core import fsync_parent_dir
from ...core.atomic_write import atomic_write_hardened_bytes
from ...core.external_constants import UTF_8_ENCODING
from ...core.hashing import sha256_hex
from ...core.locks import exclusive_file_lock
from ...core.locks_errors import LockAcquisitionError
from ...core.logging import get_logger
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

    Reconciles any crash-interrupted prior publication BEFORE taking this
    export's target lock (see :func:`_reconcile_crash_orphans_before_publication`),
    then holds one exclusive lock on the resolved target for the whole
    publication so a concurrent export to the same file is excluded, and
    composes :func:`prepare_profile_export` and :func:`publish_prepared_export`.
    """
    journal = ProfileBundleExportJournalRepository()
    _reconcile_crash_orphans_before_publication(journal)
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


def _reconcile_crash_orphans_before_publication(
    journal: ProfileBundleExportJournalRepository,
) -> None:
    """Sweep crash-interrupted prior publications before this export begins.

    This is the production trigger for :func:`reconcile_prepared_exports`. The
    journal repository is one storage-root-wide directory rather than a
    per-target or per-profile store, so a single sweep here recovers EVERY crash
    orphan left behind by any profile and any destination -- and the staged temp
    is a sibling of the operator's own chosen destination, which nothing else
    ever revisits.

    Running the sweep here, before the target lock, is required rather than
    merely convenient. The operation id is clock-free and derived from the
    profile, the resolved target identity, and the purpose, so re-exporting to
    the same target OVERWRITES the crashed run's journal -- and with it the only
    record of where that run staged its cleartext ``.export-tmp``. Reconciling
    first is what keeps those bundle bytes from being stranded on disk
    indefinitely (``sensitive-financial-data-secure-storage-only``). Reconcile
    also takes each target lock non-blocking, so it must run BEFORE this export
    acquires its own destination lock: from inside that lock it would skip the
    very operation it is here to clear.

    A failure here never fails the new export. The unfinished work stays
    journalled and is retried on the next publication, whereas refusing to
    export because some older unrelated operation could not be finalised would
    let one stale record block every future export.
    """
    try:
        reconcile_prepared_exports(journal=journal)
    except Exception:
        get_logger(__name__).warning(
            "profile export could not reconcile a crash-interrupted prior publication",
            exc_info=True,
        )


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
    payload_bytes = payload.encode(UTF_8_ENCODING)
    staged_path = _stage_export_tempfile(request.destination, payload_bytes)
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
            content_sha256=sha256_hex(payload_bytes),
            purpose=request.purpose,
            transport=request.transport,
            bundle_schema_version=bundle.bundle_schema_version,
            data_categories=categories,
            started_at=occurred_at,
            updated_at=occurred_at,
            event_occurred_at=occurred_at,
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
    """Atomically replace the target, mark COMPLETED, then emit the event.

    Replaces the target with the staged temp and fsyncs the parent directory --
    the durability point -- then transitions the operation journal to
    ``COMPLETED`` and emits the ``PROFILE_EXPORTED`` completion event before
    clearing the journal. A durably-published bundle is NEVER un-published: if
    the completion event cannot be written, the ``COMPLETED`` journal is left in
    place so a later :func:`reconcile_prepared_exports` emits the pending event,
    and the failure is surfaced rather than rolled back. The event is derived
    from the operation's fixed ``event_occurred_at``, so the live emission and
    any reconciliation emission collapse to one idempotent event.
    """
    repository = journal or ProfileBundleExportJournalRepository()
    operation = prepared.operation
    destination = prepared.request.destination

    os.replace(prepared.staged_path, destination)
    fsync_parent_dir(destination)
    completed = operation.model_copy(
        update={
            "status": ProfileBundleExportOperationStatus.COMPLETED,
            "updated_at": now().replace(microsecond=0),
        },
    )
    repository.save(completed)
    try:
        _emit_export_event(completed)
    except Exception as exc:
        raise ProfileExportError(
            "profile export published its destination but its audit event could not be "
            "recorded; the pending event completes on the next reconcile",
            context={"destination": str(destination), "audit_error": type(exc).__name__},
        ) from exc
    _safe_delete_journal(repository, completed.operation_id)
    return _result_from_operation(completed)


def _result_from_operation(operation: ProfileBundleExportOperation) -> ProfileBundleExportResult:
    return ProfileBundleExportResult(
        profile_id=operation.profile_id,
        display_name=operation.display_name,
        destination=Path(operation.destination),
        bundle_schema_version=operation.bundle_schema_version,
        purpose=operation.purpose,
        transport=operation.transport,
        data_categories=operation.data_categories,
    )


def reconcile_prepared_exports(
    *,
    journal: ProfileBundleExportJournalRepository | None = None,
) -> tuple[ProfileBundleExportOperation, ...]:
    """Reconcile crash-interrupted exports honestly in a fresh process.

    :func:`export_profile_bundle` calls this before every publication (see
    :func:`_reconcile_crash_orphans_before_publication`), so recovery happens on
    the operator's next export rather than waiting for a maintenance verb.

    Each operation is reconciled only while holding the SAME per-destination lock
    a live :func:`export_profile_bundle` holds across its whole publication. An
    operation whose target lock cannot be acquired without waiting is an in-flight
    export, not a crash orphan, and is skipped -- so a reconcile running
    concurrently with a live same-target export can never unlink its live staged
    temp or delete its journal (which would fail the live ``os.replace``). Under
    the lock the operation is re-read and resolved by state:

    - ``COMPLETED`` (replace already landed): the durably-published bundle is
      missing only its audit trail, so the ``PROFILE_EXPORTED`` event is emitted
      (idempotently, from the fixed ``event_occurred_at``) and the journal
      cleared.
    - ``PREPARED`` whose destination content matches the recorded digest: the
      atomic replace landed but the ``COMPLETED`` transition did not, so the
      bundle IS published -- the event is emitted and the journal cleared, closing
      the replace-to-``COMPLETED`` crash window.
    - ``PREPARED`` with no matching published content: a genuine orphan -- its
      staged temp is removed and its journal cleared, and no event is emitted for
      an artifact that was never durably published.
    """
    repository = journal or ProfileBundleExportJournalRepository()
    reconciled: list[ProfileBundleExportOperation] = []
    for operation in repository.list():
        destination = Path(operation.destination)
        if not destination.parent.exists():
            # No live export can be staging beside a missing parent directory, so
            # no target lock is needed. A COMPLETED operation was durably
            # published before the target was later moved away and still owes its
            # audit event; a PREPARED one never published and is a bare orphan.
            _finalise_reconciled_operation(repository, operation, published=_is_completed(operation))
            reconciled.append(operation)
            continue
        try:
            with exclusive_file_lock(destination, timeout=_RECONCILE_LOCK_TIMEOUT_S):
                current = _reload_operation(repository, operation.operation_id)
                if current is None:
                    continue
                published = _is_completed(current) or _destination_matches_digest(
                    destination,
                    current.content_sha256,
                )
                _finalise_reconciled_operation(repository, current, published=published)
                reconciled.append(current)
        except LockAcquisitionError:
            continue
    return tuple(reconciled)


def _is_completed(operation: ProfileBundleExportOperation) -> bool:
    return operation.status is ProfileBundleExportOperationStatus.COMPLETED


def _finalise_reconciled_operation(
    repository: ProfileBundleExportJournalRepository,
    operation: ProfileBundleExportOperation,
    *,
    published: bool,
) -> None:
    """Emit the pending event for a published operation, or clear an orphan.

    The staged temp is removed in BOTH cases: a harmless no-op after a normal
    ``os.replace`` consumed it, and the necessary cleanup when the destination
    already held byte-identical content from a prior identical export so the
    digest matched without our replace ever running -- leaving no cleartext
    ``.export-tmp`` bytes on disk past the operation
    (``sensitive-financial-data-secure-storage-only``).
    """
    if published:
        _emit_export_event(operation)
    _remove_orphan_staged_temp(operation)
    repository.delete(operation.operation_id)


def _destination_matches_digest(destination: Path, content_sha256: str) -> bool:
    """Return whether ``destination`` holds exactly the recorded staged payload."""
    if not destination.is_file():
        return False
    try:
        return sha256_hex(destination.read_bytes()) == content_sha256
    except OSError:
        return False


def _reload_operation(
    repository: ProfileBundleExportJournalRepository,
    operation_id: str,
) -> ProfileBundleExportOperation | None:
    """Re-read an operation under its target lock; ``None`` if it has cleared."""
    try:
        return repository.load(operation_id)
    except ProfileBundleExportJournalNotFoundError:
        return None


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

    The write is routed through the sanctioned hardened-tier primitive
    :func:`~cadrumo.core.atomic_write.atomic_write_hardened_bytes` (``O_EXCL`` +
    mode ``0o600`` + fsync + atomic create), which is the reviewed home for
    restrictive file writes -- rather than an ad-hoc ``os.open``/``os.write``.
    The staged sibling deliberately stays in place (the durable ``PREPARED``
    journal lands between it and the final replace); :func:`publish_prepared_export`
    performs the ``os.replace`` from this staged path onto the destination.
    """
    tmp_path = destination.with_name(f"{destination.name}.{os.getpid()}.{secrets.token_hex(4)}{_STAGED_TEMP_SUFFIX}")
    try:
        atomic_write_hardened_bytes(tmp_path, data)
    except BaseException:
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
        get_logger(__name__).debug("profile export journal cleanup failed", exc_info=True)


def _emit_export_event(operation: ProfileBundleExportOperation) -> None:
    """Emit the ``PROFILE_EXPORTED`` event for one operation, idempotently.

    Derives the event solely from the durable operation record, including its
    fixed ``event_occurred_at``, so a live publish emission and any later
    reconciliation emission produce the byte-identical ``event_id``; the
    content-addressed event catalogue then collapses the re-emission to one
    entry.
    """
    from ...domain.buckets import (
        BucketEvent,
        BucketEventObjectType,
        BucketEventType,
        append_bucket_event,
        derive_bucket_event_id,
    )
    from ._orchestration import _profile_export_runtime

    payload = {
        "display_name": operation.display_name,
        "out": operation.destination,
        "purpose": operation.purpose.value,
        "schema_version": str(operation.bundle_schema_version),
        "transport": operation.transport.value,
    }
    event_id = derive_bucket_event_id(
        bucket_id=operation.profile_id,
        event_type=BucketEventType.PROFILE_EXPORTED,
        occurred_at=operation.event_occurred_at,
        actor="operator",
        object_type=BucketEventObjectType.PROFILE,
        object_id=operation.profile_id,
        payload=payload,
    )
    event = BucketEvent(
        event_id=event_id,
        bucket_id=operation.profile_id,
        event_type=BucketEventType.PROFILE_EXPORTED,
        occurred_at=operation.event_occurred_at,
        actor="operator",
        object_type=BucketEventObjectType.PROFILE,
        object_id=operation.profile_id,
        payload_version=1,
        payload=payload,
    )
    with _profile_export_runtime(operation.profile_id) as event_repository:
        event_repository.save(append_bucket_event(event_repository.load(), event))


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
