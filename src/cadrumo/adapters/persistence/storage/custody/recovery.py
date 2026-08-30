"""Independent creation-enrolled recovery envelopes and portable recovery artifacts."""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar, Final, Literal, cast
from uuid import UUID

from pydantic import BaseModel, Field, ValidationError, field_validator

from .....core.external_constants import UTF_8_ENCODING as _UTF_8_ENCODING
from .....core.hashing import (
    bounded_canonical_json_bytes,
    canonical_json_digest,
    reject_duplicate_json_members,
    reject_json_constant,
    validate_prefixed_digest,
)
from .....core.identity import canonical_profile_bucket_id
from .....core.models import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from .digest_model import CustodyDigestModel
from .errors import ProfileCustodyRecordError
from .kdf_supervision import unlock_profile_custody_recovery_material, wrap_profile_custody_recovery_material
from .records import (
    PROFILE_CUSTODY_PASSWORD_GENERATION_MAX,
    ProfileCustodyKdfParameters,
    ProfileCustodyWrappedDek,
)
from .sentinel_contract import ProfileCustodySentinelRecord

if TYPE_CHECKING:
    from .....core.config import Settings

PROFILE_CUSTODY_RECOVERY_SCHEMA_VERSION: Final = 1
PROFILE_CUSTODY_RECOVERY_MAX_BYTES: Final = 1024
PROFILE_CUSTODY_RECOVERY_ARTIFACT_MAX_BYTES: Final = 1024
PROFILE_CUSTODY_RECOVERY_FILENAME: Final = "recovery.v1.json"


def validate_profile_custody_dek_epoch(value: str) -> str:
    """Validate the immutable random 128-bit epoch's canonical representation."""
    try:
        decoded = base64.b64decode(value.encode("ascii"), validate=True)
    except (UnicodeEncodeError, ValueError) as exc:
        raise ValueError("dek_epoch must be canonical base64") from exc
    if len(decoded) != 16 or base64.b64encode(decoded).decode("ascii") != value:
        raise ValueError("dek_epoch must encode exactly 16 canonical bytes")
    return value


class ProfileCustodyRecoveryAad(BaseModel):
    """Closed recovery wrapper AAD descriptor carried by durable records."""

    model_config = _STRICT_FROZEN

    schema_version: Literal[1]
    product: Literal["cadrumo"]
    purpose: Literal["profile-recovery-dek-wrap/v1"]
    key_schedule: Literal["profile-recovery-dek-wrap/v1"]


_RECOVERY_AAD = ProfileCustodyRecoveryAad(
    schema_version=1,
    product="cadrumo",
    purpose="profile-recovery-dek-wrap/v1",
    key_schedule="profile-recovery-dek-wrap/v1",
)


class _RecoveryPayload(BaseModel):
    model_config = _STRICT_FROZEN

    schema_version: Literal[1]
    profile_id: UUID
    recovery_generation: int = Field(ge=1, le=PROFILE_CUSTODY_PASSWORD_GENERATION_MAX)
    dek_epoch: str
    kdf: ProfileCustodyKdfParameters
    wrapped_dek: ProfileCustodyWrappedDek
    aad: ProfileCustodyRecoveryAad
    previous_recovery_digest: str | None

    @field_validator("dek_epoch")
    @classmethod
    def _validate_epoch(cls, value: str) -> str:
        return validate_profile_custody_dek_epoch(value)

    @field_validator("previous_recovery_digest")
    @classmethod
    def _validate_previous_digest(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return validate_prefixed_digest(value, field_name="previous_recovery_digest")


class ProfileCustodyRecoveryEnvelope(_RecoveryPayload, CustodyDigestModel):
    """One creation-enrolled, independently current-format recovery wrapper."""

    _digest_maximum_bytes: ClassVar[int] = PROFILE_CUSTODY_RECOVERY_MAX_BYTES
    _digest_subject: ClassVar[str] = "profile recovery envelope"
    _digest_mismatch_message: ClassVar[str] = "profile recovery self_digest does not match its canonical record"

    self_digest: str

    @field_validator("self_digest")
    @classmethod
    def _validate_self_digest(cls, value: str) -> str:
        return validate_prefixed_digest(value, field_name="self_digest")





    @classmethod
    def create(
        cls,
        *,
        profile_id: UUID,
        recovery_generation: int,
        dek_epoch: str,
        kdf: ProfileCustodyKdfParameters,
        wrapped_dek: ProfileCustodyWrappedDek,
        previous_recovery_digest: str | None = None,
    ) -> ProfileCustodyRecoveryEnvelope:
        """Build the one valid construction path for a current-format recovery envelope.

        Pins ``schema_version`` to the current constant, computes ``self_digest``
        from the assembled payload, then re-validates the whole record through
        :meth:`model_validate_json` rather than constructing the model directly —
        so a caller can never end up holding an envelope whose digest was never
        actually checked against its own fields.
        """
        try:
            payload = _RecoveryPayload(
                schema_version=PROFILE_CUSTODY_RECOVERY_SCHEMA_VERSION,
                profile_id=profile_id,
                recovery_generation=recovery_generation,
                dek_epoch=dek_epoch,
                kdf=kdf,
                wrapped_dek=wrapped_dek,
                aad=_RECOVERY_AAD,
                previous_recovery_digest=previous_recovery_digest,
            ).model_dump(mode="json")
            payload["self_digest"] = canonical_json_digest(
                payload,
                maximum_bytes=PROFILE_CUSTODY_RECOVERY_MAX_BYTES,
                subject="profile recovery envelope",
            )
            return cls.model_validate_json(
                bounded_canonical_json_bytes(
                    payload,
                    maximum_bytes=PROFILE_CUSTODY_RECOVERY_MAX_BYTES,
                    subject="profile recovery envelope",
                ),
            )
        except (ValidationError, ValueError, TypeError) as exc:
            raise ProfileCustodyRecordError("cannot construct a valid profile recovery envelope") from exc


def parse_profile_custody_recovery_envelope(value: bytes) -> ProfileCustodyRecoveryEnvelope:
    """Parse exactly one bounded canonical recovery envelope."""
    if len(value) > PROFILE_CUSTODY_RECOVERY_MAX_BYTES:
        raise ProfileCustodyRecordError("profile recovery envelope exceeds its canonical byte limit")
    try:
        parsed = json.loads(
            value.decode(_UTF_8_ENCODING, errors="strict"),
            object_pairs_hook=reject_duplicate_json_members,
            parse_constant=reject_json_constant,
        )
        if not isinstance(parsed, dict):
            raise ValueError("profile recovery envelope must be a JSON object")
        envelope = ProfileCustodyRecoveryEnvelope.model_validate_json(
            bounded_canonical_json_bytes(
                cast(dict[str, object], parsed),
                maximum_bytes=PROFILE_CUSTODY_RECOVERY_MAX_BYTES,
                subject="profile recovery envelope",
            ),
        )
        if envelope.canonical_json_bytes() != value:
            raise ValueError("profile recovery envelope is not canonical")
        return envelope
    except (UnicodeDecodeError, ValidationError, ValueError, TypeError) as exc:
        raise ProfileCustodyRecordError("profile recovery envelope is not a valid current-format record") from exc


def profile_custody_recovery_aad(envelope: ProfileCustodyRecoveryEnvelope) -> bytes:
    """Derive the one closed recovery-wrapper AAD domain from its record."""
    return profile_custody_recovery_aad_for(
        profile_id=envelope.profile_id,
        dek_epoch=envelope.dek_epoch,
        recovery_generation=envelope.recovery_generation,
        kdf=envelope.kdf,
        aad=envelope.aad,
    )


def create_profile_custody_recovery_envelope(
    *,
    profile_id: UUID,
    recovery_secret: str,
    dek: bytes,
    dek_epoch: str,
    kdf: ProfileCustodyKdfParameters,
    recovery_generation: int = 1,
    previous_recovery_digest: str | None = None,
    settings: Settings | None = None,
) -> ProfileCustodyRecoveryEnvelope:
    """Create the mandatory creation-time recovery wrapper through the supervised KDF owner."""
    aad = profile_custody_recovery_aad_for(
        profile_id=profile_id,
        dek_epoch=dek_epoch,
        recovery_generation=recovery_generation,
        kdf=kdf,
        aad=_RECOVERY_AAD,
    )
    wrapped_dek = wrap_profile_custody_recovery_material(
        secret=recovery_secret,
        dek=dek,
        kdf=kdf,
        associated_data=aad,
        settings=settings,
    )
    return ProfileCustodyRecoveryEnvelope.create(
        profile_id=profile_id,
        recovery_generation=recovery_generation,
        dek_epoch=dek_epoch,
        kdf=kdf,
        wrapped_dek=wrapped_dek,
        previous_recovery_digest=previous_recovery_digest,
    )


def profile_custody_recovery_aad_for(
    *,
    profile_id: UUID,
    dek_epoch: str,
    recovery_generation: int,
    kdf: ProfileCustodyKdfParameters,
    aad: ProfileCustodyRecoveryAad,
) -> bytes:
    return bounded_canonical_json_bytes(
        {
            "aad": aad.model_dump(mode="json"),
            "dek_epoch": dek_epoch,
            "kdf_digest": canonical_json_digest(
                kdf.model_dump(mode="json"),
                maximum_bytes=PROFILE_CUSTODY_RECOVERY_MAX_BYTES,
                subject="profile recovery KDF",
            ),
            "profile_id": canonical_profile_bucket_id(profile_id),
            "recovery_generation": recovery_generation,
            "schema_version": 1,
        },
        maximum_bytes=PROFILE_CUSTODY_RECOVERY_MAX_BYTES,
        subject="profile recovery AAD",
    )


@dataclass(frozen=True, slots=True)
class ProfileCustodyRecoveryUnlock:
    """A DEK accepted through the explicit recovery-only door."""

    profile_id: UUID
    dek_epoch: str
    recovery_digest: str
    dek: bytes


def unlock_profile_custody_recovery(
    envelope: ProfileCustodyRecoveryEnvelope,
    recovery_secret: str,
    *,
    sentinel: ProfileCustodySentinelRecord,
    settings: Settings | None = None,
) -> ProfileCustodyRecoveryUnlock:
    """Use the supervised unwrap boundary for an explicit recovery secret."""
    dek = unlock_profile_custody_recovery_material(
        profile_id=envelope.profile_id,
        dek_epoch=envelope.dek_epoch,
        kdf=envelope.kdf,
        wrapped_dek=envelope.wrapped_dek,
        secret=recovery_secret,
        associated_data=profile_custody_recovery_aad(envelope),
        sentinel=sentinel,
        settings=settings,
    )
    return ProfileCustodyRecoveryUnlock(
        profile_id=envelope.profile_id,
        dek_epoch=envelope.dek_epoch,
        recovery_digest=envelope.self_digest,
        dek=dek,
    )


__all__ = [
    "PROFILE_CUSTODY_RECOVERY_FILENAME",
    "PROFILE_CUSTODY_RECOVERY_MAX_BYTES",
    "PROFILE_CUSTODY_RECOVERY_SCHEMA_VERSION",
    "ProfileCustodyRecoveryAad",
    "ProfileCustodyRecoveryEnvelope",
    "ProfileCustodyRecoveryUnlock",
    "create_profile_custody_recovery_envelope",
    "parse_profile_custody_recovery_envelope",
    "profile_custody_recovery_aad",
    "unlock_profile_custody_recovery",
]
