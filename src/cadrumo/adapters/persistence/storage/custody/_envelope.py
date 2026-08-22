"""Supervised creation of strict password custody envelopes."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from ._kdf_supervision import profile_password_wrap_aad, wrap_profile_custody_password_material
from ._records import ProfileCustodyEnvelope, ProfileCustodyKdfParameters

if TYPE_CHECKING:
    from .....core.config import Settings


def create_profile_custody_password_envelope(
    *,
    profile_id: UUID,
    password: str,
    dek: bytes,
    dek_epoch: str,
    kdf: ProfileCustodyKdfParameters,
    password_generation: int = 1,
    previous_envelope_digest: str | None = None,
    settings: Settings | None = None,
) -> ProfileCustodyEnvelope:
    """Create a password wrapper through the S03 supervised KDF boundary."""
    wrapped_dek = wrap_profile_custody_password_material(
        secret=password,
        dek=dek,
        kdf=kdf,
        associated_data=profile_password_wrap_aad(
            profile_id=profile_id,
            password_generation=password_generation,
            dek_epoch=dek_epoch,
            kdf=kdf,
        ),
        settings=settings,
    )
    return ProfileCustodyEnvelope.create(
        profile_id=profile_id,
        password_generation=password_generation,
        dek_epoch=dek_epoch,
        kdf=kdf,
        wrapped_dek=wrapped_dek,
        previous_envelope_digest=previous_envelope_digest,
    )


__all__ = ["create_profile_custody_password_envelope"]
