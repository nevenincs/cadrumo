"""Sign-in custody for tests that mint a real acceleration receipt.

A mint establishes the profile's sign-in generation, which is valid only for
committed custody. These helpers either bind to custody a test already
committed, or commit a synthetic capsule for a bare profile identity.
"""

from __future__ import annotations

import base64
from hashlib import sha256
from pathlib import Path
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from ......application.user_profile.access_contracts import ProfileAccessBinding
from ......application.user_profile.login_session import authenticate_profile_candidate
from ......core.config import Settings
from ......core.profile_publication import ProfilePublicationKind
from ..capsule import load_committed_profile_password_material, publish_profile_custody_capsule
from ..errors import ProfileCustodyRecordError
from ..records import ProfileCustodyEnvelope, ProfileCustodyKdfParameters, ProfileCustodyWrappedDek
from ..sentinel import create_profile_custody_sentinel
from ..sign_in_generation import SignInGenerationCustody

if TYPE_CHECKING:
    from ......domain.calculations.registry.authority_artifact import ProfileDecodeContext

RECEIPT_LOGIN_ID = "test-login:receipt-owner"
"""A synthetic OS login locator; real ones come from the runtime login observer."""

OTHER_LOGIN_ID = "test-login:another-desktop"
"""A second synthetic login, for refusals."""

_INSTALLATION_ID = UUID("0b3c5d7e-9f10-4a2b-8c4d-5e6f7a8b9c0d")


def _binding(profile_id: UUID, *, custody_generation: int, dek_epoch: UUID) -> ProfileAccessBinding:
    return ProfileAccessBinding(
        profile_id=profile_id,
        installation_id=_INSTALLATION_ID,
        os_owner_id="synthetic-os-owner",
        custody_generation=custody_generation,
        dek_epoch=dek_epoch,
    )


def committed_sign_in(root: Path, profile_id: UUID) -> SignInGenerationCustody:
    """Bind sign-in custody to the profile custody already committed under ``root``."""
    envelope = load_committed_profile_password_material(profile_id, root=root).envelope
    return SignInGenerationCustody(
        root=root,
        binding=_binding(
            profile_id,
            custody_generation=envelope.password_generation,
            dek_epoch=UUID(bytes=base64.b64decode(envelope.dek_epoch, validate=True)),
        ),
    )


def uncommitted_sign_in(root: Path, profile_id: UUID, *, custody_generation: int = 1) -> SignInGenerationCustody:
    """Bind sign-in custody that no committed capsule backs; a mint must refuse it."""
    return SignInGenerationCustody(
        root=root,
        binding=_binding(profile_id, custody_generation=custody_generation, dek_epoch=UUID(int=1)),
    )


def sign_in_custody(root: Path, profile_id: UUID, *, custody_generation: int = 1) -> SignInGenerationCustody:
    """Bind to committed custody for ``profile_id``, committing a synthetic capsule first if none exists."""
    try:
        return committed_sign_in(root, profile_id)
    except ProfileCustodyRecordError:
        return publish_sign_in_custody(root, profile_id, custody_generation=custody_generation)


def persist_signed_in_receipt(
    root: Path,
    profile_id: UUID,
    passphrase: str,
    *,
    profile_decode_context: ProfileDecodeContext,
    login_id: str = RECEIPT_LOGIN_ID,
) -> bool:
    """Persist a receipt the way the runtime worker does after publishing a human session.

    An in-process login no longer mints one, so a test that needs a live
    sign-in receipt proves the password again through the candidate door and
    publishes from it, bound to ``login_id``, the committed custody and the
    generation the runtime would capture at publication.
    """
    sign_in = committed_sign_in(root, profile_id)
    captured = sign_in.establish().current
    with authenticate_profile_candidate(
        bucket_id=profile_id,
        passphrase_callback=lambda: passphrase,
        profile_decode_context=profile_decode_context,
    ) as candidate:
        return candidate.persist_acceleration_receipt(login_id=login_id, binding=sign_in.binding, sign_in=captured)


def publish_sign_in_custody(root: Path, profile_id: UUID, *, custody_generation: int = 1) -> SignInGenerationCustody:
    """Commit a synthetic capsule for ``profile_id`` and bind sign-in custody to it.

    The capsule carries no label, so profile listings refuse the root it lives
    in; tests that list or resolve profiles publish a full test profile instead.
    """
    seed = sha256(f"receipt-sign-in:{profile_id}:{custody_generation}".encode("ascii")).digest()
    envelope = ProfileCustodyEnvelope.create(
        profile_id=profile_id,
        password_generation=custody_generation,
        dek_epoch=base64.b64encode(seed[:16]).decode("ascii"),
        kdf=ProfileCustodyKdfParameters(
            algorithm="argon2id",
            version=19,
            memory_mib=19,
            iterations=2,
            parallelism=1,
            salt_b64=base64.b64encode(seed[16:]).decode("ascii"),
            output_bytes=32,
        ),
        wrapped_dek=ProfileCustodyWrappedDek(
            nonce_b64=base64.b64encode(seed[:12]).decode("ascii"),
            ciphertext_b64=base64.b64encode(seed).decode("ascii"),
            tag_b64=base64.b64encode(seed[:16]).decode("ascii"),
        ),
    )
    publish_profile_custody_capsule(
        profile_id=profile_id,
        transaction_id=uuid4(),
        publication_kind=ProfilePublicationKind.ENROLL,
        password_envelope=envelope,
        sentinel=create_profile_custody_sentinel(envelope=envelope, dek=sha256(seed).digest()),
        data_files={"state/current.bin": b"synthetic encrypted payload"},
        settings=Settings(cadrumo_local_storage_root=root),
    )
    return committed_sign_in(root, profile_id)
