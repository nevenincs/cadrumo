"""The encrypted, exact-current profile fact record carried by a capsule.

The capsule lifecycle owns directory publication.  This module owns only the
typed record payload which that lifecycle stages in ``data/``.  It has no path
discovery, no manifest access, and no generic persistence operation: callers
either build revision one for an as-yet-unpublished capsule or decode the one
committed record through an authenticated, envelope-bound session.
"""

from __future__ import annotations

import base64
import hashlib
import json
from dataclasses import dataclass
from typing import Any, Final
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from ...adapters.persistence.storage.crypto import EncryptedBlob, decrypt_record, encrypt_record
from ...adapters.persistence.storage.custody import ProfileCustodyEnvelope
from ...core.identity import ProfileId
from ...domain.user_profile import UserProfileRecord


PROFILE_RECORD_DATA_FILENAME: Final = "profile-record.v1.json"
PROFILE_RECORD_SCHEMA_VERSION: Final = 1
_RECORD_AAD_PURPOSE: Final = "cadrumo.profile-record.v1"
_DIGEST_PREFIX: Final = "sha256:"
_RECORD_CONFIG = ConfigDict(strict=True, frozen=True, extra="forbid", hide_input_in_errors=True)


class ProfileRecordConflictError(ValueError):
    """The supplied session or compare-and-swap witness is no longer current."""


class ProfileRecordIntegrityError(ValueError):
    """A committed record artifact is malformed, mis-bound, or cannot authenticate."""


def _canonical_json(value: object) -> bytes:
    return json.dumps(value, allow_nan=False, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")


def _digest(value: bytes) -> str:
    return f"{_DIGEST_PREFIX}{hashlib.sha256(value).hexdigest()}"


def _validate_digest(value: str) -> str:
    if len(value) != 71 or not value.startswith(_DIGEST_PREFIX) or any(part not in "0123456789abcdef" for part in value[7:]):
        raise ValueError("record digest must be a lowercase sha256 digest")
    return value


def _record_bytes(record: UserProfileRecord) -> bytes:
    return _canonical_json(record.model_dump(mode="json"))


def _aad(
    *,
    profile_id: UUID,
    envelope_digest: str,
    password_generation: int,
    dek_epoch: str,
    revision: int,
    previous_record_digest: str | None,
    content_digest: str,
) -> bytes:
    return _canonical_json(
        {
            "content_digest": content_digest,
            "dek_epoch": dek_epoch,
            "envelope_digest": envelope_digest,
            "password_generation": password_generation,
            "previous_record_digest": previous_record_digest,
            "profile_id": str(profile_id),
            "purpose": _RECORD_AAD_PURPOSE,
            "revision": revision,
            "schema_version": PROFILE_RECORD_SCHEMA_VERSION,
        }
    )


class _ProfileRecordArtifactPayload(BaseModel):
    model_config = _RECORD_CONFIG

    schema_version: int = Field(ge=1)
    profile_id: ProfileId
    envelope_digest: str
    password_generation: int = Field(ge=1)
    dek_epoch: str = Field(min_length=1)
    revision: int = Field(ge=1)
    previous_record_digest: str | None
    content_digest: str
    nonce_b64: str
    ciphertext_b64: str

    @field_validator("envelope_digest", "content_digest")
    @classmethod
    def _validate_digest_field(cls, value: str) -> str:
        return _validate_digest(value)

    @field_validator("previous_record_digest")
    @classmethod
    def _validate_previous_digest(cls, value: str | None) -> str | None:
        return None if value is None else _validate_digest(value)

    @field_validator("nonce_b64", "ciphertext_b64")
    @classmethod
    def _validate_b64(cls, value: str) -> str:
        try:
            decoded = base64.b64decode(value.encode("ascii"), validate=True)
        except (UnicodeEncodeError, ValueError) as exc:
            raise ValueError("record encryption field is not canonical base64") from exc
        if base64.b64encode(decoded).decode("ascii") != value:
            raise ValueError("record encryption field is not canonical base64")
        return value

    @model_validator(mode="after")
    def _validate_first_revision(self) -> _ProfileRecordArtifactPayload:
        if self.revision == 1 and self.previous_record_digest is not None:
            raise ValueError("first profile record revision must not name a predecessor")
        if self.revision > 1 and self.previous_record_digest is None:
            raise ValueError("later profile record revision must name its predecessor")
        return self


class ProfileRecordArtifact(_ProfileRecordArtifactPayload):
    """Versioned encrypted record payload which is staged as capsule data."""

    def canonical_json_bytes(self) -> bytes:
        return _canonical_json(self.model_dump(mode="json"))

    @property
    def encrypted_blob(self) -> EncryptedBlob:
        try:
            return EncryptedBlob(
                nonce=base64.b64decode(self.nonce_b64.encode("ascii"), validate=True),
                ciphertext=base64.b64decode(self.ciphertext_b64.encode("ascii"), validate=True),
            )
        except (ValidationError, ValueError) as exc:
            raise ProfileRecordIntegrityError("profile record encryption shape is invalid") from exc


@dataclass(slots=True)
class ProfileRecordSession:
    """A short-lived record authority bound to the exact unlocked envelope."""

    profile_id: UUID
    envelope_digest: str
    password_generation: int
    dek_epoch: str
    _dek: bytearray

    @classmethod
    def from_envelope(cls, *, envelope: ProfileCustodyEnvelope, dek: bytes) -> ProfileRecordSession:
        if len(dek) != 32:
            raise ProfileRecordIntegrityError("profile record session requires a 32-byte DEK")
        return cls(
            profile_id=envelope.profile_id,
            envelope_digest=envelope.self_digest,
            password_generation=envelope.password_generation,
            dek_epoch=envelope.dek_epoch,
            _dek=bytearray(dek),
        )

    def close(self) -> None:
        self._dek[:] = b"\0" * len(self._dek)

    def _require_open_dek(self) -> bytes:
        if not self._dek or not any(self._dek):
            raise ProfileRecordIntegrityError("profile record session is closed")
        return bytes(self._dek)

    def create_initial(self, record: UserProfileRecord) -> bytes:
        """Build revision one; only the lifecycle may place it in a stage."""
        if UUID(str(record.profile_id)) != self.profile_id:
            raise ProfileRecordIntegrityError("initial profile record UUID differs from its custody session")
        return _encode_artifact(
            session=self,
            record=record,
            revision=1,
            previous_record_digest=None,
        )

    def decode_current(
        self,
        payload: bytes,
        *,
        expected_revision: int | None = None,
        expected_content_digest: str | None = None,
    ) -> tuple[UserProfileRecord, ProfileRecordArtifact]:
        """Authenticate the one current record and enforce an optional CAS witness."""
        try:
            artifact = ProfileRecordArtifact.model_validate_json(payload)
        except ValidationError as exc:
            raise ProfileRecordIntegrityError("profile record artifact is not a canonical current record") from exc
        if artifact.canonical_json_bytes() != payload:
            raise ProfileRecordIntegrityError("profile record artifact is not canonical")
        if (
            UUID(str(artifact.profile_id)) != self.profile_id
            or artifact.envelope_digest != self.envelope_digest
            or artifact.password_generation != self.password_generation
            or artifact.dek_epoch != self.dek_epoch
        ):
            raise ProfileRecordConflictError("profile record does not bind the authenticated custody session")
        if expected_revision is not None and artifact.revision != expected_revision:
            raise ProfileRecordConflictError("profile record revision compare-and-swap failed")
        if expected_content_digest is not None and artifact.content_digest != expected_content_digest:
            raise ProfileRecordConflictError("profile record digest compare-and-swap failed")
        try:
            plaintext = decrypt_record(
                artifact.encrypted_blob,
                key=self._require_open_dek(),
                associated_data=_aad(
                    profile_id=self.profile_id,
                    envelope_digest=artifact.envelope_digest,
                    password_generation=artifact.password_generation,
                    dek_epoch=artifact.dek_epoch,
                    revision=artifact.revision,
                    previous_record_digest=artifact.previous_record_digest,
                    content_digest=artifact.content_digest,
                ),
            )
            record = UserProfileRecord.model_validate_json(plaintext)
        except (ValidationError, ValueError) as exc:
            raise ProfileRecordIntegrityError("profile record cannot be authenticated and decoded") from exc
        if UUID(str(record.profile_id)) != self.profile_id or f"sha256:{record.content_digest}" != artifact.content_digest:
            raise ProfileRecordIntegrityError("profile record plaintext differs from its authenticated identity or digest")
        return record, artifact

    def prepare_replace(
        self,
        current: ProfileRecordArtifact,
        record: UserProfileRecord,
        *,
        expected_revision: int,
        expected_content_digest: str,
    ) -> bytes:
        """Prepare the next CAS revision for lifecycle-owned physical publication."""
        if current.revision != expected_revision or current.content_digest != expected_content_digest:
            raise ProfileRecordConflictError("profile record revision compare-and-swap failed")
        if UUID(str(record.profile_id)) != self.profile_id:
            raise ProfileRecordIntegrityError("replacement profile record UUID differs from its custody session")
        if record.record_revision != current.revision + 1 or record.previous_record_digest != current.content_digest[7:]:
            raise ProfileRecordIntegrityError("replacement record does not carry the next revision and current digest")
        return _encode_artifact(
            session=self,
            record=record,
            revision=current.revision + 1,
            previous_record_digest=current.content_digest,
        )


def _encode_artifact(
    *,
    session: ProfileRecordSession,
    record: UserProfileRecord,
    revision: int,
    previous_record_digest: str | None,
) -> bytes:
    record_bytes = _record_bytes(record)
    content_digest = f"sha256:{record.content_digest}"
    aad = _aad(
        profile_id=session.profile_id,
        envelope_digest=session.envelope_digest,
        password_generation=session.password_generation,
        dek_epoch=session.dek_epoch,
        revision=revision,
        previous_record_digest=previous_record_digest,
        content_digest=content_digest,
    )
    encrypted = encrypt_record(record_bytes, key=session._require_open_dek(), associated_data=aad)
    return ProfileRecordArtifact(
        schema_version=PROFILE_RECORD_SCHEMA_VERSION,
        profile_id=str(session.profile_id),
        envelope_digest=session.envelope_digest,
        password_generation=session.password_generation,
        dek_epoch=session.dek_epoch,
        revision=revision,
        previous_record_digest=previous_record_digest,
        content_digest=content_digest,
        nonce_b64=base64.b64encode(encrypted.nonce).decode("ascii"),
        ciphertext_b64=base64.b64encode(encrypted.ciphertext).decode("ascii"),
    ).canonical_json_bytes()


__all__ = [
    "PROFILE_RECORD_DATA_FILENAME",
    "PROFILE_RECORD_SCHEMA_VERSION",
    "ProfileRecordArtifact",
    "ProfileRecordConflictError",
    "ProfileRecordIntegrityError",
    "ProfileRecordSession",
]
