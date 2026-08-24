"""Local-filesystem :class:`adapters.outbound.storage.StorageProvider` implementation.

Stores objects under a configurable root directory. Each namespace is
a subdirectory; each object is a single file named
``<hmac_prefix_8>--<label>.<ext>``. Metadata (``content_hash``,
``byte_length``, ``written_at``, full HMAC, and label) lives in a sibling JSON
sidecar so the listing API can return :class:`ProviderObjectMetadata` without
re-hashing the payload.

Bytes-in / bytes-out: encryption + classification stay above this
layer. The provider treats every payload as opaque bytes and uses
:func:`adapters.outbound.storage._integrity.verify_content_hash` to
enforce the stored digest on read.
"""

from __future__ import annotations

import json
import typing
from collections.abc import Iterator, Mapping
from datetime import datetime
from pathlib import Path

from ....application.operator_actions import no_action_precondition_verdict
from ....core import ActionEvidenceProvenance, NoRecoveryOutcome, iter_directory, scan_directory
from ....core.atomic_write import DurableWriteBatch, atomic_write_hardened_bytes, atomic_write_text
from ....core.errors import CoreValidationError
from ....core.external_constants import UTF_8_ENCODING
from ....core.hashing import sha256_hex
from ....core.logging import get_logger
from ....core.paths import is_windows_long_path_error
from ....core.time import now, validate_utc_aware
from ._errors import (
    OutboundStorageConflictError,
    OutboundStorageIntegrityError,
    OutboundStorageNotFoundError,
    OutboundStoragePathTooLongError,
    OutboundStoragePermissionError,
    OutboundStorageValidationError,
    StorageCorruptionError,
)
from ._integrity import verify_content_hash, verify_payload_byte_length
from ._key_validation import assert_admissible_object_key_hmac
from ._object_name import build_provider_object_name, provider_object_hmac_prefix, sanitize_provider_object_label
from ._records import ProviderKind, ProviderObjectMetadata, ProviderProbeReport

_logger = get_logger(__name__)

_FILE_EXTENSION = ".bin"
_SIDECAR_EXTENSION = ".meta.json"
_PROBE_NAMESPACE = "_probe"


def _local_failure_verdict(
    condition_id: str,
    *,
    facts: Mapping[str, str | int | bool],
    outcome: NoRecoveryOutcome = NoRecoveryOutcome.SAFETY,
):
    """Project an observed local-provider failure through the shared policy."""
    return no_action_precondition_verdict(
        condition_id=condition_id,
        facts=facts,
        provenance=ActionEvidenceProvenance.RUNTIME_OBSERVATION,
        outcome=outcome,
    )


def _validate_namespace(namespace: str) -> str:
    cleaned = namespace.strip()
    if not cleaned:
        raise OutboundStorageValidationError(
            "namespace must not be blank",
            translated_message="adapters.outbound.storage.local.errors.namespace_blank",
        )
    if "/" in cleaned or "\\" in cleaned or cleaned.startswith("."):
        raise OutboundStorageValidationError(
            f"namespace {namespace!r} contains forbidden characters",
            context={"namespace": namespace},
            translated_message="adapters.outbound.storage.local.errors.namespace_forbidden_characters",
        )
    return cleaned


def _validate_hmac(object_key_hmac: str) -> str:
    """Delegate to the one admissibility rule both backends share."""
    return assert_admissible_object_key_hmac(object_key_hmac, backend="local")


def _sidecar_filename(object_key_hmac: str, label: str) -> str:
    return build_provider_object_name(object_key_hmac, label, extension=_SIDECAR_EXTENSION)


def _parse_sidecar_byte_length(value: object) -> int:
    """Return a non-negative sidecar byte length or classify metadata corruption."""
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        raise StorageCorruptionError(
            f"sidecar byte_length has unexpected type: {type(value)!r}",
            context={"actual_type": repr(type(value))},
            translated_message="adapters.outbound.storage.local.errors.byte_length_invalid",
            precondition_verdict=_local_failure_verdict(
                "storage.local.sidecar.byte_length_valid", facts={"field": "byte_length", "valid": False}
            ),
        )
    try:
        byte_length = int(value)
    except ValueError:
        raise StorageCorruptionError(
            f"sidecar byte_length is not an integer: {value!r}",
            context={"actual_value": str(value)},
            translated_message="adapters.outbound.storage.local.errors.byte_length_invalid",
            precondition_verdict=_local_failure_verdict(
                "storage.local.sidecar.byte_length_valid", facts={"field": "byte_length", "valid": False}
            ),
        ) from None
    if byte_length < 0:
        raise StorageCorruptionError(
            f"sidecar byte_length must not be negative: {byte_length}",
            context={"actual_value": str(byte_length)},
            translated_message="adapters.outbound.storage.local.errors.byte_length_invalid",
            precondition_verdict=_local_failure_verdict(
                "storage.local.sidecar.byte_length_valid", facts={"field": "byte_length", "valid": False}
            ),
        )
    return byte_length


def _parse_sidecar_written_at(value: object) -> datetime:
    """Return the sidecar's persisted write instant, or classify corruption.

    ``get`` and ``iter_objects`` each parsed this field with their own copy of
    the same three lines, and both substituted ``now()`` when the value was
    missing or unparseable. That turned immutable storage corruption into
    apparently fresh metadata, and — because the two surfaces call the clock at
    different instants — made the SAME object report two different write times
    depending on which one an operator read it through. The payload stayed
    intact while its chronology silently did not, so nothing downstream could
    learn the sidecar had been damaged.

    A tz-naive value is refused rather than assumed UTC. The writer stores an
    aware instant, so a naive one is damage; reading it as UTC would recover a
    wrong instant wherever the writer was not on UTC, which is the same silent
    substitution in a smaller disguise.

    Raises:
        :class:`StorageCorruptionError`: When the field is absent, is not a
            string, does not parse, or carries no timezone.
    """
    if not isinstance(value, str) or not value.strip():
        raise StorageCorruptionError(
            f"sidecar written_at is absent or not a string: {value!r}",
            context={"actual_value": repr(value)},
            translated_message="adapters.outbound.storage.local.errors.written_at_invalid",
            precondition_verdict=_local_failure_verdict(
                "storage.local.sidecar.written_at_valid", facts={"field": "written_at", "valid": False}
            ),
        )
    try:
        written_at = datetime.fromisoformat(value)
    except ValueError:
        raise StorageCorruptionError(
            f"sidecar written_at is not an ISO-8601 instant: {value!r}",
            context={"actual_value": value},
            translated_message="adapters.outbound.storage.local.errors.written_at_invalid",
            precondition_verdict=_local_failure_verdict(
                "storage.local.sidecar.written_at_valid", facts={"field": "written_at", "valid": False}
            ),
        ) from None
    try:
        validate_utc_aware(written_at)
    except CoreValidationError:
        raise StorageCorruptionError(
            f"sidecar written_at carries no timezone: {value!r}",
            context={"actual_value": value},
            translated_message="adapters.outbound.storage.local.errors.written_at_invalid",
            precondition_verdict=_local_failure_verdict(
                "storage.local.sidecar.written_at_valid", facts={"field": "written_at", "valid": False}
            ),
        ) from None
    return written_at


class LocalFileSystemProvider:
    """Bytes-in / bytes-out provider backed by a :class:`pathlib.Path` tree."""

    def __init__(self, root: Path) -> None:
        """Bind the provider to ``root``.

        The root directory is created on first write if absent. The
        constructor itself never touches the filesystem so test
        fixtures and settings-driven instantiation stay cheap.
        """
        self._root = Path(root)

    @property
    def root(self) -> Path:
        """Provider storage root as a :class:`pathlib.Path`."""
        return self._root

    def _ensure_namespace_dir(self, namespace: str) -> Path:
        target = self._root / namespace
        try:
            target.mkdir(parents=True, exist_ok=True)
        except PermissionError as exc:
            raise OutboundStoragePermissionError(
                f"cannot create namespace directory {target}: {exc}",
                context={"namespace": namespace, "path": str(target)},
                translated_message="adapters.outbound.storage.local.errors.namespace_create_permission",
                precondition_verdict=_local_failure_verdict(
                    "storage.local.namespace.writable", facts={"operation": "create_namespace"}
                ),
            ) from None
        except OSError as exc:
            if is_windows_long_path_error(exc):
                raise OutboundStoragePathTooLongError(
                    f"cannot create namespace directory {target}: path exceeds the Windows MAX_PATH ceiling ({exc})",
                    context={"namespace": namespace, "path": str(target)},
                    translated_message="adapters.outbound.storage.local.errors.namespace_create_path_too_long",
                    precondition_verdict=_local_failure_verdict(
                        "storage.local.path.within_limit", facts={"operation": "create_namespace"}
                    ),
                ) from None
            raise
        return target

    def _resolve_object_path(self, namespace: str, object_key_hmac: str) -> Path | None:
        """Find the on-disk file for ``object_key_hmac`` if present.

        Searches the namespace directory for a file matching the HMAC
        prefix, then verifies the full HMAC in its sidecar. The label suffix
        is operator-mutable, so it cannot participate in identity resolution.
        A matching prefix without a matching sidecar HMAC is a collision, not
        an existing object: treating it as a match could overwrite, return, or
        delete another object's payload.
        """
        namespace_dir = self._root / namespace
        if not namespace_dir.is_dir():
            return None
        prefix = provider_object_hmac_prefix(object_key_hmac)
        resolved_path: Path | None = None
        for entry in scan_directory(namespace_dir):
            if not (entry.is_file() and entry.name.startswith(f"{prefix}--") and entry.suffix == _FILE_EXTENSION):
                continue
            sidecar_path = entry.with_name(entry.stem + _SIDECAR_EXTENSION)
            if not sidecar_path.is_file():
                # Preserve the public get/delete behavior for an orphaned
                # payload: get reports its missing sidecar and delete can
                # remove it. A valid foreign sidecar elsewhere still wins as
                # a collision below.
                resolved_path = entry
                continue
            sidecar = self._load_sidecar(sidecar_path)
            sidecar_hmac = sidecar.get("object_key_hmac")
            if sidecar_hmac != object_key_hmac:
                raise OutboundStorageIntegrityError(
                    f"HMAC prefix collision for {object_key_hmac!r}: "
                    f"sidecar {sidecar_path.name!r} identifies {sidecar_hmac!r}",
                    context={
                        "object_key_hmac": object_key_hmac,
                        "sidecar_object_key_hmac": repr(sidecar_hmac),
                        "sidecar_path": str(sidecar_path),
                    },
                    precondition_verdict=_local_failure_verdict(
                        "storage.local.sidecar.identity_matches",
                        facts={"operation": "resolve_object", "prefix_collision": True},
                    ),
                )
            resolved_path = entry
        return resolved_path

    def _load_sidecar(self, sidecar_path: Path) -> Mapping[str, object]:
        try:
            raw = json.loads(sidecar_path.read_text(encoding=UTF_8_ENCODING))
        except (OSError, json.JSONDecodeError) as exc:
            raise OutboundStorageIntegrityError(
                f"sidecar {sidecar_path} is unreadable or malformed: {exc}",
                context={"sidecar_path": str(sidecar_path)},
                translated_message="adapters.outbound.storage.local.errors.sidecar_malformed",
                precondition_verdict=_local_failure_verdict(
                    "storage.local.sidecar.schema_valid", facts={"sidecar_valid": False}
                ),
            ) from None
        if not isinstance(raw, dict):
            raise OutboundStorageIntegrityError(
                f"sidecar {sidecar_path} is not a JSON object",
                context={"sidecar_path": str(sidecar_path)},
                translated_message="adapters.outbound.storage.local.errors.sidecar_not_object",
                precondition_verdict=_local_failure_verdict(
                    "storage.local.sidecar.schema_valid", facts={"sidecar_valid": False}
                ),
            )
        # CAST-RATIONALE-SIDECAR-MAPPING: json.loads returns Any; isinstance
        # guard above confirms dict shape; cast narrows the static type to
        # Mapping[str, object] without altering runtime behaviour.
        return typing.cast(Mapping[str, object], raw)

    def put(
        self,
        namespace: str,
        object_key_hmac: str,
        payload: bytes,
        *,
        content_hash: str,
        label: str,
        batch: DurableWriteBatch | None = None,
    ) -> ProviderObjectMetadata:
        """Atomically write the object and its sidecar, returning :class:`ProviderObjectMetadata`.

        ``batch`` opts this write into a :class:`DurableWriteBatch`, deferring
        its fsyncs to the batch commit. Sound here specifically because the
        store is content-addressed: ``content_hash`` names the payload, so a
        crash mid-batch yields a file that fails its own digest check on read
        and whose source document is still available to re-import. A bulk
        evidence ingest passes one batch for the whole run; a single ``put``
        passes nothing and keeps per-file durability.

        Atomicity guarantee: the payload file is written through
        :func:`~cadrumo.core.atomic_write.atomic_write_hardened_bytes` (the
        master-key ``O_EXCL`` + mode ``0o600`` + fsync pattern) rather than
        the standard tier. The payload here is already-encrypted ciphertext
        (encryption and classification stay above this provider layer), but
        the 2026-05-30 security-paths audit flagged the sidecar's plaintext
        ``content_hash``/``byte_length`` metadata as a size-channel
        inference aid against the encrypted blob set, so the object file is
        hardened defence-in-depth even though its own content is opaque.
        The sidecar is written afterwards through
        :func:`~cadrumo.core.atomic_write.atomic_write_text` (standard
        tier), closing the crash window where a torn sidecar write could
        leave a committed object with missing or corrupted metadata; on
        sidecar-write failure the payload is removed so no orphaned object
        lingers without metadata.
        """
        namespace_clean = _validate_namespace(namespace)
        hmac_clean = _validate_hmac(object_key_hmac)
        label_clean = sanitize_provider_object_label(label)
        if not content_hash.strip():
            raise OutboundStorageValidationError(
                "content_hash must not be blank",
                translated_message="adapters.outbound.storage.local.errors.content_hash_blank",
            )

        namespace_dir = self._ensure_namespace_dir(namespace_clean)
        existing_path = self._resolve_object_path(namespace_clean, hmac_clean)
        stale_pair: tuple[Path, Path] | None = None
        if existing_path is not None and existing_path.name != build_provider_object_name(
            hmac_clean,
            label_clean,
            extension=_FILE_EXTENSION,
        ):
            # Label drifted; the rename is part of put() semantics. The
            # coordinator's diff classifier handles "did label change"
            # via the rename-detection path on push.
            #
            # The stale pair is recorded here but removed only after the
            # replacement payload AND its sidecar have both committed. The
            # replacement lands under a different filename (the label is part
            # of the name), so deferring the removal cannot clobber it, while
            # removing it up front meant a failing sidecar write left neither
            # the old object nor the new one on disk.
            stale_pair = (
                existing_path,
                existing_path.with_name(existing_path.stem + _SIDECAR_EXTENSION),
            )

        target_path = namespace_dir / build_provider_object_name(
            hmac_clean,
            label_clean,
            extension=_FILE_EXTENSION,
        )
        sidecar_path = namespace_dir / _sidecar_filename(hmac_clean, label_clean)

        try:
            atomic_write_hardened_bytes(target_path, payload, batch=batch)
        except PermissionError as exc:
            raise OutboundStoragePermissionError(
                f"cannot write object payload to {target_path}: {exc}",
                context={"path": str(target_path)},
                translated_message="adapters.outbound.storage.local.errors.payload_write_permission",
                precondition_verdict=_local_failure_verdict(
                    "storage.local.payload.writable", facts={"operation": "put", "writable": False}
                ),
            ) from None
        except OSError as exc:
            if is_windows_long_path_error(exc):
                raise OutboundStoragePathTooLongError(
                    f"cannot write object payload to {target_path}: path exceeds the Windows MAX_PATH ceiling ({exc})",
                    context={"path": str(target_path)},
                    translated_message="adapters.outbound.storage.local.errors.payload_write_path_too_long",
                    precondition_verdict=_local_failure_verdict(
                        "storage.local.path.within_limit", facts={"operation": "put_payload", "within_limit": False}
                    ),
                ) from None
            raise OutboundStorageConflictError(
                f"failed to commit object payload to {target_path}: {exc}",
                context={"path": str(target_path)},
                translated_message="adapters.outbound.storage.local.errors.payload_commit_failed",
                precondition_verdict=_local_failure_verdict(
                    "storage.local.payload.commit_succeeded",
                    facts={"operation": "put", "committed": False},
                    outcome=NoRecoveryOutcome.OPERATOR_DECISION,
                ),
            ) from None

        written_at = now()
        sidecar_payload = {
            "namespace": namespace_clean,
            "object_key_hmac": hmac_clean,
            "label": label_clean,
            "byte_length": len(payload),
            "content_hash": content_hash,
            "written_at": written_at.isoformat(),
        }
        try:
            atomic_write_text(sidecar_path, json.dumps(sidecar_payload, sort_keys=True), encoding=UTF_8_ENCODING)
        except OSError as exc:
            target_path.unlink(missing_ok=True)
            if is_windows_long_path_error(exc):
                raise OutboundStoragePathTooLongError(
                    f"cannot write sidecar {sidecar_path}: path exceeds the Windows MAX_PATH ceiling ({exc})",
                    context={"path": str(sidecar_path)},
                    translated_message="adapters.outbound.storage.local.errors.sidecar_write_path_too_long",
                    precondition_verdict=_local_failure_verdict(
                        "storage.local.path.within_limit", facts={"operation": "put_sidecar", "within_limit": False}
                    ),
                ) from None
            raise OutboundStoragePermissionError(
                f"failed to write sidecar {sidecar_path}: {exc}",
                context={"path": str(sidecar_path)},
                translated_message="adapters.outbound.storage.local.errors.sidecar_write_failed",
                precondition_verdict=_local_failure_verdict(
                    "storage.local.sidecar.writable", facts={"operation": "put_sidecar", "writable": False}
                ),
            ) from None

        if stale_pair is not None:
            # Both halves of the replacement are committed; only now is the
            # previous label's pair genuinely superseded.
            for stale in stale_pair:
                stale.unlink(missing_ok=True)

        return ProviderObjectMetadata(
            namespace=namespace_clean,
            object_key_hmac=hmac_clean,
            provider_object_id=str(target_path),
            byte_length=len(payload),
            content_hash=content_hash,
            written_at=written_at,
        )

    def get(self, namespace: str, object_key_hmac: str) -> tuple[bytes, ProviderObjectMetadata]:
        """Read the object payload from disk and return verified metadata.

        Locates the ``.bin`` file by HMAC prefix, loads the sibling
        ``.meta.json`` sidecar, reads the raw bytes, and compares the
        :func:`core.hashing.sha256_hex` digest against the sidecar's
        ``content_hash`` field through :func:`verify_content_hash`. Both
        ``sha256-<hex>``-prefixed strings and bare hex digests are accepted.

        Args:
            namespace: Logical bucket name; maps to a subdirectory of
                ``root``.
            object_key_hmac: Full HMAC string identifying the object.

        Returns:
            A two-tuple containing payload bytes and
            :class:`ProviderObjectMetadata`.

        Raises:
            :class:`OutboundStorageNotFoundError`: When the object file is
                absent.
            :class:`OutboundStorageIntegrityError`: When the sidecar is
                missing, unreadable, or contains non-JSON content; or when the
                payload digest does not match the stored hash.
            :class:`OutboundStoragePermissionError`: When the object file
                cannot be read due to OS permissions.
            :class:`StorageCorruptionError`: When the sidecar ``byte_length``
                field has an unexpected type, or its ``written_at`` is absent,
                unparseable, or tz-naive.
            :class:`OutboundStorageValidationError`: When ``namespace`` or
                ``object_key_hmac`` fail format checks.
        """
        namespace_clean = _validate_namespace(namespace)
        hmac_clean = _validate_hmac(object_key_hmac)

        target_path = self._resolve_object_path(namespace_clean, hmac_clean)
        if target_path is None:
            raise OutboundStorageNotFoundError(
                f"object {hmac_clean!r} not found in namespace {namespace_clean!r}",
                context={"namespace": namespace_clean, "object_key_hmac": hmac_clean},
                translated_message="adapters.outbound.storage.local.errors.object_not_found",
                precondition_verdict=_local_failure_verdict(
                    "storage.local.object.present",
                    facts={"operation": "get", "object_present": False},
                    outcome=NoRecoveryOutcome.OPERATOR_DECISION,
                ),
            )
        sidecar_path = target_path.with_name(target_path.stem + _SIDECAR_EXTENSION)
        if not sidecar_path.is_file():
            raise OutboundStorageIntegrityError(
                f"object {target_path.name} has no sidecar; storage corrupt",
                context={"path": str(target_path)},
                translated_message="adapters.outbound.storage.local.errors.sidecar_missing",
                precondition_verdict=_local_failure_verdict(
                    "storage.local.sidecar.present", facts={"operation": "get", "sidecar_present": False}
                ),
            )
        sidecar = self._load_sidecar(sidecar_path)

        try:
            payload = target_path.read_bytes()
        except PermissionError as exc:
            raise OutboundStoragePermissionError(
                f"cannot read object payload from {target_path}: {exc}",
                context={"path": str(target_path)},
                translated_message="adapters.outbound.storage.local.errors.payload_read_permission",
                precondition_verdict=_local_failure_verdict(
                    "storage.local.payload.readable", facts={"operation": "get", "readable": False}
                ),
            ) from None

        actual_hash = sha256_hex(payload)
        stored_hash = str(sidecar.get("content_hash", ""))
        if not stored_hash:
            # A sidecar with no digest cannot be verified against, and
            # ProviderObjectMetadata.content_hash is min_length=1, so the only
            # alternatives are to refuse or to invent a value. This used to
            # invent one -- `stored_hash or f"sha256-{actual_hash}"` -- which
            # handed the caller a digest computed from whatever bytes were on
            # disk, indistinguishable from one that had actually been checked.
            # `put` refuses a blank content_hash, so reaching here means the
            # sidecar was truncated or edited outside the application.
            raise OutboundStorageIntegrityError(
                f"sidecar {sidecar_path} carries no content_hash; storage corrupt",
                context={"sidecar_path": str(sidecar_path), "path": str(target_path)},
                translated_message="adapters.outbound.storage.local.errors.sidecar_malformed",
                precondition_verdict=_local_failure_verdict(
                    "storage.local.sidecar.digest_present", facts={"operation": "get", "content_hash_present": False}
                ),
            )
        # The stored hash may be a vendor-prefixed string ("sha256-XXX")
        # or a bare hex digest; we accept either as long as the digest
        # portion matches. The local policy verifies any non-empty digest.
        verify_content_hash(
            actual_hash,
            stored_hash,
            message=f"content_hash mismatch for {target_path.name}",
            context={"path": str(target_path), "stored_hash": stored_hash, "actual_sha256": actual_hash},
            translated_message="adapters.outbound.storage.local.errors.content_hash_mismatch",
        )

        written_at = _parse_sidecar_written_at(sidecar.get("written_at"))

        byte_length = _parse_sidecar_byte_length(sidecar.get("byte_length"))
        verify_payload_byte_length(
            payload,
            byte_length,
            message=f"byte_length mismatch for {target_path.name}",
            context={"path": str(target_path)},
            translated_message="adapters.outbound.storage.local.errors.content_hash_mismatch",
        )
        metadata = ProviderObjectMetadata(
            namespace=namespace_clean,
            object_key_hmac=hmac_clean,
            provider_object_id=str(target_path),
            byte_length=byte_length,
            content_hash=stored_hash,
            written_at=written_at,
        )
        return payload, metadata

    def delete(self, namespace: str, object_key_hmac: str) -> bool:
        """Remove the object file and its sidecar from disk, or neither.

        Returns ``False`` immediately when the object is absent; deleting a
        non-existent object is idempotent.  The sidecar is removed with
        ``missing_ok=True`` so a pre-existing orphaned payload without a
        sidecar is still cleanly deleted.

        A failure leaves the PAIR, never half of it. The payload used to be
        unlinked first and the sidecar second, so a sidecar cleanup that failed
        after the payload was already gone raised while leaving nothing to
        retry: ``iter_objects`` no longer reported the object, ``get`` could
        not read it, and the orphaned sidecar path then blocked a re-``put``
        under the same key. The object was un-deletable, un-readable and
        un-writable at once.

        Two changes make the failure recoverable. The sidecar goes first, so a
        refusal there removes nothing at all. And its bytes are read before
        that removal, so a payload unlink that then fails can put the sidecar
        back — the sidecar is metadata this method already holds, whereas the
        payload is not something it could restore. Either way the retry that
        follows sees the same state the caller started from.

        Both unlinks are guarded on ``OSError`` rather than ``PermissionError``
        alone: the ways a filesystem refuses to remove a path are not one
        errno, and on some platforms an unlink of a directory-shaped sidecar
        raises :exc:`IsADirectoryError`, which is not a
        :exc:`PermissionError`. A narrower catch let exactly the corruption
        shape above escape untranslated.

        Args:
            namespace: Logical bucket name.
            object_key_hmac: Full HMAC string identifying the object.

        Returns:
            ``True`` when the object was found and deleted; ``False`` when it
            was already absent.

        Raises:
            :class:`OutboundStoragePermissionError`: When the OS refuses to
                read or remove either half of the pair.
            :class:`OutboundStorageValidationError`: When ``namespace`` or
                ``object_key_hmac`` fail format checks.
        """
        namespace_clean = _validate_namespace(namespace)
        hmac_clean = _validate_hmac(object_key_hmac)

        target_path = self._resolve_object_path(namespace_clean, hmac_clean)
        if target_path is None:
            return False
        sidecar_path = target_path.with_name(target_path.stem + _SIDECAR_EXTENSION)

        sidecar_backup: str | None = None
        if sidecar_path.is_file():
            try:
                sidecar_backup = sidecar_path.read_text(encoding=UTF_8_ENCODING)
            except OSError as exc:
                raise OutboundStoragePermissionError(
                    f"cannot read sidecar {sidecar_path} before deleting object {target_path}: {exc}",
                    context={"path": str(target_path), "sidecar_path": str(sidecar_path)},
                    translated_message="adapters.outbound.storage.local.errors.object_delete_permission",
                    precondition_verdict=_local_failure_verdict(
                        "storage.local.sidecar.readable", facts={"operation": "delete", "readable": False}
                    ),
                ) from None

        try:
            sidecar_path.unlink(missing_ok=True)
        except OSError as exc:
            raise OutboundStoragePermissionError(
                f"cannot delete sidecar {sidecar_path}: {exc}",
                context={"path": str(target_path), "sidecar_path": str(sidecar_path)},
                translated_message="adapters.outbound.storage.local.errors.object_delete_permission",
                precondition_verdict=_local_failure_verdict(
                    "storage.local.sidecar.deletable", facts={"operation": "delete", "deletable": False}
                ),
            ) from None

        try:
            target_path.unlink(missing_ok=True)
        except OSError as exc:
            self._restore_sidecar(sidecar_path, sidecar_backup)
            raise OutboundStoragePermissionError(
                f"cannot delete object {target_path}: {exc}",
                context={"path": str(target_path), "sidecar_path": str(sidecar_path)},
                translated_message="adapters.outbound.storage.local.errors.object_delete_permission",
                precondition_verdict=_local_failure_verdict(
                    "storage.local.payload.deletable", facts={"operation": "delete", "deletable": False}
                ),
            ) from None
        return True

    @staticmethod
    def _restore_sidecar(sidecar_path: Path, contents: str | None) -> None:
        """Put a removed sidecar back after its partner's unlink failed.

        Best-effort by necessity: this runs while an error is already on its
        way out, and a restore that raised would replace the operator's real
        failure with a second one. A failure here is logged and leaves the
        payload orphaned — the state ``get`` already reports as corrupt and
        ``iter_objects`` already skips, which is strictly better than the
        vanished-object state this whole path exists to avoid.
        """
        if contents is None:
            return
        try:
            atomic_write_text(sidecar_path, contents, encoding=UTF_8_ENCODING)
        except OSError:
            _logger.exception("delete: could not restore sidecar %s after a failed payload unlink", sidecar_path)

    def iter_namespaces(self) -> Iterator[str]:
        """Yield the name of every namespace subdirectory under ``root``.

        Returns immediately (yields nothing) when ``root`` does not yet
        exist on disk.

        Yields:
            Directory names in case-normalised name order.
        """
        if not self._root.is_dir():
            return
        for entry in iter_directory(self._root):
            if entry.is_dir():
                yield entry.name

    def iter_objects(self, namespace: str) -> Iterator[ProviderObjectMetadata]:
        """Yield metadata for every object in ``namespace``.

        Only ``.bin`` files with a companion ``.meta.json`` sidecar are
        yielded; files without a sidecar are silently skipped (the coordinator
        surfaces those as integrity issues via its own diff classifier).

        Args:
            namespace: Logical bucket name.

        Yields:
            :class:`ProviderObjectMetadata` records in sorted filename order.

        Raises:
            :class:`OutboundStorageNotFoundError`: When the namespace
                directory is absent.
            :class:`OutboundStorageIntegrityError`: When a sidecar file is
                unreadable or contains non-JSON content.
            :class:`StorageCorruptionError`: When a sidecar ``byte_length``
                field has an unexpected type, or a ``written_at`` is absent,
                unparseable, or tz-naive.
            :class:`OutboundStorageValidationError`: When ``namespace`` fails
                format checks.
        """
        namespace_clean = _validate_namespace(namespace)
        namespace_dir = self._root / namespace_clean
        if not namespace_dir.is_dir():
            raise OutboundStorageNotFoundError(
                f"namespace {namespace_clean!r} does not exist",
                context={"namespace": namespace_clean},
                translated_message="adapters.outbound.storage.local.errors.namespace_not_found",
                precondition_verdict=_local_failure_verdict(
                    "storage.local.namespace.present",
                    facts={"operation": "iter_objects", "namespace_present": False},
                    outcome=NoRecoveryOutcome.OPERATOR_DECISION,
                ),
            )
        for entry in scan_directory(namespace_dir):
            if not entry.is_file() or entry.suffix != _FILE_EXTENSION:
                continue
            sidecar_path = entry.with_name(entry.stem + _SIDECAR_EXTENSION)
            if not sidecar_path.is_file():
                # Skip orphan-without-sidecar; the coordinator's diff
                # classifier surfaces it as an integrity issue elsewhere.
                continue
            sidecar = self._load_sidecar(sidecar_path)
            written_at = _parse_sidecar_written_at(sidecar.get("written_at"))
            byte_length = _parse_sidecar_byte_length(sidecar.get("byte_length"))
            yield ProviderObjectMetadata(
                namespace=namespace_clean,
                object_key_hmac=str(sidecar.get("object_key_hmac", "")),
                provider_object_id=str(entry),
                byte_length=byte_length,
                content_hash=str(sidecar.get("content_hash", "")),
                written_at=written_at,
            )

    def probe(self, *, read_only: bool = False) -> ProviderProbeReport:
        """Assess filesystem accessibility and write permissions, returning a :class:`ProviderProbeReport`.

        Attempts to create ``root`` if absent.  Then, unless
        ``read_only=True``, performs a sentinel write/delete round-trip in
        a ``_probe`` namespace to confirm write access end-to-end.

        The method never raises; every failure mode is encoded in the returned
        :class:`ProviderProbeReport`.

        Args:
            read_only: When ``True``, skip the sentinel write round-trip and
                report ``writable=False`` regardless of actual permissions.

        Returns:
            A :class:`ProviderProbeReport` with ``reachable``, ``writable``,
            and a human-readable ``detail`` string describing the outcome.
        """
        if not self._root.exists():
            try:
                self._root.mkdir(parents=True, exist_ok=True)
            except (PermissionError, OSError):
                return ProviderProbeReport(
                    provider_kind=ProviderKind.LOCAL_FILESYSTEM,
                    read_only=read_only,
                    reachable=False,
                    writable=False,
                    detail="root unreachable",
                )

        if read_only:
            return ProviderProbeReport(
                provider_kind=ProviderKind.LOCAL_FILESYSTEM,
                read_only=read_only,
                reachable=True,
                writable=False,
                detail="read_only probe; root is reachable",
            )

        # Sentinel-file round-trip in `_probe/`.
        try:
            metadata = self.put(
                _PROBE_NAMESPACE,
                "00000000probe",
                b"",
                content_hash="sha256-empty",
                label="sentinel",
            )
        except (PermissionError, OSError, OutboundStoragePermissionError, OutboundStorageConflictError):
            return ProviderProbeReport(
                provider_kind=ProviderKind.LOCAL_FILESYSTEM,
                read_only=read_only,
                reachable=True,
                writable=False,
                detail="sentinel write refused",
            )
        try:
            self.delete(_PROBE_NAMESPACE, "00000000probe")
        except (PermissionError, OSError, OutboundStoragePermissionError) as exc:
            _logger.debug(
                "local storage probe cleanup failed with error_type=%s",
                type(exc).__name__,
            )
            # The round-trip is a write AND a delete. Reporting writable=True
            # after the delete failed claims a guarantee the probe did not
            # obtain, and leaves the sentinel behind to prove it; the Google
            # provider reports writable=False on the equivalent failure.
            del metadata
            return ProviderProbeReport(
                provider_kind=ProviderKind.LOCAL_FILESYSTEM,
                read_only=read_only,
                reachable=True,
                writable=False,
                detail=f"sentinel cleanup failed: {type(exc).__name__}",
            )
        del metadata
        return ProviderProbeReport(
            provider_kind=ProviderKind.LOCAL_FILESYSTEM,
            read_only=read_only,
            reachable=True,
            writable=True,
            detail="sentinel round-trip ok",
        )


__all__ = ["LocalFileSystemProvider"]
