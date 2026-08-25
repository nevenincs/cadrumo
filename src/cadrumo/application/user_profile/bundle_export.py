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

from ...core import fsync_parent_dir, scan_directory
from ...core.atomic_write import atomic_write_hardened_bytes
from ...core.external_constants import UTF_8_ENCODING
from ...core.hashing import sha256_hex
from ...core.locks import exclusive_file_lock
from ...core.locks_errors import LockAcquisitionError
from ...core.logging import get_logger
from ...core.time import now
from ...domain.user_profile.errors import ProfileExportError, ProfileNotFoundError
from .bundle_export_contracts import (
    ProfileBundleExportReconcileFailure,
    ProfileBundleExportRequest,
    ProfileBundleExportResult,
    ProfileBundleExportTarget,
    ProfileBundleExportTransport,
    bundle_data_categories,
    bundle_excluded_data_categories,
)
from .bundle_export_operation import (
    ProfileBundleExportJournalNotFoundError,
    ProfileBundleExportJournalRepository,
    ProfileBundleExportOperation,
    ProfileBundleExportOperationStatus,
    derive_export_operation_id,
    is_canonical_profile_export_staged_path,
    profile_export_staged_path,
)
from .custody_ports import default_profile_bucket_event_history_repository

if TYPE_CHECKING:
    from cadrumo.application.workflow.profile_bucket_models import ProfileBucketPointer

    from ...domain.user_profile.portable_export import UserProfilePortableExport

# The hardened writer stages through its own inner sibling before the rename;
# see :func:`_orphan_staged_paths` for why recovery must reach it too.
_HARDENED_INNER_TEMP_SUFFIX = ".tmp"

# Reconcile takes each target lock non-blocking: a lock a live export already
# holds means an in-flight publication, not a crash orphan, so reconcile skips
# it rather than waiting.
_RECONCILE_LOCK_TIMEOUT_S = 0.0

# Export is an operator handoff, so the trail names the operator rather than the
# emitting module. The payload version tracks the export event's own key set.
_PROFILE_BUNDLE_EVENT_ACTOR = "operator"
_PROFILE_BUNDLE_EVENT_PAYLOAD_VERSION = 1


@dataclass(frozen=True)
class PreparedProfileExport:
    """In-memory handle to one staged, journalled, not-yet-published export."""

    operation: ProfileBundleExportOperation
    staged_path: Path
    pointer: ProfileBucketPointer
    bundle: UserProfilePortableExport
    request: ProfileBundleExportRequest


@dataclass(frozen=True)
class ProfileBundleExportReconciliation:
    """Outcome of one reconciliation sweep across every export journal.

    ``reconciled`` are the operations the sweep resolved and cleared;
    ``failures`` are the ones it isolated and left journalled for a later
    attempt. An operation skipped because a live export holds its target lock is
    in neither: it is healthy in-flight work, not a failure.
    """

    reconciled: tuple[ProfileBundleExportOperation, ...]
    failures: tuple[ProfileBundleExportReconcileFailure, ...]


def export_profile_bundle(request: ProfileBundleExportRequest) -> ProfileBundleExportResult:
    """Resolve, serialize, atomically publish, and record one profile export.

    Reconciles any crash-interrupted prior publication BEFORE taking this
    export's target lock (see :func:`_reconcile_crash_orphans_before_publication`),
    then holds one exclusive lock on the resolved target for the whole
    publication so a concurrent export to the same file is excluded, and
    composes :func:`prepare_profile_export` and :func:`publish_prepared_export`.
    """
    journal = ProfileBundleExportJournalRepository()
    reconcile_failures = _reconcile_crash_orphans_before_publication(journal)
    try:
        with exclusive_file_lock(request.destination):
            prepared = prepare_profile_export(request, journal=journal)
            published = publish_prepared_export(prepared, journal=journal)
            return published.model_copy(update={"reconcile_failures": reconcile_failures})
    except ProfileExportError:
        raise
    except OSError as exc:
        raise ProfileExportError(
            translated_message="errors.fail.profile_export",
            context={"destination": str(request.destination), "destination_published": False},
        ) from exc


def _reconcile_crash_orphans_before_publication(
    journal: ProfileBundleExportJournalRepository,
) -> tuple[ProfileBundleExportReconcileFailure, ...]:
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

    The isolated failures are RETURNED rather than logged and dropped. A journal
    left behind may still describe cleartext bundle bytes on disk, and the
    operator running this export is the one who needs told -- the maintenance
    verb is not the path they are on.
    """
    try:
        return reconcile_prepared_exports(journal=journal).failures
    except Exception:
        get_logger(__name__).warning(
            "profile export could not reconcile a crash-interrupted prior publication",
            exc_info=True,
        )
        return ()


def prepare_profile_export(
    request: ProfileBundleExportRequest,
    *,
    journal: ProfileBundleExportJournalRepository | None = None,
) -> PreparedProfileExport:
    """Record the PREPARED journal, THEN stage the bundle to a restrictive temp.

    The journal is written BEFORE any cleartext reaches disk, naming the staged
    path it is about to write. That ordering is the whole crash contract: the
    reconciliation sweep is journal-driven, so cleartext staged without a
    journal entry pointing at it would be unreachable by every recovery
    surface. Staging first left exactly that window -- serialization, category
    derivation, and a journal write that can wait on the repository lock all
    sat between the cleartext hitting disk and the record naming it -- and a
    crash inside it stranded a readable profile bundle that no sweep could ever
    find (``sensitive-financial-data-secure-storage-only``).

    A crash between the journal write and a completed staging is harmless: the
    reconciliation finds a ``PREPARED`` operation whose destination does not
    hold the recorded digest, clears the staged path it names (whether that file
    exists, is half-written, or was never created), and emits no event.
    """
    from .profile_record_repository import require_profile_record_session

    repository = journal or ProfileBundleExportJournalRepository()
    target = ProfileBundleExportTarget(destination=request.destination)
    pointer = _resolve_export_profile(request.profile_name)
    _refuse_link_target(request.destination)
    require_profile_record_session(pointer.bucket_id)
    bundle = _serialize_export_bundle(pointer.bucket_id)
    payload = _render_export_payload(bundle, request=request)
    payload_bytes = payload.encode(UTF_8_ENCODING)
    categories = bundle_data_categories(bundle)
    excluded_categories = bundle_excluded_data_categories(bundle)
    staged_path = _staged_temp_path(request.destination)
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
        excluded_data_categories=excluded_categories,
        started_at=occurred_at,
        updated_at=occurred_at,
        event_occurred_at=occurred_at,
    )
    repository.save(operation)
    try:
        _stage_export_tempfile(staged_path, payload_bytes)
    except BaseException:
        _discard_prepared_operation(repository, operation)
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
            translated_message="errors.fail.profile_export",
            context={
                "destination": str(destination),
                "audit_error": type(exc).__name__,
                "destination_published": True,
                "audit_event_recorded": False,
            },
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
        excluded_data_categories=operation.excluded_data_categories,
    )


def reconcile_prepared_exports(
    *,
    journal: ProfileBundleExportJournalRepository | None = None,
) -> ProfileBundleExportReconciliation:
    """Reconcile crash-interrupted exports honestly in a fresh process.

    :func:`export_profile_bundle` calls this before every publication (see
    :func:`_reconcile_crash_orphans_before_publication`), and the operator can
    invoke it directly, so recovery happens on the next export or on demand.

    Every operation is isolated. One journal that cannot be read, or one
    operation that cannot be finalised -- a profile deleted after its crash, a
    destination on a volume that has gone away -- is recorded in ``failures``
    and the walk continues, so a single bad record can never starve every
    later-ordered operation of its recovery. A failed operation keeps its
    journal, so the next sweep retries it. Failures are reported rather than
    swallowed: a journal left behind may still describe cleartext bundle bytes
    on disk, which is precisely what an operator needs told.

    Each operation is reconciled only while holding the SAME per-destination lock
    a live :func:`export_profile_bundle` holds across its whole publication. An
    operation whose target lock cannot be acquired without waiting is an in-flight
    export, not a crash orphan, and is skipped (a skip, not a failure) -- so a
    reconcile running concurrently with a live same-target export can never
    unlink its live staged temp or delete its journal (which would fail the live
    ``os.replace``). Under the lock the operation is re-read and resolved by
    state:

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
    scan = repository.scan()
    reconciled: list[ProfileBundleExportOperation] = []
    failures = [
        ProfileBundleExportReconcileFailure(
            journal_id=unreadable.journal_id,
            destination=None,
            reason=unreadable.reason,
        )
        for unreadable in scan.unreadable
    ]
    for operation in scan.operations:
        try:
            current = _reconcile_one_operation(repository, operation)
        except Exception as exc:
            get_logger(__name__).warning(
                "profile export reconciliation could not finalise one operation",
                exc_info=True,
            )
            failures.append(
                ProfileBundleExportReconcileFailure(
                    journal_id=operation.operation_id,
                    destination=operation.destination,
                    reason=type(exc).__name__,
                ),
            )
            continue
        if current is not None:
            reconciled.append(current)
    return ProfileBundleExportReconciliation(reconciled=tuple(reconciled), failures=tuple(failures))


def _reconcile_one_operation(
    repository: ProfileBundleExportJournalRepository,
    operation: ProfileBundleExportOperation,
) -> ProfileBundleExportOperation | None:
    """Reconcile exactly one operation, or return ``None`` when it is skipped.

    ``None`` means the operation was deliberately left alone -- its target lock
    is held by a live export, or its journal cleared between the scan and the
    lock -- never that it failed. A failure raises, so the caller can isolate it.
    """
    destination = Path(operation.destination)
    if not destination.parent.exists():
        # No live export can be staging beside a missing parent directory, so
        # no target lock is needed. A COMPLETED operation was durably
        # published before the target was later moved away and still owes its
        # audit event; a PREPARED one never published and is a bare orphan.
        _finalise_reconciled_operation(repository, operation, published=_is_completed(operation))
        return operation
    try:
        with exclusive_file_lock(destination, timeout=_RECONCILE_LOCK_TIMEOUT_S):
            current = _reload_operation(repository, operation.operation_id)
            if current is None:
                return None
            published = _is_completed(current) or _destination_matches_digest(
                destination,
                current.content_sha256,
            )
            _finalise_reconciled_operation(repository, current, published=published)
            return current
    except LockAcquisitionError:
        return None


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
    from cadrumo.application.workflow.profile_bucket_scan import read_profile_bucket, read_profile_bucket_by_id

    from ...core.bucket_pointer import resolve_active_bucket_id

    if profile_name is not None:
        pointer = read_profile_bucket(profile_name)
        missing_identity = profile_name
    else:
        active = resolve_active_bucket_id()
        pointer = read_profile_bucket_by_id(active) if active is not None else None
        missing_identity = active or "active"
    if pointer is None:
        raise ProfileNotFoundError(
            translated_message="errors.refused.refused_profile_not_found",
            context={"profile": missing_identity, "target_exists": False},
        )
    return pointer


def _serialize_export_bundle(bucket_id: str) -> UserProfilePortableExport:
    from .bundle import serialize_profile_bundle

    return serialize_profile_bundle(bucket_id=bucket_id)


def _render_export_payload(
    bundle: UserProfilePortableExport,
    *,
    request: ProfileBundleExportRequest,
) -> str:
    if request.transport is ProfileBundleExportTransport.CLEARTEXT_LOCAL:
        if request.passphrase is not None:
            raise ProfileExportError(
                translated_message="errors.fail.profile_export",
                context={"export_mode": "cleartext", "passphrase_supplied": True},
            )
        return bundle.model_dump_json(indent=2)
    if request.passphrase is None:
        raise ProfileExportError(
            translated_message="errors.fail.profile_export",
            context={"export_mode": "passphrase_encrypted", "passphrase_supplied": False},
        )
    from .bundle_encryption import encrypt_profile_bundle_for_passphrase

    encrypted = encrypt_profile_bundle_for_passphrase(
        bundle,
        passphrase=request.passphrase.get_secret_value(),
    )
    return encrypted.model_dump_json(indent=2)


def _staged_temp_path(destination: Path) -> Path:
    """Derive the staged sibling path for ``destination`` without touching disk.

    Deriving the name separately from writing it is what lets the durable
    journal be recorded BEFORE any cleartext exists, naming the exact path the
    staging is about to create.
    """
    return profile_export_staged_path(
        destination,
        process_id=os.getpid(),
        nonce=secrets.token_hex(4),
    )


def _stage_export_tempfile(staged_path: Path, data: bytes) -> None:
    """Write ``data`` to the already-journalled ``staged_path`` at ``0o600``.

    The write is routed through the sanctioned hardened-tier primitive
    :func:`~cadrumo.core.atomic_write.atomic_write_hardened_bytes` (``O_EXCL`` +
    mode ``0o600`` + fsync + atomic create), which is the reviewed home for
    restrictive file writes -- rather than an ad-hoc ``os.open``/``os.write``.
    The staged sibling deliberately stays in place;
    :func:`publish_prepared_export` performs the ``os.replace`` from it onto the
    destination.

    That primitive stages through an inner ``<staged_path>.<pid>.<hex>.tmp``
    sibling of its own and unlinks it on any ordinary failure -- but not on a
    hard kill, where no ``finally`` runs. Recovery therefore cannot key on this
    path alone; see :func:`_orphan_staged_paths`.
    """
    try:
        atomic_write_hardened_bytes(staged_path, data)
    except BaseException:
        staged_path.unlink(missing_ok=True)
        raise


def _refuse_link_target(path: Path) -> None:
    if path.is_symlink():
        raise ProfileExportError(
            translated_message="errors.fail.profile_export",
            context={"destination": str(path), "destination_is_symlink": True},
        )
    if path.exists() and not path.is_file():
        raise ProfileExportError(
            translated_message="errors.fail.profile_export",
            context={"destination": str(path), "destination_is_regular_file": False},
        )


def _orphan_staged_paths(operation: ProfileBundleExportOperation) -> tuple[Path, ...]:
    """Return every cleartext file this operation's staging could have created.

    The journalled staged path is only one of two. The hardened writer stages
    through its own inner ``<staged_path>.<pid>.<hex>.tmp`` sibling and unlinks
    it in a ``finally`` -- which never runs under a hard kill, leaving a full
    cleartext bundle whose name does NOT end in the staged suffix. Keying
    recovery on the journalled path alone therefore left the hardened writer's
    own orphans unreachable, so the inner temps are enumerated from the same
    prefix rather than trusted to clean themselves up.

    The prefix match is done over a directory listing rather than
    :meth:`~pathlib.Path.glob`, because the operator chooses the destination
    name and a literal ``[`` in it would otherwise be read as a glob character
    class and silently match nothing.
    """
    destination = Path(operation.destination)
    staged = Path(operation.staged_path)
    if not is_canonical_profile_export_staged_path(destination, staged):
        return ()
    candidates = [staged]
    parent = staged.parent
    if parent.is_dir():
        inner_prefix = f"{staged.name}."
        candidates.extend(
            entry
            for entry in scan_directory(parent)
            if entry.name.startswith(inner_prefix) and entry.name.endswith(_HARDENED_INNER_TEMP_SUFFIX)
        )
    return tuple(path for path in candidates if not path.is_symlink())


def _remove_orphan_staged_temp(operation: ProfileBundleExportOperation) -> None:
    """Delete a reconciled operation's orphan cleartext temps, never its target."""
    for path in _orphan_staged_paths(operation):
        path.unlink(missing_ok=True)


def _discard_prepared_operation(
    repository: ProfileBundleExportJournalRepository,
    operation: ProfileBundleExportOperation,
) -> None:
    """Clear a journalled operation whose staging failed before it published.

    Best-effort: anything left behind stays journalled, so the next
    reconciliation sweep finds and clears it rather than stranding cleartext.
    """
    try:
        _remove_orphan_staged_temp(operation)
        repository.delete(operation.operation_id)
    except OSError:
        get_logger(__name__).debug("profile export could not discard a failed preparation", exc_info=True)


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
    from ...domain.buckets import BucketEventObjectType, BucketEventType, emit_bucket_event
    from .profile_record_repository import require_profile_record_session

    require_profile_record_session(operation.profile_id)
    emit_bucket_event(
        repository=default_profile_bucket_event_history_repository(),
        bucket_id=operation.profile_id,
        event_type=BucketEventType.PROFILE_EXPORTED,
        occurred_at=operation.event_occurred_at,
        actor=_PROFILE_BUNDLE_EVENT_ACTOR,
        object_type=BucketEventObjectType.PROFILE,
        object_id=operation.profile_id,
        payload={
            "display_name": operation.display_name,
            "out": operation.destination,
            "purpose": operation.purpose.value,
            "schema_version": str(operation.bundle_schema_version),
            "transport": operation.transport.value,
        },
        payload_version=_PROFILE_BUNDLE_EVENT_PAYLOAD_VERSION,
    )


__all__ = [
    "PreparedProfileExport",
    "ProfileBundleExportReconciliation",
    "export_profile_bundle",
    "prepare_profile_export",
    "publish_prepared_export",
    "reconcile_prepared_exports",
]
