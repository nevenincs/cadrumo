"""Creation and strict storage of the current capsule DEK proof."""

from __future__ import annotations

import base64
import os
from pathlib import Path
from typing import Final

from ..crypto import GCM_TAG_SIZE, encrypt_record
from ._errors import ProfileCustodyRecordError
from ._records import ProfileCustodyEnvelope
from ._sentinel_contract import (
    ProfileCustodySentinelRecord,
    parse_profile_custody_sentinel_record,
    profile_custody_sentinel_aad,
    profile_custody_sentinel_plaintext,
)

PROFILE_CUSTODY_SENTINEL_FILENAME: Final = "dek.sentinel.v1.json"
PROFILE_CUSTODY_SENTINEL_MAX_BYTES: Final = 8 * 1024


def create_profile_custody_sentinel(
    *,
    envelope: ProfileCustodyEnvelope,
    dek: bytes,
) -> ProfileCustodySentinelRecord:
    """Encrypt the immutable DEK proof that every wrapper must authenticate."""
    blob = encrypt_record(
        profile_custody_sentinel_plaintext(
            profile_id=envelope.profile_id,
            dek_epoch=envelope.dek_epoch,
        ),
        key=dek,
        associated_data=profile_custody_sentinel_aad(envelope),
    )
    record = ProfileCustodySentinelRecord(
        schema_version=1,
        product="cadrumo",
        profile_id=envelope.profile_id,
        dek_epoch=envelope.dek_epoch,
        data_format_version=1,
        purpose="profile-dek-sentinel/v1",
        nonce_b64=base64.b64encode(blob.nonce).decode("ascii"),
        ciphertext_b64=base64.b64encode(blob.ciphertext[:-GCM_TAG_SIZE]).decode("ascii"),
        tag_b64=base64.b64encode(blob.ciphertext[-GCM_TAG_SIZE:]).decode("ascii"),
    )
    return parse_profile_custody_sentinel_record(record.canonical_json_bytes())


def write_profile_custody_sentinel(path: Path, record: ProfileCustodySentinelRecord) -> None:
    """Write a validated sentinel once into an exclusively created staging path."""
    _write_exclusive_fsynced(path, record.canonical_json_bytes())


def _write_exclusive_fsynced(path: Path, payload: bytes) -> None:
    if not payload or len(payload) > PROFILE_CUSTODY_SENTINEL_MAX_BYTES:
        raise ProfileCustodyRecordError("profile custody sentinel write is outside its bounded format")
    try:
        descriptor = os.open(
            path,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0),
            0o600,
        )
    except OSError as exc:
        raise ProfileCustodyRecordError("profile custody sentinel staging path is unavailable") from exc
    try:
        written = os.write(descriptor, payload)
        if written != len(payload):
            raise OSError("profile custody sentinel short write")
        os.fsync(descriptor)
    except OSError as exc:
        raise ProfileCustodyRecordError("profile custody sentinel could not be durably staged") from exc
    finally:
        os.close(descriptor)


__all__ = [
    "PROFILE_CUSTODY_SENTINEL_FILENAME",
    "PROFILE_CUSTODY_SENTINEL_MAX_BYTES",
    "create_profile_custody_sentinel",
    "write_profile_custody_sentinel",
]
