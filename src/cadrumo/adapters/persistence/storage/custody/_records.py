"""Strict, current-format records for password-wrapped profile custody."""

from __future__ import annotations

import base64
import binascii
import json
import re
from typing import Final, Literal, cast
from uuid import UUID

from pydantic import BaseModel, Field, ValidationError, field_validator, model_validator

from .....core import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from .....core.credentials import assess_profile_password as _assess_profile_password
from .....core.external_constants import UTF_8_ENCODING as _UTF_8_ENCODING
from .....core.hashing import (
    bounded_canonical_json_bytes,
    canonical_json_digest,
    reject_duplicate_json_members,
    reject_json_constant,
)
from ..crypto import GCM_TAG_SIZE, KEY_SIZE, NONCE_SIZE
from .errors import ProfileCustodyPasswordError, ProfileCustodyRecordError

PROFILE_CUSTODY_ENVELOPE_SCHEMA_VERSION: Final = 1
#: The password envelope's name inside a capsule's ``custody/`` directory.
#: Named beside its size bound and its sentinel/recovery siblings, which
#: already carry one; it was the last capsule member whose filename was a
#: literal repeated at each publication and read site.
PROFILE_CUSTODY_ENVELOPE_FILENAME: Final = "envelope.v1.json"
#: Largest possible canonical v1 envelope: all fixed-width fields, a present
#: predecessor digest, and the ten-digit maximum password generation.
PROFILE_CUSTODY_ENVELOPE_MAX_BYTES: Final = 704
PROFILE_CUSTODY_PASSWORD_GENERATION_MAX: Final = 2_147_483_647
PROFILE_CUSTODY_KDF_MEMORY_MIB: Final[frozenset[int]] = frozenset({19, 32, 64, 128, 256})
PROFILE_CUSTODY_KDF_ITERATIONS: Final[frozenset[int]] = frozenset({2, 3, 4, 6, 8, 10})
PROFILE_CUSTODY_KDF_PARALLELISM: Final[frozenset[int]] = frozenset({1, 2, 4})

_KDF_SALT_BYTES: Final = 16
_DEK_EPOCH_BYTES: Final = 16
_SHA256_DIGEST_RE: Final = re.compile(r"sha256:[0-9a-f]{64}\Z")
_KEY_SCHEDULE: Final = "profile-password-dek-wrap/v1"


def _decode_canonical_b64(value: str, *, field_name: str, expected_bytes: int) -> str:
    expected_length = 4 * ((expected_bytes + 2) // 3)
    if len(value) != expected_length:
        raise ValueError(f"{field_name} must contain exactly {expected_length} base64 characters")
    try:
        decoded = base64.b64decode(value.encode("ascii"), validate=True)
    except (UnicodeEncodeError, binascii.Error) as exc:
        raise ValueError(f"{field_name} must be canonical base64") from exc
    if len(decoded) != expected_bytes:
        raise ValueError(f"{field_name} must encode exactly {expected_bytes} bytes")
    if base64.b64encode(decoded).decode("ascii") != value:
        raise ValueError(f"{field_name} must use canonical base64")
    return value


def _validate_digest(value: str, *, field_name: str) -> str:
    if _SHA256_DIGEST_RE.fullmatch(value) is None:
        raise ValueError(f"{field_name} must be a lowercase sha256 digest")
    return value


def _canonical_json_bytes(value: object) -> bytes:
    return bounded_canonical_json_bytes(
        value,
        maximum_bytes=PROFILE_CUSTODY_ENVELOPE_MAX_BYTES,
        subject="profile custody envelope",
    )


def _encode_profile_password(password: str) -> bytes:
    """Encode an exact password after canonical defense-in-depth assessment."""
    assessment = _assess_profile_password(password)
    if assessment.reason is not None:
        raise ProfileCustodyPasswordError(
            f"profile password refused by canonical policy: {assessment.reason.value}",
        )
    return password.encode(_UTF_8_ENCODING, errors="strict")


def _decode_profile_password(value: bytes) -> str:
    """Strictly decode and assess a password received through byte transport."""
    try:
        password = value.decode(_UTF_8_ENCODING, errors="strict")
    except UnicodeDecodeError as exc:
        raise ProfileCustodyPasswordError("profile password transport is not strict UTF-8") from exc
    _encode_profile_password(password)
    return password


class ProfileCustodyKdfParameters(BaseModel):
    """The finite Argon2id parameter grid accepted by custody v1."""

    model_config = _STRICT_FROZEN

    algorithm: Literal["argon2id"]
    version: Literal[19]
    memory_mib: Literal[19, 32, 64, 128, 256]
    iterations: Literal[2, 3, 4, 6, 8, 10]
    parallelism: Literal[1, 2, 4]
    salt_b64: str
    output_bytes: Literal[32]

    @field_validator("salt_b64")
    @classmethod
    def _validate_salt(cls, value: str) -> str:
        return _decode_canonical_b64(value, field_name="salt_b64", expected_bytes=_KDF_SALT_BYTES)


class ProfileCustodyWrappedDek(BaseModel):
    """Authenticated AES-GCM payload carrying exactly one 32-byte DEK."""

    model_config = _STRICT_FROZEN

    nonce_b64: str
    ciphertext_b64: str
    tag_b64: str

    @field_validator("nonce_b64")
    @classmethod
    def _validate_nonce(cls, value: str) -> str:
        return _decode_canonical_b64(value, field_name="nonce_b64", expected_bytes=NONCE_SIZE)

    @field_validator("ciphertext_b64")
    @classmethod
    def _validate_ciphertext(cls, value: str) -> str:
        return _decode_canonical_b64(value, field_name="ciphertext_b64", expected_bytes=KEY_SIZE)

    @field_validator("tag_b64")
    @classmethod
    def _validate_tag(cls, value: str) -> str:
        return _decode_canonical_b64(value, field_name="tag_b64", expected_bytes=GCM_TAG_SIZE)


class _ProfileCustodyEnvelopePayload(BaseModel):
    """Validated v1 envelope fields before self-digest construction."""

    model_config = _STRICT_FROZEN

    schema_version: Literal[1]
    profile_id: UUID
    password_generation: int = Field(ge=1, le=PROFILE_CUSTODY_PASSWORD_GENERATION_MAX)
    dek_epoch: str
    password_encoding: Literal["utf-8"]
    key_schedule: Literal["profile-password-dek-wrap/v1"]
    kdf: ProfileCustodyKdfParameters
    wrapped_dek: ProfileCustodyWrappedDek
    previous_envelope_digest: str | None

    @field_validator("dek_epoch")
    @classmethod
    def _validate_dek_epoch(cls, value: str) -> str:
        return _decode_canonical_b64(value, field_name="dek_epoch", expected_bytes=_DEK_EPOCH_BYTES)

    @field_validator("previous_envelope_digest")
    @classmethod
    def _validate_previous_envelope_digest(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _validate_digest(value, field_name="previous_envelope_digest")


class ProfileCustodyEnvelope(_ProfileCustodyEnvelopePayload):
    """Immutable v1 authority for one profile's normal password unlock."""

    self_digest: str

    @field_validator("self_digest")
    @classmethod
    def _validate_self_digest(cls, value: str) -> str:
        return _validate_digest(value, field_name="self_digest")

    @model_validator(mode="after")
    def _verify_self_digest(self) -> ProfileCustodyEnvelope:
        if self.self_digest != self.computed_self_digest:
            raise ValueError("profile custody self_digest does not match its canonical record")
        return self

    @property
    def canonical_payload(self) -> dict[str, object]:
        """Return the exact digest payload, excluding only ``self_digest``."""
        payload = cast(dict[str, object], self.model_dump(mode="json"))
        del payload["self_digest"]
        return payload

    @property
    def computed_self_digest(self) -> str:
        """Return the canonical SHA-256 digest for this envelope's payload."""
        return canonical_json_digest(
            self.canonical_payload,
            maximum_bytes=PROFILE_CUSTODY_ENVELOPE_MAX_BYTES,
            subject="profile custody envelope",
        )

    def canonical_json_bytes(self) -> bytes:
        """Serialise the complete envelope in its unique canonical JSON form."""
        return _canonical_json_bytes(self.model_dump(mode="json"))

    @classmethod
    def create(
        cls,
        *,
        profile_id: UUID,
        password_generation: int,
        dek_epoch: str,
        kdf: ProfileCustodyKdfParameters,
        wrapped_dek: ProfileCustodyWrappedDek,
        previous_envelope_digest: str | None = None,
    ) -> ProfileCustodyEnvelope:
        """Build a validated envelope with its canonical self-digest."""
        try:
            payload = _ProfileCustodyEnvelopePayload(
                schema_version=PROFILE_CUSTODY_ENVELOPE_SCHEMA_VERSION,
                profile_id=profile_id,
                password_generation=password_generation,
                dek_epoch=dek_epoch,
                password_encoding=cast(Literal["utf-8"], _UTF_8_ENCODING),
                key_schedule=_KEY_SCHEDULE,
                kdf=kdf,
                wrapped_dek=wrapped_dek,
                previous_envelope_digest=previous_envelope_digest,
            ).model_dump(mode="json")
            payload["self_digest"] = canonical_json_digest(
                payload,
                maximum_bytes=PROFILE_CUSTODY_ENVELOPE_MAX_BYTES,
                subject="profile custody envelope",
            )
            return cls.model_validate_json(_canonical_json_bytes(payload))
        except (ValidationError, ValueError, TypeError) as exc:
            raise ProfileCustodyRecordError("cannot construct a valid profile custody envelope") from exc


def parse_profile_custody_envelope(value: bytes) -> ProfileCustodyEnvelope:
    """Parse one canonical strict UTF-8 current-format custody envelope."""
    if len(value) > PROFILE_CUSTODY_ENVELOPE_MAX_BYTES:
        raise ProfileCustodyRecordError(
            f"profile custody envelope exceeds {PROFILE_CUSTODY_ENVELOPE_MAX_BYTES}-byte canonical limit",
        )
    try:
        text = value.decode(_UTF_8_ENCODING, errors="strict")
        parsed = json.loads(
            text,
            object_pairs_hook=reject_duplicate_json_members,
            parse_constant=reject_json_constant,
        )
        if not isinstance(parsed, dict):
            raise ValueError("profile custody record must be a JSON object")
        canonical_input = _canonical_json_bytes(cast(dict[str, object], parsed))
        envelope = ProfileCustodyEnvelope.model_validate_json(canonical_input)
        if value != envelope.canonical_json_bytes():
            raise ValueError("profile custody record is not in canonical JSON form")
        return envelope
    except (UnicodeDecodeError, ValidationError, ValueError, TypeError) as exc:
        raise ProfileCustodyRecordError("profile custody envelope is not a valid current-format record") from exc


__all__ = [
    "PROFILE_CUSTODY_ENVELOPE_MAX_BYTES",
    "PROFILE_CUSTODY_ENVELOPE_SCHEMA_VERSION",
    "PROFILE_CUSTODY_KDF_ITERATIONS",
    "PROFILE_CUSTODY_KDF_MEMORY_MIB",
    "PROFILE_CUSTODY_KDF_PARALLELISM",
    "PROFILE_CUSTODY_PASSWORD_GENERATION_MAX",
    "ProfileCustodyEnvelope",
    "ProfileCustodyKdfParameters",
    "ProfileCustodyWrappedDek",
    "parse_profile_custody_envelope",
]
