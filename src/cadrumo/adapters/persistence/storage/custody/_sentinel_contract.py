"""Canonical DEK-sentinel proof contract for current profile custody."""

from __future__ import annotations

import json
import secrets
from typing import Final, Literal, cast
from uuid import UUID

from pydantic import BaseModel, ValidationError, field_validator, model_validator

from .....core import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from .....core.external_constants import UTF_8_ENCODING as _UTF_8_ENCODING
from .....core.hashing import reject_duplicate_json_members, reject_json_constant
from .....core.identity import canonical_profile_bucket_id
from ..crypto import GCM_TAG_SIZE, NONCE_SIZE, EncryptedBlob, decrypt_record
from ._kdf_codec import (
    canonical_frame_bytes as _canonical_frame_bytes,
)
from ._kdf_codec import (
    decode_canonical_b64 as _decode_canonical_b64,
)
from ._records import ProfileCustodyEnvelope
from .errors import ProfileCustodyRecordError

_PROFILE_CUSTODY_DATA_FORMAT_VERSION: Final = 1
_PROFILE_CUSTODY_SENTINEL_PURPOSE: Final = "profile-dek-sentinel/v1"
_PROFILE_CUSTODY_SENTINEL_PROOF: Final = "profile-dek-sentinel-proof/v1"


def profile_custody_sentinel_aad(envelope: ProfileCustodyEnvelope) -> bytes:
    """Derive the only AAD accepted for a current-format DEK sentinel."""
    return profile_custody_sentinel_aad_for(
        profile_id=envelope.profile_id,
        dek_epoch=envelope.dek_epoch,
    )


def profile_custody_sentinel_aad_for(*, profile_id: UUID, dek_epoch: str) -> bytes:
    """Derive sentinel AAD from the immutable custody identity alone."""
    return _canonical_frame_bytes(
        {
            "data_format_version": _PROFILE_CUSTODY_DATA_FORMAT_VERSION,
            "dek_epoch": dek_epoch,
            "product": "cadrumo",
            "profile_id": canonical_profile_bucket_id(profile_id),
            "purpose": _PROFILE_CUSTODY_SENTINEL_PURPOSE,
            "schema_version": 1,
        },
    )


def profile_custody_sentinel_plaintext(
    *,
    profile_id: UUID,
    dek_epoch: str,
    data_format_version: Literal[1] = 1,
) -> bytes:
    """Derive the non-caller-selectable sentinel plaintext for one DEK epoch."""
    return _canonical_frame_bytes(
        {
            "data_format_version": data_format_version,
            "dek_epoch": dek_epoch,
            "product": "cadrumo",
            "profile_id": canonical_profile_bucket_id(profile_id),
            "proof": _PROFILE_CUSTODY_SENTINEL_PROOF,
            "purpose": _PROFILE_CUSTODY_SENTINEL_PURPOSE,
            "schema_version": 1,
        },
    )


class ProfileCustodySentinelRecord(BaseModel):
    """Strict proof input consumed before a custody transaction can publish it."""

    model_config = _STRICT_FROZEN

    schema_version: Literal[1]
    product: Literal["cadrumo"]
    profile_id: UUID
    dek_epoch: str
    data_format_version: Literal[1]
    purpose: Literal["profile-dek-sentinel/v1"]
    nonce_b64: str
    ciphertext_b64: str
    tag_b64: str

    @field_validator("dek_epoch")
    @classmethod
    def _validate_epoch(cls, value: str) -> str:
        _decode_canonical_b64(value, field_name="dek_epoch", expected_bytes=16)
        return value

    @field_validator("nonce_b64")
    @classmethod
    def _validate_nonce(cls, value: str) -> str:
        _decode_canonical_b64(value, field_name="nonce_b64", expected_bytes=NONCE_SIZE)
        return value

    @field_validator("tag_b64")
    @classmethod
    def _validate_tag(cls, value: str) -> str:
        _decode_canonical_b64(value, field_name="tag_b64", expected_bytes=GCM_TAG_SIZE)
        return value

    @field_validator("ciphertext_b64")
    @classmethod
    def _validate_ciphertext(cls, value: str) -> str:
        _decode_canonical_b64(value, field_name="ciphertext_b64", expected_bytes=None)
        return value

    @model_validator(mode="after")
    def _verify_exact_proof_shape(self) -> ProfileCustodySentinelRecord:
        ciphertext = _decode_canonical_b64(
            self.ciphertext_b64,
            field_name="ciphertext_b64",
            expected_bytes=None,
        )
        expected = profile_custody_sentinel_plaintext(
            profile_id=self.profile_id,
            dek_epoch=self.dek_epoch,
            data_format_version=self.data_format_version,
        )
        if len(ciphertext) != len(expected):
            raise ValueError("sentinel ciphertext must have the canonical proof length")
        return self

    def encrypted_blob(self) -> EncryptedBlob:
        """Return the format-neutral AEAD representation after strict validation."""
        return EncryptedBlob(
            nonce=_decode_canonical_b64(self.nonce_b64, field_name="nonce_b64", expected_bytes=NONCE_SIZE),
            ciphertext=(
                _decode_canonical_b64(self.ciphertext_b64, field_name="ciphertext_b64", expected_bytes=None)
                + _decode_canonical_b64(self.tag_b64, field_name="tag_b64", expected_bytes=GCM_TAG_SIZE)
            ),
        )

    def canonical_json_bytes(self) -> bytes:
        """Return the unique strict transport representation for a custody transaction."""
        return _canonical_frame_bytes(cast(dict[str, object], self.model_dump(mode="json")))


def parse_profile_custody_sentinel_record(value: bytes) -> ProfileCustodySentinelRecord:
    """Parse one canonical sentinel record without creating or publishing it."""
    try:
        decoded = value.decode(_UTF_8_ENCODING, errors="strict")
        parsed = json.loads(
            decoded, object_pairs_hook=reject_duplicate_json_members, parse_constant=reject_json_constant
        )
        if not isinstance(parsed, dict):
            raise ValueError("profile custody sentinel must be an object")
        payload = cast("dict[str, object]", parsed)
        record = ProfileCustodySentinelRecord.model_validate_json(_canonical_frame_bytes(payload))
        if record.canonical_json_bytes() != value:
            raise ValueError("profile custody sentinel is not canonical")
        return record
    except (UnicodeDecodeError, ValidationError, ValueError, TypeError) as exc:
        raise ProfileCustodyRecordError("profile custody sentinel is not a valid current-format record") from exc


def verify_profile_custody_sentinel(
    *,
    dek: bytes,
    profile_id: UUID,
    dek_epoch: str,
    sentinel: ProfileCustodySentinelRecord,
) -> None:
    """Prove that the supplied DEK matches the immutable sentinel identity."""
    if sentinel.profile_id != profile_id or sentinel.dek_epoch != dek_epoch:
        raise ProfileCustodyRecordError("profile custody sentinel identity does not match its envelope")
    try:
        actual_sentinel = decrypt_record(
            sentinel.encrypted_blob(),
            key=dek,
            associated_data=profile_custody_sentinel_aad_for(profile_id=profile_id, dek_epoch=dek_epoch),
        )
    except Exception as exc:
        raise ProfileCustodyRecordError("profile custody sentinel did not authenticate") from exc
    expected_sentinel = profile_custody_sentinel_plaintext(
        profile_id=profile_id,
        dek_epoch=dek_epoch,
    )
    if not secrets.compare_digest(actual_sentinel, expected_sentinel):
        raise ProfileCustodyRecordError("profile custody sentinel contents did not match")


__all__ = [
    "ProfileCustodySentinelRecord",
    "parse_profile_custody_sentinel_record",
    "profile_custody_sentinel_aad",
    "profile_custody_sentinel_aad_for",
    "profile_custody_sentinel_plaintext",
    "verify_profile_custody_sentinel",
]
