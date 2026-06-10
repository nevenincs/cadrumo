"""Bucket-DEK activation helpers for master-key providers."""

from __future__ import annotations

import binascii
import json
import secrets
from pathlib import Path
from typing import Final

from pydantic import ValidationError

from .....core.external_constants import UTF_8_ENCODING as _UTF_8_ENCODING
from ..crypto._crypto import KEY_SIZE
from ..errors import DecryptionError, MasterKeyMaterialMissingError, MasterKeyUnavailableError
from ._master_key_io import _b64decode, _b64encode, atomic_write_secure_bytes
from ._master_key_records import _WrappedBucketDekDocument

_MASTER_KEY_UNAVAILABLE_MESSAGE_KEY: Final[str] = "errors.auth.auth_storage_master_key_unavailable"


def master_key_unavailable_error(message: str) -> MasterKeyUnavailableError:
    """Build and return a :class:`MasterKeyUnavailableError` for this substrate."""
    return MasterKeyUnavailableError(message, translated_message=_MASTER_KEY_UNAVAILABLE_MESSAGE_KEY)


def bucket_dek_path(*, storage_root: Path, bucket_id: str) -> Path:
    """Return the separated keystore path for one bucket's wrapped DEK."""
    from .._namespace_registry import BUCKET_DEK_FILENAME
    from ..bucket._keystore_paths import keystore_path, validate_keystore_separation

    validate_keystore_separation(storage_root, bucket_id)
    return keystore_path(storage_root, bucket_id) / BUCKET_DEK_FILENAME


def bucket_key_schedule(*, storage_root: Path, bucket_id: str):
    """Return the bucket's key schedule, or ``None`` when no manifest exists."""
    from ..bucket._layout import bucket_paths
    from ..bucket._manifest_io import MISSING_BUCKET_MANIFEST_MESSAGE, read_manifest
    from ..errors import StorageValidationError

    try:
        return read_manifest(bucket_paths(storage_root, bucket_id)).key_schedule
    except StorageValidationError as exc:
        if str(exc) == MISSING_BUCKET_MANIFEST_MESSAGE:
            return None
        raise


def idle_minutes_for_bucket(*, storage_root: Path, bucket_id: str, default_minutes: int) -> int:
    """Resolve the idle window from the bucket manifest, falling back to settings."""
    from ..bucket._layout import bucket_paths
    from ..bucket._manifest_io import MISSING_BUCKET_MANIFEST_MESSAGE, read_manifest
    from ..errors import StorageValidationError

    try:
        manifest = read_manifest(bucket_paths(storage_root, bucket_id))
    except StorageValidationError as exc:
        if str(exc) == MISSING_BUCKET_MANIFEST_MESSAGE:
            return default_minutes
        raise
    configured = manifest.idle_lock_minutes
    return configured if configured is not None else default_minutes


def load_or_mint_bucket_dek(
    *,
    kek: bytes,
    storage_root: Path,
    bucket_id: str,
    allow_bootstrap_mint: bool,
) -> bytes:
    """Unwrap the per-bucket DEK, or mint it for a not-yet-registered bucket."""
    from ..bucket._manifest import BucketKeySchedule
    from ._dek_wrap import unwrap_dek, wrap_dek

    path = bucket_dek_path(storage_root=storage_root, bucket_id=bucket_id)
    key_schedule = bucket_key_schedule(storage_root=storage_root, bucket_id=bucket_id)
    if key_schedule is None:
        if allow_bootstrap_mint:
            if path.is_file():
                wrapped = read_wrapped_bucket_dek(path)
                try:
                    return unwrap_dek(kek=kek, wrapped=wrapped, bucket_id=bucket_id)
                except DecryptionError as exc:
                    raise master_key_unavailable_error(
                        "staged bucket DEK did not authenticate under the active master key; "
                        "verify the selected profile, passphrase, and secret-store backend.",
                    ) from exc
            dek = secrets.token_bytes(KEY_SIZE)
            wrapped = wrap_dek(kek=kek, dek=dek, bucket_id=bucket_id)
            write_wrapped_bucket_dek(path, wrapped)
            return dek
        raise MasterKeyMaterialMissingError(
            f"bucket {bucket_id!r} has no manifest; run `aeat config profile create NAME` "
            "to create a profile before invoking commands that decrypt or persist stored records.",
        )

    if key_schedule is BucketKeySchedule.BUCKET_DEK_V1:
        if not path.is_file():
            raise MasterKeyMaterialMissingError(
                f"bucket {bucket_id!r} is enrolled in the bucket-dek-v1 key schedule "
                f"but its wrapped DEK is missing at {path}; run `aeat config recover` "
                "or restore the bucket keystore from backup before decrypting or "
                "persisting records.",
            )
        wrapped = read_wrapped_bucket_dek(path)
        try:
            return unwrap_dek(kek=kek, wrapped=wrapped, bucket_id=bucket_id)
        except DecryptionError as exc:
            raise master_key_unavailable_error(
                "bucket DEK did not authenticate under the active master key; "
                "verify the selected profile, passphrase, and secret-store backend.",
            ) from exc

    raise MasterKeyMaterialMissingError(
        f"bucket {bucket_id!r} has unsupported key schedule {key_schedule!r}; "
        "run `aeat config recover` before decrypting or persisting records.",
    )


def wrapped_dek_from_document(document: _WrappedBucketDekDocument):
    """Return a strict wrapped-DEK object from a persisted JSON document."""
    from ._dek_wrap import WrappedDek

    try:
        nonce = _b64decode(document.nonce_b64)
        ciphertext = _b64decode(document.ciphertext_b64)
        tag = _b64decode(document.tag_b64)
    except (ValueError, binascii.Error) as exc:
        raise master_key_unavailable_error("bucket DEK document carries malformed base64.") from exc
    try:
        return WrappedDek(nonce=nonce, ciphertext=ciphertext, tag=tag)
    except ValidationError as exc:
        raise master_key_unavailable_error("bucket DEK document carries malformed field lengths.") from exc


def document_from_wrapped_dek(wrapped) -> _WrappedBucketDekDocument:
    """Return the JSON document shape for a wrapped bucket DEK."""
    return _WrappedBucketDekDocument(
        nonce_b64=_b64encode(wrapped.nonce),
        ciphertext_b64=_b64encode(wrapped.ciphertext),
        tag_b64=_b64encode(wrapped.tag),
    )


def read_wrapped_bucket_dek(path: Path):
    """Read and validate a wrapped bucket-DEK document from disk."""
    try:
        document = _WrappedBucketDekDocument.model_validate_json(path.read_text(encoding=_UTF_8_ENCODING))
    except (OSError, ValueError, ValidationError) as exc:
        raise master_key_unavailable_error("failed to read bucket DEK document.") from exc
    return wrapped_dek_from_document(document)


def write_wrapped_bucket_dek(path: Path, wrapped) -> None:
    """Persist a wrapped bucket-DEK document through the secure atomic writer."""
    document = document_from_wrapped_dek(wrapped)
    payload = json.dumps(
        document.model_dump(mode="json"),
        indent=2,
        sort_keys=True,
    ).encode(_UTF_8_ENCODING)
    atomic_write_secure_bytes(path, payload + b"\n")
